# Import data from Yugipedia (https://yugipedia.com).
import datetime
import json
import os.path
import re
import time
import typing
import uuid
import xml.etree.ElementTree

import requests
import wikitextparser

from ..database import *

API_URL = "https://yugipedia.com/api.php"
RATE_LIMIT = 1.1

CACHED_DATA_FILENAME = "yugipedia_data.json"
CARDS_FILENAME = "yugipedia_cards.json"
TOKENS_FILENAME = "yugipedia_tokens.json"

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

    # print(f"Making request: {json.dumps(params)}")
    response = requests.get(
        API_URL,
        params=params,
        headers={
            "User-Agent": f"YGOJSON/{SCHEMA_VERSION} (https://github.com/iconmaster5326/YGOJSON)"
        },
    )
    if not response.ok:
        response.raise_for_status()
    # print(f"Got response: {response.text}")
    return response


class WikiPage:
    id: int
    name: str
    data: typing.Optional[str]

    def __init__(self, id: int, name: str, data: typing.Optional[str] = None) -> None:
        self.id = id
        self.name = name
        self.data = data


EXPORT_MAX = 50

NAMESPACES = {"mw": "http://www.mediawiki.org/xml/export-0.10/"}


def export_pages(pages: typing.Iterable[WikiPage]) -> typing.Iterable[WikiPage]:
    page_lookup = {str(p.id): p for p in pages}
    query = {
        "action": "query",
        "redirects": "1",
        "export": 1,
        "exportnowrap": 1,
        "pageids": "|".join(str(p.id) for p in pages),
    }
    response_text = make_request(query).text
    pages_xml = xml.etree.ElementTree.fromstring(response_text)
    n_pages = 0
    for page_xml in pages_xml.findall("mw:page", NAMESPACES):
        n_pages += 1
        page = page_lookup[str(int(page_xml.find("mw:id", NAMESPACES).text))]
        page.data = (
            page_xml.find("mw:revision", NAMESPACES).find("mw:text", NAMESPACES).text
        )
        yield page
    if len(page_lookup) != n_pages:
        print(
            f"warning: exported {len(page_lookup)} pages, but only got {n_pages} results!"
        )


def get_page_data(
    pages: typing.Iterable[WikiPage], redownload_old_data: bool = False
) -> typing.Iterable[WikiPage]:
    path = os.path.join(TEMP_DIR, CACHED_DATA_FILENAME)
    cached_data = {}

    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            cached_data = json.load(file)

    try:
        queued_for_export = []

        def export() -> typing.Iterable[WikiPage]:
            for pageToYield in export_pages(queued_for_export):
                if pageToYield.data:
                    cached_data[str(pageToYield.id)] = pageToYield.data
                yield pageToYield
            queued_for_export.clear()

        for page in pages:
            if not redownload_old_data and str(page.id) in cached_data:
                page.data = cached_data[str(page.id)]
                yield page
            else:
                queued_for_export.append(page)
                if len(queued_for_export) >= EXPORT_MAX:
                    for x in export():
                        yield x
        if len(queued_for_export) > 0:
            for x in export():
                yield x
    finally:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(cached_data, file, indent=2)


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


def get_cateogry_members(page: typing.Union[str, int]) -> typing.Iterable[WikiPage]:
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
        "cmlimit": "max",
        "cmtype": "page",
    }

    for results in paginate_query(query):
        for result in results["categorymembers"]:
            yield WikiPage(result["pageid"], result["title"])


def get_subcategories(page: typing.Union[str, int]) -> typing.Iterable[WikiPage]:
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
        "cmlimit": "max",
        "cmtype": "subcat",
    }

    for results in paginate_query(query):
        for result in results["categorymembers"]:
            yield WikiPage(result["pageid"], result["title"])


def get_cateogry_members_recursive(
    page: typing.Union[str, int]
) -> typing.Iterable[WikiPage]:
    for x in get_cateogry_members(page):
        yield x
    for x in get_subcategories(page):
        for y in get_cateogry_members_recursive(x.id):
            yield y


CAT_TCG_CARDS = "Category:TCG cards"
CAT_OCG_CARDS = "Category:OCG cards"
CAT_TOKENS = "Category:Tokens"


def get_token_ids() -> typing.Set[int]:
    path = os.path.join(TEMP_DIR, TOKENS_FILENAME)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            return {x for x in json.load(file)}

    seen = set()
    for page in get_cateogry_members(CAT_TOKENS):
        seen.add(page.id)

    with open(path, "w", encoding="utf-8") as file:
        json.dump([x for x in seen], file, indent=2)

    return seen


def get_card_pages() -> typing.Iterable[WikiPage]:
    path = os.path.join(TEMP_DIR, CARDS_FILENAME)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            for page in json.load(file):
                yield WikiPage(page["id"], page["name"])
        return

    result = []
    seen = set()
    for page in get_cateogry_members(CAT_TCG_CARDS):
        if page.id not in seen:
            result.append(page)
            seen.add(page.id)
            yield page
    for page in get_cateogry_members(CAT_OCG_CARDS):
        if page.id not in seen:
            result.append(page)
            seen.add(page.id)
            yield page

    with open(path, "w", encoding="utf-8") as file:
        json.dump([{"id": x.id, "name": x.name} for x in result], file, indent=2)


# def get_set_pages() -> typing.Iterable[WikiPage]:
#     seen = set()
#     for x in get_cateogry_members_recursive("Category:OCG sets"):
#         yield x
#         seen.add(x.id)
#     for x in get_cateogry_members_recursive("Category:TCG sets"):
#         if x.id not in seen:
#             yield x
#             seen.add(x.id)


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
    cards: typing.Iterable[WikiPage], changelog: typing.Iterable[ChangelogEntry]
) -> typing.Tuple[typing.Iterable[WikiPage], typing.Iterable[int]]:
    """
    Finds recent changes.
    Returns a tuple: 1st element is new or changed cards, 2nd is new tokens.
    """
    changed_cards: typing.List[WikiPage] = []

    card_ids = {x.id for x in cards}
    pages_to_catcheck: typing.List[ChangelogEntry] = []
    for change in changelog:
        if change.id in card_ids:
            changed_cards.append(change)
        elif change.type == ChangeType.CATEGORIZE or change.type == ChangeType.NEW:
            pages_to_catcheck.append(change)

    new_cards: typing.List[WikiPage] = changed_cards
    new_tokens: typing.List[int] = []
    batch: typing.List[ChangelogEntry] = []

    def get_cats():
        for pages in paginate_query(
            {
                "action": "query",
                "prop": "categories",
                "pageids": "|".join(str(x.id) for x in batch),
                "redirects": "1",
            }
        ):
            for page in pages["pages"]:
                if "categories" in page and any(
                    x["title"] == CAT_OCG_CARDS or x["title"] == CAT_TCG_CARDS
                    for x in page["categories"]
                ):
                    new_cards.append(WikiPage(page["pageid"], page["title"]))
                if "categories" in page and any(
                    x["title"] == CAT_TOKENS for x in page["categories"]
                ):
                    new_tokens.append(page["pageid"])
        batch.clear()

    for page in pages_to_catcheck:
        batch.append(page)
        if len(batch) >= EXPORT_MAX:
            get_cats()
    if len(batch) > 0:
        get_cats()

    path = os.path.join(TEMP_DIR, CARDS_FILENAME)
    with open(path, encoding="utf-8") as file:
        cards_json = json.load(file)
    for c in new_cards:
        if c.id not in card_ids:
            # print(f"changelog: new card: {c.name}")
            cards_json.append({"id": c.id, "name": c.name})
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cards_json, file)

    path = os.path.join(TEMP_DIR, TOKENS_FILENAME)
    with open(path, encoding="utf-8") as file:
        tokens_json = json.load(file)
    for t in new_tokens:
        if t not in tokens_json:
            # print(f"changelog: new token: {t}")
            tokens_json.append(t)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(tokens_json, file)

    return new_cards, new_tokens


T = typing.TypeVar("T")


def get_cardtable2_entry(
    cardtable2: wikitextparser.Template, key: str, default: T = None
) -> typing.Union[str, T]:
    try:
        arg = next(iter([x for x in cardtable2.arguments if x.name.strip() == key]))
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


def parse_card(
    page: WikiPage,
    card: Card,
    data: wikitextparser.WikiText,
    token_ids: typing.Set[int],
) -> bool:
    """
    Parse a card from a wiki page. Returns False if this is not actually a valid card
    for the database, and True otherwise.
    """

    if page.id in token_ids:
        # print(f"warning: skipping card in tokens cateogry: {page.name}")
        return False

    cardtable = next(
        iter([x for x in data.templates if x.name.strip() == "CardTable2"])
    )

    for locale, key in LOCALES.items():
        value = get_cardtable2_entry(cardtable, locale + "_name" if locale else "name")
        if not locale and not value:
            value = page.name
        if value and value.strip():
            value = value.strip()
            card.text.setdefault(key, CardText(name=value))
            card.text[key].name = value
        value = get_cardtable2_entry(cardtable, locale + "_lore" if locale else "lore")
        if value and value.strip():
            if key not in card.text:
                # print(f"warning: card has no name in {key} but has effect: {page.name}")
                pass
            else:
                card.text[key].effect = value.strip()
        value = get_cardtable2_entry(
            cardtable, locale + "_pendulum_effect" if locale else "pendulum_effect"
        )
        if value and value.strip():
            if key not in card.text:
                # print(f"warning: card has no name in {key} but has pend. effect: {page.name}")
                pass
            else:
                card.text[key].pendulum_effect = value.strip()
        if any(
            (t.name.strip() == "Unofficial name" or t.name.strip() == "Unofficial lore")
            and LOCALES_FULL.get(t.arguments[0].value.strip()) == key
            for t in data.templates
        ):
            if key not in card.text:
                # print(f"warning: card has no name in {key} but is unofficial: {page.name}")
                pass
            else:
                card.text[key].official = False

    if card.card_type == CardType.MONSTER:
        typeline = get_cardtable2_entry(cardtable, "types")
        if not typeline:
            print(f"warning: monster has no typeline: {page.name}")
            return False
        if "Skill" in typeline:
            # print(f"warning: skipping skill card: {page.name}")
            return False
        if "Token" in typeline:
            # print(f"warning: skipping token card: {page.name}")
            return False

        value = get_cardtable2_entry(cardtable, "attribute")
        if not value:
            print(f"warning: monster has no attribute: {page.name}")
            return False
        if value.strip().lower() not in Attribute._value2member_map_:
            print(f"warning: unknown attribute '{value.strip()}' in {page.name}")
            return False
        card.attribute = Attribute(value.strip().lower())

        typeline = [x.strip() for x in typeline.split("/")]
        for x in typeline:
            if (
                x not in MONSTER_CARD_TYPES
                and x not in TYPES
                and x not in CLASSIFICATIONS
                and x not in ABILITIES
            ):
                print(f"warning: monster typeline bit unknown in {page.name}: {x}")
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
        if not card.type:
            print(f"warning: monster has no type: {page.name}")
            return False

        value = get_cardtable2_entry(cardtable, "level")
        if value:
            try:
                card.level = int(value)
            except ValueError:
                print(f"warning: unknown level '{value.strip()}' in {page.name}")
                return False

        value = get_cardtable2_entry(cardtable, "rank")
        if value:
            try:
                card.rank = int(value)
            except ValueError:
                print(f"warning: unknown rank '{value.strip()}' in {page.name}")
                return False

        value = get_cardtable2_entry(cardtable, "atk")
        if value:
            try:
                card.atk = "?" if value.strip() == "?" else int(value)
            except ValueError:
                print(f"warning: unknown ATK '{value.strip()}' in {page.name}")
                return False
        value = get_cardtable2_entry(cardtable, "def")
        if value:
            try:
                card.def_ = "?" if value.strip() == "?" else int(value)
            except ValueError:
                print(f"warning: unknown DEF '{value.strip()}' in {page.name}")
                return False

        value = get_cardtable2_entry(cardtable, "pendulum_scale")
        if value:
            try:
                card.scale = int(value)
            except ValueError:
                print(f"warning: unknown scale '{value.strip()}' in {page.name}")
                return False

        value = get_cardtable2_entry(cardtable, "link_arrows")
        if value:
            card.link_arrows = [
                LinkArrow(x.lower().replace("-", "").strip()) for x in value.split(",")
            ]
    elif card.card_type == CardType.SPELL or card.card_type == CardType.TRAP:
        value = get_cardtable2_entry(cardtable, "property")
        if not value:
            print(f"warning: spelltrap has no subcategory: {page.name}")
            return False
        card.subcategory = SubCategory(value.lower().replace("-", "").strip())

    value = get_cardtable2_entry(cardtable, "password")
    if value:
        vmatch = re.match(r"^\d+", value.strip())
        if vmatch and value.strip() not in card.passwords:
            card.passwords.append(value.strip())
        if not vmatch and value.strip() and value.strip() != "none":
            print(f"warning: bad password '{value.strip()}' in card {page.name}")

    # TODO: images, sets, legality, video games

    if not card.yugipedia_pages:
        card.yugipedia_pages = []
    for existing_page in card.yugipedia_pages or []:
        if not existing_page.name and existing_page.id == page.id:
            existing_page.name = page.name
        elif not existing_page.id and existing_page.name == page.name:
            existing_page.id = page.id
    if not any(x.id == page.id for x in card.yugipedia_pages):
        card.yugipedia_pages.append(YugipediaPage(page.name, page.id))

    value = get_cardtable2_entry(cardtable, "database_id", "")
    vmatch = re.match(r"^\d+", value.strip())
    if vmatch:
        card.db_id = int(vmatch.group(0))
    # TODO: other ids

    # TODO: errata, series

    return True


def import_from_yugipedia(
    db: Database,
    *,
    progress_monitor: typing.Optional[typing.Callable[[Card, bool], None]] = None,
) -> typing.Tuple[int, int]:
    # db.last_yugipedia_read = None  # DEBUG
    if db.last_yugipedia_read:
        cards = [
            x
            for x in get_changes(
                get_card_pages(), get_changelog(db.last_yugipedia_read)
            )[0]
        ]
    else:
        cards = [x for x in get_card_pages()]

    n_found = n_new = 0
    token_ids = get_token_ids()

    for page in get_page_data(cards, db.last_yugipedia_read is not None):
        data = wikitextparser.parse(page.data or "")
        try:
            cardtable = next(
                iter([x for x in data.templates if x.name.strip() == "CardTable2"])
            )
        except StopIteration:
            print(f"warning: found card without card table: {page.name}")
            continue

        ct = get_cardtable2_entry(cardtable, "card_type", "monster").strip().lower()
        if ct not in [x.value for x in CardType]:
            # print(f"warning: found card with illegal card type: {ct}")
            continue

        found = page.id in db.cards_by_yugipedia_id
        card = db.cards_by_yugipedia_id.get(page.id) or Card(
            id=uuid.uuid4(), card_type=CardType(ct)
        )

        if parse_card(page, card, data, token_ids):
            db.add_card(card)
            if found:
                n_found += 1
            else:
                n_new += 1

            if progress_monitor:
                progress_monitor(card, found)

    db.last_yugipedia_read = datetime.datetime.now()
    return n_found, n_new
