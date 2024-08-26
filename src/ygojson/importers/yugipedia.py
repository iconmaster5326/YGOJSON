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


def make_request(rawparams: typing.Dict[str, str], n_tries=0) -> requests.Response:
    global _last_access

    now = time.time()
    while (now - _last_access) <= RATE_LIMIT:
        time.sleep(now - _last_access)
        now = time.time()
    _last_access = time.time()

    params = {
        "format": "json",
        "utf8": "1",
        "formatversion": "2",
        "redirects": "1",
    }
    params.update(rawparams)

    if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
        logging.debug(f"Making request: {json.dumps(params)}")
    try:
        response = requests.get(
            API_URL,
            params=params,
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=13,
        )
        if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
            logging.debug(
                f"Got response: {response.status_code} {response.reason} {response.text}"
            )
        if not response.ok:
            # timeout; servers must be hammered
            logging.error(
                f"Yugipedia server returned {response.status_code}: {response.reason}; waiting and retrying..."
            )
            time.sleep(RATE_LIMIT * 30)
            return make_request(rawparams, n_tries + 1)
        return response
    except requests.exceptions.Timeout:
        logging.error("timeout; waiting and retrying...")
        time.sleep(RATE_LIMIT * 30)
        return make_request(rawparams, n_tries + 1)


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
CAT_TOKENS = "Category:Tokens"
CAT_SKILLS = "Category:Skill Cards"
CAT_UNUSABLE = "Category:Unusable cards"
CAT_MD_UNCRAFTABLE = "Category:Yu-Gi-Oh! Master Duel cards that cannot be crafted"
CAT_ARCHETYPES = "Category:Archetypes"
CAT_SERIES = "Category:Series"

SET_CATS = [
    "Category:TCG sets",
    "Category:OCG sets",
    "Category:Yu-Gi-Oh! Master Duel sets",
    "Category:Yu-Gi-Oh! Duel Links sets",
]

BANLIST_CATS = {
    "tcg": "Category:TCG Advanced Format Forbidden & Limited Lists",
    "ocg": "Category:OCG Forbidden & Limited Lists",
    "ocg-kr": "Category:Korean OCG Forbidden & Limited Lists",
    # "ocg-ae": "Category:Asian-English OCG Forbidden & Limited Lists",
    # "ocg-tc": "Category:Traditional Chinese OCG Forbidden & Limited Lists",
    "ocg-sc": "Category:Simplified Chinese OCG Forbidden & Limited Lists",
    "speed": "Category:TCG Speed Duel Forbidden & Limited Lists",
    "masterduel": "Category:Yu-Gi-Oh! Master Duel Forbidden & Limited Lists",
    "duellinks": "Category:Yu-Gi-Oh! Duel Links Forbidden & Limited Lists",
}

DBID_SUFFIX = "_database_id"
DBNAME_SUFFIX = "_name"
RELDATE_SUFFIX = "_release_date"

EXT_PREFIX = "extension::"
FILE_PREFIX = "file::"


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
    with tqdm.tqdm(
        total=len(SET_CATS), desc="Fetching Yugipedia set list"
    ) as progress_bar:
        result = []
        seen = set()

        for cat in SET_CATS:

            @batcher.getCategoryMembersRecursive(cat)
            def catMem(members: typing.List[int]):
                result.extend(x for x in members if x not in seen)
                seen.update(members)
                progress_bar.update(1)

        return result


def get_series_pages(batcher: "YugipediaBatcher") -> typing.Iterable[int]:
    with tqdm.tqdm(total=2, desc="Fetching Yugipedia series list") as progress_bar:
        result = []
        seen = set()

        @batcher.getCategoryMembers(CAT_ARCHETYPES)
        def catMem1(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        @batcher.getCategoryMembers(CAT_SERIES)
        def catMem2(members: typing.List[int]):
            result.extend(x for x in members if x not in seen)
            seen.update(members)
            progress_bar.update(1)

        return result


def get_changelog(
    batcher: "YugipediaBatcher", since: datetime.datetime
) -> typing.Iterable[ChangelogEntry]:
    query = {
        "action": "query",
        "list": "recentchanges",
        "rcend": since.isoformat(),
        "rclimit": "max",
    }

    for results in paginate_query(query):
        for result in results["recentchanges"]:
            batcher.removeFromCache(result["title"])
            batcher.removeFromCache(result["pageid"])
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
    "na": "en",
    "eu": "en",
    "oc": "en",
    "au": "en",
    "fr": "fr",
    "fc": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "es": "es",
    "sp": "es",
    "jp": "ja",
    "ja": "ja",
    "ko": "ko",
    "kr": "ko",
    "tc": "zh-TW",
    "sc": "zh-CN",
    "ae": "ae",
}

LOCALES_FULL = {
    "English": "en",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portugese": "pt",
    "Spanish": "es",
    "Japanese": "ja",
    "Korean": "ko",
    "Traditional Chinese": "zh-TW",
    "Simplified Chinese": "zh-CN",
    "Asian English": "ae",
    "Asian-English": "ae",
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
            re.sub(
                r"\{\{[Rr]uby\|([^\|]*)\|(?:[^\}]*)?\}\}",
                r"\1",
                x.replace("<br />", "\n"),
            )
        )
        for x in s.split("\n")
    )


def parse_card(
    batcher: "YugipediaBatcher",
    page: int,
    card: Card,
    data: wikitextparser.WikiText,
    categories: typing.List[int],
    banlists: typing.Dict[str, typing.List["Banlist"]],
    series_members: typing.Dict[str, typing.Set[Card]],
) -> bool:
    """
    Parse a card from a wiki page. Returns False if this is not actually a valid card
    for the database, and True otherwise.
    """

    title = batcher.idsToNames[page]
    cardtable = next(
        iter([x for x in data.templates if x.name.strip().lower() == "cardtable2"])
    )

    for locale, key in LOCALES.items():
        lang = Language.normalize(key)
        value = get_table_entry(cardtable, locale + "_name" if locale else "name")
        if not locale and not value:
            value = title
        if value and value.strip():
            value = _strip_markup(value.strip())
            card.text.setdefault(lang, CardText(name=value))
            card.text[lang].name = value
        value = get_table_entry(cardtable, locale + "_lore" if locale else "lore")
        if value and value.strip():
            if lang not in card.text:
                # logging.warn(f"Card has no name in {key} but has effect: {title}")
                pass
            else:
                card.text[lang].effect = _strip_markup(value.strip())
        value = get_table_entry(
            cardtable, locale + "_pendulum_effect" if locale else "pendulum_effect"
        )
        if value and value.strip():
            if lang not in card.text:
                # logging.warn(f"Card has no name in {key} but has pend. effect: {title}")
                pass
            else:
                card.text[lang].pendulum_effect = _strip_markup(value.strip())
        if any(
            (t.name.strip() == "Unofficial name" or t.name.strip() == "Unofficial lore")
            and LOCALES_FULL.get(t.arguments[0].value.strip()) == key
            for t in data.templates
        ):
            if lang not in card.text:
                # logging.warn(f"Card has no name in {key} but is unofficial: {title}")
                pass
            else:
                card.text[lang].official = False

    if "en" not in card.text:
        card.text[Language.ENGLISH] = CardText(name=title, official=False)
    elif not card.text[Language.ENGLISH].name:
        card.text[Language.ENGLISH].name = title
        card.text[Language.ENGLISH].official = False

    if card.card_type in {
        CardType.MONSTER,
        CardType.TOKEN,
    }:  # parse monsterlike cards' common attributes
        typeline = get_table_entry(cardtable, "types")
        if not typeline:
            typeline = ""
            if card.card_type != CardType.TOKEN:
                logging.warn(f"Monster has no typeline: {title}")
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
                if card.card_type != CardType.TOKEN:
                    logging.warn(f"Unknown attribute '{value.strip()}' in {title}")
            else:
                card.attribute = Attribute(value)

        typeline = [x.strip() for x in typeline.split("/") if x.strip()]

        for x in typeline:
            if (
                x
                not in {
                    "?",
                    "???",
                    "Token",
                    "Counter",
                }  # type to be announced or is token; omit it
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
                if card.card_type != CardType.TOKEN:
                    logging.warn(f"Unknown level '{value.strip()}' in {title}")
                    return False

        value = get_table_entry(cardtable, "atk")
        if value and value.strip() != "???":
            try:
                card.atk = "?" if value.strip() in MYSTERY_ATK_DEFS else int(value)
            except ValueError:
                logging.warn(f"Unknown ATK '{value.strip()}' in {title}")
                if card.card_type != CardType.TOKEN:
                    return False
        value = get_table_entry(cardtable, "def")
        if value and value.strip() != "???":
            try:
                card.def_ = "?" if value.strip() in MYSTERY_ATK_DEFS else int(value)
            except ValueError:
                logging.warn(f"Unknown DEF '{value.strip()}' in {title}")
                if card.card_type != CardType.TOKEN:
                    return False

    if card.card_type == CardType.MONSTER:
        value = get_table_entry(cardtable, "rank")
        if value and value.strip() != "???":
            try:
                card.rank = int(value)
            except ValueError:
                logging.warn(f"Unknown rank '{value.strip()}' in {title}")
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
    elif card.card_type == CardType.TOKEN:
        pass
    elif card.card_type == CardType.SKILL:
        char = get_table_entry(cardtable, "character", "").strip()
        if char:
            card.character = char
        typeline = [
            x.strip()
            for x in get_table_entry(cardtable, "types", "").split("/")
            if x.strip()
        ]
        if len(typeline) == 3:
            card.skill_type = typeline[2]
        elif len(typeline) > 3:
            logging.warn(f"Found skill card {title} with weird typeline: {typeline}")
    else:
        logging.warn(f"Skipping {card.card_type} card: {title}")
        return False

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
                if len(in_image) == 1:
                    image_name = in_image[0]
                elif len(in_image) == 2:
                    image_name = in_image[1]
                elif len(in_image) == 3:
                    image_name = in_image[1]
                else:
                    logging.warn(
                        f"Weird image string for {title}: {' ; '.join(in_image)}"
                    )
                    return

                @batcher.getImageURL("File:" + image_name)
                def onGetImage(url: str):
                    out_image.card_art = url

            for image in card.images:
                in_image = in_images.pop(0)
                add_image(in_image, image)
            for in_image in in_images:
                new_image = CardImage(id=uuid.uuid4())
                if len(card.passwords) == 1:
                    # we don't have the full ability to correspond passwords here
                    # but this will do for 99% of cards
                    new_image.password = card.passwords[0]
                add_image(in_image, new_image)
                card.images.append(new_image)

    md_title = title + MD_DISAMBIG_SUFFIX

    @batcher.getPageContents(md_title)
    def onGetMD(raw_vg_data: str):
        vg_data = wikitextparser.parse(raw_vg_data)
        for vg_table in [
            x for x in vg_data.templates if x.name.strip().lower() == "master duel card"
        ]:
            rarity = get_table_entry(vg_table, "rarity")
            if rarity and rarity.strip():
                rarity = rarity.strip().lower()
                if rarity in {"?", "???"}:
                    pass  # unknown rarity; this is fine
                elif rarity not in VideoGameRaity._value2member_map_:
                    logging.warn(
                        f"Found MD page for '{md_title}' with invalid rarity: {rarity}"
                    )
                else:
                    card.master_duel_rarity = VideoGameRaity(rarity)

        card.master_duel_craftable = True

        @batcher.getPageID(CAT_MD_UNCRAFTABLE)
        def onGetCatID(uncraftable_id: int, _: str):
            @batcher.getPageCategories(md_title)
            def onGetCats(cats: typing.List[int]):
                if uncraftable_id in cats:
                    card.master_duel_craftable = False

    dl_title = title + DL_DISAMBIG_SUFFIX

    @batcher.getPageContents(dl_title)
    def onGetDL(raw_vg_data: str):
        vg_data = wikitextparser.parse(raw_vg_data)
        for vg_table in [
            x for x in vg_data.templates if x.name.strip().lower() == "duel links card"
        ]:
            rarity = get_table_entry(vg_table, "rarity")
            if rarity and rarity.strip():
                rarity = rarity.strip().lower()
                if rarity in {"?", "???"}:
                    pass  # unknown rarity; this is fine
                elif rarity not in VideoGameRaity._value2member_map_:
                    logging.warn(
                        f"Found DL page for '{dl_title}' with invalid rarity: {rarity}"
                    )
                else:
                    card.duel_links_rarity = VideoGameRaity(rarity)

    limit_text = get_table_entry(cardtable, "limitation_text")
    if limit_text and limit_text.strip():
        card.illegal = True
        card.legality.clear()
    else:
        for rawformat, ban_history in banlists.items():
            if rawformat not in Format._value2member_map_:
                logging.warn(f"Found unknown legality format in {title}: {rawformat}")
                continue
            format = Format(rawformat)

            card_history = card.legality.get(format)
            if card_history:
                card_history.history.clear()

            for history_item in ban_history:
                if title in history_item.cards:
                    legality = history_item.cards[title]
                    if not card_history:
                        card.legality.setdefault(format, CardLegality(current=legality))
                        card_history = card.legality[format]
                    card_history.current = legality
                    card_history.history.append(
                        LegalityPeriod(legality=legality, date=history_item.date)
                    )

    for archseries in [
        x.strip()
        for x in get_table_entry(cardtable, "archseries", "")
        .replace("*", "")
        .split("\n")
        if x.strip()
    ]:
        series_members.setdefault(archseries.lower(), set())
        series_members[archseries.lower()].add(card)

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

    # TODO: errata

    return True


CARD_GALLERY_NAMESPACE = "Set Card Galleries:"

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
#   | dnrpr                                  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Rare Parallel Rare | DNRPR }}
#   | dnpr                                   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Normal Parallel Rare      | DNPR  }}
#   | drpr  | duel terminal  parallel        = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Rare Parallel Rare        | DRPR  }}
#   | dspr  | duel terminal super parallel   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Super Parallel Rare       | DSPR  }}
#   | dupr  | duel terminal ultra parallel   = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Ultra Parallel Rare       | DUPR  }}
#   | dscpr | duel terminal secret parallel  = {{ safesubst:<noinclude/>#if: {{{full|}}} | Duel Terminal Secret Parallel Rare      | DScPR }}
#   | rr    | rush                           = {{ safesubst:<noinclude/>#if: {{{full|}}} | Rush Rare                               | RR    }}
#   | grr   | gold rush                      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Gold Rush Rare                          | GRR   }}
#   | orr   | over rush                      = {{ safesubst:<noinclude/>#if: {{{full|}}} | Over Rush Rare                          | ORR   }}

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

_RARITY_FTS_RAW: typing.List[typing.Tuple[typing.List[str], str]] = [
    (
        [
            "c",
            "common",
            "Common",
        ],
        "C",
    ),
    (
        [
            "nr",
            "normal",
            "Normal Rare",
        ],
        "NR",
    ),
    (
        [
            "sp",
            "short print",
            "Short Print",
        ],
        "SP",
    ),
    (
        [
            "ssp",
            "super short print",
            "Super Short Print",
        ],
        "SSP",
    ),
    (
        [
            "hfr",
            "holofoil",
            "Holofoil Rare",
        ],
        "HFR",
    ),
    (
        [
            "r",
            "rare",
            "Rare",
        ],
        "R",
    ),
    (
        [
            "sr",
            "super",
            "Super Rare",
        ],
        "SR",
    ),
    (
        [
            "ur",
            "ultra",
            "Ultra Rare",
        ],
        "UR",
    ),
    (
        [
            "utr",
            "ultimate",
            "Ultimate Rare",
        ],
        "UtR",
    ),
    (
        [
            "gr",
            "ghost",
            "Ghost Rare",
        ],
        "GR",
    ),
    (
        [
            "hr",
            "hgr",
            "holographic",
            "Holographic Rare",
        ],
        "HGR",
    ),
    (
        [
            "se",
            "scr",
            "secret",
            "Secret Rare",
        ],
        "ScR",
    ),
    (
        [
            "pscr",
            "prismatic secret",
            "Prismatic Secret Rare",
        ],
        "PScR",
    ),
    (
        [
            "uscr",
            "ultra secret",
            "Ultra Secret Rare",
        ],
        "UScR",
    ),
    (
        [
            "scur",
            "secret ultra",
            "Secret Ultra Rare",
        ],
        "ScUR",
    ),
    (
        [
            "escr",
            "extra secret",
            "Extra Secret Rare",
        ],
        "EScR",
    ),
    (
        [
            "20scr",
            "20th secret",
            "20th Secret Rare",
        ],
        "20ScR",
    ),
    (
        [
            "qcscr",
            "quarter century secret",
            "Quarter Century Secret Rare",
        ],
        "QCScR",
    ),
    (
        [
            "10000scr",
            "10000 secret",
            "10000 Secret Rare",
        ],
        "10000ScR",
    ),
    (
        [
            "str",
            "starlight",
            "Starlight Rare",
            "alt",
            "altr",
            "alternate",
            "Alternate Rare",
        ],
        "StR",
    ),
    (
        [
            "plr",
            "platinum",
            "Platinum Rare",
        ],
        "PlR",
    ),
    (
        [
            "plscr",
            "platinum secret",
            "Platinum Secret Rare",
        ],
        "PlScR",
    ),
    (
        [
            "pr",
            "parallel",
            "Parallel Rare",
        ],
        "PR",
    ),
    (
        [
            "pc",
            "parallel common",
            "Parallel Common",
        ],
        "PC",
    ),
    (
        [
            "npr",
            "normal parallel",
            "Normal Parallel Rare",
        ],
        "NPR",
    ),
    (
        [
            "rpr",
            "rare parallel",
            "Rare Parallel Rare",
        ],
        "RPR",
    ),
    (
        [
            "spr",
            "super parallel",
            "Super Parallel Rare",
        ],
        "SPR",
    ),
    (
        [
            "upr",
            "ultra parallel",
            "Ultra Parallel Rare",
        ],
        "UPR",
    ),
    (
        [
            "scpr",
            "secret parallel",
            "Secret Parallel Rare",
        ],
        "ScPR",
    ),
    (
        [
            "escpr",
            "extra secret parallel",
            "Extra Secret Parallel Rare",
        ],
        "EScPR",
    ),
    (
        [
            "h",
            "hobby",
            "Hobby Rare",
        ],
        "H",
    ),
    (
        [
            "sfr",
            "starfoil",
            "Starfoil Rare",
        ],
        "SFR",
    ),
    (
        [
            "msr",
            "mosaic",
            "Mosaic Rare",
        ],
        "MSR",
    ),
    (
        [
            "shr",
            "shatterfoil",
            "Shatterfoil Rare",
        ],
        "SHR",
    ),
    (
        [
            "cr",
            "collectors",
            "Collectors Rare",
            "Collector's Rare",
        ],
        "CR",
    ),
    (
        [
            "hgpr",
            "holographic parallel",
            "Holographic Parallel Rare",
        ],
        "HGPR",
    ),
    (
        [
            "urpr",
            "ultra pharaohs",
            "pharaohs",
            "Ultra Rare (Pharaoh's Rare)",
        ],
        "URPR",
    ),
    (
        [
            "kcc",
            "kcn",
            "kaiba corporation common",
            "kaiba corporation normal",
            "Kaiba Corporation Common",
        ],
        "KCC",
    ),
    (
        [
            "kcr",
            "kaiba corporation",
            "Kaiba Corporation Rare",
        ],
        "KCR",
    ),
    (
        [
            "kcsr",
            "kaiba corporation super",
            "Kaiba Corporation Super Rare",
        ],
        "KCSR",
    ),
    (
        [
            "kcur",
            "kaiba corporation ultra",
            "Kaiba Corporation Ultra Rare",
        ],
        "KCUR",
    ),
    (
        [
            "kcscr",
            "kaiba corporation secret",
            "Kaiba Corporation Secret Rare",
        ],
        "KCScR",
    ),
    (
        [
            "mr",
            "mlr",
            "millennium",
            "Millennium Rare",
        ],
        "MLR",
    ),
    (
        [
            "mlsr",
            "millennium super",
            "Millennium Super Rare",
        ],
        "MLSR",
    ),
    (
        [
            "mlur",
            "millennium ultra",
            "Millennium Ultra Rare",
        ],
        "MLUR",
    ),
    (
        [
            "mlscr",
            "millennium secret",
            "Millennium Secret Rare",
        ],
        "MLScR",
    ),
    (
        [
            "mlgr",
            "millennium gold",
            "Millennium Gold Rare",
        ],
        "MLGR",
    ),
    (
        [
            "gur",
            "gold",
            "Gold Rare",
        ],
        "GUR",
    ),
    (
        [
            "gscr",
            "gold secret",
            "Gold Secret Rare",
        ],
        "GScR",
    ),
    (
        [
            "ggr",
            "ghost/gold",
            "Ghost/Gold Rare",
        ],
        "GGR",
    ),
    (
        [
            "pgr",
            "premium gold",
            "Premium Gold Rare",
        ],
        "PGR",
    ),
    (
        [
            "dpc",
            "duel terminal parallel common",
            "Duel Terminal Parallel Common",
        ],
        "DPC",
    ),
    (
        [
            "dnrpr",
            "Duel Terminal Normal Rare Parallel Rare",
        ],
        "DNRPR",
    ),
    (
        [
            "dnpr",
            "Duel Terminal Normal Parallel Rare",
        ],
        "DNPR",
    ),
    (
        [
            "drpr",
            "duel terminal parallel",
            "Duel Terminal Rare Parallel Rare",
        ],
        "DRPR",
    ),
    (
        [
            "dspr",
            "duel terminal super parallel",
            "Duel Terminal Super Parallel Rare",
        ],
        "DSPR",
    ),
    (
        [
            "dupr",
            "duel terminal ultra parallel",
            "Duel Terminal Ultra Parallel Rare",
        ],
        "DUPR",
    ),
    (
        [
            "dscpr",
            "duel terminal secret parallel",
            "Duel Terminal Secret Parallel Rare",
        ],
        "DScPR",
    ),
    (
        [
            "rr",
            "rush",
            "Rush Rare",
        ],
        "RR",
    ),
    (
        [
            "grr",
            "gold rush",
            "Gold Rush Rare",
        ],
        "GRR",
    ),
    (["orr", "over rush", "Over Rush Rare"], "ORR"),
]
RAIRTY_FULL_TO_SHORT = {kk.lower(): v for k, v in _RARITY_FTS_RAW for kk in k}

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
    "starfoil": CardRarity.STARFOIL,  # sfr
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
    "DT": SetEdition.LIMITED,
}

EDITIONS_IN_NAV = {
    "1e": SetEdition.FIRST,
    "ue": SetEdition.UNLIMTED,
    "le": SetEdition.LIMITED,
}

EDITIONS_IN_NAV_REVERSE = {v: k for k, v in EDITIONS_IN_NAV.items()}

FORMATS_IN_NAV = {
    "en": "TCG",
    "na": "TCG",
    "eu": "TCG",
    "au": "TCG",
    "oc": "TCG",
    "fr": "TCG",
    "fc": "TCG",
    "de": "TCG",
    "it": "TCG",
    "pt": "TCG",
    "es": "TCG",
    "sp": "TCG",
    "jp": "OCG",
    "ja": "OCG",
    "ko": "OCG",
    "kr": "OCG",
    "tc": "OCG",
    "sc": "OCG",
    "ae": "OCG",
}

FALLBACK_LOCALES = {
    "en": "",
    "na": "en",
    "eu": "en",
    "au": "en",
    "oc": "en",
    "fc": "fr",
    "jp": "ja",
    "ae": "jp",
    "sp": "es",
    "kr": "ko",
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


def _parse_month(m: str) -> int:
    try:
        return datetime.datetime.strptime(m, "%B").month
    except ValueError:
        try:
            return datetime.datetime.strptime(m, "%b").month
        except ValueError:
            return int(m)


def _parse_date(value: str) -> typing.Optional[datetime.date]:
    found_date = re.search(r"(\w+)\s+(\d+),\s*(\d+)", value)
    if found_date:
        (month, day, year) = found_date.groups()
    else:
        found_date = re.search(r"(\w+)\s+(\d+)", value)
        if found_date:
            (month, year) = found_date.groups()
            day = "1"
        else:
            found_date = re.search(r"(\d\d\d\d)", value)
            if found_date:
                (year,) = found_date.groups()
                month = "1"
                day = "1"
            else:
                return None

    try:
        return datetime.date(
            month=_parse_month(month),
            day=int(day),
            year=int(year),
        )
    except ValueError:
        return None


class ImageLocator(typing.NamedTuple):
    edition: SetEdition
    altinfo: str


class PrintingLocator(typing.NamedTuple):
    card: Card
    rarity: CardRarity


class RawPrinting:
    card: Card
    code: str
    rarity: CardRarity
    image: typing.Dict[ImageLocator, str]
    qty: int
    noabbr: bool

    def __init__(
        self, card: Card, code: str, rarity: CardRarity, qty: int, noabbr: bool
    ) -> None:
        self.card = card
        self.code = code
        self.rarity = rarity
        self.image = {}
        self.qty = qty
        self.noabbr = noabbr

    def locator(self) -> PrintingLocator:
        return PrintingLocator(self.card, self.rarity)


class RawLocale:
    key: str
    format: str
    editions: typing.Set[SetEdition]
    cards: typing.Dict[PrintingLocator, RawPrinting]
    date: typing.Optional[datetime.date]
    images: typing.Dict[SetEdition, str]
    db_ids: typing.List[int]

    def __init__(self, key: str, format: str) -> None:
        self.key = key
        self.format = format
        self.editions = set()
        self.cards = {}
        self.date = None
        self.images = {}
        self.db_ids = []


FALLBACK_RARITIES = {
    CardRarity.COMMON: CardRarity.SHORTPRINT,
    CardRarity.SHORTPRINT: CardRarity.COMMON,
}


def parse_tcg_ocg_set(
    db: Database,
    batcher: "YugipediaBatcher",
    pageid: int,
    set_: Set,
    data: wikitextparser.WikiText,
    raw_data: str,
    settable: wikitextparser.Template,
    card_ids: typing.List[int],
) -> bool:
    title = batcher.idsToNames[pageid]
    set_.yugipedia = ExternalIdPair(title, pageid)

    for lc, key in LOCALES.items():
        namearg = get_table_entry(settable, lc + "_name" if lc else "name")
        if not lc and not namearg:
            namearg = title
        if namearg and namearg.strip():
            namearg = _strip_markup(namearg.strip())
            set_.name[Language.normalize(key)] = namearg

    navs = [x for x in data.templates if x.name.strip().lower() == "set navigation"]
    if len(navs) > 1:
        logging.warn(f"Found set with multiple set navigation tables: {title}")

    raw_locales: typing.Dict[str, RawLocale] = {}
    packimages: typing.Dict[str, str] = {}

    def get_card(name: str):
        class GetCardDecorator:
            def __init__(self, callback: typing.Callable[[Card], None]) -> None:
                @batcher.getPageID(name)
                def getID(cardid: int, cardname: str):
                    if cardid not in card_ids:

                        @batcher.getPageID(name + " (card)")
                        def getID(cardid: int, cardname: str):
                            card = db.cards_by_yugipedia_id.get(cardid)
                            if not card:
                                logging.warn(
                                    f"Could not find card {cardname} (card) ({cardid})"
                                )
                                return
                            callback(card)

                        return
                    card = db.cards_by_yugipedia_id.get(cardid)
                    if not card:
                        logging.warn(f"Could not find card {cardname} ({cardid})")
                        return
                    callback(card)

        return GetCardDecorator

    def addcardlist(
        setname: str, raw_locale: RawLocale, editions: typing.Set[SetEdition]
    ):
        listpagename = f"Set Card Lists:{setname} ({raw_locale.format.upper()}-{raw_locale.key.upper()})"

        @batcher.getPageContents(listpagename)
        def onGetList(raw_cardlist_data: str):
            cardlist_data = wikitextparser.parse(raw_cardlist_data)
            setlists = [
                x
                for x in cardlist_data.templates
                if x.name.lower().strip() == "set list"
            ]

            def add_card_to_cardlist(
                name: str,
                code: str,
                rarity: CardRarity,
                qty: typing.Optional[int],
                noabbr: bool,
            ):
                @get_card(name)
                def onGetCard(card: Card):
                    rc = RawPrinting(card, code, rarity, qty or 1, noabbr)
                    raw_locale.cards[rc.locator()] = rc

            for setlist in setlists:
                raw_default_rarity = get_table_entry(setlist, "rarities", "C").strip()
                if not raw_default_rarity:
                    raw_default_rarity = "C"
                raw_long_default_rarities = [
                    x.strip() for x in raw_default_rarity.split(",") if x.strip()
                ]
                raw_short_default_rarities = [
                    RAIRTY_FULL_TO_SHORT.get(x.lower(), x.lower())
                    for x in raw_long_default_rarities
                ]
                default_rarities = [
                    RARITY_STR_TO_ENUM.get(x.lower())
                    or FULL_RARITY_STR_TO_ENUM.get(x.lower())
                    for x in raw_short_default_rarities
                ]
                if not default_rarities:
                    default_rarities = [CardRarity.COMMON]
                elif not all(default_rarities):
                    logging.warn(
                        f"Could not determine default rarity of {listpagename}: {raw_default_rarity}"
                    )
                    default_rarities = [CardRarity.COMMON]
                if typing.TYPE_CHECKING:
                    default_rarities = [x for x in default_rarities if x]

                raw_default_reprint_status = get_table_entry(setlist, "print")

                raw_default_qty = get_table_entry(setlist, "qty", "").strip()
                default_qty = None
                if raw_default_qty:
                    try:
                        default_qty = int(raw_default_qty)
                    except ValueError:
                        logging.warn(
                            f"Could not determine default quantity of {listpagename}: {raw_default_qty}"
                        )

                raw_options = get_table_entry(setlist, "options", "").strip()
                noabbr = "noabbr" in raw_options.lower()

                for arg in setlist.arguments:
                    if arg.positional:
                        rows = [x.strip() for x in arg.value.split("\n") if x.strip()]
                        for row in rows:
                            comment_parts = [
                                x.strip() for x in row.split("//") if x.strip()
                            ]
                            if not comment_parts:
                                continue
                            pre_comment = comment_parts[0]
                            post_comment = " // ".join(comment_parts[1:])

                            cols = [x.strip() for x in pre_comment.split(";")]

                            if not cols:
                                continue

                            col_index = 0

                            if not noabbr:
                                code = cols[col_index]
                                col_index += 1
                            else:
                                abbr_override = re.match(r"abbr::[^\s;]+", post_comment)
                                if abbr_override:
                                    code = str(abbr_override.group(1))
                                else:
                                    code = ""

                            name = cols[col_index] if len(cols) > col_index else None
                            if not name:
                                continue
                            name = name.replace("#", "")
                            col_index += 1

                            raw_rarities = (
                                [
                                    x.strip()
                                    for x in cols[col_index].split(",")
                                    if x.strip()
                                ]
                                if len(cols) > col_index
                                else []
                            )
                            rarities: typing.List[CardRarity] = []
                            for raw_rarity in raw_rarities:
                                rarity = RARITY_STR_TO_ENUM.get(
                                    raw_rarity.lower()
                                ) or FULL_RARITY_STR_TO_ENUM.get(raw_rarity.lower())
                                if not rarity:
                                    logging.warn(
                                        f"Got strange rarity in {listpagename}, in row {name}: {raw_rarity}"
                                    )
                                else:
                                    rarities.append(rarity)
                            col_index += 1

                            if raw_default_reprint_status:
                                col_index += 1

                            qty = None
                            if default_qty is not None and len(cols) > col_index:
                                raw_qty = cols[col_index]
                                if raw_qty:
                                    try:
                                        qty = int(raw_qty)
                                    except ValueError:
                                        logging.warn(
                                            f"Got strange quantity in {listpagename}, in row {name}: {raw_qty}"
                                        )
                                col_index += 1

                            for rarity in rarities or default_rarities:
                                add_card_to_cardlist(
                                    name,
                                    code,
                                    rarity,
                                    qty if qty is not None else default_qty,
                                    noabbr,
                                )

            if not setlists:
                logging.warn(
                    f"Found set list page without set list template: {listpagename}"
                )

            batcher.flushPendingOperations()
            for edition in editions:
                get_gallery_data(setname, raw_locale, edition, raw_locale.key)

    def get_gallery_data(
        setname: str, raw_locale: RawLocale, edition: SetEdition, locale_code: str
    ):
        raw_locale.editions.add(edition)

        def do(galleryname: str):
            @batcher.getPageContents(galleryname)
            def onGetList(raw_gallery_data: str):
                gallery_data = wikitextparser.parse(raw_gallery_data)
                gallery_templates = [
                    x
                    for x in gallery_data.templates
                    if x.name.strip().lower() == "set gallery"
                ]
                subgallery_htmls = re.findall(
                    r"<gallery[^\n]*\n(.*?)\n</gallery>", raw_gallery_data, re.DOTALL
                )

                def add_card_image(name: str, rarity: CardRarity, alt: str, image: str):
                    @batcher.getImageURL(f"File:{image}")
                    def onGetImage(url: str):
                        def onGetCard(card: Card, card_rarity: CardRarity = rarity):
                            pl = PrintingLocator(card, card_rarity)
                            if pl not in raw_locale.cards:
                                if (
                                    rarity == card_rarity
                                    and card_rarity in FALLBACK_RARITIES
                                ):
                                    onGetCard(card, FALLBACK_RARITIES[card_rarity])
                                if (
                                    not alt
                                ):  # some special cards, like oversized cards, should be ignored
                                    logging.warn(
                                        f"Printing in gallery {galleryname} not found in locale: {name} / {rarity.value} -- Available in {[pl.rarity.value for pl in raw_locale.cards if pl.card == card]}"
                                    )
                            else:
                                rc = raw_locale.cards[pl]
                                rc.image[ImageLocator(edition, alt)] = url

                        @get_card(name)
                        def do(card: Card):
                            onGetCard(card)

                for gallery in gallery_templates:
                    default_abbr = get_table_entry(gallery, "abbr", "").strip()

                    raw_default_rarity = (
                        get_table_entry(gallery, "rarities", "").strip()
                        or get_table_entry(gallery, "rarity", "").strip()
                    )
                    if not raw_default_rarity:
                        raw_default_rarity = "C"
                    raw_short_default_rarity = RAIRTY_FULL_TO_SHORT.get(
                        raw_default_rarity.lower(), raw_default_rarity.lower()
                    )
                    default_rarity = RARITY_STR_TO_ENUM.get(
                        raw_short_default_rarity.lower()
                    ) or FULL_RARITY_STR_TO_ENUM.get(raw_short_default_rarity.lower())
                    if not default_rarity:
                        logging.warn(
                            f"Could not determine default rarity of {galleryname}: {raw_default_rarity}"
                        )
                        default_rarity = CardRarity.COMMON

                    default_alt = get_table_entry(gallery, "alt", "").strip()

                    for arg in gallery.arguments:
                        if arg.positional:
                            rows = [
                                x.strip() for x in arg.value.split("\n") if x.strip()
                            ]
                            for row in rows:
                                comment_parts = [
                                    x.strip() for x in row.split("//") if x.strip()
                                ]
                                if not comment_parts:
                                    continue
                                pre_comment = comment_parts[0]
                                post_comment = " // ".join(comment_parts[1:])
                                abbr_override = re.search(
                                    r"abbr::\s*([^\s;]+)", post_comment
                                )
                                file_override = re.search(
                                    r"file::\s*([^\s;]+)", post_comment
                                )
                                ext_override = re.search(
                                    r"extension::\s*([^\s;]+)", post_comment
                                )

                                cols = [x.strip() for x in pre_comment.split(";")]

                                if not cols:
                                    continue

                                col_index = 0

                                code = default_abbr if default_abbr else None
                                if not default_abbr and len(cols) > col_index:
                                    code = cols[col_index]
                                    col_index += 1
                                if abbr_override:
                                    code = str(abbr_override.group(1))

                                if len(cols) > col_index:
                                    name = cols[col_index]
                                    col_index += 1
                                else:
                                    continue

                                rarity = default_rarity
                                raw_rarity = raw_default_rarity
                                if len(cols) > col_index:
                                    raw_rarity = cols[col_index]
                                    rarity_override = RARITY_STR_TO_ENUM.get(
                                        raw_rarity.lower()
                                    ) or FULL_RARITY_STR_TO_ENUM.get(raw_rarity.lower())
                                    if rarity_override:
                                        rarity = rarity_override
                                    col_index += 1

                                alt = default_alt if default_alt else ""
                                if len(cols) > col_index:
                                    raw_alt = cols[col_index]
                                    if raw_alt:
                                        raw_alt = alt
                                    col_index += 1

                                if file_override:
                                    image = file_override.group(1)
                                else:
                                    image = re.sub(r"\W", r"", name)
                                    if code:
                                        code_before_dash = re.match(r"[^\-]+", code)
                                        if code_before_dash:
                                            image += f"-{code_before_dash.group(0)}"
                                    image += f"-{raw_locale.key.upper()}"
                                    if raw_rarity:
                                        rarity_code = RAIRTY_FULL_TO_SHORT.get(
                                            raw_rarity.lower()
                                        )
                                        if rarity_code:
                                            image += f"-{rarity_code}"
                                        else:
                                            image += f"-{raw_rarity}"
                                            logging.warn(
                                                f"Could not decipher rarity code for {name} in {galleryname}: {raw_rarity}"
                                            )
                                    ed_str = EDITIONS_IN_NAV_REVERSE[edition].upper()
                                    if "-" + ed_str in galleryname:
                                        image += f"-{ed_str}"
                                    if alt:
                                        image += f"-{alt}"
                                    if ext_override:
                                        image += f".{ext_override.group(1)}"
                                    else:
                                        image += ".png"

                                add_card_image(name, rarity, alt, image)

                for subgallery in subgallery_htmls:
                    lines = [x.strip() for x in subgallery.split("\n") if x.strip()]
                    for line in lines:
                        parsed_line = wikitextparser.parse(line)
                        if len(parsed_line.wikilinks) < 3:
                            logging.warn(
                                f"Found strange subgallery line in {galleryname}: {line}"
                            )
                        else:
                            raw_image = re.match(r"\s*([^\|\s]+)", line)
                            if raw_image:
                                image = str(raw_image.group(1))
                            else:
                                image = ""

                            (codelink, raritylink, namelink, *_) = parsed_line.wikilinks
                            rarity = RARITY_STR_TO_ENUM.get(
                                raritylink.target.strip().lower()
                            ) or FULL_RARITY_STR_TO_ENUM.get(
                                raritylink.target.strip().lower()
                            )
                            if not rarity:
                                logging.warn(
                                    f"Found strange rarity in subgallery in {galleryname}: {raritylink.target}"
                                )
                                continue
                            name = namelink.target.strip()
                            add_card_image(name, rarity, "", image)

                if not gallery_templates and not subgallery_htmls:
                    logging.warn(f"No gallery tables found in {galleryname}!")

        do(
            f"Set Card Galleries:{setname} ({raw_locale.format.upper()}-{raw_locale.key.upper()}-{EDITIONS_IN_NAV_REVERSE[edition].upper()})"
        )
        do(
            f"Set Card Galleries:{setname} ({raw_locale.format.upper()}-{raw_locale.key.upper()})"
        )

    def parse_packimage_line(line: str):
        imagename = re.match(r"\S+", line)
        if imagename:
            gallery_links = [
                link.target.strip()
                for link in wikitextparser.parse(line).wikilinks
                if link.target.strip().lower().startswith("set card galleries:")
            ]

            @batcher.getImageURL("File:" + imagename.group(0))
            def onImage(url: str):
                for gallery_link in gallery_links:
                    lc = re.search(r"\([^\-]+\-([^\)]+)\)", gallery_link)
                    if lc:
                        packimages[lc.group(1).lower()] = url

    for nav in navs:
        lists = [
            x.strip().lower()
            for x in get_table_entry(nav, "lists", "").split(",")
            if x.strip()
        ]
        galleries: typing.Dict[str, typing.List[str]] = {}
        setname = title

        for arg in nav.arguments:
            if arg.positional and arg.name == "0":
                # alternate set name
                setname = arg.value.strip()
            if arg.name.endswith("_galleries") and all(
                not arg.name.startswith(x) for x in EDITIONS_IN_NAV
            ):
                logging.warn(
                    f"Found gallery argument for unknown edition in {title}: {arg.name}"
                )

        for edition in EDITIONS_IN_NAV:
            galleries[edition] = [
                x.strip().lower()
                for x in get_table_entry(nav, f"{edition}_galleries", "").split(",")
                if x.strip()
            ]

        if not lists and not galleries:
            logging.warn(f"Found set without card lists or galleries: {title}")

        all_lcs = {lc for lc in [*lists, *[y for x in galleries.values() for y in x]]}
        for lc in all_lcs:
            if lc not in FORMATS_IN_NAV:
                logging.warn(f"Unknown locale in {title}: {lc}")
            else:
                raw_locale = RawLocale(lc, FORMATS_IN_NAV[lc])
                raw_locales[lc] = raw_locale

                db_lc = lc
                while db_lc is not None:
                    dbarg = get_table_entry(
                        settable, db_lc + DBID_SUFFIX if db_lc else DBID_SUFFIX[1:]
                    )
                    if dbarg:
                        raw_ids = [
                            x.strip()
                            for x in dbarg.replace("*", "").split("\n")
                            if x.strip()
                        ]
                        for raw_id in raw_ids:
                            try:
                                raw_locale.db_ids.append(int(raw_id))
                            except ValueError:
                                if raw_id != "none":
                                    logging.warn(
                                        f"Found bad konami ID in {title}: {raw_id}"
                                    )
                        break
                    db_lc = FALLBACK_LOCALES.get(db_lc)

                date_lc = lc
                while date_lc is not None:
                    reldatearg = get_table_entry(
                        settable,
                        date_lc + RELDATE_SUFFIX if date_lc else RELDATE_SUFFIX[1:],
                    )
                    if reldatearg:
                        raw_locale.date = _parse_date(_strip_markup(reldatearg.strip()))
                        break
                    date_lc = FALLBACK_LOCALES.get(date_lc)

                if not any(x.lower() == lc for x in lists):
                    logging.warn(
                        f"Found set navigation in {title} with gallery but no list for locale {lc}"
                    )
                    continue

                addcardlist(
                    setname,
                    raw_locale,
                    {EDITIONS_IN_NAV[ec] for ec, lcs in galleries.items() if lc in lcs},
                )

    if not navs:
        logging.warn(f"Found set without set navigation table: {title}")
        return False

    if not raw_locales:
        logging.warn(f"Found set without locales: {title}")
        return False

    packimages_html = re.search(
        r"<gallery[^\n]*\n(.*?)\n</gallery>", raw_data, re.DOTALL
    )
    if packimages_html:
        lines = [x.strip() for x in packimages_html.group(1).split("\n") if x.strip()]
        for line in lines:
            parse_packimage_line(line)

    batcher.flushPendingOperations()

    old_printing_ids = {
        PrintingLocator(p.card, p.rarity or CardRarity.COMMON): p.id
        for c in set_.contents
        for p in c.cards
    }

    set_.locales.clear()
    set_.contents.clear()

    raw_printings_to_content: typing.Dict[
        typing.Tuple[PrintingLocator, ...], SetContents
    ] = {}
    raw_printings_to_printings: typing.Dict[
        SetContents, typing.Dict[PrintingLocator, CardPrinting]
    ] = {}

    for raw_locale in raw_locales.values():
        fmt = Format(raw_locale.format.lower())

        for edition in raw_locale.editions:
            image = packimages.get(
                f"{raw_locale.key}-{EDITIONS_IN_NAV_REVERSE[edition]}"
            ) or packimages.get(raw_locale.key)
            if image:
                raw_locale.images[edition] = image

        prefix = commonprefix(c.code for c in raw_locale.cards.values())
        prefixfixer = re.match(r"[^\-]+\-\D*", prefix)
        if prefixfixer:
            prefix = prefixfixer.group(0)

        locale = SetLocale(
            key=Locale.normalize(raw_locale.key),
            language=LOCALES.get(raw_locale.key, raw_locale.key),
            editions=[*raw_locale.editions],
            formats=[fmt],
            image=[*raw_locale.images.values(), None][0],
            date=raw_locale.date,
            prefix=None
            if all(rc.noabbr for rc in raw_locale.cards.values())
            else prefix,
            db_ids=raw_locale.db_ids,
        )
        set_.locales[locale.key] = locale

        ptc_key = tuple(raw_locale.cards)
        if ptc_key in raw_printings_to_content:
            content = raw_printings_to_content[ptc_key]
            content.locales.append(locale)
            for edition in raw_locale.editions:
                if edition not in content.editions:
                    content.editions.append(edition)
            if fmt not in content.formats:
                content.formats.append(fmt)
        else:
            content = SetContents(
                locales=[locale],
                editions=[*raw_locale.editions],
                formats=[fmt],
                image=[*raw_locale.images.values(), None][0],
            )
            raw_printings_to_printings[content] = {}
            for rc in raw_locale.cards.values():
                rcl = rc.locator()
                if rcl in raw_printings_to_printings[content]:
                    logging.warn(
                        f"Found mutliple printings with the same code and rarity in the same locale in {title}: {rcl.card.text[Language.ENGLISH].name} / {rcl.rarity.value}"
                    )
                    continue
                printing = CardPrinting(
                    id=old_printing_ids[rcl]
                    if rcl in old_printing_ids
                    else uuid.uuid4(),
                    card=rc.card,
                    rarity=rc.rarity,
                    suffix=None if rc.noabbr else rc.code[len(prefix) :],
                    replica=any(il.altinfo.lower() == "rp" for il in rc.image),
                    qty=rc.qty,
                )
                raw_printings_to_printings[content][rcl] = printing
                content.cards.append(printing)

            set_.contents.append(content)

        for edition in raw_locale.editions:
            locale.card_images.setdefault(edition, {})
            for rc in raw_locale.cards.values():
                ils = [il for il in rc.image if il.edition == edition]
                if len(ils) > 1:
                    logging.warn(
                        f"Found multiple images for the same card {rc.card.text[Language.ENGLISH].name} / {rc.rarity}, in {title}: {[il.altinfo for il in ils]}"
                    )
                if ils:
                    il = ils[0]
                    locale.card_images[edition][
                        raw_printings_to_printings[content][rc.locator()]
                    ] = rc.image[il]

    return True


MD_DISAMBIG_SUFFIX = " (Master Duel)"
DL_DISAMBIG_SUFFIX = " (Duel Links)"
ARCHETYPE_DISAMBIG_SUFFIX = " (archetype)"
SERIES_DISAMBIG_SUFFIX = " (series)"


def parse_md_set(
    db: Database,
    batcher: "YugipediaBatcher",
    pageid: int,
    set_: Set,
    data: wikitextparser.WikiText,
    raw_data: str,
    settable: wikitextparser.Template,
) -> bool:
    title = batcher.idsToNames[pageid]
    set_.name[Language.ENGLISH] = (
        title[: -len(MD_DISAMBIG_SUFFIX)]
        if title.endswith(MD_DISAMBIG_SUFFIX)
        else title
    )
    set_.yugipedia = ExternalIdPair(title, pageid)

    set_.date = _parse_date(
        _strip_markup(get_table_entry(settable, "release_date", "")).strip()
    )
    if set_.contents:
        contents = set_.contents[0]
    else:
        contents = SetContents(formats=[Format.MASTERDUEL])

    found_cards: typing.Set[Card] = set()
    setlists = [
        x for x in data.templates if x.name.strip().lower() == "master duel set list"
    ]
    if not setlists:
        logging.warn(f"Found Master Duel set without setlists: {title}")
        return False

    raw_imagename = get_table_entry(settable, "image")
    if raw_imagename and raw_imagename.strip():
        raw_imagename = f"File:{raw_imagename.strip()}"
    else:
        raw_imagename = f"File:{title}-Pack-Master Duel.png"

    @batcher.getImageURL(raw_imagename)
    def onGetImage(url: str):
        contents.image = url

    for setlist in setlists:
        for arg in setlist.arguments:
            if not arg.positional:
                continue
            for row in [x.strip() for x in arg.value.split("\n") if x.strip()]:
                # first is card; second is rarity; third is (optional) quantity (in decks) or reprint status (in packs)
                parts = [x.strip() for x in row.split(";") if x.strip()]
                if not parts:
                    continue

                cardname = parts[0]
                if cardname.endswith(MD_DISAMBIG_SUFFIX):
                    cardname = cardname[: -len(MD_DISAMBIG_SUFFIX)]

                def add_card(card: Card):
                    found_cards.add(card)
                    if card not in {p.card for p in contents.cards}:
                        contents.cards.append(CardPrinting(id=uuid.uuid4(), card=card))

                def do(cardname: str):
                    @batcher.getPageID(cardname)
                    def onGetID(cardid: int, _: str):
                        card = db.cards_by_yugipedia_id.get(cardid)
                        if not card:

                            @batcher.getPageID(cardname + " (card)")
                            def onGetID(cardid: int, _: str):
                                card = db.cards_by_yugipedia_id.get(cardid)
                                if not card:
                                    logging.warn(
                                        f"Unknown card in MD set {title}: {cardname}"
                                    )
                                else:
                                    add_card(card)

                        else:
                            add_card(card)

                do(cardname)

    def deloldprints():
        for i, printing in enumerate([*contents.cards]):
            if printing.card not in found_cards:
                del contents.cards[i]
                return deloldprints()
                # if printing.card not in {p.card for p in contents.removed_cards}:
                #     contents.removed_cards.append(printing)

    deloldprints()

    if contents not in set_.contents:
        set_.contents.append(contents)

    return True


def parse_dl_set(
    db: Database,
    batcher: "YugipediaBatcher",
    pageid: int,
    set_: Set,
    data: wikitextparser.WikiText,
    raw_data: str,
    settable: wikitextparser.Template,
) -> bool:
    title = batcher.idsToNames[pageid]
    set_.name[Language.ENGLISH] = (
        title[: -len(DL_DISAMBIG_SUFFIX)]
        if title.endswith(DL_DISAMBIG_SUFFIX)
        else title
    )
    set_.yugipedia = ExternalIdPair(title, pageid)

    set_.date = _parse_date(
        _strip_markup(get_table_entry(settable, "release_date", "")).strip()
    )
    if set_.contents:
        contents = set_.contents[0]
    else:
        contents = SetContents(formats=[Format.DUELLINKS])

    found_cards: typing.Set[Card] = set()
    setlists = [x for x in data.templates if x.name.strip().lower() == "set list"]
    if not setlists:
        logging.warn(f"Found Duel Links set without setlists: {title}")
        return False

    raw_imagename = get_table_entry(settable, "image")
    if raw_imagename and raw_imagename.strip():

        @batcher.getImageURL(f"File:{raw_imagename.strip()}")
        def onGetImage(url: str):
            contents.image = url

    for setlist in setlists:
        for arg in setlist.arguments:
            if not arg.positional:
                continue
            for row in [x.strip() for x in arg.value.split("\n") if x.strip()]:
                # 1st is card; 2nd is rarity; 3rd is (optional) reprint status; 4th is (optional) quantity
                parts = [x.strip() for x in row.split(";") if x.strip()]
                if not parts:
                    continue

                cardname = parts[0]
                if cardname.endswith(DL_DISAMBIG_SUFFIX):
                    cardname = cardname[: -len(DL_DISAMBIG_SUFFIX)]

                def add_card(card: Card):
                    found_cards.add(card)
                    if card not in {p.card for p in contents.cards}:
                        contents.cards.append(CardPrinting(id=uuid.uuid4(), card=card))

                def do(cardname: str):
                    @batcher.getPageID(cardname)
                    def onGetID(cardid: int, _: str):
                        card = db.cards_by_yugipedia_id.get(cardid)
                        if not card:

                            @batcher.getPageID(cardname + " (card)")
                            def onGetID(cardid: int, _: str):
                                card = db.cards_by_yugipedia_id.get(cardid)
                                if not card:
                                    logging.warn(
                                        f"Unknown card in DL set {title}: {cardname}"
                                    )
                                else:
                                    add_card(card)

                        else:
                            add_card(card)

                do(cardname)

    def deloldprints():
        for i, printing in enumerate([*contents.cards]):
            if printing.card not in found_cards:
                del contents.cards[i]
                return deloldprints()
                # if printing.card not in {p.card for p in contents.removed_cards}:
                #     contents.removed_cards.append(printing)

    deloldprints()

    if contents not in set_.contents:
        set_.contents.append(contents)

    return True


def parse_series(
    db: Database,
    batcher: "YugipediaBatcher",
    pageid: int,
    title: str,
    series: Series,
    data: wikitextparser.WikiText,
    seriestable: wikitextparser.Template,
    series_members: typing.Dict[str, typing.Set[Card]],
) -> bool:
    name = title
    if name.endswith(ARCHETYPE_DISAMBIG_SUFFIX):
        name = title[: -len(ARCHETYPE_DISAMBIG_SUFFIX)]
    if name.endswith(SERIES_DISAMBIG_SUFFIX):
        name = title[: -len(SERIES_DISAMBIG_SUFFIX)]

    for locale, key in LOCALES.items():
        value = get_table_entry(seriestable, locale + "_name" if locale else "name")
        if not locale and not value:
            value = name
        if value and value.strip():
            value = _strip_markup(value.strip())
            series.name[Language.normalize(key)] = value

    @batcher.getPageCategories(pageid)
    def onCatsGet(cats: typing.List[int]):
        if batcher.namesToIDs.get(CAT_ARCHETYPES) in cats:
            series.archetype = True
        elif batcher.namesToIDs.get(CAT_SERIES) in cats:
            series.archetype = False

    if name.lower() in series_members:
        series.members.update(series_members[name.lower()])
    if title.lower() in series_members:
        series.members.update(series_members[title.lower()])

    series.yugipedia = ExternalIdPair(title, pageid)
    return True


class Banlist:
    format: str
    date: datetime.date
    cards: typing.Dict[str, Legality]

    def __init__(
        self,
        *,
        format: str,
        date: datetime.date,
        cards: typing.Optional[typing.Dict[str, Legality]] = None,
    ) -> None:
        self.format = format
        self.date = date
        self.cards = cards or {}


BANLIST_STR_TO_LEGALITY = {
    "unlimited": Legality.UNLIMITED,
    "no_longer_on_list": Legality.UNLIMITED,
    "no-longer-on-list": Legality.UNLIMITED,
    "semi-limited": Legality.SEMILIMITED,
    "semi_limited": Legality.SEMILIMITED,
    "limited": Legality.LIMITED,
    "forbidden": Legality.FORBIDDEN,
    # speed duel legalities
    "limited_0": Legality.FORBIDDEN,
    "limited_1": Legality.LIMIT1,
    "limited_2": Legality.LIMIT2,
    "limited_3": Legality.LIMIT3,
}


def _parse_banlist(
    batcher: "YugipediaBatcher", pageid: int, format: str, raw_data: str
) -> typing.Optional[Banlist]:
    data = wikitextparser.parse(raw_data)

    limitlists = [
        x for x in data.templates if x.name.strip().lower() == "limitation list"
    ]
    md_limitlists = [
        x
        for x in data.templates
        if x.name.strip().lower() == "master duel limitation status list"
    ]
    if not limitlists and not md_limitlists:
        if (
            format != "masterduel"
        ):  # master duel has a lot of event banlists we want to ignore
            logging.warn(
                f"Found banlist without limitlist template: {batcher.idsToNames[pageid]}"
            )
        return None

    cards: typing.Dict[str, Legality] = {}
    raw_start_date = None

    for limitlist in limitlists:
        raw_start_date = _strip_markup(
            get_table_entry(limitlist, "start_date", "")
        ).strip()

        for arg in limitlist.arguments:
            if arg.name and arg.name.strip().lower() in BANLIST_STR_TO_LEGALITY:
                legality = BANLIST_STR_TO_LEGALITY[arg.name.strip().lower()]
                cardlist = [
                    x.split("//")[0].strip() for x in arg.value.split("\n") if x.strip()
                ]
                for card in cardlist:
                    if card.lower().endswith(DL_DISAMBIG_SUFFIX):
                        card = card[: -len(DL_DISAMBIG_SUFFIX)]
                    cards[card] = legality

    for limitlist in md_limitlists:
        raw_date = get_table_entry(limitlist, "date")
        if raw_date and raw_date.strip():
            raw_start_date = _strip_markup(raw_date).strip()

        for row in [
            x.split("//")[0].strip()
            for x in get_table_entry(limitlist, "cards", "").split("\n")
            if x.strip()
        ]:
            parts = [x.strip() for x in row.split(";")]
            if len(parts) == 2:
                (name, raw_legality) = parts
            elif len(parts) == 3:
                (name, _, raw_legality) = parts
            else:
                logging.warn(
                    f"Unparsable master duel banlist row in {batcher.idsToNames[pageid]}: {row}"
                )
                continue

            if raw_legality.lower() not in BANLIST_STR_TO_LEGALITY:
                logging.warn(
                    f"Unknown legality in master duel banlist row in {batcher.idsToNames[pageid]}: {raw_legality}"
                )
                continue

            cards[name] = BANLIST_STR_TO_LEGALITY[raw_legality.lower()]

    start_date = _parse_date(raw_start_date or "")
    if not start_date:
        logging.warn(
            f"Found invalid start date of {batcher.idsToNames[pageid]}: {raw_start_date}"
        )
        return None

    return Banlist(format=format, date=start_date, cards=cards)


def get_banlist_pages(
    batcher: "YugipediaBatcher",
) -> typing.Dict[str, typing.List[Banlist]]:
    with tqdm.tqdm(
        total=len(BANLIST_CATS), desc="Fetching Yugipedia banlists"
    ) as progress_bar:
        result: typing.Dict[str, typing.List["Banlist"]] = {}

        for format, catname in BANLIST_CATS.items():

            def do(format: str, catname: str):
                @batcher.getCategoryMembers(catname)
                def onGetBanlistCat(members: typing.List[int]):
                    for member in members:

                        def do(member: int):
                            @batcher.getPageID(member)
                            def onGetID(_pageid: int, _title: str):
                                @batcher.getPageContents(member)
                                def onGetContents(raw_data: str):
                                    banlist = _parse_banlist(
                                        batcher, member, format, raw_data
                                    )
                                    if banlist:
                                        result.setdefault(format, [])
                                        result[format].append(banlist)

                        do(member)
                    progress_bar.update(1)

            do(format, catname)

        batcher.flushPendingOperations()
        for format, banlists in result.items():
            banlists.sort(key=lambda b: b.date)
            running_totals: typing.Dict[str, Legality] = {}
            for banlist in banlists:
                for card, legality in {**banlist.cards}.items():
                    if card in running_totals and running_totals[card] == legality:
                        del banlist.cards[card]
                    else:
                        running_totals[card] = legality

        return result


def import_from_yugipedia(
    db: Database,
    *,
    import_cards: bool = True,
    import_sets: bool = True,
    import_series: bool = True,
    production: bool = False,
) -> typing.Tuple[int, int]:
    n_found = n_new = 0

    with YugipediaBatcher() as batcher:
        atexit.register(
            lambda: batcher.saveCachesToDisk()
        )  # to ensure we never lose cache data

        last_access = db.last_yugipedia_read
        db.last_yugipedia_read = (
            datetime.datetime.now()
        )  # a conservative estimate of when we accessed, so we don't miss new changelog entries

        if last_access is not None:
            if (
                production
                and datetime.datetime.now().timestamp() - last_access.timestamp()
                > TIME_TO_JUST_REDOWNLOAD_ALL_PAGES
            ):
                # fetching the changelog would take too long; just blow up the cache
                batcher.clearCache()
            else:
                # clear the cache of any changed pages
                _ = [*get_changelog(batcher, last_access)]

        series_members: typing.Dict[str, typing.Set[Card]] = {}

        cards = []
        if import_cards:
            banlists = get_banlist_pages(batcher)
            cards = [*get_card_pages(batcher)]

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
                            if (
                                ct == "counter"
                                or batcher.namesToIDs.get(CAT_TOKENS) in categories
                            ):
                                ct = "token"
                            if batcher.namesToIDs.get(CAT_SKILLS) in categories:
                                ct = "skill"
                            if ct not in CardType._value2member_map_:
                                logging.warn(f"Found card with illegal card type: {ct}")
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
                            if not card and batcher.idsToNames[pageid] != "Token":
                                # find by english name except for Token, which has a lot of cards called exactly that
                                card = db.cards_by_en_name.get(
                                    batcher.idsToNames[pageid]
                                )
                            if not card:
                                card = Card(id=uuid.uuid4(), card_type=CardType(ct))

                            if parse_card(
                                batcher,
                                pageid,
                                card,
                                data,
                                categories,
                                banlists,
                                series_members,
                            ):
                                db.add_card(card)
                                if found:
                                    n_found += 1
                                else:
                                    n_new += 1

                do(pageid)

            batcher.saveCachesToDisk()

        if import_sets:
            sets = [*get_set_pages(batcher)]

            for setid in tqdm.tqdm(sets, desc="Importing sets from Yugipedia"):

                def do(pageid: int):
                    @batcher.getPageContents(pageid)
                    def onGetData(raw_data: str):
                        nonlocal n_found, n_new, cards

                        data = wikitextparser.parse(raw_data)

                        settables = [
                            x
                            for x in data.templates
                            if x.name.strip().lower() == "infobox set"
                        ]
                        for settable in settables:

                            def do(settable: wikitextparser.Template):
                                nonlocal cards

                                found = True
                                set_ = db.sets_by_yugipedia_id.get(pageid)
                                if not set_:
                                    for arg in settable.arguments:
                                        if arg.name and arg.name.strip().endswith(
                                            DBID_SUFFIX
                                        ):
                                            db_ids = [
                                                x.strip()
                                                for x in arg.value.replace(
                                                    "*", ""
                                                ).split("\n")
                                                if x.strip()
                                            ]
                                            try:
                                                for db_id in db_ids:
                                                    set_ = db.sets_by_konami_sid.get(
                                                        int(db_id)
                                                    )
                                                    if set_:
                                                        break
                                            except ValueError:
                                                if arg.value.strip() != "none":
                                                    logging.warn(
                                                        f'Unparsable konami set ID for {arg.name} in {batcher.idsToNames.get(pageid, pageid)}: "{arg.value}"'
                                                    )
                                if not set_:
                                    set_ = db.sets_by_en_name.get(
                                        get_table_entry(settable, "en_name", "")
                                    )
                                if not set_:
                                    set_ = Set(id=uuid.uuid4())
                                    found = False

                                cards = cards or [*get_card_pages(batcher)]

                                @batcher.getPageID(pageid)
                                def onGetID(pageid: int, title: str):
                                    nonlocal n_found, n_new

                                    if parse_tcg_ocg_set(
                                        db,
                                        batcher,
                                        pageid,
                                        set_,
                                        data,
                                        raw_data,
                                        settable,
                                        cards,
                                    ):
                                        db.add_set(set_)
                                        if found:
                                            n_found += 1
                                        else:
                                            n_new += 1

                            do(settable)

                        md_settables = [
                            x
                            for x in data.templates
                            if x.name.strip().lower() == "infobox master duel set"
                        ]
                        for md_settable in md_settables:

                            @batcher.getPageID(pageid)
                            def onGetName(pageid: int, title: str):
                                found = True
                                set_ = db.sets_by_yugipedia_id.get(pageid)
                                if not set_:
                                    set_ = Set(id=uuid.uuid4())
                                    found = False

                                if parse_md_set(
                                    db,
                                    batcher,
                                    pageid,
                                    set_,
                                    data,
                                    raw_data,
                                    md_settable,
                                ):
                                    nonlocal n_found, n_new
                                    db.add_set(set_)
                                    if found:
                                        n_found += 1
                                    else:
                                        n_new += 1

                        dl_settables = [
                            x
                            for x in data.templates
                            if x.name.strip().lower() == "infobox duel links set"
                        ]
                        for dl_settable in dl_settables:

                            @batcher.getPageID(pageid)
                            def onGetName(pageid: int, title: str):
                                found = True
                                set_ = db.sets_by_yugipedia_id.get(pageid)
                                if not set_:
                                    set_ = Set(id=uuid.uuid4())
                                    found = False

                                if parse_dl_set(
                                    db,
                                    batcher,
                                    pageid,
                                    set_,
                                    data,
                                    raw_data,
                                    dl_settable,
                                ):
                                    nonlocal n_found, n_new
                                    db.add_set(set_)
                                    if found:
                                        n_found += 1
                                    else:
                                        n_new += 1

                        if not settables and not md_settables and not dl_settables:

                            @batcher.getPageID(pageid)
                            def onGetName(pageid: int, title: str):
                                logging.warn(f"Found set without set table: {title}")

                            return

                do(setid)

            batcher.saveCachesToDisk()

        if import_series:
            series = [*get_series_pages(batcher)]

            for seriesid in tqdm.tqdm(series, desc="Importing series from Yugipedia"):

                def do(pageid: int):
                    @batcher.getPageContents(pageid)
                    def onGetData(raw_data: str):
                        nonlocal n_found, n_new

                        title = batcher.idsToNames[pageid]
                        data = wikitextparser.parse(raw_data)

                        seriestables = [
                            x
                            for x in data.templates
                            if x.name.strip().lower()
                            in {
                                "infobox archseries",
                                "infobox archetype",
                                "infobox series",
                            }
                        ]
                        for seriestable in seriestables:
                            series = db.series_by_yugipedia_id.get(pageid)
                            found = True
                            if not series and title.endswith(ARCHETYPE_DISAMBIG_SUFFIX):
                                series = db.series_by_en_name.get(
                                    title[: -len(ARCHETYPE_DISAMBIG_SUFFIX)]
                                )
                            if not series and title.endswith(SERIES_DISAMBIG_SUFFIX):
                                series = db.series_by_en_name.get(
                                    title[: -len(SERIES_DISAMBIG_SUFFIX)]
                                )
                            if not series:
                                series = db.series_by_en_name.get(title)
                            if not series:
                                series = Series(id=uuid.uuid4())
                                found = False

                            if parse_series(
                                db,
                                batcher,
                                pageid,
                                title,
                                series,
                                data,
                                seriestable,
                                series_members,
                            ):
                                db.add_series(series)
                                if found:
                                    n_found += 1
                                else:
                                    n_new += 1

                        if not seriestables:
                            logging.warn(
                                f"Found series without series table: {batcher.idsToNames[pageid]}"
                            )
                            return

                do(seriesid)

    return n_found, n_new


BATCH_MAX = 50

PAGES_FILENAME = "yugipedia_pages.json"
CONTENTS_FILENAME = "yugipedia_contents.json"
NAMESPACES = {"mw": "http://www.mediawiki.org/xml/export-0.10/"}
IMAGE_URLS_FILENAME = "yugipedia_images.json"
CAT_MEMBERS_FILENAME = "yugipedia_members.json"
PAGE_CATS_FILENAME = "yugipedia_categories.json"
MISSING_PAGES_FILENAME = "yugipedia_missing.json"


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
    missingPagesCache: typing.Set[str]

    def __init__(self) -> None:
        self.namesToIDs = {}
        self.idsToNames = {}
        self.use_cache = True
        self.missingPagesCache = set()

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

        path = os.path.join(TEMP_DIR, MISSING_PAGES_FILENAME)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                self.missingPagesCache = {v for v in json.load(file)}

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

    def removeFromCache(self, page: typing.Union[int, str]):
        def del_(cache, page):
            if page in cache:
                del cache[page]

        pageid = title = None
        if type(page) is int:
            pageid = page
            title = self.idsToNames.get(page)
        elif type(page) is str:
            title = page
            pageid = self.namesToIDs.get(page)

        if title:
            if title in self.missingPagesCache:
                self.missingPagesCache.remove(title)
            del_(self.namesToIDs, title)
        if pageid:
            if str(pageid) in self.missingPagesCache:
                self.missingPagesCache.remove(str(pageid))
            del_(self.idsToNames, pageid)
            del_(self.pageContentsCache, pageid)
            del_(self.pageCategoriesCache, pageid)
            del_(self.imagesCache, pageid)
            del_(self.categoryMembersCache, pageid)

    def saveCachesToDisk(self):
        path = os.path.join(TEMP_DIR, PAGES_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                [{"id": k, "name": v} for k, v in self.idsToNames.items()],
                file,
                indent=2,
            )

        path = os.path.join(TEMP_DIR, MISSING_PAGES_FILENAME)
        with open(path, "w", encoding="utf-8") as file:
            json.dump([v for v in self.missingPagesCache], file, indent=2)

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

    def operationsPending(self) -> bool:
        return bool(
            self.pendingGetPageContents
            or self.pendingGetPageCategories
            or self.pendingImages
            or self.pendingGetPageID
        )

    def flushPendingOperations(self):
        while self.operationsPending():
            self._executeGetContentsBatch()
            self._executeGetCategoriesBatch()
            self._executeGetImageURLBatch()
            self._executeGetPageIDBatch()

    def clearCache(self):
        self.categoryMembersCache.clear()
        self.pageCategoriesCache.clear()
        self.pageContentsCache.clear()
        self.imagesCache.clear()
        self.missingPagesCache.clear()

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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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

        for p in pages:
            page = p if type(p) is int else self.namesToIDs.get(str(p))
            if page not in self.pageContentsCache:
                self.missingPagesCache.add(str(p))
                self.missingPagesCache.add(str(page))

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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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
                "prop": "categories",
                **({"pageids": "|".join(pageids)} if pageids else {}),
                **({"titles": "|".join(pagetitles)} if pagetitles else {}),
            }

            cats_got: typing.Dict[int, typing.List[int]] = {}

            for result_page in paginate_query(query):
                for result in result_page["pages"]:
                    if result.get("missing") or result.get("invalid"):
                        self.missingPagesCache.add(
                            str(result.get("title") or result.get("pageid") or "")
                        )
                        continue

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
                if result.get("missing") or result.get("invalid"):
                    self.missingPagesCache.add(
                        str(result.get("title") or result.get("pageid") or "")
                    )
                    continue
                pageid = result["pageid"]
                self.categoryMembersCache[result["pageid"]] = members
                self.namesToIDs[result["title"]] = result["pageid"]
                self.idsToNames[result["pageid"]] = result["title"]
            for result in results["categorymembers"]:
                if result.get("missing") or result.get("invalid"):
                    self.missingPagesCache.add(
                        str(result.get("title") or result.get("pageid") or "")
                    )
                    continue
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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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
                        self.missingPagesCache.add(
                            str(result.get("title") or result.get("pageid") or "")
                        )
                        continue

                    title = result["title"]
                    pageid = result["pageid"]

                    self.namesToIDs[title] = pageid
                    self.idsToNames[pageid] = title

                    if "imageinfo" not in result:
                        # this happens if an image metadata exists but no actual file with a URL; ignore it
                        # logging.warn(f"Page is not an image file: {title}")
                        self.missingPagesCache.add(title)
                        self.missingPagesCache.add(str(pageid))
                        continue

                    for image in result["imageinfo"]:
                        if result.get("filemissing"):
                            # We can't download licensed images.
                            # This is their (bad) way of telling us that.
                            self.missingPagesCache.add(title)
                            self.missingPagesCache.add(str(pageid))
                            # logging.warn(f"Image file cannot be accessed: {title}")
                            continue
                        if "url" not in image:
                            logging.warn(
                                f"Found strange response from server for image URL: {json.dumps(image)}"
                            )
                            continue
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
                if batcher.use_cache and str(page) in batcher.missingPagesCache:
                    return

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
            redirects: typing.Dict[str, str] = {}
            for result_page in paginate_query(query):
                for redirect in result_page.get("redirects", []):
                    redirects[redirect["from"]] = redirect["to"]

                for result in result_page["pages"]:
                    if result.get("missing") or result.get("invalid"):
                        self.missingPagesCache.add(
                            str(result.get("title") or result.get("pageid") or "")
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
            for from_, to_ in redirects.items():
                if to_ in self.namesToIDs:
                    pageid = self.namesToIDs[to_]

                    self.namesToIDs[from_] = pageid

                    for callback in pending.get(from_, []):
                        callback(pageid, to_)
                else:
                    self.missingPagesCache.add(from_)

        do([p for p in pages if type(p) is int])
        do([p for p in pages if type(p) is str])
