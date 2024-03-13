# Import data from Yugipedia (https://yugipedia.com).
import datetime
import json
import os.path
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


def get_cards_changed(
    cards: typing.Iterable[WikiPage], changelog: typing.Iterable[ChangelogEntry]
) -> typing.Iterable[WikiPage]:
    card_ids = {x.id for x in cards}
    new_cards = []
    for change in changelog:
        if change.id in card_ids:
            yield change
        elif change.type == ChangeType.CATEGORIZE or change.type == ChangeType.NEW:
            new_cards.append(change)
    for card_w_data in get_page_data(new_cards, True):
        if CAT_TCG_CARDS in card_w_data.data or CAT_OCG_CARDS in card_w_data.data:
            yield card_w_data


T = typing.TypeVar("T")


def get_cardtable2_entry(
    cardtable2: wikitextparser.Template, key: str, default: T = None
) -> typing.Union[str, T]:
    try:
        arg = next(iter([x for x in cardtable2.arguments if x.name.strip() == key]))
        return arg.value
    except StopIteration:
        return default


def parse_card(card: Card, data: wikitextparser.WikiText) -> bool:
    """
    Parse a card from a wiki page. Returns False if this is not actually a valid card
    for the database, and True otherwise.
    """
    cardtable = next(
        iter([x for x in data.templates if x.name.strip() == "CardTable2"])
    )
    return False


def import_from_yugipedia(
    db: Database,
    *,
    progress_monitor: typing.Optional[typing.Callable[[Card, bool], None]] = None,
) -> typing.Tuple[int, int]:
    # db.last_yugipedia_read = None # DEBUG
    if db.last_yugipedia_read:
        cards = [
            x
            for x in get_cards_changed(
                get_card_pages(), get_changelog(db.last_yugipedia_read)
            )
        ]
    else:
        cards = [x for x in get_card_pages()]

    n_found = n_new = 0
    for page in get_page_data(cards):
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

        if parse_card(card, data):
            db.add_card(card)
            if found:
                n_found += 1
            else:
                n_new += 1

        if progress_monitor:
            progress_monitor(card, found)

    db.last_yugipedia_read = datetime.datetime.now()
    return n_found, n_new
