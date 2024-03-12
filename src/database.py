import json
import os
import os.path
import typing

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TEMP_DIR = os.path.join(ROOT_DIR, "temp")
DATA_DIR = os.path.join(ROOT_DIR, "data")
AGGREGATE_DIR = os.path.join(DATA_DIR, "aggregate")

CARDLIST_FILENAME = "cards.json"
CARDS_DIRNAME = "cards"

AGG_CARDS_FILENAME = "cards.json"

Card = typing.Dict[str, typing.Any]


class Database:
    cards: typing.List[Card]
    cards_by_id: typing.Dict[str, Card]
    cards_by_password: typing.Dict[str, Card]
    cards_by_yamlyugi: typing.Dict[int, Card]
    cards_by_en_name: typing.Dict[str, Card]
    cards_by_konami_cid: typing.Dict[int, Card]

    def __init__(
        self, *, individuals_dir: str = DATA_DIR, aggregates_dir: str = AGGREGATE_DIR
    ):
        self.individuals_dir = individuals_dir
        self.aggregates_dir = aggregates_dir

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
            with open(
                os.path.join(self.individuals_dir, CARDLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump([card["id"] for card in self.cards], outfile, indent=2)
            os.makedirs(
                os.path.join(self.individuals_dir, CARDS_DIRNAME), exist_ok=True
            )
            for card in self.cards:
                self._save_card(card)
                if progress_monitor:
                    progress_monitor(card)
        if generate_aggregates:
            os.makedirs(AGGREGATE_DIR, exist_ok=True)
            with open(
                os.path.join(self.aggregates_dir, AGG_CARDS_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(self.cards, outfile, indent=2)

    def _card_path(self, card_json: Card) -> str:
        return os.path.join(
            self.individuals_dir, CARDS_DIRNAME, card_json["id"] + ".json"
        )

    def _save_card(self, card_json: Card):
        path = self._card_path(card_json)
        # if os.path.exists(path):
        #     os.remove(path)
        with open(path, "w", encoding="utf-8") as outfile:
            json.dump(card_json, outfile, indent=2)

    def _load_card(self, id: str) -> Card:
        with open(
            os.path.join(self.individuals_dir, CARDS_DIRNAME, id + ".json"),
            encoding="utf-8",
        ) as outfile:
            return json.load(outfile)

    def _load_cardlist(self) -> typing.List[str]:
        if not os.path.exists(os.path.join(self.individuals_dir, CARDLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, CARDLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return json.load(outfile)


def load_database(
    *,
    progress_monitor: typing.Optional[typing.Callable[[Card], None]] = None,
    individuals_dir: str = DATA_DIR,
    aggregates_dir: str = AGGREGATE_DIR,
) -> Database:
    result = Database(aggregates_dir=aggregates_dir, individuals_dir=individuals_dir)
    if os.path.exists(os.path.join(aggregates_dir, AGG_CARDS_FILENAME)):
        with open(
            os.path.join(aggregates_dir, AGG_CARDS_FILENAME), encoding="utf-8"
        ) as outfile:
            for card in json.load(outfile):
                result.addCard(card)
                if progress_monitor:
                    progress_monitor(card)
    else:
        for card in (result._load_card(id) for id in result._load_cardlist()):
            result.addCard(card)
            if progress_monitor:
                progress_monitor(card)
    return result
