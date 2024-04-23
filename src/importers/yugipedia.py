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

    # print(f"Making request: {json.dumps(params)}")
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
    # print(f"Got response: {response.text}")
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


def get_token_ids(batcher: "YugipediaBatcher") -> typing.Set[int]:
    seen = set()

    @batcher.getCategoryMembers(CAT_TOKENS)
    def catMem(members: typing.List[int]):
        seen.update(members)

    return seen


def get_card_pages(batcher: "YugipediaBatcher") -> typing.Iterable[int]:
    result = []
    seen = set()

    @batcher.getCategoryMembers(CAT_TCG_CARDS)
    def catMem1(members: typing.List[int]):
        result.extend([x for x in members if x not in seen])
        seen.update(members)

    @batcher.getCategoryMembers(CAT_OCG_CARDS)
    def catMem2(members: typing.List[int]):
        result.extend([x for x in members if x not in seen])
        seen.update(members)

    return result


def get_set_pages(batcher: "YugipediaBatcher") -> typing.Iterable[int]:
    result = []
    seen = set()

    @batcher.getCategoryMembersRecursive(CAT_TCG_SETS)
    def catMem1(members: typing.List[int]):
        result.extend([x for x in members if x not in seen])
        seen.update(members)

    @batcher.getCategoryMembersRecursive(CAT_OCG_SETS)
    def catMem2(members: typing.List[int]):
        result.extend([x for x in members if x not in seen])
        seen.update(members)

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
    cards: typing.Iterable[int],
    changelog: typing.Iterable[ChangelogEntry],
) -> typing.Tuple[typing.Iterable[WikiPage], typing.Iterable[int]]:
    """
    Finds recent changes.
    Returns a tuple: 1st element is new or changed cards, 2nd is new tokens.
    """
    changed_cards: typing.List[WikiPage] = []

    card_ids = set(cards)
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
                # TODO: move this into the batcher
                batcher.namesToIDs[page["title"]] = page["pageid"]
                batcher.idsToNames[page["pageid"]] = page["title"]

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
        if len(batch) >= BATCH_MAX:
            get_cats()
    if len(batch) > 0:
        get_cats()

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


def _strip_markup(s: str) -> str:
    return "\n".join(wikitextparser.remove_markup(x) for x in s.split("\n"))


def _get_image_urls(filenames: typing.Iterable[str]) -> typing.Iterable[str]:
    for response in paginate_query(
        {
            "action": "query",
            "prop": "imageinfo",
            "titles": "|".join(f"File:{filename}" for filename in filenames),
            "iiprop": "url",
        }
    ):
        for info in response["pages"]:
            yield info["imageinfo"][0]["url"]


def parse_card(
    batcher: "YugipediaBatcher",
    page: int,
    card: Card,
    data: wikitextparser.WikiText,
    token_ids: typing.Set[int],
) -> bool:
    """
    Parse a card from a wiki page. Returns False if this is not actually a valid card
    for the database, and True otherwise.
    """

    if page in token_ids:
        # print(f"warning: skipping card in tokens cateogry: {page.name}")
        return False

    cardtable = next(
        iter([x for x in data.templates if x.name.strip() == "CardTable2"])
    )

    for locale, key in LOCALES.items():
        value = get_cardtable2_entry(cardtable, locale + "_name" if locale else "name")
        if not locale and not value:
            value = batcher.idsToNames[page]
        if value and value.strip():
            value = _strip_markup(value.strip())
            card.text.setdefault(key, CardText(name=value))
            card.text[key].name = value
        value = get_cardtable2_entry(cardtable, locale + "_lore" if locale else "lore")
        if value and value.strip():
            if key not in card.text:
                # print(f"warning: card has no name in {key} but has effect: {page.name}")
                pass
            else:
                card.text[key].effect = _strip_markup(value.strip())
        value = get_cardtable2_entry(
            cardtable, locale + "_pendulum_effect" if locale else "pendulum_effect"
        )
        if value and value.strip():
            if key not in card.text:
                # print(f"warning: card has no name in {key} but has pend. effect: {page.name}")
                pass
            else:
                card.text[key].pendulum_effect = _strip_markup(value.strip())
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
            print(f"warning: monster has no typeline: {batcher.idsToNames[page]}")
            return False
        if "Skill" in typeline:
            # print(f"warning: skipping skill card: {batcher.idsToNames[page]}")
            return False
        if "Token" in typeline:
            # print(f"warning: skipping token card: {batcher.idsToNames[page]}")
            return False

        value = get_cardtable2_entry(cardtable, "attribute")
        if not value:
            print(f"warning: monster has no attribute: {batcher.idsToNames[page]}")
            return False
        if value.strip().lower() not in Attribute._value2member_map_:
            print(
                f"warning: unknown attribute '{value.strip()}' in {batcher.idsToNames[page]}"
            )
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
                print(
                    f"warning: monster typeline bit unknown in {batcher.idsToNames[page]}: {x}"
                )
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
            print(f"warning: monster has no type: {batcher.idsToNames[page]}")
            return False

        value = get_cardtable2_entry(cardtable, "level")
        if value:
            try:
                card.level = int(value)
            except ValueError:
                print(
                    f"warning: unknown level '{value.strip()}' in {batcher.idsToNames[page]}"
                )
                return False

        value = get_cardtable2_entry(cardtable, "rank")
        if value:
            try:
                card.rank = int(value)
            except ValueError:
                print(
                    f"warning: unknown rank '{value.strip()}' in {batcher.idsToNames[page]}"
                )
                return False

        value = get_cardtable2_entry(cardtable, "atk")
        if value:
            try:
                card.atk = "?" if value.strip() == "?" else int(value)
            except ValueError:
                print(
                    f"warning: unknown ATK '{value.strip()}' in {batcher.idsToNames[page]}"
                )
                return False
        value = get_cardtable2_entry(cardtable, "def")
        if value:
            try:
                card.def_ = "?" if value.strip() == "?" else int(value)
            except ValueError:
                print(
                    f"warning: unknown DEF '{value.strip()}' in {batcher.idsToNames[page]}"
                )
                return False

        value = get_cardtable2_entry(cardtable, "pendulum_scale")
        if value:
            try:
                card.scale = int(value)
            except ValueError:
                print(
                    f"warning: unknown scale '{value.strip()}' in {batcher.idsToNames[page]}"
                )
                return False

        value = get_cardtable2_entry(cardtable, "link_arrows")
        if value:
            card.link_arrows = [
                LinkArrow(x.lower().replace("-", "").strip()) for x in value.split(",")
            ]
    elif card.card_type == CardType.SPELL or card.card_type == CardType.TRAP:
        value = get_cardtable2_entry(cardtable, "property")
        if not value:
            print(f"warning: spelltrap has no subcategory: {batcher.idsToNames[page]}")
            return False
        card.subcategory = SubCategory(value.lower().replace("-", "").strip())

    value = get_cardtable2_entry(cardtable, "password")
    if value:
        vmatch = re.match(r"^\d+", value.strip())
        if vmatch and value.strip() not in card.passwords:
            card.passwords.append(value.strip())
        if not vmatch and value.strip() and value.strip() != "none":
            print(
                f"warning: bad password '{value.strip()}' in card {batcher.idsToNames[page]}"
            )

    # generally, we want YGOProDeck to handle generic images
    # But if all else fails, we can add one!
    # TODO: batch image fetches
    # (this doesn't exactly hammer Yugpedia how we do it now,
    # since only a handful of cards are Like This,
    # but we should batch them eventually all the same)
    if all("yugipedia.com" in (image.card_art or "") for image in card.images):
        in_images_raw = get_cardtable2_entry(cardtable, "image")
        if in_images_raw:
            in_images = [
                [x.strip() for x in x.split(";")]
                for x in in_images_raw.split("\n")
                if x.strip()
            ]
            for image in card.images:
                in_image = in_images.pop(0)
                if len(in_image) != 1 and len(in_image) != 3:
                    print(
                        f"warning: weird image string for {batcher.idsToNames[page]}: {' ; '.join(in_image)}"
                    )
                    continue
                image.card_art = next(
                    iter(
                        _get_image_urls(
                            [in_image[0] if len(in_image) == 1 else in_image[1]]
                        )
                    )
                )
            for in_image in in_images:
                if len(in_image) != 1 and len(in_image) != 3:
                    print(
                        f"warning: weird image string for {batcher.idsToNames[page]}: {' ; '.join(in_image)}"
                    )
                    continue
                image = CardImage(
                    id=uuid.uuid4(),
                    card_art=next(
                        iter(
                            _get_image_urls(
                                [in_image[0] if len(in_image) == 1 else in_image[1]]
                            )
                        )
                    ),
                )
                if len(card.passwords) == 1:
                    # we don't have the full ability to correspond passwords here
                    # but this will do for 99% of cards
                    image.password = card.passwords[0]
                card.images.append(image)

    # TODO: sets, legality, video games

    if not card.yugipedia_pages:
        card.yugipedia_pages = []
    for existing_page in card.yugipedia_pages or []:
        if not existing_page.name and existing_page.id == page:
            existing_page.name = batcher.idsToNames[page]
        elif not existing_page.id and existing_page.name == batcher.idsToNames[page]:
            existing_page.id = page
    if not any(x.id == page for x in card.yugipedia_pages):
        card.yugipedia_pages.append(ExternalIdPair(batcher.idsToNames[page], page))

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
    with YugipediaBatcher() as batcher:
        token_ids = get_token_ids(batcher)

        cards: typing.List[int]
        if db.last_yugipedia_read:
            if (
                datetime.datetime.now().timestamp() - db.last_yugipedia_read.timestamp()
                > TIME_TO_JUST_REDOWNLOAD_ALL_PAGES
            ):
                # TODO: clear cache
                cards = [x for x in get_card_pages(batcher)]
            else:
                cards = [
                    x.id
                    for x in get_changes(
                        batcher,
                        get_card_pages(batcher),
                        get_changelog(db.last_yugipedia_read),
                    )[0]
                ]
        else:
            cards = [x for x in get_card_pages(batcher)]

    n_found = n_new = 0

    with YugipediaBatcher() as batcher:
        for pageid in cards:

            @batcher.getPageContents(pageid, useCache=db.last_yugipedia_read is None)
            def onGetData(raw_data: str):
                nonlocal n_found, n_new

                data = wikitextparser.parse(raw_data)
                try:
                    cardtable = next(
                        iter(
                            [
                                x
                                for x in data.templates
                                if x.name.strip() == "CardTable2"
                            ]
                        )
                    )
                except StopIteration:
                    print(
                        f"warning: found card without card table: {batcher.idsToNames[pageid]}"
                    )
                    return

                ct = (
                    get_cardtable2_entry(cardtable, "card_type", "monster")
                    .strip()
                    .lower()
                )
                if ct not in [x.value for x in CardType]:
                    # print(f"warning: found card with illegal card type: {ct}")
                    return

                found = pageid in db.cards_by_yugipedia_id
                card = db.cards_by_yugipedia_id.get(pageid) or Card(
                    id=uuid.uuid4(), card_type=CardType(ct)
                )

                if parse_card(batcher, pageid, card, data, token_ids):
                    db.add_card(card)
                    if found:
                        n_found += 1
                    else:
                        n_new += 1

                    if progress_monitor:
                        progress_monitor(card, found)

    db.last_yugipedia_read = datetime.datetime.now()
    return n_found, n_new


BATCH_MAX = 50

PAGES_FILENAME = "yugipedia_pages.json"
CONTENTS_FILENAME = "yugipedia_contents.json"
NAMESPACES = {"mw": "http://www.mediawiki.org/xml/export-0.10/"}
IMAGE_URLS_FILENAME = "yugipedia_images.json"
CAT_MEMBERS_FILENAME = "yugipedia_members.json"


class CategoryMemberType(enum.Enum):
    PAGE = "page"
    SUBCAT = "subcat"
    FILE = "file"


class CategoryMember(WikiPage):
    def __init__(self, id: int, name: str, type: CategoryMemberType) -> None:
        super().__init__(id, name)
        self.type = type


class YugipediaBatcher:
    def __init__(self) -> None:
        self.namesToIDs = {}
        self.idsToNames = {}

        self.pendingGetPageContents = {}
        self.pageContentsCache = {}

        self.categoryMembersCache = {}

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        while self.pendingGetPageContents:
            self._executeGetContentsBatch()

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

    namesToIDs: typing.Dict[str, int]
    idsToNames: typing.Dict[int, str]

    pageContentsCache: typing.Dict[int, str]
    pendingGetPageContents: typing.Dict[
        typing.Union[str, int], typing.List[typing.Callable[[str], None]]
    ]

    def getPageContents(self, page: typing.Union[str, int], *, useCache: bool = True):
        batcher = self

        class GetPageXMLDecorator:
            def __init__(self, callback: typing.Callable[[str], None]) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )
                if useCache and pageid in batcher.pageContentsCache:
                    callback(batcher.pageContentsCache[pageid])
                else:
                    batcher.pendingGetPageContents.setdefault(pageid or page, [])
                    batcher.pendingGetPageContents[pageid or page].append(callback)
                    if (
                        sum(1 for x in batcher.pendingGetPageContents.keys())
                        >= BATCH_MAX
                    ):
                        batcher._executeGetContentsBatch()

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetPageXMLDecorator

    def _executeGetContentsBatch(self):
        pages = self.pendingGetPageContents.keys()
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
            for callback in self.pendingGetPageContents.get(id, []):
                callback(contents)
            for callback in self.pendingGetPageContents.get(title, []):
                callback(contents)

        self.pendingGetPageContents.clear()

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

    def getCategoryMembers(
        self, page: typing.Union[str, int], *, useCache: bool = True
    ):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )

                if not useCache or pageid not in batcher.categoryMembersCache:
                    pageid = batcher._populateCatMembers(page)

                if pageid is None:
                    raise Exception(f"ID not found: {page}")

                callback(
                    [
                        x.id
                        for x in batcher.categoryMembersCache[pageid]
                        if x.type == CategoryMemberType.FILE
                    ]
                )

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetCatMemDecorator

    def getSubcategories(self, page: typing.Union[str, int], *, useCache: bool = True):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                pageid = (
                    page if type(page) is int else batcher.namesToIDs.get(str(page))
                )

                if not useCache or pageid not in batcher.categoryMembersCache:
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

    def getCategoryMembersRecursive(
        self, page: typing.Union[str, int], *, useCache: bool = True
    ):
        batcher = self

        class GetCatMemDecorator:
            def __init__(
                self, callback: typing.Callable[[typing.List[int]], None]
            ) -> None:
                result = []

                @batcher.getCategoryMembers(page, useCache=useCache)
                def getMembers(members: typing.List[int]):
                    result.extend(members)

                @batcher.getSubcategories(page, useCache=useCache)
                def getSubcats(members: typing.List[int]):
                    for member in members:

                        @batcher.getCategoryMembersRecursive(member, useCache=useCache)
                        def recur(members: typing.List[int]):
                            result.extend(members)

                callback(result)

            def __call__(self) -> None:
                raise Exception(
                    "Not supposed to call YugipediaBatcher-decorated function!"
                )

        return GetCatMemDecorator