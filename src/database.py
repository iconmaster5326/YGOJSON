import typing
import os
import os.path
import json

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TEMP_DIR = os.path.join(ROOT_DIR, "temp")
DATA_DIR = os.path.join(ROOT_DIR, "data")
CARDLIST_FILE = os.path.join(DATA_DIR, "cards.json")
CARDS_DIR = os.path.join(DATA_DIR, "cards")
AGGREGATE_DIR = os.path.join(DATA_DIR, "aggregate")
AGG_CARDS_FILE = os.path.join(AGGREGATE_DIR, "cards.json")

Card = typing.Dict[str, typing.Any]


class Database:
    cards: typing.List[Card]
    cards_by_id: typing.Dict[str, Card]
    cards_by_password: typing.Dict[str, Card]
    cards_by_yamlyugi: typing.Dict[int, Card]
    cards_by_en_name: typing.Dict[str, Card]
    cards_by_konami_cid: typing.Dict[int, Card]

    def __init__(self):
        self.cards = []
        self.cards_by_id = {}
        self.cards_by_password = {}
        self.cards_by_yamlyugi = {}
        self.cards_by_en_name = {}
        self.cards_by_konami_cid = {}

    def addCard(self, card: Card):
        if card["id"] not in self.cards_by_id:
            self.cards.append(card)

        self.cards_by_id[card["id"]] = card
        for pw in card["passwords"]:
            self.cards_by_password[pw] = card
        if "yamlyugiID" in card["externalIDs"]:
            self.cards_by_yamlyugi[card["externalIDs"]["yamlyugiID"]] = card
        if "en" in card["text"] and "name" in card["text"]["en"]:
            self.cards_by_en_name[card["text"]["en"]["name"]] = card
        if "dbID" in card["externalIDs"]:
            self.cards_by_konami_cid[card["externalIDs"]["dbID"]] = card

    def save(
        self,
        *,
        progress_monitor: typing.Optional[typing.Callable[[Card], None]] = None,
        generate_individuals: bool = True,
        generate_aggregates: bool = True,
    ):
        if generate_individuals:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(CARDLIST_FILE, "w", encoding="utf-8") as outfile:
                json.dump([card["id"] for card in self.cards], outfile, indent=2)
            os.makedirs(CARDS_DIR, exist_ok=True)
            for card in self.cards:
                _save_card(card)
                if progress_monitor:
                    progress_monitor(card)
        if generate_aggregates:
            os.makedirs(AGGREGATE_DIR, exist_ok=True)
            with open(AGG_CARDS_FILE, "w", encoding="utf-8") as outfile:
                json.dump(self.cards, outfile, indent=2)


def load_database(
    *, progress_monitor: typing.Optional[typing.Callable[[Card], None]] = None
) -> Database:
    result = Database()
    if os.path.exists(AGG_CARDS_FILE):
        with open(AGG_CARDS_FILE, encoding="utf-8") as outfile:
            for card in json.load(outfile):
                result.addCard(card)
                if progress_monitor:
                    progress_monitor(card)
    else:
        for card in (_load_card(id) for id in _load_cardlist()):
            result.addCard(card)
            if progress_monitor:
                progress_monitor(card)
    return result


def _card_path(card_json: Card) -> str:
    return os.path.join(CARDS_DIR, card_json["id"] + ".json")


def _save_card(card_json: Card):
    path = _card_path(card_json)
    # if os.path.exists(path):
    #     os.remove(path)
    with open(path, "w", encoding="utf-8") as outfile:
        json.dump(card_json, outfile, indent=2)


def _load_card(id: str) -> Card:
    with open(os.path.join(CARDS_DIR, id + ".json"), encoding="utf-8") as outfile:
        return json.load(outfile)


def _load_cardlist() -> typing.List[str]:
    if not os.path.exists(CARDLIST_FILE):
        return []
    with open(CARDLIST_FILE, encoding="utf-8") as outfile:
        return json.load(outfile)
