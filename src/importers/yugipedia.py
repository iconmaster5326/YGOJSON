# Import data from Yugipedia (https://yugipedia.com).
import datetime
import json
import os.path
import time
import typing
import uuid

import requests

from ..database import *

API_URL = "https://yugipedia.com/api.php"
RATE_LIMIT = 1.1

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

    response = requests.get(
        API_URL,
        params=params,
        headers={
            "User-Agent": f"YGOJSON/{SCHEMA_VERSION} (https://github.com/iconmaster5326/YGOJSON)"
        },
    )
    if not response.ok:
        response.raise_for_status()
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
    while True:
        in_json = make_request(query).json()
        yield in_json["query"]
        if "continue" in in_json:
            query["continue"] = in_json["continue"]
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
        "cmtype": "subcat",
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
        "cmtype": "page",
    }

    for results in paginate_query(query):
        for result in results["categorymembers"]:
            yield WikiPage(result["pageid"], result["title"])


def get_cateogry_members_recursive(page: typing.Union[str, int]):
    for x in get_cateogry_members(page):
        yield x
    for x in get_subcategories(page):
        for y in get_cateogry_members_recursive(x.id):
            yield y


def get_card_pages() -> typing.Iterable[WikiPage]:
    return get_cateogry_members("Category:Duel Monsters cards")


def get_set_pages() -> typing.Iterable[WikiPage]:
    for x in get_cateogry_members_recursive("Category:OCG sets"):
        yield x
    for x in get_cateogry_members_recursive("Category:TCG sets"):
        yield x


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
