import datetime
import enum
import json
import os
import os.path
import typing
import uuid

SCHEMA_VERSION = 1

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TEMP_DIR = os.path.join(ROOT_DIR, "temp")
DATA_DIR = os.path.join(ROOT_DIR, "data")
AGGREGATE_DIR = os.path.join(DATA_DIR, "aggregate")

CARDLIST_FILENAME = "cards.json"
CARDS_DIRNAME = "cards"

AGG_CARDS_FILENAME = "cards.json"


class CardType(enum.Enum):
    MONSTER = "monster"
    SPELL = "spell"
    TRAP = "trap"


class Attribute(enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    FIRE = "fire"
    WATER = "water"
    WIND = "wind"
    EARTH = "earth"
    DIVINE = "divine"


class MonsterCardType(enum.Enum):
    RITUAL = "ritual"
    FUSION = "fusion"
    SYNCHRO = "synchro"
    XYZ = "xyz"
    PENDULUM = "pendulum"
    LINK = "link"


class Race(enum.Enum):
    BEASTWARRIOR = "beastwarrior"
    ZOMBIE = "zombie"
    FIEND = "fiend"
    DINOSAUR = "dinosaur"
    DRAGON = "dragon"
    BEAST = "beast"
    ILLUSION = "illusion"
    INSECT = "insect"
    WINGEDBEAST = "wingedbeast"
    WARRIOR = "warrior"
    SEASERPENT = "seaserpent"
    AQUA = "aqua"
    PYRO = "pyro"
    THUNDER = "thunder"
    SPELLCASTER = "spellcaster"
    PLANT = "plant"
    ROCK = "rock"
    REPTILE = "reptile"
    FAIRY = "fairy"
    FISH = "fish"
    MACHINE = "machine"
    DIVINEBEAST = "divinebeast"
    PSYCHIC = "psychic"
    CREATORGOD = "creatorgod"
    WYRM = "wyrm"
    CYBERSE = "cyberse"


class Classification(enum.Enum):
    NORMAL = "normal"
    EFFECT = "effect"
    PENDULUM = "pendulum"
    TUNER = "tuner"
    SPECIALSUMMON = "specialsummon"


class Ability(enum.Enum):
    TOON = "toon"
    SPIRIT = "spirit"
    UNION = "union"
    GEMINI = "gemini"
    FLIP = "flip"


class LinkArrow(enum.Enum):
    TOPLEFT = "topleft"
    TOPCENTER = "topcenter"
    TOPRIGHT = "topright"
    MIDDLELEFT = "middleleft"
    MIDDLERIGHT = "middleright"
    BOTTOMLEFT = "bottomleft"
    BOTTOMCENTER = "bottomcenter"
    BOTTOMRIGHT = "bottomright"


class SubCategory(enum.Enum):
    NORMAL = "normal"
    CONTINUOUS = "continuous"
    EQUIP = "equip"
    QUICKPLAY = "quickplay"
    FIELD = "field"
    RITUAL = "ritual"
    COUNTER = "counter"


class Legality(enum.Enum):
    UNLIMITED = "unlimited"
    SEMILIMITED = "semilimited"
    LIMITED = "limited"
    FORBIDDEN = "forbidden"
    UNRELEASED = "unreleased"
    UNKNOWN = "unknown"


class Format(enum.Enum):
    OCG = "ocg"
    TCG = "tcg"
    SPEED = "speed"
    DUELLINKS = "duellinks"
    MASTERDUEL = "masterduel"


class VideoGameRaity(enum.Enum):
    NORMAL = "n"
    RARE = "r"
    SUPER = "sr"
    ULTRA = "ur"


class CardText:
    name: str
    effect: typing.Optional[str]
    pendulum_effect: typing.Optional[str]
    official: bool

    def __init__(
        self,
        *,
        name: str,
        effect: typing.Optional[str] = None,
        pendulum_effect: typing.Optional[str] = None,
        official: bool = True,
    ):
        self.name = name
        self.effect = effect
        self.pendulum_effect = pendulum_effect
        self.official = official


class CardImage:
    id: uuid.UUID
    password: typing.Optional[str]
    crop_art: typing.Optional[str]
    card_art: typing.Optional[str]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        password: typing.Optional[str] = None,
        crop_art: typing.Optional[str] = None,
        card_art: typing.Optional[str] = None,
    ):
        self.id = id
        self.password = password
        self.crop_art = crop_art
        self.card_art = card_art


class LegalityPeriod:
    legality: Legality
    date: datetime.date

    def __init__(
        self,
        *,
        legality: Legality,
        date: datetime.date,
    ):
        self.legality = legality
        self.date = date


class CardLegality:
    current: Legality
    history: typing.Optional[typing.List[LegalityPeriod]]

    def __init__(
        self,
        *,
        current: Legality,
        history: typing.Optional[typing.List[LegalityPeriod]] = None,
    ):
        self.current = current
        self.history = history


class Card:
    id: uuid.UUID
    text: typing.Dict[str, CardText]
    card_type: CardType
    attribute: typing.Optional[Attribute]
    monster_card_types: typing.Optional[typing.List[MonsterCardType]]
    type: typing.Optional[Race]
    classifications: typing.Optional[typing.List[Classification]]
    abilities: typing.Optional[typing.List[Ability]]
    level: typing.Optional[int]
    rank: typing.Optional[int]
    atk: typing.Union[int, str, None]
    def_: typing.Union[int, str, None]
    scale: typing.Optional[int]
    link_arrows: typing.Optional[typing.List[LinkArrow]]
    subcategory: typing.Optional[SubCategory]
    passwords: typing.List[str]
    images: typing.List[CardImage]
    sets: typing.List["Set"]
    legality: typing.Dict[Format, CardLegality]
    master_duel_rarity: typing.Optional[VideoGameRaity]
    master_duel_craftable: typing.Optional[bool]
    duel_links_rarity: typing.Optional[VideoGameRaity]
    yugipedia_name: typing.Optional[str]
    yugipedia_id: typing.Optional[int]
    db_id: typing.Optional[int]
    ygoprodeck_id: typing.Optional[int]
    ygoprodeck_name: typing.Optional[str]
    yugiohprices_name: typing.Optional[str]
    yamlyugi_id: typing.Optional[int]
    series: typing.List["Series"]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        text: typing.Optional[typing.Dict[str, CardText]] = None,
        card_type: CardType,
        attribute: typing.Optional[Attribute] = None,
        monster_card_types: typing.Optional[typing.List[MonsterCardType]] = None,
        type: typing.Optional[Race] = None,
        classifications: typing.Optional[typing.List[Classification]] = None,
        abilities: typing.Optional[typing.List[Ability]] = None,
        level: typing.Optional[int] = None,
        rank: typing.Optional[int] = None,
        atk: typing.Union[int, str, None] = None,
        def_: typing.Union[int, str, None] = None,
        scale: typing.Optional[int] = None,
        link_arrows: typing.Optional[typing.List[LinkArrow]] = None,
        subcategory: typing.Optional[SubCategory] = None,
        passwords: typing.Optional[typing.List[str]] = None,
        images: typing.Optional[typing.List[CardImage]] = None,
        sets: typing.Optional[typing.List["Set"]] = None,
        legality: typing.Optional[typing.Dict[Format, CardLegality]] = None,
        master_duel_rarity: typing.Optional[VideoGameRaity] = None,
        master_duel_craftable: typing.Optional[bool] = None,
        duel_links_rarity: typing.Optional[VideoGameRaity] = None,
        yugipedia_name: typing.Optional[str] = None,
        yugipedia_id: typing.Optional[int] = None,
        db_id: typing.Optional[int] = None,
        ygoprodeck_id: typing.Optional[int] = None,
        ygoprodeck_name: typing.Optional[str] = None,
        yugiohprices_name: typing.Optional[str] = None,
        yamlyugi_id: typing.Optional[int] = None,
        series: typing.Optional[typing.List["Series"]] = None,
    ):
        self.id = id
        self.text = text or {}
        self.card_type = card_type
        self.attribute = attribute
        self.monster_card_types = monster_card_types
        self.type = type
        self.classifications = classifications
        self.abilities = abilities
        self.level = level
        self.rank = rank
        self.atk = atk
        self.def_ = def_
        self.scale = scale
        self.link_arrows = link_arrows
        self.subcategory = subcategory
        self.passwords = passwords or []
        self.images = images or []
        self.sets = sets or []
        self.legality = legality or {}
        self.master_duel_rarity = master_duel_rarity
        self.master_duel_craftable = master_duel_craftable
        self.duel_links_rarity = duel_links_rarity
        self.yugipedia_name = yugipedia_name
        self.yugipedia_id = yugipedia_id
        self.db_id = db_id
        self.ygoprodeck_id = ygoprodeck_id
        self.ygoprodeck_name = ygoprodeck_name
        self.yugiohprices_name = yugiohprices_name
        self.yamlyugi_id = yamlyugi_id
        self.series = series or []

    def to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/card.json",
            "id": str(self.id),
            "text": {
                k: {
                    "name": v.name,
                    **({"effect": v.effect} if v.effect is not None else {}),
                    **(
                        {"pendulumEffect": v.pendulum_effect}
                        if v.pendulum_effect is not None
                        else {}
                    ),
                    **({"official": False} if not v.official else {}),
                }
                for k, v in self.text.items()
            },
            "cardType": self.card_type.value,
            **(
                {
                    "attribute": self.attribute.value,
                    "monsterCardTypes": [x.value for x in self.monster_card_types],
                    "type": self.type.value,
                    "classifications": [x.value for x in self.classifications],
                    "abilities": [x.value for x in self.abilities],
                    **({"level": self.level} if self.level is not None else {}),
                    **({"rank": self.rank} if self.rank is not None else {}),
                    "atk": self.atk,
                    **({"def": self.def_} if self.def_ is not None else {}),
                    **({"scale": self.scale} if self.scale is not None else {}),
                    **(
                        {"linkArrows": [x.value for x in self.link_arrows]}
                        if self.link_arrows
                        else {}
                    ),
                }
                if self.card_type == CardType.MONSTER
                else {}
            ),
            **(
                {
                    "subcategory": self.subcategory.value,
                }
                if self.card_type == CardType.SPELL or self.card_type == CardType.TRAP
                else {}
            ),
            "passwords": self.passwords,
            "images": [
                {
                    "id": str(x.id),
                    **({"password": x.password} if x.password else {}),
                    **({"art": x.crop_art} if x.crop_art else {}),
                    **({"card": x.card_art} if x.card_art else {}),
                }
                for x in self.images
            ],
            "sets": [x.id for x in self.sets],
            "legality": {
                k.value: {
                    "current": v.current.value,
                    **(
                        {
                            "history": [
                                {
                                    "legality": x.legality.value,
                                    "date": x.date.isoformat(),
                                }
                                for x in v.history
                            ]
                        }
                        if v.history
                        else {}
                    ),
                }
                for k, v in self.legality.items()
            },
            **(
                {
                    "masterDuel": {
                        "rarity": self.master_duel_rarity.value,
                        "craftable": self.master_duel_craftable or False,
                    }
                }
                if self.master_duel_rarity
                else {}
            ),
            **(
                {
                    "duelLinks": {
                        "rarity": self.duel_links_rarity.value,
                    }
                }
                if self.duel_links_rarity
                else {}
            ),
            "externalIDs": {
                **(
                    {"yugipediaName": self.yugipedia_name}
                    if self.yugipedia_name
                    else {}
                ),
                **({"yugipediaID": self.yugipedia_id} if self.yugipedia_id else {}),
                **({"dbID": self.db_id} if self.db_id else {}),
                **({"ygoprodeckID": self.ygoprodeck_id} if self.ygoprodeck_id else {}),
                **(
                    {"ygoprodeckName": self.ygoprodeck_name}
                    if self.ygoprodeck_name
                    else {}
                ),
                **(
                    {"yugiohpricesName": self.yugiohprices_name}
                    if self.yugiohprices_name
                    else {}
                ),
                **({"yamlyugiID": self.yamlyugi_id} if self.yamlyugi_id else {}),
            },
            "series": [x.id for x in self.series],
        }


class Series:
    id: uuid.UUID


class Set:
    id: uuid.UUID


class Database:
    cards: typing.List[Card]
    cards_by_id: typing.Dict[uuid.UUID, Card]
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
        if str(card.id) not in self.cards_by_id:
            self.cards.append(card)

        self.cards_by_id[card.id] = card
        for pw in card.passwords:
            self.cards_by_password[pw] = card
        if card.yamlyugi_id:
            self.cards_by_yamlyugi[card.yamlyugi_id] = card
        if "en" in card.text:
            self.cards_by_en_name[card.text["en"].name] = card
        if card.db_id:
            self.cards_by_konami_cid[card.db_id] = card

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
                json.dump([str(card.id) for card in self.cards], outfile, indent=2)
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
                json.dump([x.to_json() for x in self.cards], outfile, indent=2)

    def _save_card(self, card: Card):
        with open(
            os.path.join(self.individuals_dir, CARDS_DIRNAME, str(card.id) + ".json"),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(card.to_json(), outfile, indent=2)

    def _load_card(self, id: uuid.UUID) -> Card:
        with open(
            os.path.join(self.individuals_dir, CARDS_DIRNAME, str(id) + ".json"),
            encoding="utf-8",
        ) as outfile:
            rawcard: typing.Dict[str, typing.Any] = json.load(outfile)
        return Card(
            id=uuid.UUID(rawcard["id"]),
            text={
                k: CardText(
                    name=v["name"],
                    effect=v.get("effect"),
                    pendulum_effect=v.get("pendulumEffect"),
                    official=v.get("official", True),
                )
                for k, v in rawcard.get("text", {}).items()
            },
            card_type=CardType(rawcard["cardType"]),
            attribute=Attribute(rawcard["attribute"])
            if "attribute" in rawcard
            else None,
            monster_card_types=[MonsterCardType(x) for x in rawcard["monsterCardTypes"]]
            if "monsterCardTypes" in rawcard
            else None,
            type=Race(rawcard["type"]) if "type" in rawcard else None,
            classifications=[Classification(x) for x in rawcard["classifications"]]
            if "classifications" in rawcard
            else None,
            abilities=[Ability(x) for x in rawcard["abilities"]]
            if "abilities" in rawcard
            else None,
            level=rawcard.get("level"),
            rank=rawcard.get("rank"),
            atk=rawcard.get("atk"),
            def_=rawcard.get("def"),
            scale=rawcard.get("scale"),
            link_arrows=[LinkArrow(x) for x in rawcard["linkArrows"]]
            if "linkArrows" in rawcard
            else None,
            subcategory=SubCategory(rawcard["subcategory"])
            if "subcategory" in rawcard
            else None,
            passwords=rawcard["passwords"],
            images=[
                CardImage(
                    id=uuid.UUID(x["id"]),
                    password=x.get("password"),
                    crop_art=x.get("art"),
                    card_art=x.get("card"),
                )
                for x in rawcard["images"]
            ],
            sets=[],
            legality={
                k: CardLegality(
                    current=Legality(v.get("current") or "unknown"),
                    history=[
                        LegalityPeriod(
                            legality=Legality(x["legality"]),
                            date=datetime.date.fromisoformat(x["date"]),
                        )
                        for x in v.get("history", [])
                    ],
                )
                for k, v in rawcard.get("legality", {}).items()
            },
            master_duel_rarity=VideoGameRaity(rawcard["masterDuel"]["rarity"])
            if "masterDuel" in rawcard
            else None,
            master_duel_craftable=rawcard["masterDuel"]["craftable"]
            if "masterDuel" in rawcard
            else None,
            duel_links_rarity=VideoGameRaity(rawcard["duelLinks"]["rarity"])
            if "duelLinks" in rawcard
            else None,
            yugipedia_name=rawcard["externalIDs"].get("yugipediaName"),
            yugipedia_id=rawcard["externalIDs"].get("yugipediaID"),
            db_id=rawcard["externalIDs"].get("dbID"),
            ygoprodeck_id=rawcard["externalIDs"].get("ygoprodeckID"),
            ygoprodeck_name=rawcard["externalIDs"].get("ygoprodeckName"),
            yugiohprices_name=rawcard["externalIDs"].get("yugiohpricesName"),
            yamlyugi_id=rawcard["externalIDs"].get("yamlyugiID"),
            series=[],
        )

    def _load_cardlist(self) -> typing.List[uuid.UUID]:
        if not os.path.exists(os.path.join(self.individuals_dir, CARDLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, CARDLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]


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
