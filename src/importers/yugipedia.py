# Import data from Yugipedia (https://yugipedia.com).
import atexit
import datetime
import json
import logging
import os.path
import re
import time
import typing
import uuid
import xml.etree.ElementTree

import requests
import tqdm
import wikitextparser

from ..database import *

API_URL = "https://yugipedia.com/api.php"
RATE_LIMIT = 1.1
TIME_TO_JUST_REDOWNLOAD_ALL_PAGES = 30 * 24 * 60 * 60  # 1 month-ish

_last_access = time.time()


def make_request(rawparams: typing.Dict[str, str]) -> requests.Response:
    now = time.time()
    while (now - _last_access) <= RATE_LIMIT:
        time.sleep(now - _last_access)
        now = time.time()

    params = {
        "format": "json",
        "utf8": "1",
        "formatversion": "2",
    }
    params.update(rawparams)

    # logging.debug(f"Making request: {json.dumps(params)}")
    response = requests.get(
        API_URL,
        params=params,
        headers={
            "User-Agent": f"YGOJSON/{SCHEMA_VERSION} (https://github.com/iconmaster5326/YGOJSON)"
        },
    )
    if not response.ok:
        if response.status_code == 524:
            # timeout; servers must be hammered
            # wait an extended period of time and try again
            time.sleep(RATE_LIMIT * 10)
            return make_request(rawparams)
        response.raise_for_status()
    # logging.debug(f"Got response: {response.text}")
    return response


class WikiPage:
    id: int
    name: str

    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name


class ChangeType(enum.Enum):
    CATEGORIZE = "categorize"
    EDIT = "edit"
    EXTERNAL = "external"
    LOG = "log"
    NEW = "new"


class ChangelogEntry(WikiPage):
    type: ChangeType

    def __init__(self, id: int, name: str, type: ChangeType) -> None:
        super().__init__(id, name)
        self.type = type


def paginate_query(query) -> typing.Iterable:
    query = query.copy()
    while True:
        in_json = make_request(query).json()
        if "query" not in in_json:
            raise ValueError(
                f"Got bad JSON: {json.dumps(in_json)} from query: {json.dumps(query)}"
            )
        yield in_json["query"]
        if "continue" in in_json:
            query.update(in_json["continue"])
        else:
            break


CAT_TCG_CARDS = "Category:TCG cards"
CAT_OCG_CARDS = "Category:OCG cards"
CAT_TCG_SETS = "Category:TCG sets"
CAT_OCG_SETS = "Category:OCG sets"
CAT_TOKENS = "Category:Tokens"
CAT_SKILLS = "Category:Skill Cards"
CAT_UNUSABLE = "Category:Unusable cards"

DBID_SUFFIX = "_database_id"
DBNAME_SUFFIX = "_name"


def get_card_pages(batcher: "YugipediaBatcher") -> typing.Iterable[int]:
    with tqdm.tqdm(total=2, desc="Fetching Yugipedia card list") as progress_bar:
        result = []
        seen = set()

        @batcher.getCategoryMembers(CAT_TCG_CARDS)
        def catMem1(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        @batcher.getCategoryMembers(CAT_OCG_CARDS)
        def catMem2(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        return result


def get_set_pages(batcher: "YugipediaBatcher") -> typing.Iterable[int]:
    with tqdm.tqdm(total=2, desc="Fetching Yugipedia set list") as progress_bar:
        result = []
        seen = set()

        @batcher.getCategoryMembersRecursive(CAT_TCG_SETS)
        def catMem1(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        @batcher.getCategoryMembersRecursive(CAT_OCG_SETS)
        def catMem2(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        return result


def get_changelog(since: datetime.datetime) -> typing.Iterable[ChangelogEntry]:
    query = {
        "action": "query",
        "list": "recentchanges",
        "redirects": "1",
        "rcend": since.isoformat(),
        "rclimit": "max",
    }

    for results in paginate_query(query):
        for result in results["recentchanges"]:
            yield ChangelogEntry(
                result["pageid"], result["title"], ChangeType(result["type"])
            )


def get_changes(
    batcher: "YugipediaBatcher",
    relevant_pages: typing.Iterable[int],
    relevant_cats: typing.Iterable[str],
    changelog: typing.Iterable[ChangelogEntry],
) -> typing.Iterable[int]:
    """
    Finds recent changes.
    Returns any cards changed or newly created.
    """
    changed_cards: typing.List[int] = []

    card_ids = set(relevant_pages)
    pages_to_catcheck: typing.List[ChangelogEntry] = []
    for change in changelog:
        if change.id in card_ids:
            changed_cards.append(change.id)
        elif (
            change.type == ChangeType.CATEGORIZE or change.type == ChangeType.NEW
        ) and not change.name.startswith("Category:"):
            pages_to_catcheck.append(change)

    new_cards: typing.Set[int] = {x for x in changed_cards}

    for entry in pages_to_catcheck:

        def do(entry: ChangelogEntry):
            @batcher.getPageCategories(entry.id)
            def onGetCats(cats: typing.List[int]):
                for cat in relevant_cats:
                    if batcher.namesToIDs[cat] in cats:
                        if all(
                            x.id != entry.id
                            for x in batcher.categoryMembersCache[
                                batcher.namesToIDs[cat]
                            ]
                        ):
                            batcher.categoryMembersCache[
                                batcher.namesToIDs[cat]
                            ].append(
                                CategoryMember(
                                    id=entry.id,
                                    name=entry.name,
                                    type=CategoryMemberType.PAGE,
                                )
                            )
                        new_cards.add(entry.id)

        do(entry)

    batcher.flushPendingOperations()
    return new_cards


T = typing.TypeVar("T")


def get_table_entry(
    table: wikitextparser.Template, key: str, default: T = None
) -> typing.Union[str, T]:
    try:
        arg = next(iter([x for x in table.arguments if x.name.strip() == key]))
        return arg.value
    except StopIteration:
        return default


LOCALES = {
    "": "en",
    "en": "en",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "es": "es",
    "ja": "ja",
    "ko": "ko",
    "tc": "zh-TW",
    "sc": "zh-CN",
}

LOCALES_FULL = {
    "English": "en",
    # TODO
}

MONSTER_CARD_TYPES = {
    "Ritual": MonsterCardType.RITUAL,
    "Fusion": MonsterCardType.FUSION,
    "Synchro": MonsterCardType.SYNCHRO,
    "Xyz": MonsterCardType.XYZ,
    "Pendulum": MonsterCardType.PENDULUM,
    "Link": MonsterCardType.LINK,
}
TYPES = {
    "Beast-Warrior": Race.BEASTWARRIOR,
    "Zombie": Race.ZOMBIE,
    "Fiend": Race.FIEND,
    "Dinosaur": Race.DINOSAUR,
    "Dragon": Race.DRAGON,
    "Beast": Race.BEAST,
    "Illusion": Race.ILLUSION,
    "Insect": Race.INSECT,
    "Winged Beast": Race.WINGEDBEAST,
    "Warrior": Race.WARRIOR,
    "Sea Serpent": Race.SEASERPENT,
    "Aqua": Race.AQUA,
    "Pyro": Race.PYRO,
    "Thunder": Race.THUNDER,
    "Spellcaster": Race.SPELLCASTER,
    "Plant": Race.PLANT,
    "Rock": Race.ROCK,
    "Reptile": Race.REPTILE,
    "Fairy": Race.FAIRY,
    "Fish": Race.FISH,
    "Machine": Race.MACHINE,
    "Divine-Beast": Race.DIVINEBEAST,
    "Psychic": Race.PSYCHIC,
    "Creator God": Race.CREATORGOD,
    "Wyrm": Race.WYRM,
    "Cyberse": Race.CYBERSE,
}
CLASSIFICATIONS = {
    "Normal": Classification.NORMAL,
    "Effect": Classification.EFFECT,
    "Pendulum": Classification.PENDULUM,
    "Tuner": Classification.TUNER,
    # specialsummon omitted
}
ABILITIES = {
    "Toon": Ability.TOON,
    "Spirit": Ability.SPIRIT,
    "Union": Ability.UNION,
    "Gemini": Ability.GEMINI,
    "Flip": Ability.FLIP,
}


MYSTERY_ATK_DEFS = {"?", "????", "X000"}


def _strip_markup(s: str) -> str:
    return "\n".join(
        wikitextparser.remove_markup(
            re.sub(r"\{\{[Rr]uby\|([^\|]*)\|(?:[^\}]*)?\}\}", r"\1", x)
        )
        for x in s.split("\n")
    )


def parse_card(
    batcher: "YugipediaBatcher",
    page: int,
    card: Card,
    data: wikitextparser.WikiText,
    categories: typing.List[int],
) -> bool:
    """
    Parse a card from a wiki page. Returns False if this is not actually a valid card
    for the database, and True otherwise.
    """

    title = batcher.idsToNames[page]
    if batcher.namesToIDs.get(CAT_TOKENS) in categories:
        logging.debug(f"Skipping token: {title}")
        return False

    cardtable = next(
        iter([x for x in data.templates if x.name.strip().lower() == "cardtable2"])
    )

    for locale, key in LOCALES.items():
        value = get_table_entry(cardtable, locale + "_name" if locale else "name")
        if not locale and not value:
            value = title
        if value and value.strip():
            value = _strip_markup(value.strip())
            card.text.setdefault(key, CardText(name=value))
            card.text[key].name = value
        value = get_table_entry(cardtable, locale + "_lore" if locale else "lore")
        if value and value.strip():
            if key not in card.text:
                logging.warn(f"Card has no name in {key} but has effect: {title}")
                pass
            else:
                card.text[key].effect = _strip_markup(value.strip())
        value = get_table_entry(
            cardtable, locale + "_pendulum_effect" if locale else "pendulum_effect"
        )
        if value and value.strip():
            if key not in card.text:
                logging.warn(f"Card has no name in {key} but has pend. effect: {title}")
                pass
            else:
                card.text[key].pendulum_effect = _strip_markup(value.strip())
        if any(
            (t.name.strip() == "Unofficial name" or t.name.strip() == "Unofficial lore")
            and LOCALES_FULL.get(t.arguments[0].value.strip()) == key
            for t in data.templates
        ):
            if key not in card.text:
                logging.warn(f"Card has no name in {key} but is unofficial: {title}")
                pass
            else:
                card.text[key].official = False

    if card.card_type == CardType.MONSTER:
        typeline = get_table_entry(cardtable, "types")
        if not typeline:
            logging.warn(f"Monster has no typeline: {title}")
            return False
        if "Skill" in typeline:
            logging.debug(f"Skipping skill card: {title}")
            return False
        if "Token" in typeline:
            logging.debug(f"Skipping token card: {title}")
            return False

        value = get_table_entry(cardtable, "attribute")
        if not value:
            # logging.warn(f"Monster has no attribute: {title}")
            pass  # some illegal-for-play monsters have no attribute
        else:
            value = value.strip().lower()
            if value == "???":
                pass  # attribute to be announced; omit it
            elif value not in Attribute._value2member_map_:
                logging.warn(f"Unknown attribute '{value.strip()}' in {title}")
            else:
                card.attribute = Attribute(value)

        typeline = [x.strip() for x in typeline.split("/") if x.strip()]
        for x in typeline:
            if (
                x != "???"  # type to be announced; omit it
                and x not in MONSTER_CARD_TYPES
                and x not in TYPES
                and x not in CLASSIFICATIONS
                and x not in ABILITIES
            ):
                logging.warn(f"Monster typeline bit unknown in {title}: {x}")
        if not card.monster_card_types:
            card.monster_card_types = []
        for k, v in MONSTER_CARD_TYPES.items():
            if k in typeline and v not in card.monster_card_types:
                card.monster_card_types.append(v)
        for k, v in TYPES.items():
            if k in typeline:
                card.type = v
        if not card.classifications:
            card.classifications = []
        for k, v in CLASSIFICATIONS.items():
            if k in typeline and v not in card.classifications:
                card.classifications.append(v)
        if not card.abilities:
            card.abilities = []
        for k, v in ABILITIES.items():
            if k in typeline and v not in card.abilities:
                card.abilities.append(v)
        # if not card.type and "???" not in typeline:
        #     # some illegal-for-play monsters have no type
        #     logging.warn(f"Monster has no type: {title}")

        value = get_table_entry(cardtable, "level")
        if value and value.strip() != "???":
            try:
                card.level = int(value)
            except ValueError:
                logging.warn(f"Unknown level '{value.strip()}' in {title}")
                return False

        value = get_table_entry(cardtable, "rank")
        if value and value.strip() != "???":
            try:
                card.rank = int(value)
            except ValueError:
                logging.warn(f"Unknown rank '{value.strip()}' in {title}")
                return False

        value = get_table_entry(cardtable, "atk")
        if value and value.strip() != "???":
            try:
                card.atk = "?" if value.strip() in MYSTERY_ATK_DEFS else int(value)
            except ValueError:
                logging.warn(f"Unknown ATK '{value.strip()}' in {title}")
                return False
        value = get_table_entry(cardtable, "def")
        if value and value.strip() != "???":
            try:
                card.def_ = "?" if value.strip() in MYSTERY_ATK_DEFS else int(value)
            except ValueError:
                logging.warn(f"Unknown DEF '{value.strip()}' in {title}")
                return False

        value = get_table_entry(cardtable, "pendulum_scale")
        if value and value.strip() != "???":
            try:
                card.scale = int(value)
            except ValueError:
                logging.warn(f"Unknown scale '{value.strip()}' in {title}")
                return False

        value = get_table_entry(cardtable, "link_arrows")
        if value:
            card.link_arrows = [
                LinkArrow(x.lower().replace("-", "").strip()) for x in value.split(",")
            ]
    elif card.card_type == CardType.SPELL or card.card_type == CardType.TRAP:
        value = get_table_entry(cardtable, "property")
        if not value:
            logging.warn(f"Spell/trap has no subcategory: {title}")
            return False
        card.subcategory = SubCategory(value.lower().replace("-", "").strip())

    value = get_table_entry(cardtable, "password")
    if value:
        vmatch = re.match(r"^\d+", value.strip())
        if vmatch and value.strip() not in card.passwords:
            card.passwords.append(value.strip())
        if not vmatch and value.strip() and value.strip() != "none":
            logging.warn(f"Bad password '{value.strip()}' in card {title}")

    # generally, we want YGOProDeck to handle generic images
    # But if all else fails, we can add one!
    if all(
        (not image.card_art and not image.crop_art)
        or "yugipedia.com" in (image.card_art or "")
        for image in card.images
    ):
        in_images_raw = get_table_entry(cardtable, "image")
        if in_images_raw:
            in_images = [
                [x.strip() for x in x.split(";")]
                for x in in_images_raw.split("\n")
                if x.strip()
            ]

            def add_image(in_image: list, out_image: CardImage):
                image_name = in_image[0] if len(in_image) == 1 else in_image[1]

                @batcher.getImageURL("File:" + image_name)
                def onGetImage(url: str):
                    out_image.card_art = url

            for image in card.images:
                in_image = in_images.pop(0)
                if len(in_image) != 1 and len(in_image) != 3:
                    logging.warn(
                        f"Weird image string for {title}: {' ; '.join(in_image)}"
                    )
                    continue
                add_image(in_image, image)
            for in_image in in_images:
                if len(in_image) != 1 and len(in_image) != 3:
                    logging.warn(
                        f"Weird image string for {title}: {' ; '.join(in_image)}"
                    )
                    continue
                new_image = CardImage(id=uuid.uuid4())
                if len(card.passwords) == 1:
                    # we don't have the full ability to correspond passwords here
                    # but this will do for 99% of cards
                    new_image.password = card.passwords[0]
                add_image(in_image, new_image)
                card.images.append(new_image)

    # TODO: legality, video games

    if not card.yugipedia_pages:
        card.yugipedia_pages = []
    for existing_page in card.yugipedia_pages or []:
        if not existing_page.name and existing_page.id == page:
            existing_page.name = title
        elif not existing_page.id and existing_page.name == title:
            existing_page.id = page
    if not any(x.id == page for x in card.yugipedia_pages):
        card.yugipedia_pages.append(ExternalIdPair(title, page))

    value = get_table_entry(cardtable, "database_id", "")
    vmatch = re.match(r"^\d+", value.strip())
    if vmatch:
        card.db_id = int(vmatch.group(0))

    # TODO: errata, series

    return True


CARD_GALLERY_NAMESPACE = "Set Card Galleries:"

RARITY_STR_TO_ENUM = {
    "c": CardRarity.COMMON,
    "sp": CardRarity.SHORTPRINT,
    "ssp": CardRarity.SHORTPRINT,
    "nr": CardRarity.SHORTPRINT,
    "r": CardRarity.RARE,
    "sr": CardRarity.SUPER,
    "ur": CardRarity.ULTRA,
    "rar": CardRarity.ULTRA,  # not official, but typos were made in a few galleries (?)
    "utr": CardRarity.ULTIMATE,
    "se": CardRarity.SECRET,
    "scr": CardRarity.SECRET,
    "uscr": CardRarity.ULTRASECRET,
    "pscr": CardRarity.PRISMATICSECRET,
    "hr": CardRarity.GHOST,
    "hgr": CardRarity.GHOST,
    "gr": CardRarity.GHOST,
    "pr": CardRarity.PARALLEL,
    "npr": CardRarity.COMMONPARALLEL,
    "pc": CardRarity.COMMONPARALLEL,
    "rpr": CardRarity.RAREPARALLEL,
    "spr": CardRarity.SUPERPARALLEL,
    "upr": CardRarity.ULTRAPARALLEL,
    "dpc": CardRarity.DTPC,
    "dnpr": CardRarity.DTPC,
    "dnrpr": CardRarity.DTPSP,
    "drpr": CardRarity.DTRPR,
    "dspr": CardRarity.DTSPR,
    "dupr": CardRarity.DTUPR,
    "dscpr": CardRarity.DTSCPR,
    "gur": CardRarity.GOLD,
    "10000scr": CardRarity.TENTHOUSANDSECRET,
    "20scr": CardRarity.TWENTITHSECRET,
    "cr": CardRarity.COLLECTORS,
    "escr": CardRarity.EXTRASECRET,
    "escpr": CardRarity.EXTRASECRETPARALLEL,
    "ggr": CardRarity.GOLDGHOST,
    "gscr": CardRarity.GOLDSECRET,
    "sfr": CardRarity.STARFOIL,
    "msr": CardRarity.MOSAIC,
    "shr": CardRarity.SHATTERFOIL,
    "hgpr": CardRarity.GHOSTPARALLEL,
    "plr": CardRarity.PLATINUM,
    "plscr": CardRarity.PLATINUMSECRET,
    "pgr": CardRarity.PREMIUMGOLD,
    "qcscr": CardRarity.TWENTYFIFTHSECRET,
    "scpr": CardRarity.SECRETPARALLEL,
    "altr": CardRarity.STARLIGHT,
    "str": CardRarity.STARLIGHT,
    "urpr": CardRarity.PHARAOHS,
    "kcc": CardRarity.KCCOMMON,
    "kcn": CardRarity.KCCOMMON,
    "kcr": CardRarity.KCRARE,
    "kcsr": CardRarity.KCSUPER,
    "kcur": CardRarity.KCULTRA,
    "kcscr": CardRarity.KCSECRET,
    "mr": CardRarity.MILLENIUM,
    "mlr": CardRarity.MILLENIUM,
    "mlsr": CardRarity.MILLENIUMSUPER,
    "mlur": CardRarity.MILLENIUMULTRA,
    "mlscr": CardRarity.MILLENIUMSECRET,
    "mlgr": CardRarity.MILLENIUMGOLD,
}

#   | c     | common                         = {{ safesubst:<noinclude/>#if: {{{full|}}} | Common                                  | C     }}
#   | nr    | normal                         = {{ safesubst:<noinclude/>#if: {{{full|}}} | Normal Rare                             | NR    }}
#   | sp    | short print                    = {{ safesubst:<noinclude/>#if: {{{full|}}} | Short Print                             | SP    }}
#   | ssp   | super short print              = {{ safesubst:<noinclude/>#if: {{{full|}}} | Super Short Print                       | SSP   }}
#   | hfr   | holofoil                       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Holofoil Rare                           | HFR   }}
#   | r     | rare                           = {{ safesubst:<noinclude/>#if: {{{full|}}} | Rare                                    | R     }}
#   | sr    | super                          = {{ safesubst:<noinclude/>#if: {{{full|}}} | Super Rare                              | SR    }}
#   | ur    | ultra                          = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ultra Rare                              | UR    }}
#   | utr   | ultimate                       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ultimate Rare                           | UtR   }}
#   | gr    | ghost                          = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ghost Rare                              | GR    }}
#   | hr | hgr | holographic                 = {{ safesubst:<noinclude/>#if: {{{full|}}} | Holographic Rare                        | HGR   }}
#   | se | scr | secret                      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Secret Rare                             | ScR   }}
#   | pscr  | prismatic secret               = {{ safesubst:<noinclude/>#if: {{{full|}}} | Prismatic Secret Rare                   | PScR  }}
#   | uscr  | ultra secret                   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ultra Secret Rare                       | UScR  }}
#   | scur  | secret ultra                   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Secret Ultra Rare                       | ScUR  }}
#   | escr  | extra secret                   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Extra Secret Rare                       | EScR  }}
#   | 20scr | 20th secret                    = {{ safesubst:<noinclude/>#if: {{{full|}}} | 20th Secret Rare                        | 20ScR }}
#   | qcscr | quarter century secret         = {{ safesubst:<noinclude/>#if: {{{full|}}} | Quarter Century Secret Rare             | QCScR }}
#   | 10000scr | 10000 secret                = {{ safesubst:<noinclude/>#if: {{{full|}}} | 10000 Secret Rare                       | 10000ScR }}
#   | altr  | str | alternate | starlight    = {{ safesubst:<noinclude/>#if: {{{full|}}} | Starlight Rare                          | StR   }}
#   | plr   | platinum                       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Platinum Rare                           | PlR   }}
#   | plscr | platinum secret                = {{ safesubst:<noinclude/>#if: {{{full|}}} | Platinum Secret Rare                    | PlScR }}
#   | pr    | parallel                       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Parallel Rare                           | PR    }}
#   | pc    | parallel common                = {{ safesubst:<noinclude/>#if: {{{full|}}} | Parallel Common                         | PC    }}
#   | npr   | normal parallel                = {{ safesubst:<noinclude/>#if: {{{full|}}} | Normal Parallel Rare                    | NPR   }}
#   | rpr   | rare parallel                  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Rare Parallel Rare                      | RPR   }}
#   | spr   | super parallel                 = {{ safesubst:<noinclude/>#if: {{{full|}}} | Super Parallel Rare                     | SPR   }}
#   | upr   | ultra parallel                 = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ultra Parallel Rare                     | UPR   }}
#   | scpr  | secret parallel                = {{ safesubst:<noinclude/>#if: {{{full|}}} | Secret Parallel Rare                    | ScPR  }}
#   | escpr | extra secret parallel          = {{ safesubst:<noinclude/>#if: {{{full|}}} | Extra Secret Parallel Rare              | EScPR }}
#   | h     | hobby                          = {{ safesubst:<noinclude/>#if: {{{full|}}} | Hobby Rare                              | H     }}
#   | sfr   | starfoil                       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Starfoil Rare                           | SFR   }}
#   | msr   | mosaic                         = {{ safesubst:<noinclude/>#if: {{{full|}}} | Mosaic Rare                             | MSR   }}
#   | shr   | shatterfoil                    = {{ safesubst:<noinclude/>#if: {{{full|}}} | Shatterfoil Rare                        | SHR   }}
#   | cr    | collectors                     = {{ safesubst:<noinclude/>#if: {{{full|}}} | Collector's Rare                        | CR    }}
#   | hgpr  | holographic parallel           = {{ safesubst:<noinclude/>#if: {{{full|}}} | Holographic Parallel Rare               | HGPR  }}
#   | urpr  | ultra pharaohs | pharaohs      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ultra Rare (Pharaoh's Rare)             | URPR  }}
#   | kcc | kcn | kaiba corporation common | kaiba corporation normal = {{ safesubst:<noinclude/>#if: {{{full|}}} | Kaiba Corporation Common | KCC }}
#   | kcr   | kaiba corporation              = {{ safesubst:<noinclude/>#if: {{{full|}}} | Kaiba Corporation Rare                  | KCR   }}
#   | kcsr  | kaiba corporation super        = {{ safesubst:<noinclude/>#if: {{{full|}}} | Kaiba Corporation Super Rare            | KCSR  }}
#   | kcur  | kaiba corporation ultra        = {{ safesubst:<noinclude/>#if: {{{full|}}} | Kaiba Corporation Ultra Rare            | KCUR  }}
#   | kcscr | kaiba corporation secret       = {{ safesubst:<noinclude/>#if: {{{full|}}} | Kaiba Corporation Secret Rare           | KCScR }}
#   | mr | mlr | millennium                  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Millennium Rare                         | MLR   }}
#   | mlsr  | millennium super               = {{ safesubst:<noinclude/>#if: {{{full|}}} | Millennium Super Rare                   | MLSR  }}
#   | mlur  | millennium ultra               = {{ safesubst:<noinclude/>#if: {{{full|}}} | Millennium Ultra Rare                   | MLUR  }}
#   | mlscr | millennium secret              = {{ safesubst:<noinclude/>#if: {{{full|}}} | Millennium Secret Rare                  | MLScR }}
#   | mlgr  | millennium gold                = {{ safesubst:<noinclude/>#if: {{{full|}}} | Millennium Gold Rare                    | MLGR  }}
#   | gur   | gold                           = {{ safesubst:<noinclude/>#if: {{{full|}}} | Gold Rare                               | GUR   }}
#   | gscr  | gold secret                    = {{ safesubst:<noinclude/>#if: {{{full|}}} | Gold Secret Rare                        | GScR  }}
#   | ggr   | ghost/gold                     = {{ safesubst:<noinclude/>#if: {{{full|}}} | Ghost/Gold Rare                         | GGR   }}
#   | pgr   | premium gold                   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Premium Gold Rare                       | PGR   }}
#   | dpc   | duel terminal parallel common  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Parallel Common           | DPC   }}
#   | dnrpr | duel terminal normal  parallel = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Rare Parallel Rare | DNRPR }}
#   |         duel terminal normal parallel  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Parallel Rare      | DNPR  }}
#   | dnpr                                   = {{ safesubst:<noinclude/>#ifeq: {{ lc: {{{1}}} }} | duel terminal normal rare parallel rare
#     | {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Rare Parallel Rare | DNRPR }}
#     | {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Parallel Rare      | DNPR  }} }}
#   | drpr  | duel terminal  parallel        = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Rare Parallel Rare        | DRPR  }}
#   | dspr  | duel terminal super parallel   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Super Parallel Rare       | DSPR  }}
#   | dupr  | duel terminal ultra parallel   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Ultra Parallel Rare       | DUPR  }}
#   | dscpr | duel terminal secret parallel  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Secret Parallel Rare      | DScPR }}
#   | rr    | rush                           = {{ safesubst:<noinclude/>#if: {{{full|}}} | Rush Rare                               | RR    }}
#   | grr   | gold rush                      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Gold Rush Rare                          | GRR   }}
#   | orr   | over rush                      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Over Rush Rare                          | ORR   }}

FULL_RARITY_STR_TO_ENUM = {
    "common": CardRarity.COMMON,  # c
    "short print": CardRarity.SHORTPRINT,  # sp
    "super short print": CardRarity.SHORTPRINT,  # ssp
    "normal rare": CardRarity.SHORTPRINT,  # nr
    "rare": CardRarity.RARE,  # r
    "super rare": CardRarity.SUPER,  # sr
    "ultra rare": CardRarity.ULTRA,  # ur
    "ultimate rare": CardRarity.ULTIMATE,  # utr
    "secret rare": CardRarity.SECRET,  # se / scr
    "ultra secret rare": CardRarity.ULTRASECRET,  # uscr
    "prismatic secret rare": CardRarity.PRISMATICSECRET,  # pscr
    "holographic rare": CardRarity.GHOST,  # hr / hgr
    "ghost rare": CardRarity.GHOST,  # gr
    "parallel rare": CardRarity.PARALLEL,  # pr
    "normal parallel rare": CardRarity.COMMONPARALLEL,  # npr
    "parallel common": CardRarity.COMMONPARALLEL,  # pc
    "rare parallel rare": CardRarity.RAREPARALLEL,  # rpr
    "super parallel rare": CardRarity.SUPERPARALLEL,  # spr
    "ultra parallel rare": CardRarity.ULTRAPARALLEL,  # upr
    "duel terminal parallel common": CardRarity.DTPC,  # dpc
    "duel terminal normal parallel rare": CardRarity.DTPC,  # dnpr
    "duel terminal rare parallel rare": CardRarity.DTPSP,  # drpr
    "duel terminal normal rare parallel rare": CardRarity.DTRPR,  # dnrpr
    "duel terminal super parallel rare": CardRarity.DTSPR,  # dspr
    "duel terminal ultra parallel rare": CardRarity.DTUPR,  # dupr
    "duel terminal secret parallel rare": CardRarity.DTSCPR,  # dscpr
    "gold rare": CardRarity.GOLD,  # gur
    "10000 secret rare": CardRarity.TENTHOUSANDSECRET,  # 10000scr
    "20th secret rare": CardRarity.TWENTITHSECRET,  # 20scr
    "collector's rare": CardRarity.COLLECTORS,  # cr
    "collectors rare": CardRarity.COLLECTORS,  # cr
    "extra secret": CardRarity.EXTRASECRET,  # escr
    "extra secret rare": CardRarity.EXTRASECRET,  # escr
    "extra secret parallel rare": CardRarity.EXTRASECRETPARALLEL,  # escpr
    "ghost/gold rare": CardRarity.GOLDGHOST,  # ggr
    "gold secret rare": CardRarity.GOLDSECRET,  # gscr
    "starfoil rare": CardRarity.STARFOIL,  # sfr
    "mosaic rare": CardRarity.MOSAIC,  # msr
    "shatterfoil rare": CardRarity.SHATTERFOIL,  # shr
    "holographic parallel rare": CardRarity.GHOSTPARALLEL,  # hgpr
    "platinum rare": CardRarity.PLATINUM,  # plr
    "platinum secret rare": CardRarity.PLATINUMSECRET,  # plscr
    "premium gold rare": CardRarity.PREMIUMGOLD,  # pgr
    "quarter century secret rare": CardRarity.TWENTYFIFTHSECRET,  # qcscr
    "secret parallel rare": CardRarity.SECRETPARALLEL,  # scpr
    "starlight rare": CardRarity.STARLIGHT,  # altr / str
    "alternate rare": CardRarity.STARLIGHT,  # altr / str
    "ultra rare (pharaoh's rare)": CardRarity.PHARAOHS,  # urpr
    "kaiba corporation common": CardRarity.KCCOMMON,  # kcc / kcn
    "kaiba corporation rare": CardRarity.KCRARE,  # kcr
    "kaiba corporation super rare": CardRarity.KCSUPER,  # kcsr
    "kaiba corporation ultra rare": CardRarity.KCULTRA,  # kcur
    "kaiba corporation secret rare": CardRarity.KCSECRET,  # kcscr
    "millennium rare": CardRarity.MILLENIUM,  # mr / mlr
    "millennium super rare": CardRarity.MILLENIUMSUPER,  # mlsr
    "millennium ultra rare": CardRarity.MILLENIUMULTRA,  # mlur
    "millennium secret rare": CardRarity.MILLENIUMSECRET,  # mlscr
    "millennium gold rare": CardRarity.MILLENIUMGOLD,  # mlgr
}

EDITION_STR_TO_ENUM = {
    "1E": SetEdition.FIRST,
    "UE": SetEdition.UNLIMTED,
    "REPRINT": SetEdition.UNLIMTED,
    "LE": SetEdition.LIMITED,
    # TODO: is this right?
    "DT": SetEdition.UNLIMTED,
}


def commonprefix(m: typing.Iterable[str]):
    "Given a list of strings, returns the longest common leading component"

    m = [*m]
    if not m:
        return ""
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1


def _printing_equal(p1: CardPrinting, p2: CardPrinting) -> bool:
    return p1.card == p2.card and p1.rarity == p2.rarity and p1.suffix == p2.suffix


def parse_set(
    db: Database,
    batcher: "YugipediaBatcher",
    pageid: int,
    set_: Set,
    data: wikitextparser.WikiText,
    raw_data: str,
    settable: wikitextparser.Template,
) -> bool:
    for arg in settable.arguments:
        if arg.name and arg.name.strip().endswith(DBNAME_SUFFIX) and arg.value.strip():
            lang = arg.name.strip()[: -len(DBNAME_SUFFIX)]
            if lang == "ja":
                lang = "jp"  # hooray for consistency!
            value = _strip_markup(arg.value).strip()
            if value:
                set_.name[lang] = value
    if "en" not in set_.name:
        set_.name["en"] = batcher.idsToNames[pageid]

    gallery_html = re.search(
        r"&lt;gallery[^\n]*\n(.*?)\n&lt;/gallery&gt;", raw_data, re.DOTALL
    ) or re.search(r"<gallery[^\n]*\n(.*?)\n</gallery>", raw_data, re.DOTALL)
    if not gallery_html:
        logging.warn(f"Did not find gallery HTML for {batcher.idsToNames[pageid]}")
        return False

    old_printings: typing.Dict[
        typing.Tuple[str, uuid.UUID, str, typing.Optional[CardRarity]], CardPrinting
    ] = {
        (locale.key, printing.card.id, printing.suffix or "", printing.rarity): printing
        for contents in set_.contents
        for printing in [*contents.cards, *contents.removed_cards]
        for locale in contents.locales
    }

    set_.locales.clear()
    set_.contents.clear()

    for line in gallery_html.group(1).split("\n"):
        if not line.strip():
            continue

        gallery_info = re.match(
            r"([^\|]+)\|(?:[^&]*&lt;[^&]*&gt;)?(.*)", line.strip()
        ) or re.match(r"([^\|]+)\|(?:[^<]*<[^>]*>)?(.*)", line.strip())
        if not gallery_info:
            logging.warn(
                f'Unparsable gallery line on {batcher.idsToNames[pageid]}: "{line.strip()}"'
            )
            continue
        gallery_image_name = gallery_info.group(1).strip()
        gallery_links = wikitextparser.parse(gallery_info.group(2))

        for link in gallery_links.wikilinks:
            if link.target.startswith(CARD_GALLERY_NAMESPACE):

                def do(galleryname: str):
                    locale_info = re.search(
                        r"\((\w+)-(\w+)-(\w+)\)", galleryname
                    ) or re.search(r"\((\w+)-(\w+)\)", galleryname)
                    if not locale_info:
                        logging.warn(f"No locale found for: {galleryname}")
                        return

                    @batcher.getPageContents(galleryname)
                    def onGetData(gallery_raw_data: str):
                        default_rarity = None
                        lang = locale_info.group(2).strip().lower()
                        locale = SetLocale(
                            key=lang,
                            language=lang,
                        )
                        edition = None
                        if len(locale_info.groups()) >= 3:
                            edition = EDITION_STR_TO_ENUM.get(
                                locale_info.group(3).strip().upper()
                            )
                            if not edition:
                                logging.warn(
                                    f"Unknown edition of set {galleryname}: {locale_info.group(3)}"
                                )

                        format_found = locale_info.group(1).strip().lower()
                        if format_found not in Format._value2member_map_:
                            logging.warn(
                                f"Invalid format found for {galleryname}: {format_found}"
                            )
                            return

                        contents = SetContents(
                            locales=[locale],
                            formats=[Format(format_found)],
                            editions=[edition] if edition else [],
                        )

                        @batcher.getImageURL("File:" + gallery_image_name)
                        def onGetImage(url: str):
                            locale.image = url

                        gallery_data = wikitextparser.parse(gallery_raw_data)

                        gallery_tables = [
                            x
                            for x in gallery_data.templates
                            if x.name.strip().lower() == "set gallery"
                        ]

                        subgalleries = [
                            [
                                x.strip()
                                for x in subgallery_html.group(1).split("\n")
                                if x.strip()
                            ]
                            for subgallery_html in [
                                *re.finditer(
                                    r"&lt;gallery[^\n]*\n(.*?)\n&lt;/gallery&gt;",
                                    gallery_raw_data,
                                    re.DOTALL,
                                ),
                                *re.finditer(
                                    r"<gallery[^\n]*\n(.*?)\n</gallery>",
                                    gallery_raw_data,
                                    re.DOTALL,
                                ),
                            ]
                        ]

                        if not gallery_tables and not subgalleries:
                            logging.warn(
                                f"Found gallery without gallery table or subgallery: {galleryname}"
                            )
                            return

                        printings = []

                        for gallery_table in gallery_tables:
                            default_rarity = get_table_entry(gallery_table, "rarity")
                            abbr = get_table_entry(gallery_table, "abbr")

                            for rawprintings in gallery_table.arguments:
                                if rawprintings.positional:
                                    for rawprinting in rawprintings.value.split("\n"):
                                        if rawprinting.strip():
                                            parts = [
                                                x.strip()
                                                for x in rawprinting.strip()
                                                .split("//")[0]
                                                .strip()
                                                .split(";")
                                            ]
                                            if abbr:
                                                printings.append(("", *parts))
                                            else:
                                                printings.append((*parts,))

                        for subgallery in subgalleries:
                            printings.extend(
                                (
                                    lambda m: (
                                        m.group(1).strip(),
                                        m.group(3).strip(),
                                        m.group(2).strip(),
                                    )
                                    if m
                                    else None
                                )(
                                    re.match(
                                        r"[^\|]*\|[^\[]*\[\[([^\]]*)\]\][^\[]*\[\[([^\]]*)\]\][^\[]*\[\[([^\]]*)\]\]",
                                        x,
                                    )
                                )
                                for x in subgallery
                            )

                        prefixmatch = re.match(
                            r"^[^\-]+\-\D*",
                            commonprefix(
                                printing[0] for printing in printings if printing
                            ),
                        )
                        locale.prefix = prefixmatch.group(0) if prefixmatch else ""

                        for printing in printings:
                            if not printing:
                                continue
                            if len(printing) < 2:
                                logging.warn(
                                    f"Expected 3 entries but got {len(printing)} in {galleryname}: {printing}"
                                )
                                continue
                            (code, name, *_) = printing
                            name = re.sub(
                                r"\s+",
                                r" ",
                                name.split("|")[0].replace("{", "").replace("{", ""),
                            ).strip()
                            if len(printing) >= 3:
                                rarity = printing[2]
                            else:
                                rarity = default_rarity

                            found_rairty = None
                            if rarity:
                                rarity = rarity.strip().lower()
                                found_rairty = RARITY_STR_TO_ENUM.get(
                                    rarity
                                ) or FULL_RARITY_STR_TO_ENUM.get(rarity)
                                if not found_rairty:
                                    logging.warn(
                                        f"Unknown rarity for {name} in {galleryname}: {rarity}"
                                    )

                            def getCardID(
                                name: str,
                                code: str,
                                found_rairty: typing.Optional[CardRarity],
                                locale: SetLocale,
                            ):
                                @batcher.getPageID(CAT_TOKENS)
                                def catID(tokensid: int, _: str):
                                    @batcher.getPageID(CAT_SKILLS)
                                    def catID(skillsid: int, _: str):
                                        @batcher.getPageID(CAT_UNUSABLE)
                                        def catID(unusableid: int, _: str):
                                            @batcher.getPageID(name)
                                            def onGetCardID(printingid: int, _: str):
                                                @batcher.getPageCategories(name)
                                                def onGetCardCats(
                                                    categories: typing.List[int],
                                                ):
                                                    if (
                                                        tokensid in categories
                                                        or skillsid in categories
                                                        or unusableid in categories
                                                    ):
                                                        return  # skip tokens, skill cards, and unplayables (for now)

                                                    def addToContents(id: int):
                                                        card = db.cards_by_yugipedia_id[
                                                            id
                                                        ]
                                                        suffix = code[
                                                            len(locale.prefix or "") :
                                                        ]
                                                        existing = old_printings.get(
                                                            (
                                                                locale.key,
                                                                card.id,
                                                                suffix,
                                                                found_rairty,
                                                            )
                                                        )
                                                        if existing:
                                                            contents.cards.append(
                                                                existing
                                                            )
                                                        else:
                                                            contents.cards.append(
                                                                CardPrinting(
                                                                    id=uuid.uuid4(),
                                                                    card=card,
                                                                    suffix=suffix,
                                                                    rarity=found_rairty,
                                                                )
                                                            )

                                                    if (
                                                        printingid
                                                        not in db.cards_by_yugipedia_id
                                                    ):
                                                        # try looking for (card) version
                                                        @batcher.getPageID(
                                                            name + " (card)"
                                                        )
                                                        def onGetCardID(
                                                            printingid: int, _: str
                                                        ):
                                                            @batcher.getPageCategories(
                                                                name
                                                            )
                                                            def onGetCardCats(
                                                                categories: typing.List[
                                                                    int
                                                                ],
                                                            ):
                                                                if (
                                                                    tokensid
                                                                    in categories
                                                                    or skillsid
                                                                    in categories
                                                                    or unusableid
                                                                    in categories
                                                                ):
                                                                    pass  # skip tokens, skill cards, and unplayables (for now)
                                                                elif (
                                                                    printingid
                                                                    not in db.cards_by_yugipedia_id
                                                                ):
                                                                    logging.warn(
                                                                        f'Card "{name}" not found in database in "{galleryname}"'
                                                                    )
                                                                else:
                                                                    addToContents(
                                                                        printingid
                                                                    )

                                                    else:
                                                        addToContents(printingid)

                            getCardID(name, code, found_rairty, locale)

                        for arg in settable.arguments:
                            if arg.name and arg.name.strip().endswith(DBID_SUFFIX):
                                lang = arg.name.strip()[: -len(DBID_SUFFIX)]
                                if lang == "ja":
                                    lang = "jp"  # hooray for consistency!

                                if lang == locale.key:
                                    db_ids = [
                                        x.strip()
                                        for x in arg.value.replace("*", "").split("\n")
                                        if x.strip()
                                    ]
                                    try:
                                        locale.db_ids = [
                                            int(x) for x in db_ids if x != "none"
                                        ]
                                    except ValueError:
                                        logging.warn(
                                            f"Unknown Konami ID for {batcher.idsToNames[pageid]}: {db_ids}"
                                        )

                        if locale.key in set_.locales:
                            # merge locales
                            existing_locale = set_.locales[locale.key]
                            existing_locale.db_ids.extend(
                                [
                                    x
                                    for x in locale.db_ids
                                    if x not in existing_locale.db_ids
                                ]
                            )

                            locale = existing_locale
                            contents.locales = [locale]
                        else:
                            set_.locales[locale.key] = locale

                        for similar_content in [
                            other_contents
                            for other_contents in set_.contents
                            if (
                                all(
                                    _printing_equal(p1, p2)
                                    for p1, p2 in zip(
                                        contents.cards, other_contents.cards
                                    )
                                )
                                and all(
                                    _printing_equal(p1, p2)
                                    for p1, p2 in zip(
                                        contents.removed_cards,
                                        other_contents.removed_cards,
                                    )
                                )
                            )
                        ]:
                            # same contents; merge
                            similar_content.locales.extend(
                                [
                                    x
                                    for x in contents.locales
                                    if x not in similar_content.locales
                                ]
                            )
                            similar_content.formats.extend(
                                [
                                    x
                                    for x in contents.formats
                                    if x not in similar_content.formats
                                ]
                            )
                            similar_content.editions.extend(
                                [
                                    x
                                    for x in contents.editions
                                    if x not in similar_content.editions
                                ]
                            )
                            break
                        else:
                            set_.contents.append(contents)

                do(link.target)

    set_.yugipedia = ExternalIdPair(batcher.idsToNames[pageid], pageid)
    return True


def import_from_yugipedia(
    db: Database,
    *,
    import_cards: bool = True,
    import_sets: bool = True,
) -> typing.Tuple[int, int]:
    n_found = n_new = 0

    with YugipediaBatcher() as batcher:
        atexit.register(lambda: batcher.saveCachesToDisk())

        if import_cards:
            cards: typing.List[int]
            if db.last_yugipedia_read is not None:
                if (
                    datetime.datetime.now().timestamp()
                    - db.last_yugipedia_read.timestamp()
                    > TIME_TO_JUST_REDOWNLOAD_ALL_PAGES
                ):
                    cards = [x for x in get_card_pages(batcher)]
                else:
                    batcher.use_cache = False
                    cards = [
                        x
                        for x in get_changes(
                            batcher,
                            get_card_pages(batcher),
                            [CAT_OCG_CARDS, CAT_TCG_CARDS],
                            get_changelog(db.last_yugipedia_read),
                        )
                    ]
                    batcher.use_cache = True
            else:
                cards = [x for x in get_card_pages(batcher)]

            for pageid in tqdm.tqdm(cards, desc="Importing cards from Yugipedia"):

                def do(pageid: int):
                    @batcher.getPageCategories(pageid)
                    def onGetCats(categories: typing.List[int]):
                        @batcher.getPageContents(pageid)
                        def onGetData(raw_data: str):
                            nonlocal n_found, n_new

                            data = wikitextparser.parse(raw_data)
                            try:
                                cardtable = next(
                                    iter(
                                        [
                                            x
                                            for x in data.templates
                                            if x.name.strip().lower() == "cardtable2"
                                        ]
                                    )
                                )
                            except StopIteration:
                                logging.warn(
                                    f"Found card without card table: {batcher.idsToNames[pageid]}"
                                )
                                return

                            ct = (
                                get_table_entry(cardtable, "card_type", "monster")
                                .strip()
                                .lower()
                            )
                            if ct not in [x.value for x in CardType]:
                                # logging.warn(f"Found card with illegal card type: {ct}")
                                return

                            found = pageid in db.cards_by_yugipedia_id
                            card = db.cards_by_yugipedia_id.get(pageid)
                            if not card:
                                value = get_table_entry(cardtable, "database_id", "")
                                vmatch = re.match(r"^\d+", value.strip())
                                if vmatch:
                                    card = db.cards_by_konami_cid.get(
                                        int(vmatch.group(0))
                                    )
                            if not card:
                                value = get_table_entry(cardtable, "password", "")
                                vmatch = re.match(r"^\d+", value.strip())
                                if vmatch:
                                    card = db.cards_by_password.get(vmatch.group(0))
                            if not card:
                                card = db.cards_by_en_name.get(
                                    batcher.idsToNames[pageid]
                                )
                            if not card:
                                card = Card(id=uuid.uuid4(), card_type=CardType(ct))

                            if parse_card(batcher, pageid, card, data, categories):
                                db.add_card(card)
                                if found:
                                    n_found += 1
                                else:
                                    n_new += 1

                do(pageid)

        if import_sets:
            sets: typing.List[int]
            if db.last_yugipedia_read is not None:
                if (
                    datetime.datetime.now().timestamp()
                    - db.last_yugipedia_read.timestamp()
                    > TIME_TO_JUST_REDOWNLOAD_ALL_PAGES
                ):
                    sets = [x for x in get_set_pages(batcher)]
                else:
                    batcher.use_cache = False
                    sets = [
                        x
                        for x in get_changes(
                            batcher,
                            get_set_pages(batcher),
                            [CAT_OCG_SETS, CAT_TCG_SETS],
                            get_changelog(db.last_yugipedia_read),
                        )
                    ]
                    batcher.use_cache = True
            else:
                sets = [x for x in get_set_pages(batcher)]

            for setid in tqdm.tqdm(sets, desc="Importing sets from Yugipedia"):

                def do(pageid: int):
                    @batcher.getPageContents(pageid)
                    def onGetData(raw_data: str):
                        nonlocal n_found, n_new

                        data = wikitextparser.parse(raw_data)
                        try:
                            settable = next(
                                iter(
                                    [
                                        x
                                        for x in data.templates
                                        if x.name.strip().lower() == "infobox set"
                                    ]
                                )
                            )
                        except StopIteration:
                            logging.warn(
                                f"Found set without set table: {batcher.idsToNames[pageid]}"
                            )
                            return

                        found = pageid in db.sets_by_yugipedia_id
                        set_ = db.sets_by_yugipedia_id.get(pageid)
                        if not set_:
                            for arg in settable.arguments:
                                if arg.name and arg.name.strip().endswith(DBID_SUFFIX):
                                    db_ids = [
                                        x.strip()
                                        for x in arg.value.replace("*", "").split("\n")
                                        if x.strip()
                                    ]
                                    try:
                                        for db_id in db_ids:
                                            set_ = db.sets_by_konami_sid.get(int(db_id))
                                            if set_:
                                                break
                                    except ValueError:
                                        if arg.value.strip() != "none":
                                            logging.warn(
                                                f'Unparsable konami set ID for {arg.name} in {batcher.idsToNames[pageid]}: "{arg.value}"'
                                            )
                        if not set_:
                            set_ = db.sets_by_en_name.get(
                                get_table_entry(settable, "en_name", "")
                            )
                        if not set_:
                            set_ = Set(id=uuid.uuid4())

                        if parse_set(
                            db, batcher, pageid, set_, data, raw_data, settable
                        ):
                            db.add_set(set_)
                            if found:
                                n_found += 1
                            else:
                                n_new += 1

                do(setid)

    db.last_yugipedia_read = datetime.datetime.now()
    return n_found, n_new


BATCH_MAX = 50

PAGES_FILENAME = "yugipedia_pages.json"
CONTENTS_FILENAME = "yugipedia_contents.json"
NAMESPACES = {"mw": "http://www.mediawiki.org/xml/export-0.10/"}
IMAGE_URLS_FILENAME = "yugipedia_images.json"
CAT_MEMBERS_FILENAME = "yugipedia_members.json"
PAGE_CATS_FILENAME = "yugipedia_categories.json"


class CategoryMemberType(enum.Enum):
    PAGE = "page"
    SUBCAT = "subcat"
    FILE = "file"


class CategoryMember(WikiPage):
    def __init__(self, id: int, name: str, type: CategoryMemberType) -> None:
        super().__init__(id, name)
        self.type = type


class YugipediaBatcher:
    use_cache: bool

    def __init__(self) -> None:
        self.namesToIDs = {}
        self.idsToNames = {}
        self.use_cache = True

        self.pendingGetPageContents = {}
        self.pageContentsCache = {}

        self.pendingGetPageCategories = {}
        self.pageCategoriesCache = {}

        self.imagesCache = {}
        self.pendingImages = {}

        self.categoryMembersCache = {}

        self.pendingGetPageID = {}

        path = os.path.join(TEMP_DIR, PAGES_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                pages = json.load(file)
                self.namesToIDs = {page["name"]: page["id"] for page in pages}
                self.idsToNames = {page["id"]: page["name"] for page in pages}

        path = os.path.join(TEMP_DIR, CONTENTS_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                self.pageContentsCache = {int(k): v for k, v in json.load(file).items()}

        path = os.path.join(TEMP_DIR, PAGE_CATS_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                self.pageCategoriesCache = {
                    int(k): v for k, v in json.load(file).items()
                }

        path = os.path.join(TEMP_DIR, CAT_MEMBERS_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                self.categoryMembersCache = {
                    int(k): [
                        CategoryMember(
                            x["id"], x["name"], CategoryMemberType(x["type"])
                        )
                        for x in v
                    ]
                    for k, v in json.load(file).items()
                }

        path = os.path.join(TEMP_DIR, IMAGE_URLS_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                self.imagesCache = {int(k): v for k, v in json.load(file).items()}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        self.flushPendingOperations()
        self.saveCachesToDisk()

    def saveCachesToDisk(self):
        path = os.path.join(TEMP_DIR, PAGES_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                [{"id": k, "name": v} for k, v in self.idsToNames.items()],
                file,
                indent=2,
            )

        path = os.path.join(TEMP_DIR, CONTENTS_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                {str(k): v for k, v in self.pageContentsCache.items()}, file, indent=2
            )

        path = os.path.join(TEMP_DIR, PAGE_CATS_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                {str(k): v for k, v in self.pageCategoriesCache.items()}, file, indent=2
            )

        path = os.path.join(TEMP_DIR, CAT_MEMBERS_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    k: [{"id": x.id, "name": x.name, "type": x.type.value} for x in v]
                    for k, v in self.categoryMembersCache.items()
                },
                file,
                indent=2,
            )

        path = os.path.join(TEMP_DIR, IMAGE_URLS_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump({str(k): v for k, v in self.imagesCache.items()}, file, indent=2)

    def flushPendingOperations(self):
        while (
            self.pendingGetPageContents
            or self.pendingGetPageCategories
            or self.pendingImages
            or self.pendingGetPageID
        ):
            self._executeGetContentsBatch()
            self._executeGetCategoriesBatch()
            self._executeGetImageURLBatch()
            self._executeGetPageIDBatch()

    def clearCache(self):
        self.categoryMembersCache.clear()
        self.pageCategoriesCache.clear()
        self.pageContentsCache.clear()
        self.imagesCache.clear()

    namesToIDs: typing.Dict[str, int]
    idsToNames: typing.Dict[int, str]

    pageContentsCache: typing.Dict[int, str]
    pendingGetPageContents: typing.Dict[
        typing.Union[str, int], typing.List[typing.Callable[[str], None]]
    ]

    def getPageContents(self, page: typing.Union[str, int]):
        batcher = self

        class GetPageXMLDecorator:
            def __init__(self, callback: typing.Callable[[str], None]) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )
                if batcher.use_cache and pageid in batcher.pageContentsCache:
                    callback(batcher.pageContentsCache[pageid])
                else:
                    batcher.pendingGetPageContents.setdefault(pageid or page, [])
                    batcher.pendingGetPageContents[pageid or page].append(callback)
                    if len(batcher.pendingGetPageContents.keys()) >= BATCH_MAX:
                        batcher._executeGetContentsBatch()

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetPageXMLDecorator

    def _executeGetContentsBatch(self):
        if not self.pendingGetPageContents:
            return
        pending = {k: v for k, v in self.pendingGetPageContents.items()}
        self.pendingGetPageContents.clear()
        pages = pending.keys()

        def do(pages: typing.Iterable[typing.Union[int, str]]):
            if not pages:
                return
            pageids = [str(p) for p in pages if type(p) is int]
            pagetitles = [str(p) for p in pages if type(p) is str]
            query = {
                "action": "query",
                "redirects": "1",
                "export": 1,
                "exportnowrap": 1,
                **({"pageids": "|".join(pageids)} if pageids else {}),
                **({"titles": "|".join(pagetitles)} if pagetitles else {}),
            }
            response_text = make_request(query).text
            pages_xml = xml.etree.ElementTree.fromstring(response_text)

            for page_xml in pages_xml.findall("mw:page", NAMESPACES):
                id = int(page_xml.find("mw:id", NAMESPACES).text)
                title = page_xml.find("mw:title", NAMESPACES).text

                self.namesToIDs[title] = id
                self.idsToNames[id] = title

                contents = (
                    page_xml.find("mw:revision", NAMESPACES)
                    .find("mw:text", NAMESPACES)
                    .text
                )
                self.pageContentsCache[id] = contents
                for callback in pending.get(id, []):
                    callback(contents)
                for callback in pending.get(title, []):
                    callback(contents)

        do([p for p in pages if type(p) is int])
        do([p for p in pages if type(p) is str])

    pageCategoriesCache: typing.Dict[int, typing.List[int]]
    pendingGetPageCategories: typing.Dict[
        typing.Union[str, int], typing.List[typing.Callable[[typing.List[int]], None]]
    ]

    def getPageCategories(self, page: typing.Union[str, int]):
        batcher = self

        class GetPageCategoriesDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )
                if batcher.use_cache and pageid in batcher.pageCategoriesCache:
                    callback(batcher.pageCategoriesCache[pageid])
                else:
                    batcher.pendingGetPageCategories.setdefault(pageid or page, [])
                    batcher.pendingGetPageCategories[pageid or page].append(callback)
                    if len(batcher.pendingGetPageCategories.keys()) >= BATCH_MAX:
                        batcher._executeGetCategoriesBatch()

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetPageCategoriesDecorator

    def _executeGetCategoriesBatch(self):
        if not self.pendingGetPageCategories:
            return
        pending = {k: v for k, v in self.pendingGetPageCategories.items()}
        self.pendingGetPageCategories.clear()
        pages = pending.keys()

        def do(pages: typing.Iterable[typing.Union[int, str]]):
            if not pages:
                return
            pageids = [str(p) for p in pages if type(p) is int]
            pagetitles = [str(p) for p in pages if type(p) is str]
            query = {
                "action": "query",
                "redirects": "1",
                "prop": "categories",
                **({"pageids": "|".join(pageids)} if pageids else {}),
                **({"titles": "|".join(pagetitles)} if pagetitles else {}),
            }

            cats_got: typing.Dict[int, typing.List[int]] = {}

            for result_page in paginate_query(query):
                for result in result_page["pages"]:
                    self.namesToIDs[result["title"]] = result["pageid"]
                    self.idsToNames[result["pageid"]] = result["title"]
                    cats_got.setdefault(result["pageid"], [])

                    if "categories" not in result:
                        continue

                    unknown_cats = [
                        x["title"]
                        for x in result["categories"]
                        if x["title"] not in self.namesToIDs
                    ]
                    if unknown_cats:
                        query2 = {
                            "action": "query",
                            "redirects": "1",
                            "titles": "|".join(unknown_cats),
                        }
                        for result2_page in paginate_query(query2):
                            for result2 in result2_page["pages"]:
                                if "pageid" not in result2:
                                    continue
                                self.namesToIDs[result2["title"]] = result2["pageid"]
                                self.idsToNames[result2["pageid"]] = result2["title"]

                    cats_got[result["pageid"]].extend(
                        [
                            self.namesToIDs[x["title"]]
                            for x in result["categories"]
                            if x["title"] in self.namesToIDs
                        ]
                    )

            for pageid, cats in cats_got.items():
                self.pageCategoriesCache[pageid] = cats
                for callback in pending.get(pageid, []):
                    callback(cats)
                for callback in pending.get(self.idsToNames[pageid], []):
                    callback(cats)

        do([p for p in pages if type(p) is int])
        do([p for p in pages if type(p) is str])

    categoryMembersCache: typing.Dict[int, typing.List[CategoryMember]]

    def _populateCatMembers(self, page: typing.Union[str, int]) -> int:
        query = {
            "action": "query",
            "list": "categorymembers",
            "redirects": "1",
            **(
                {
                    "cmtitle": page,
                }
                if type(page) is str
                else {}
            ),
            **(
                {
                    "cmpageid": page,
                }
                if type(page) is int
                else {}
            ),
            **(
                {
                    "titles": page,
                }
                if type(page) is str
                else {}
            ),
            **(
                {
                    "pageids": page,
                }
                if type(page) is int
                else {}
            ),
            "cmlimit": "max",
            "cmprop": "ids|title|type",
        }

        members: typing.List[CategoryMember] = []
        for results in paginate_query(query):
            for result in results.get("pages") or []:
                pageid = result["pageid"]
                self.categoryMembersCache[result["pageid"]] = members
                self.namesToIDs[result["title"]] = result["pageid"]
                self.idsToNames[result["pageid"]] = result["title"]
            for result in results["categorymembers"]:
                members.append(
                    CategoryMember(
                        result["pageid"],
                        result["title"],
                        CategoryMemberType(result["type"]),
                    )
                )

        return pageid

    def getCategoryMembers(self, page: typing.Union[str, int]):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )

                if not batcher.use_cache or pageid not in batcher.categoryMembersCache:
                    pageid = batcher._populateCatMembers(page)

                if pageid is None:
                    raise Exception(f"ID not found: {page}")

                callback(
                    [
                        x.id
                        for x in batcher.categoryMembersCache[pageid]
                        if x.type == CategoryMemberType.PAGE
                    ]
                )

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetCatMemDecorator

    def getSubcategories(self, page: typing.Union[str, int]):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )

                if not batcher.use_cache or pageid not in batcher.categoryMembersCache:
                    pageid = batcher._populateCatMembers(page)

                if pageid is None:
                    raise Exception(f"ID not found: {page}")

                callback(
                    [
                        x.id
                        for x in batcher.categoryMembersCache[pageid]
                        if x.type == CategoryMemberType.SUBCAT
                    ]
                )

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetCatMemDecorator

    def getCategoryMembersRecursive(self, page: typing.Union[str, int]):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                result = []

                @batcher.getCategoryMembers(page)
                def getMembers(members: typing.List[int]):
                    result.extend(members)

                @batcher.getSubcategories(page)
                def getSubcats(members: typing.List[int]):
                    for member in members:

                        @batcher.getCategoryMembersRecursive(member)
                        def recur(members: typing.List[int]):
                            result.extend(members)

                callback(result)

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetCatMemDecorator

    imagesCache: typing.Dict[int, str]
    pendingImages: typing.Dict[
        typing.Union[int, str], typing.List[typing.Callable[[str], None]]
    ]

    def getImageURL(self, page: typing.Union[str, int]):
        batcher = self

        class GetImageDecorator:
            def __init__(self, callback: typing.Callable[[str], None]) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )
                if batcher.use_cache and pageid in batcher.imagesCache:
                    callback(batcher.imagesCache[pageid])
                else:
                    batcher.pendingImages.setdefault(pageid or page, [])
                    batcher.pendingImages[pageid or page].append(callback)
                    if len(batcher.pendingImages.keys()) >= BATCH_MAX:
                        batcher._executeGetImageURLBatch()

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetImageDecorator

    def _executeGetImageURLBatch(self):
        if not self.pendingImages:
            return
        pending = {k: v for k, v in self.pendingImages.items()}
        self.pendingImages.clear()
        pages = pending.keys()

        def do(pages: typing.Iterable[typing.Union[int, str]]):
            if not pages:
                return
            pageids = [str(p) for p in pages if type(p) is int]
            pagetitles = [str(p) for p in pages if type(p) is str]
            query = {
                "action": "query",
                "prop": "imageinfo",
                **({"pageids": "|".join(pageids)} if pageids else {}),
                **({"titles": "|".join(pagetitles)} if pagetitles else {}),
                "iiprop": "url",
            }
            for result_page in paginate_query(query):
                for result in result_page["pages"]:
                    if result.get("missing") or result.get("invalid"):
                        continue

                    pageid = result["pageid"]
                    title = result["title"]

                    self.namesToIDs[title] = pageid
                    self.idsToNames[pageid] = title

                    if "imageinfo" not in result:
                        continue

                    for image in result["imageinfo"]:
                        url = image["url"]
                        self.imagesCache[pageid] = url
                        for callback in pending.get(pageid, []):
                            callback(url)
                        for callback in pending.get(title, []):
                            callback(url)

        do([p for p in pages if type(p) is int])
        do([p for p in pages if type(p) is str])

    pendingGetPageID: typing.Dict[
        typing.Union[int, str], typing.List[typing.Callable[[int, str], None]]
    ]

    def getPageID(self, page: typing.Union[str, int]):
        batcher = self

        class GetIDDecorator:
            def __init__(self, callback: typing.Callable[[int, str], None]) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )
                # we make the dangerous assumption here that page IDs and internal titles never change
                # (that is, we ignore batcher.use_cache)
                if page in batcher.namesToIDs:
                    callback(batcher.namesToIDs[page], page)
                elif page in batcher.idsToNames:
                    callback(page, batcher.idsToNames[page])
                else:
                    batcher.pendingGetPageID.setdefault(pageid or page, [])
                    batcher.pendingGetPageID[pageid or page].append(callback)
                    if len(batcher.pendingGetPageID.keys()) >= BATCH_MAX:
                        batcher._executeGetPageIDBatch()

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetIDDecorator

    def _executeGetPageIDBatch(self):
        if not self.pendingGetPageID:
            return
        pending = {k: v for k, v in self.pendingGetPageID.items()}
        self.pendingGetPageID.clear()
        pages = pending.keys()

        def do(pages: typing.Iterable[typing.Union[int, str]]):
            if not pages:
                return
            pageids = [str(p) for p in pages if type(p) is int]
            pagetitles = [str(p) for p in pages if type(p) is str]
            query = {
                "action": "query",
                **({"pageids": "|".join(pageids)} if pageids else {}),
                **({"titles": "|".join(pagetitles)} if pagetitles else {}),
            }
            for result_page in paginate_query(query):
                for result in result_page["pages"]:
                    if result.get("missing") or result.get("invalid"):
                        continue
                    if "pageid" not in result or "title" not in result:
                        logging.warn(
                            f"In _executeGetPageIDBatch: bad page ID result: {result}"
                        )
                        continue

                    pageid = result["pageid"]
                    title = result["title"]

                    self.namesToIDs[title] = pageid
                    self.idsToNames[pageid] = title

                    for callback in pending.get(pageid, []):
                        callback(pageid, title)
                    for callback in pending.get(title, []):
                        callback(pageid, title)

        do([p for p in pages if type(p) is int])
        do([p for p in pages if type(p) is str])
