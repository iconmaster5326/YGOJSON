import datetime
import enum
import json
import logging
import os
import os.path
import typing
import uuid
import zipfile

import requests
import tqdm

SCHEMA_VERSION = 1

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
TEMP_DIR = os.path.join(ROOT_DIR, "temp")
DATA_DIR = os.path.join(ROOT_DIR, "data")
MANUAL_DATA_DIR = os.path.join(ROOT_DIR, "manual-data")
INDIVIDUAL_DIR = os.path.join(DATA_DIR, "individual")
AGGREGATE_DIR = os.path.join(DATA_DIR, "aggregate")
META_FILENAME = "meta.json"

CARDLIST_FILENAME = "cards.json"
CARDS_DIRNAME = "cards"
AGG_CARDS_FILENAME = "cards.json"

SETLIST_FILENAME = "sets.json"
SETS_DIRNAME = "sets"
AGG_SETS_FILENAME = "sets.json"

SERIESLIST_FILENAME = "series.json"
SERIES_DIRNAME = "series"
AGG_SERIES_FILENAME = "series.json"

DISTROLIST_FILENAME = "distributions.json"
DISTROS_DIRNAME = "distributions"
AGG_DISTROS_FILENAME = "distributions.json"

PRODUCTLIST_FILENAME = "sealedProducts.json"
PRODUCTS_DIRNAME = "sealedProducts"
AGG_PRODUCTS_FILENAME = "sealedProducts.json"

MANUAL_SETS_DIR = os.path.join(MANUAL_DATA_DIR, "sets")
MANUAL_DISTROS_DIR = os.path.join(MANUAL_DATA_DIR, "distributions")
MANUAL_PRODUCTS_DIR = os.path.join(MANUAL_DATA_DIR, "sealed-products")


class CardType(enum.Enum):
    MONSTER = "monster"
    SPELL = "spell"
    TRAP = "trap"
    TOKEN = "token"
    SKILL = "skill"


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
    # OCG/TCG
    UNLIMITED = "unlimited"
    SEMILIMITED = "semilimited"
    LIMITED = "limited"
    FORBIDDEN = "forbidden"
    # speed duel
    LIMIT1 = "limit1"
    LIMIT2 = "limit2"
    LIMIT3 = "limit3"
    # other
    UNRELEASED = "unreleased"


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


class SetEdition(enum.Enum):
    FIRST = "1st"
    UNLIMTED = "unlimited"
    LIMITED = "limited"
    NONE = ""  # not part of the actual enum, but used when a set has no editions


class SpecialDistroType(enum.Enum):
    PRECON = "preconstructed"


class SetBoxType(enum.Enum):
    HOBBY = "hobby"
    RETAIL = "retail"


class CardRarity(enum.Enum):
    COMMON = "common"
    SHORTPRINT = "shortprint"
    RARE = "rare"
    SUPER = "super"
    ULTRA = "ultra"
    ULTIMATE = "ultimate"
    SECRET = "secret"
    ULTRASECRET = "ultrasecret"
    PRISMATICSECRET = "prismaticsecret"
    GHOST = "ghost"
    PARALLEL = "parallel"
    COMMONPARALLEL = "commonparallel"
    RAREPARALLEL = "rareparallel"
    SUPERPARALLEL = "superparallel"
    ULTRAPARALLEL = "ultraparallel"
    DTPC = "dtpc"
    DTPSP = "dtpsp"
    DTRPR = "dtrpr"
    DTSPR = "dtspr"
    DTUPR = "dtupr"
    DTSCPR = "dtscpr"
    GOLD = "gold"
    TENTHOUSANDSECRET = "10000secret"
    TWENTITHSECRET = "20thsecret"
    COLLECTORS = "collectors"
    EXTRASECRET = "extrasecret"
    EXTRASECRETPARALLEL = "extrasecretparallel"
    GOLDGHOST = "goldghost"
    GOLDSECRET = "goldsecret"
    STARFOIL = "starfoil"
    MOSAIC = "mosaic"
    SHATTERFOIL = "shatterfoil"
    GHOSTPARALLEL = "ghostparallel"
    PLATINUM = "platinum"
    PLATINUMSECRET = "platinumsecret"
    PREMIUMGOLD = "premiumgold"
    TWENTYFIFTHSECRET = "25thsecret"
    SECRETPARALLEL = "secretparallel"
    STARLIGHT = "starlight"
    PHARAOHS = "pharaohs"
    KCCOMMON = "kccommon"
    KCRARE = "kcrare"
    KCSUPER = "kcsuper"
    KCULTRA = "kcultra"
    KCSECRET = "kcsecret"
    MILLENIUM = "millenium"
    MILLENIUMSUPER = "milleniumsuper"
    MILLENIUMULTRA = "milleniumultra"
    MILLENIUMSECRET = "milleniumsecret"
    MILLENIUMGOLD = "milleniumgold"


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
    history: typing.List[LegalityPeriod]

    def __init__(
        self,
        *,
        current: Legality,
        history: typing.Optional[typing.List[LegalityPeriod]] = None,
    ):
        self.current = current
        self.history = history or []


class ExternalIdPair:
    name: str
    id: int

    def __init__(self, name: str, id: int) -> None:
        self.name = name
        self.id = id


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
    character: typing.Optional[str]
    skill_type: typing.Optional[str]
    passwords: typing.List[str]
    images: typing.List[CardImage]
    sets: typing.List["Set"]
    illegal: bool
    legality: typing.Dict[str, CardLegality]
    master_duel_rarity: typing.Optional[VideoGameRaity]
    master_duel_craftable: typing.Optional[bool]
    duel_links_rarity: typing.Optional[VideoGameRaity]
    yugipedia_pages: typing.Optional[typing.List[ExternalIdPair]]
    ygoprodeck: typing.Optional[ExternalIdPair]
    db_id: typing.Optional[int]
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
        character: typing.Optional[str] = None,
        skill_type: typing.Optional[str] = None,
        passwords: typing.Optional[typing.List[str]] = None,
        images: typing.Optional[typing.List[CardImage]] = None,
        sets: typing.Optional[typing.List["Set"]] = None,
        illegal: bool = False,
        legality: typing.Optional[typing.Dict[str, CardLegality]] = None,
        master_duel_rarity: typing.Optional[VideoGameRaity] = None,
        master_duel_craftable: typing.Optional[bool] = None,
        duel_links_rarity: typing.Optional[VideoGameRaity] = None,
        yugipedia_pages: typing.Optional[typing.List[ExternalIdPair]] = None,
        db_id: typing.Optional[int] = None,
        ygoprodeck: typing.Optional[ExternalIdPair] = None,
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
        self.character = character
        self.skill_type = skill_type
        self.passwords = passwords or []
        self.images = images or []
        self.sets = sets or []
        self.illegal = illegal
        self.legality = legality or {}
        self.master_duel_rarity = master_duel_rarity
        self.master_duel_craftable = master_duel_craftable
        self.duel_links_rarity = duel_links_rarity
        self.yugipedia_pages = yugipedia_pages
        self.db_id = db_id
        self.ygoprodeck = ygoprodeck
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
            **({"attribute": self.attribute.value} if self.attribute else {}),
            **(
                {"monsterCardTypes": [x.value for x in self.monster_card_types]}
                if self.monster_card_types
                else {}
            ),
            **({"type": self.type.value} if self.type else {}),
            **(
                {"classifications": [x.value for x in self.classifications]}
                if self.classifications
                else {}
            ),
            **(
                {"abilities": [x.value for x in self.abilities]}
                if self.abilities
                else {}
            ),
            **({"level": self.level} if self.level is not None else {}),
            **({"rank": self.rank} if self.rank is not None else {}),
            **({"atk": self.atk} if self.atk is not None else {}),
            **({"def": self.def_} if self.def_ is not None else {}),
            **({"scale": self.scale} if self.scale is not None else {}),
            **(
                {"linkArrows": [x.value for x in self.link_arrows]}
                if self.link_arrows
                else {}
            ),
            **({"character": self.character} if self.character is not None else {}),
            **({"skillType": self.skill_type} if self.skill_type is not None else {}),
            **({"subcategory": self.subcategory.value} if self.subcategory else {}),
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
            "sets": [str(x.id) for x in self.sets],
            **({"illegal": self.illegal} if self.illegal else {}),
            "legality": {
                k: {
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
                        "craftable": self.master_duel_craftable
                        if self.master_duel_craftable is not None
                        else True,
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
                    {
                        "yugipedia": [
                            {"name": x.name, "id": x.id} for x in self.yugipedia_pages
                        ]
                    }
                    if self.yugipedia_pages
                    else {}
                ),
                **({"dbID": self.db_id} if self.db_id else {}),
                **(
                    {
                        "ygoprodeck": {
                            "id": self.ygoprodeck.id,
                            "name": self.ygoprodeck.name,
                        }
                    }
                    if self.ygoprodeck
                    else {}
                ),
                **(
                    {"yugiohpricesName": self.yugiohprices_name}
                    if self.yugiohprices_name
                    else {}
                ),
                **({"yamlyugiID": self.yamlyugi_id} if self.yamlyugi_id else {}),
            },
            "series": [str(x.id) for x in self.series],
        }


class PackDistroWeight:
    rarities: typing.List[CardRarity]
    chance: int

    def __init__(
        self,
        *,
        rarities: typing.Optional[typing.List[CardRarity]] = None,
        chance: int = 1,
    ) -> None:
        self.rarities = rarities or []
        self.chance = chance

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            **({"rarities": [x.value for x in self.rarities]} if self.rarities else {}),
            **({"chance": self.chance} if self.chance != 1 else {}),
        }


class PackDistroSlot:
    _slot_type_name: typing.ClassVar[str]

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        raise NotImplementedError

    @classmethod
    def _from_json(
        cls, db: "Database", in_json: typing.Dict[str, typing.Any]
    ) -> "PackDistroSlot":
        raise NotImplementedError


class PackDistroSlotPool(PackDistroSlot):
    _slot_type_name = "pool"

    set: typing.Optional["Set"]
    rarity: typing.List[PackDistroWeight]
    qty: int
    card_types: typing.List[CardType]
    duplicates: bool
    proportionate: bool

    def __init__(
        self,
        *,
        set: typing.Optional["Set"] = None,
        rarity: typing.Optional[typing.List[PackDistroWeight]] = None,
        qty: int = 1,
        card_types: typing.Optional[typing.List[CardType]] = None,
        duplicates: bool = False,
        proportionate: bool = False,
    ) -> None:
        super().__init__()
        self.set = set
        self.rarity = rarity or []
        self.qty = qty
        self.card_types = card_types or []
        self.duplicates = duplicates
        self.proportionate = proportionate

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "type": type(self)._slot_type_name,
            **({"set": str(self.set.id)} if self.set else {}),
            **({"rarity": [x._to_json() for x in self.rarity]} if self.rarity else {}),
            **({"qty": self.qty} if self.qty != 1 else {}),
            **(
                {"card_types": [x.value for x in self.card_types]}
                if self.card_types
                else {}
            ),
            **({"duplicates": self.duplicates} if self.duplicates else {}),
            **({"proportionate": self.proportionate} if self.proportionate else {}),
        }

    @classmethod
    def _from_json(
        cls, db: "Database", in_json: typing.Dict[str, typing.Any]
    ) -> "PackDistroSlot":
        return PackDistroSlotPool(
            set=db.sets_by_id[uuid.UUID(in_json["set"])]
            if in_json.get("set")
            else None,
            rarity=[
                PackDistroWeight(
                    rarities=[CardRarity(y) for y in x["rarities"]]
                    if x.get("rarities")
                    else None,
                    chance=x["chance"] if x.get("chance") is not None else 1,
                )
                for x in in_json["rarity"]
            ]
            if in_json.get("rarity")
            else None,
            qty=in_json["qty"] if in_json.get("qty") is not None else 1,
            card_types=[CardType(x) for x in in_json["cardTypes"]]
            if in_json.get("cardTypes")
            else None,
            duplicates=in_json["duplicates"]
            if in_json.get("duplicates") is not None
            else False,
            proportionate=in_json["proportionate"]
            if in_json.get("proportionate") is not None
            else False,
        )


class PackDistroSlotCards(PackDistroSlot):
    _slot_type_name = "guaranteedPrintings"

    cards: typing.List["CardPrinting"]

    def __init__(
        self, cards: typing.Optional[typing.List["CardPrinting"]] = None
    ) -> None:
        super().__init__()
        self.cards = cards or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "type": type(self)._slot_type_name,
            "printings": [str(x.id) for x in self.cards],
        }

    @classmethod
    def _from_json(
        cls, db: "Database", in_json: typing.Dict[str, typing.Any]
    ) -> "PackDistroSlot":
        return PackDistroSlotCards(
            cards=[db.printings_by_id[uuid.UUID(x)] for x in in_json["printings"]]
        )


class PackDistroSlotSet(PackDistroSlot):
    _slot_type_name = "guaranteedSet"

    set: "Set"

    def __init__(self, set: "Set") -> None:
        super().__init__()
        self.set = set

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "type": type(self)._slot_type_name,
            "set": str(self.set.id),
        }

    @classmethod
    def _from_json(
        cls, db: "Database", in_json: typing.Dict[str, typing.Any]
    ) -> "PackDistroSlot":
        return PackDistroSlotSet(
            set=db.sets_by_id[uuid.UUID(in_json["set"])],
        )


DISTRO_SLOT_TYPES: typing.Dict[str, typing.Type[PackDistroSlot]] = {
    clazz._slot_type_name: clazz
    for clazz in [
        PackDistroSlotPool,
        PackDistroSlotCards,
        PackDistroSlotSet,
    ]
}


class PackDistrobution:
    id: uuid.UUID
    name: typing.Optional[str]
    slots: typing.List[PackDistroSlot]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[str] = None,
        slots: typing.Optional[typing.List[PackDistroSlot]] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.slots = slots or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/distribution.json",
            "id": str(self.id),
            **({"name": self.name} if self.name else {}),
            "slots": [x._to_json() for x in self.slots],
        }


class SealedProductLocale:
    key: str
    date: typing.Optional[datetime.date]
    image: typing.Optional[str]
    db_ids: typing.List[int]

    def __init__(
        self,
        *,
        key: str,
        date: typing.Optional[datetime.date] = None,
        image: typing.Optional[str] = None,
        db_ids: typing.Optional[typing.List[int]] = None,
    ) -> None:
        self.key = key
        self.date = date
        self.image = image
        self.db_ids = db_ids or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            **({"date": self.date.isoformat()} if self.date else {}),
            **({"image": self.image} if self.image else {}),
            "externalIDs": {
                **({"dbIDs": self.db_ids} if self.db_ids else {}),
            },
        }


class SealedProductPack:
    set: "Set"
    card: typing.Optional["Card"]

    def __init__(self, *, set: "Set", card: typing.Optional["Card"] = None) -> None:
        self.set = set
        self.card = card


class SealedProductContents:
    locales: typing.List[SealedProductLocale]
    image: typing.Optional[str]
    packs: typing.Dict[SealedProductPack, int]

    def __init__(
        self,
        *,
        image: typing.Optional[str] = None,
        locales: typing.Optional[typing.List[SealedProductLocale]] = None,
        packs: typing.Optional[typing.Dict[SealedProductPack, int]] = None,
    ) -> None:
        self.image = image
        self.locales = locales or []
        self.packs = packs or {}

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            **({"locales": [x.key for x in self.locales]} if self.locales else {}),
            **({"image": self.image} if self.image else {}),
            "packs": [
                {
                    "set": str(k.set.id),
                    **({"card": str(k.card.id)} if k.card else {}),
                    **({"qty": v} if v != 1 else {}),
                }
                for k, v in self.packs.items()
            ],
        }


class SealedProduct:
    id: uuid.UUID
    date: typing.Optional[datetime.date]
    name: typing.Dict[str, str]
    locales: typing.Dict[str, SealedProductLocale]
    contents: typing.List[SealedProductContents]
    yugipedia: typing.Optional[ExternalIdPair]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        date: typing.Optional[datetime.date] = None,
        name: typing.Optional[typing.Dict[str, str]] = None,
        locales: typing.Optional[typing.Dict[str, SealedProductLocale]] = None,
        contents: typing.Optional[typing.List[SealedProductContents]] = None,
        yugipedia: typing.Optional[ExternalIdPair] = None,
    ) -> None:
        self.id = id
        self.date = date
        self.name = name or {}
        self.locales = locales or {}
        self.contents = contents or []
        self.yugipedia = yugipedia

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "id": str(self.id),
            **({"date": self.date.isoformat()} if self.date else {}),
            "name": self.name,
            **(
                {"locales": {k: v._to_json() for k, v in self.locales.items()}}
                if self.locales
                else {}
            ),
            "contents": [x._to_json() for x in self.contents],
            "externalIDs": {
                **(
                    {
                        "yugipedia": {
                            "id": self.yugipedia.id,
                            "name": self.yugipedia.name,
                        }
                    }
                    if self.yugipedia
                    else {}
                ),
            },
        }


class Series:
    id: uuid.UUID
    name: typing.Dict[str, str]
    archetype: bool
    members: typing.Set[Card]
    yugipedia: typing.Optional[ExternalIdPair]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[typing.Dict[str, str]] = None,
        archetype: bool = False,
        members: typing.Optional[typing.Set[Card]] = None,
        yugipedia: typing.Optional[ExternalIdPair] = None,
    ) -> None:
        self.id = id
        self.name = name or {}
        self.archetype = archetype
        self.members = members or set()
        self.yugipedia = yugipedia

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "archetype": self.archetype,
            "members": sorted(str(c.id) for c in self.members),
            "externalIDs": {
                **(
                    {
                        "yugipedia": {
                            "name": self.yugipedia.name,
                            "id": self.yugipedia.id,
                        }
                    }
                    if self.yugipedia is not None
                    else {}
                ),
            },
        }


class CardPrinting:
    id: uuid.UUID
    card: Card
    suffix: typing.Optional[str]
    rarity: typing.Optional[CardRarity]
    only_in_box: typing.Optional[SetBoxType]
    price: typing.Optional[float]
    language: typing.Optional[str]
    image: typing.Optional[CardImage]
    replica: bool
    qty: int

    def __init__(
        self,
        *,
        id: uuid.UUID,
        card: Card,
        suffix: typing.Optional[str] = None,
        rarity: typing.Optional[CardRarity] = None,
        only_in_box: typing.Optional[SetBoxType] = None,
        price: typing.Optional[float] = None,
        language: typing.Optional[str] = None,
        image: typing.Optional[CardImage] = None,
        replica: bool = False,
        qty: int = 1,
    ) -> None:
        self.id = id
        self.card = card
        self.suffix = suffix
        self.rarity = rarity
        self.only_in_box = only_in_box
        self.price = price
        self.language = language
        self.image = image
        self.replica = replica
        self.qty = qty

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "id": str(self.id),
            "card": str(self.card.id),
            **({"suffix": self.suffix} if self.suffix else {}),
            **({"rarity": self.rarity.value} if self.rarity else {}),
            **({"onlyInBox": self.only_in_box.value} if self.only_in_box else {}),
            **({"price": self.price} if self.price else {}),
            **({"language": self.language} if self.language else {}),
            **({"imageID": str(self.image.id)} if self.image else {}),
            **({"replica": True} if self.replica else {}),
            **({"qty": self.qty} if self.qty != 1 else {}),
        }


class SetContents:
    locales: typing.List["SetLocale"]
    formats: typing.List[Format]
    distrobution: typing.Union[None, SpecialDistroType, uuid.UUID]
    packs_per_box: typing.Optional[int]
    has_hobby_retail_differences: bool
    editions: typing.List[SetEdition]
    image: typing.Optional[str]
    box_image: typing.Optional[str]
    cards: typing.List[CardPrinting]
    removed_cards: typing.List[CardPrinting]
    ygoprodeck: typing.Optional[str]

    def __init__(
        self,
        *,
        locales: typing.Optional[typing.List["SetLocale"]] = None,
        formats: typing.Optional[typing.List[Format]] = None,
        distrobution: typing.Union[None, SpecialDistroType, uuid.UUID] = None,
        packs_per_box: typing.Optional[int] = None,
        has_hobby_retail_differences: bool = False,
        editions: typing.Optional[typing.List[SetEdition]] = None,
        image: typing.Optional[str] = None,
        box_image: typing.Optional[str] = None,
        cards: typing.Optional[typing.List[CardPrinting]] = None,
        removed_cards: typing.Optional[typing.List[CardPrinting]] = None,
        ygoprodeck: typing.Optional[str] = None,
    ) -> None:
        self.locales = locales or []
        self.formats = formats or []
        self.distrobution = distrobution
        self.packs_per_box = packs_per_box
        self.has_hobby_retail_differences = has_hobby_retail_differences
        self.editions = editions or []
        self.image = image
        self.box_image = box_image
        self.cards = cards or []
        self.removed_cards = removed_cards or []
        self.ygoprodeck = ygoprodeck

    def get_distro(
        self, db: "Database"
    ) -> typing.Union[None, SpecialDistroType, PackDistrobution]:
        if not self.distrobution:
            return None
        elif type(self.distrobution) is uuid.UUID:
            return db.distros_by_id[self.distrobution]
        elif type(self.distrobution) is SpecialDistroType:
            return self.distrobution

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        distro = None
        if type(self.distrobution) is SpecialDistroType:
            distro = self.distrobution.value
        elif type(self.distrobution) is PackDistrobution:
            distro = str(self.distrobution.id)

        return {
            **({"locales": [l.key for l in self.locales]} if self.locales else {}),
            "formats": [f.value for f in self.formats],
            **({"distrobution": distro} if self.distrobution else {}),
            **({"packsPerBox": self.packs_per_box} if self.packs_per_box else {}),
            **(
                {"hasHobbyRetailDifferences": True}
                if self.has_hobby_retail_differences
                else {}
            ),
            **({"editions": [e.value for e in self.editions]} if self.editions else {}),
            **({"image": self.image} if self.image else {}),
            **({"boxImage": self.box_image} if self.box_image else {}),
            "cards": [c._to_json() for c in self.cards],
            **(
                {"removedCards": [c._to_json() for c in self.removed_cards]}
                if self.removed_cards
                else {}
            ),
            "externalIDs": {
                **({"ygoprodeck": self.ygoprodeck} if self.ygoprodeck else {}),
            },
        }


class SetLocale:
    key: str
    language: str
    prefix: typing.Optional[str]
    date: typing.Optional[datetime.date]
    image: typing.Optional[str]
    box_image: typing.Optional[str]
    card_images: typing.Dict[SetEdition, typing.Dict[CardPrinting, str]]
    db_ids: typing.List[int]

    def __init__(
        self,
        *,
        key: str,
        language: str,
        prefix: typing.Optional[str] = None,
        date: typing.Optional[datetime.date] = None,
        image: typing.Optional[str] = None,
        box_image: typing.Optional[str] = None,
        card_images: typing.Optional[
            typing.Dict[SetEdition, typing.Dict[CardPrinting, str]]
        ] = None,
        db_ids: typing.Optional[typing.List[int]] = None,
    ) -> None:
        self.key = key
        self.language = language
        self.prefix = prefix
        self.date = date
        self.image = image
        self.box_image = box_image
        self.card_images = card_images or {}
        self.db_ids = db_ids or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "language": self.language,
            **({"prefix": self.prefix} if self.prefix else {}),
            **({"date": self.date.isoformat()} if self.date else {}),
            **({"image": self.image} if self.image else {}),
            **({"boxImage": self.box_image} if self.box_image else {}),
            "cardImages": {
                k.value: {str(kk.id): vv for kk, vv in v.items()}
                for k, v in self.card_images.items()
            },
            "externalIDs": {
                **({"dbIDs": self.db_ids} if self.db_ids else {}),
            },
        }


class Set:
    id: uuid.UUID
    date: typing.Optional[datetime.date]
    name: typing.Dict[str, str]
    locales: typing.Dict[str, SetLocale]
    contents: typing.List[SetContents]
    yugipedia: typing.Optional[ExternalIdPair]
    yugiohprices: typing.Optional[str]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        date: typing.Optional[datetime.date] = None,
        name: typing.Optional[typing.Dict[str, str]] = None,
        locales: typing.Optional[typing.Iterable[SetLocale]] = None,
        contents: typing.Optional[typing.List[SetContents]] = None,
        yugipedia: typing.Optional[ExternalIdPair] = None,
        yugiohprices: typing.Optional[str] = None,
    ) -> None:
        self.id = id
        self.date = date
        self.name = name or {}
        self.locales = {locale.key: locale for locale in locales} if locales else {}
        self.contents = contents or []
        self.yugipedia = yugipedia
        self.yugiohprices = yugiohprices

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/set.json",
            "id": str(self.id),
            **({"date": self.date.isoformat()} if self.date else {}),
            "name": self.name,
            **(
                {"locales": {k: v._to_json() for k, v in self.locales.items()}}
                if self.locales
                else {}
            ),
            "contents": [v._to_json() for v in self.contents],
            "externalIDs": {
                **(
                    {
                        "yugipedia": {
                            "name": self.yugipedia.name,
                            "id": self.yugipedia.id,
                        }
                    }
                    if self.yugipedia is not None
                    else {}
                ),
                **(
                    {"yugiohpricesName": self.yugiohprices} if self.yugiohprices else {}
                ),
            },
        }


class ManualFixupIdentifier:
    id: typing.Optional[uuid.UUID]
    name: typing.Optional[str]
    konami_id: typing.Optional[int]
    ygoprodeck_id: typing.Optional[int]
    ygoprodeck_name: typing.Optional[str]
    yugipedia_id: typing.Optional[int]
    yugipedia_name: typing.Optional[str]
    yamlyugi: typing.Optional[int]
    set: typing.Optional["ManualFixupIdentifier"]
    locale: typing.Optional[str]
    edition: typing.Optional[SetEdition]
    rarity: typing.Optional[CardRarity]
    code: typing.Optional[str]

    def __init__(self, in_json) -> None:
        self.id = None
        self.name = None
        self.konami_id = None
        self.ygoprodeck_id = None
        self.ygoprodeck_name = None
        self.yugipedia_id = None
        self.yugipedia_name = None
        self.yamlyugi = None
        self.set = None
        self.locale = None
        self.edition = None
        self.rarity = None
        self.code = None

        if type(in_json) is str:
            # either ID or name, let's find out
            try:
                self.id = uuid.UUID(in_json)
            except ValueError:
                self.name = in_json
        elif type(in_json) is dict:
            self.id = uuid.UUID(in_json["id"]) if "id" in in_json else None
            self.name = in_json.get("name")
            self.konami_id = in_json.get("konamiID")
            self.ygoprodeck_id = in_json.get("ygoprodeckID")
            self.ygoprodeck_name = in_json.get("ygoprodeckName")
            self.yugipedia_id = in_json.get("yugipediaID")
            self.yugipedia_name = in_json.get("yugipediaName")
            self.yamlyugi = in_json.get("yamlyugi")
            self.set = (
                ManualFixupIdentifier(in_json["set"]) if "set" in in_json else None
            )
            self.locale = in_json.get("locale")
            self.edition = (
                SetEdition(in_json["edition"]) if "edition" in in_json else None
            )
            self.rarity = CardRarity(in_json["rarity"]) if "rarity" in in_json else None
            self.code = in_json.get("code")
        else:
            raise ValueError(f"Bad manual-fixup identifier: {json.dumps(in_json)}")

    def to_json(self) -> typing.Union[str, typing.Dict[str, typing.Any]]:
        as_dict = {
            **({"id": str(self.id)} if self.id else {}),
            **({"name": self.name} if self.name else {}),
            **({"konamiID": self.konami_id} if self.konami_id else {}),
            **({"ygoprodeckID": self.ygoprodeck_id} if self.ygoprodeck_id else {}),
            **(
                {"ygoprodeckName": self.ygoprodeck_name} if self.ygoprodeck_name else {}
            ),
            **({"yugipediaID": self.yugipedia_id} if self.yugipedia_id else {}),
            **({"yugipediaName": self.yugipedia_name} if self.yugipedia_name else {}),
            **({"yamlyugi": self.yamlyugi} if self.yamlyugi else {}),
            **({"set": self.set.to_json()} if self.set else {}),
            **({"locale": self.locale} if self.locale else {}),
            **({"edition": self.edition.value} if self.edition else {}),
            **({"rarity": self.rarity.value} if self.rarity else {}),
            **({"code": self.code} if self.code else {}),
        }
        if len(as_dict) == 2 and "id" in as_dict and "name" in as_dict:
            return str(self.id or self.name)
        if len(as_dict) == 1 and "id" in as_dict:
            return str(self.id)
        if len(as_dict) == 1 and "name" in as_dict:
            return str(self.name)
        return as_dict

    def __str__(self) -> str:
        return json.dumps(self.to_json())


class Database:
    individuals_dir: typing.Optional[str]
    aggregates_dir: typing.Optional[str]

    increment: int
    last_yamlyugi_read: typing.Optional[datetime.datetime]
    last_yugipedia_read: typing.Optional[datetime.datetime]
    last_ygoprodeck_read: typing.Optional[datetime.datetime]

    cards: typing.List[Card]
    cards_by_id: typing.Dict[uuid.UUID, Card]
    cards_by_password: typing.Dict[str, Card]
    cards_by_yamlyugi: typing.Dict[int, Card]
    cards_by_en_name: typing.Dict[str, Card]
    cards_by_konami_cid: typing.Dict[int, Card]
    cards_by_yugipedia_id: typing.Dict[int, Card]
    cards_by_ygoprodeck_id: typing.Dict[int, Card]

    card_images_by_id: typing.Dict[uuid.UUID, CardImage]

    sets: typing.List[Set]
    sets_by_id: typing.Dict[uuid.UUID, Set]
    sets_by_en_name: typing.Dict[str, Set]
    sets_by_konami_sid: typing.Dict[int, Set]
    sets_by_yugipedia_id: typing.Dict[int, Set]
    sets_by_ygoprodeck_id: typing.Dict[str, Set]

    printings_by_id: typing.Dict[uuid.UUID, CardPrinting]
    printings_by_code: typing.Dict[str, typing.List[CardPrinting]]

    series: typing.List[Series]
    series_by_id: typing.Dict[uuid.UUID, Series]
    series_by_en_name: typing.Dict[str, Series]
    series_by_yugipedia_id: typing.Dict[int, Series]

    distros: typing.List[PackDistrobution]
    distros_by_id: typing.Dict[uuid.UUID, PackDistrobution]
    distros_by_name: typing.Dict[str, PackDistrobution]

    products: typing.List[SealedProduct]
    products_by_id: typing.Dict[uuid.UUID, SealedProduct]
    products_by_en_name: typing.Dict[str, SealedProduct]
    products_by_yugipedia_id: typing.Dict[int, SealedProduct]
    products_by_konami_pid: typing.Dict[int, SealedProduct]

    def __init__(
        self,
        *,
        individuals_dir: typing.Optional[str] = None,
        aggregates_dir: typing.Optional[str] = None,
    ):
        self.individuals_dir = individuals_dir
        self.aggregates_dir = aggregates_dir

        self.increment = 0
        self.last_yamlyugi_read = None
        self.last_yugipedia_read = None
        self.last_ygoprodeck_read = None

        self.cards = []
        self.cards_by_id = {}
        self.cards_by_password = {}
        self.cards_by_yamlyugi = {}
        self.cards_by_en_name = {}
        self.cards_by_konami_cid = {}
        self.cards_by_yugipedia_id = {}
        self.cards_by_ygoprodeck_id = {}

        self.card_images_by_id = {}

        self.sets = []
        self.sets_by_id = {}
        self.sets_by_en_name = {}
        self.sets_by_konami_sid = {}
        self.sets_by_yugipedia_id = {}
        self.sets_by_ygoprodeck_id = {}

        self.printings_by_id = {}
        self.printings_by_code = {}

        self.series = []
        self.series_by_id = {}
        self.series_by_en_name = {}
        self.series_by_yugipedia_id = {}

        self.distros = []
        self.distros_by_id = {}
        self.distros_by_name = {}

        self.products = []
        self.products_by_id = {}
        self.products_by_en_name = {}
        self.products_by_yugipedia_id = {}
        self.products_by_konami_pid = {}

    def add_card(self, card: Card):
        if card.id not in self.cards_by_id:
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
        for page in card.yugipedia_pages or []:
            self.cards_by_yugipedia_id[page.id] = card
        if card.ygoprodeck:
            self.cards_by_ygoprodeck_id[card.ygoprodeck.id] = card

        for image in card.images:
            self.card_images_by_id[image.id] = image

    def add_set(self, set_: Set):
        if set_.id not in self.sets_by_id:
            self.sets.append(set_)

        self.sets_by_id[set_.id] = set_
        if "en" in set_.name:
            self.sets_by_en_name[set_.name["en"]] = set_
        if set_.yugipedia:
            self.sets_by_yugipedia_id[set_.yugipedia.id] = set_
        for locale in set_.locales.values():
            for db_id in locale.db_ids:
                self.sets_by_konami_sid[db_id] = set_
        for content in set_.contents:
            if content.ygoprodeck:
                self.sets_by_ygoprodeck_id[content.ygoprodeck] = set_
            for printing in [*content.cards, *content.removed_cards]:
                self.printings_by_id[printing.id] = printing
                if printing.suffix:
                    for locale_id in content.locales:
                        if locale_id in set_.locales:
                            prefix = set_.locales[locale_id].prefix
                            if prefix:
                                code = prefix + printing.suffix
                                self.printings_by_code.setdefault(code, [])
                                self.printings_by_code[code].append(printing)

    def add_series(self, series: Series):
        if series.id not in self.series_by_id:
            self.series.append(series)
            self.series_by_id[series.id] = series
        if "en" in series.name:
            self.series_by_en_name[series.name["en"]] = series
        if series.yugipedia:
            self.series_by_yugipedia_id[series.yugipedia.id] = series

    def add_distro(self, distro: PackDistrobution):
        if distro.id not in self.distros_by_id:
            self.distros.append(distro)
            self.distros_by_id[distro.id] = distro
        if distro.name:
            self.distros_by_name[distro.name] = distro

    def add_product(self, product: SealedProduct):
        if product.id not in self.sets_by_id:
            self.products.append(product)

        self.products_by_id[product.id] = product
        if "en" in product.name:
            self.products_by_en_name[product.name["en"]] = product
        if product.yugipedia:
            self.products_by_yugipedia_id[product.yugipedia.id] = product
        for locale in product.locales.values():
            for db_id in locale.db_ids:
                self.products_by_konami_pid[db_id] = product

    def regenerate_backlinks(self):
        for card in self.cards:
            card.sets.clear()
            card.series.clear()
        for set_ in tqdm.tqdm(
            self.sets, total=len(self.sets), desc="Regenerating card backlinks to sets"
        ):
            for contents in set_.contents:
                for printing in contents.cards:
                    printing.card.sets.append(set_)
        for series in tqdm.tqdm(
            self.series,
            total=len(self.series),
            desc="Regenerating card backlinks to series",
        ):
            for member in series.members:
                member.series.append(series)

    def lookup_set(self, mfi: ManualFixupIdentifier) -> typing.Optional[Set]:
        result = None
        if not result and mfi.id:
            result = self.sets_by_id.get(mfi.id, result)
        if not result and mfi.konami_id:
            result = self.sets_by_konami_sid.get(mfi.konami_id, result)
        if not result and mfi.ygoprodeck_name:
            result = self.sets_by_ygoprodeck_id.get(mfi.ygoprodeck_name, result)
        if not result and mfi.yugipedia_id:
            result = self.sets_by_yugipedia_id.get(mfi.yugipedia_id, result)
        if not result and mfi.name:
            result = self.sets_by_en_name.get(mfi.name, result)
        return result

    def lookup_distro(
        self, mfi: ManualFixupIdentifier
    ) -> typing.Optional[PackDistrobution]:
        result = None
        if not result and mfi.id:
            result = self.distros_by_id.get(mfi.id, result)
        if not result and mfi.name:
            result = self.distros_by_name.get(mfi.name, result)
        return result

    def lookup_printing(
        self, mfi: ManualFixupIdentifier
    ) -> typing.Optional[CardPrinting]:
        results: typing.Set[CardPrinting] = set()

        if mfi.id:
            result = self.printings_by_id.get(mfi.id)
            if result:
                results.add(result)

        if mfi.set:
            set_ = self.lookup_set(mfi.set)
            if set_:
                printing_to_contents = {
                    p: c for c in set_.contents for p in [*c.cards, *c.removed_cards]
                }

                for content in set_.contents:
                    for printing in [*content.cards, *content.removed_cards]:
                        results.add(printing)

                card: typing.Optional[Card] = None
                if mfi.name:
                    card = self.cards_by_en_name.get(mfi.name)
                if card:
                    for result in [*results]:
                        if result.card != card and printing in results:
                            results.remove(printing)

                if mfi.code:
                    for locale in set_.locales.values():
                        for result in [*results]:
                            if (locale.prefix or "") + (
                                printing.suffix or ""
                            ) != mfi.code and printing in results:
                                results.remove(printing)

                if mfi.locale:
                    for result in [*results]:
                        if (
                            set_.locales[mfi.locale]
                            not in printing_to_contents[result].locales
                            and printing in results
                        ):
                            results.remove(printing)

                if mfi.edition:
                    for result in [*results]:
                        if (
                            SetEdition(mfi.edition)
                            not in printing_to_contents[result].editions
                            and printing in results
                        ):
                            results.remove(printing)

                if mfi.rarity:
                    for result in [*results]:
                        if (
                            result.rarity != CardRarity(mfi.rarity)
                            and printing in results
                        ):
                            results.remove(printing)

        if len(results) == 0:
            return None
        if len(results) > 1:
            raise Exception(f"Ambiguous printing MFI: {json.dumps(mfi.to_json())}")
        return next(iter(results))

    def lookup_card(self, mfi: ManualFixupIdentifier) -> typing.Optional[Card]:
        result = None
        if not result and mfi.id:
            result = self.cards_by_id.get(mfi.id, result)
        if not result and mfi.konami_id:
            result = self.cards_by_konami_cid.get(mfi.konami_id, result)
        if not result and mfi.ygoprodeck_id:
            result = self.cards_by_ygoprodeck_id.get(mfi.ygoprodeck_id, result)
        if not result and mfi.yugipedia_id:
            result = self.cards_by_yugipedia_id.get(mfi.yugipedia_id, result)
        if not result and mfi.yamlyugi:
            result = self.cards_by_yamlyugi.get(mfi.yamlyugi, result)
        if not result and mfi.name:
            result = self.cards_by_en_name.get(mfi.name, result)
        return result

    def manually_fixup_sets(self):
        for filename in tqdm.tqdm(
            os.listdir(MANUAL_SETS_DIR), desc="Applying manual fixups to sets"
        ):
            if filename.endswith(".json"):
                with open(
                    os.path.join(MANUAL_SETS_DIR, filename), encoding="utf-8"
                ) as file:
                    in_json = json.load(file)
                    for i, mfi in enumerate(
                        ManualFixupIdentifier(x) for x in in_json["sets"]
                    ):
                        set = self.lookup_set(mfi)
                        if not set:
                            logging.warn(f"Unknown set to fixup: {mfi}")
                            continue
                        for in_contents in in_json["contents"]:
                            in_locales: typing.List[str] = in_contents.get(
                                "locales", []
                            )
                            for contents in set.contents:
                                if (
                                    not in_locales
                                    or not contents.locales
                                    or any(x in in_locales for x in contents.locales)
                                ):
                                    # apply distro
                                    distro = in_contents.get("distribution")
                                    if distro:
                                        if (
                                            distro
                                            in SpecialDistroType._value2member_map_
                                        ):
                                            contents.distrobution = SpecialDistroType(
                                                distro
                                            )
                                        else:
                                            distro_mfi = ManualFixupIdentifier(distro)
                                            distro = self.lookup_distro(distro_mfi)
                                            if distro:
                                                contents.distrobution = distro.id
                                            else:
                                                logging.warn(
                                                    f"Unknown distro: {distro_mfi}"
                                                )

                                    # apply packsPerBox
                                    if "packsPerBox" in in_contents:
                                        contents.packs_per_box = in_contents[
                                            "packsPerBox"
                                        ]

                                    # apply hasHobbyRetailDifferences
                                    if "hasHobbyRetailDifferences" in in_contents:
                                        contents.has_hobby_retail_differences = (
                                            in_contents["hasHobbyRetailDifferences"]
                                        )

                                    if "perSet" in in_contents and i < len(
                                        in_contents["perSet"]
                                    ):
                                        in_per_set = in_contents["perSet"][i]

                                        # apply boxImage
                                        if "boxImage" in in_per_set:
                                            contents.box_image = in_per_set["boxImage"]

                                        # apply ygoprodeck
                                        if "ygoprodeck" in in_per_set:
                                            contents.ygoprodeck = in_per_set[
                                                "ygoprodeck"
                                            ]

    def manually_fixup_distros(self):
        for filename in tqdm.tqdm(
            os.listdir(MANUAL_DISTROS_DIR), desc="Importing pack distributions"
        ):
            if filename.endswith(".json"):
                with open(
                    os.path.join(MANUAL_DISTROS_DIR, filename), encoding="utf-8"
                ) as infile:
                    in_json = json.load(infile)

                    for in_slot in in_json["slots"]:
                        if in_slot["type"] == "pool":
                            if "set" in in_slot:
                                set_ = self.lookup_set(
                                    ManualFixupIdentifier(in_slot["set"])
                                )
                                if not set_:
                                    raise Exception(
                                        f"In pack distrobution {filename}: Set not found: {json.dumps(in_slot['set'])}"
                                    )
                                in_slot["set"] = str(set_.id)
                        elif in_slot["type"] == "guaranteedPrintings":
                            for i, in_printing in enumerate([*in_slot["printings"]]):
                                printing = self.lookup_printing(
                                    ManualFixupIdentifier(in_printing)
                                )
                                if not printing:
                                    raise Exception(
                                        f"In pack distrobution {filename}: Printing not found: {in_printing}"
                                    )
                                in_slot["printings"][i] = str(printing.id)
                        elif in_slot["type"] == "guaranteedSet":
                            set_ = self.lookup_set(
                                ManualFixupIdentifier(in_slot["set"])
                            )
                            if not set_:
                                raise Exception(
                                    f"In pack distrobution {filename}: Set not found: {json.dumps(in_slot['set'])}"
                                )
                            in_slot["set"] = str(set_.id)

                    in_id = uuid.UUID(in_json["id"])
                    if in_id in self.distros_by_id:
                        self.distros = [x for x in self.distros if x.id != in_id]
                        del self.distros_by_id[in_id]
                    self.add_distro(self._load_distro(in_json))

    def manually_fixup_products(self):
        for filename in tqdm.tqdm(
            os.listdir(MANUAL_PRODUCTS_DIR), desc="Importing sealed products"
        ):
            if filename.endswith(".json"):
                with open(
                    os.path.join(MANUAL_PRODUCTS_DIR, filename), encoding="utf-8"
                ) as infile:
                    in_json = json.load(infile)

                    for in_content in in_json["contents"]:
                        for in_pack in in_content["packs"]:
                            set_ = self.lookup_set(
                                ManualFixupIdentifier(in_pack["set"])
                            )
                            if not set_:
                                raise Exception(
                                    f"In sealed product {filename}: Set not found: {json.dumps(in_pack['set'])}"
                                )
                            in_pack["set"] = str(set_.id)

                            card = self.lookup_card(
                                ManualFixupIdentifier(in_pack["card"])
                            )
                            if not card:
                                raise Exception(
                                    f"In sealed product {filename}: Card not found: {json.dumps(in_pack['card'])}"
                                )
                            in_pack["card"] = str(card.id)

                    in_id = uuid.UUID(in_json["id"])
                    if in_id in self.products_by_id:
                        self.products = [x for x in self.products if x.id != in_id]
                        del self.products_by_id[in_id]
                    self.add_product(self._load_product(in_json))

    def _save_meta_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": "https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v1/meta.json",
            "version": SCHEMA_VERSION,
            "increment": self.increment,
            **(
                {"lastYamlyugiRead": self.last_yamlyugi_read.isoformat()}
                if self.last_yamlyugi_read
                else {}
            ),
            **(
                {"lastYugipediaRead": self.last_yugipedia_read.isoformat()}
                if self.last_yugipedia_read
                else {}
            ),
            **(
                {"lastYGOProDeckRead": self.last_ygoprodeck_read.isoformat()}
                if self.last_ygoprodeck_read
                else {}
            ),
        }

    def _load_meta_json(self, meta_json: typing.Dict[str, typing.Any]):
        self.increment = meta_json["increment"]
        self.last_yamlyugi_read = (
            datetime.datetime.fromisoformat(meta_json["lastYamlyugiRead"])
            if "lastYamlyugiRead" in meta_json
            else None
        )
        self.last_yugipedia_read = (
            datetime.datetime.fromisoformat(meta_json["lastYugipediaRead"])
            if "lastYugipediaRead" in meta_json
            else None
        )
        self.last_ygoprodeck_read = (
            datetime.datetime.fromisoformat(meta_json["lastYGOProDeckRead"])
            if "lastYGOProDeckRead" in meta_json
            else None
        )

    def save(
        self,
        *,
        generate_individuals: bool,
        generate_aggregates: bool,
    ):
        self.increment += 1

        if generate_individuals and self.individuals_dir is None:
            raise Exception("No output directory for individuals configured!")

        if generate_individuals and self.individuals_dir is not None:
            os.makedirs(self.individuals_dir, exist_ok=True)
            with open(
                os.path.join(self.individuals_dir, META_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(self._save_meta_json(), outfile, indent=2)

            with open(
                os.path.join(self.individuals_dir, CARDLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump([str(card.id) for card in self.cards], outfile, indent=2)
            os.makedirs(
                os.path.join(self.individuals_dir, CARDS_DIRNAME), exist_ok=True
            )
            for card in tqdm.tqdm(self.cards, desc="Saving individual cards"):
                self._save_card(card)

            with open(
                os.path.join(self.individuals_dir, SETLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump([str(set.id) for set in self.sets], outfile, indent=2)
            os.makedirs(os.path.join(self.individuals_dir, SETS_DIRNAME), exist_ok=True)
            for set in tqdm.tqdm(self.sets, desc="Saving individual sets"):
                self._save_set(set)

            with open(
                os.path.join(self.individuals_dir, SERIESLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump([str(series.id) for series in self.series], outfile, indent=2)
            os.makedirs(
                os.path.join(self.individuals_dir, SERIES_DIRNAME), exist_ok=True
            )
            for series in tqdm.tqdm(self.series, desc="Saving individual series"):
                self._save_series(series)

            with open(
                os.path.join(self.individuals_dir, DISTROLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [str(distro.id) for distro in self.distros], outfile, indent=2
                )
            os.makedirs(
                os.path.join(self.individuals_dir, DISTROS_DIRNAME), exist_ok=True
            )
            for distro in tqdm.tqdm(
                self.distros, desc="Saving individual pack distributions"
            ):
                self._save_distro(distro)

            with open(
                os.path.join(self.individuals_dir, PRODUCTLIST_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [str(product.id) for product in self.products], outfile, indent=2
                )
            os.makedirs(
                os.path.join(self.individuals_dir, PRODUCTS_DIRNAME), exist_ok=True
            )
            for product in tqdm.tqdm(
                self.products, desc="Saving individual sealed products"
            ):
                self._save_product(product)

        if generate_aggregates and self.aggregates_dir is None:
            raise Exception("No output directory for aggregates configured!")

        if generate_aggregates and self.aggregates_dir is not None:
            os.makedirs(self.aggregates_dir, exist_ok=True)
            with open(
                os.path.join(self.aggregates_dir, META_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(self._save_meta_json(), outfile, indent=2)

            with open(
                os.path.join(self.aggregates_dir, AGG_CARDS_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [
                        *tqdm.tqdm(
                            (x.to_json() for x in self.cards),
                            total=len(self.cards),
                            desc="Saving aggregate cards",
                        )
                    ],
                    outfile,
                    indent=2,
                )

            with open(
                os.path.join(self.aggregates_dir, AGG_SETS_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [
                        *tqdm.tqdm(
                            (x._to_json() for x in self.sets),
                            total=len(self.sets),
                            desc="Saving aggregate sets",
                        )
                    ],
                    outfile,
                    indent=2,
                )

            with open(
                os.path.join(self.aggregates_dir, AGG_SERIES_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [
                        *tqdm.tqdm(
                            (x._to_json() for x in self.series),
                            total=len(self.series),
                            desc="Saving aggregate series",
                        )
                    ],
                    outfile,
                    indent=2,
                )

            with open(
                os.path.join(self.aggregates_dir, AGG_DISTROS_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [
                        *tqdm.tqdm(
                            (x._to_json() for x in self.distros),
                            total=len(self.distros),
                            desc="Saving aggregate pack distributions",
                        )
                    ],
                    outfile,
                    indent=2,
                )

            with open(
                os.path.join(self.aggregates_dir, AGG_PRODUCTS_FILENAME),
                "w",
                encoding="utf-8",
            ) as outfile:
                json.dump(
                    [
                        *tqdm.tqdm(
                            (x._to_json() for x in self.products),
                            total=len(self.products),
                            desc="Saving aggregate sealed products",
                        )
                    ],
                    outfile,
                    indent=2,
                )

    def _save_card(self, card: Card):
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        with open(
            os.path.join(self.individuals_dir, CARDS_DIRNAME, str(card.id) + ".json"),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(card.to_json(), outfile, indent=2)

    def _load_card(self, rawcard: typing.Dict[str, typing.Any]) -> Card:
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
            character=rawcard["character"] if "character" in rawcard else None,
            skill_type=rawcard["skillType"] if "skillType" in rawcard else None,
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
            illegal=rawcard.get("illegal", False),
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
            yugipedia_pages=[
                ExternalIdPair(x["name"], x["id"])
                for x in rawcard["externalIDs"]["yugipedia"]
            ]
            if "yugipedia" in rawcard["externalIDs"]
            else None,
            db_id=rawcard["externalIDs"].get("dbID"),
            ygoprodeck=ExternalIdPair(
                name=rawcard["externalIDs"]["ygoprodeck"]["name"],
                id=rawcard["externalIDs"]["ygoprodeck"]["id"],
            )
            if "ygoprodeck" in rawcard["externalIDs"]
            else None,
            yugiohprices_name=rawcard["externalIDs"].get("yugiohpricesName"),
            yamlyugi_id=rawcard["externalIDs"].get("yamlyugiID"),
        )

    def _load_cardlist(self) -> typing.List[uuid.UUID]:
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        if not os.path.exists(os.path.join(self.individuals_dir, CARDLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, CARDLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _save_set(self, set_: Set):
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        with open(
            os.path.join(self.individuals_dir, SETS_DIRNAME, str(set_.id) + ".json"),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(set_._to_json(), outfile, indent=2)

    def _save_series(self, series: Series):
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        with open(
            os.path.join(
                self.individuals_dir, SERIES_DIRNAME, str(series.id) + ".json"
            ),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(series._to_json(), outfile, indent=2)

    def _load_printing(
        self,
        rawprinting: typing.Dict[str, typing.Any],
        printings: typing.Dict[uuid.UUID, CardPrinting],
    ) -> CardPrinting:
        result = CardPrinting(
            id=uuid.UUID(rawprinting["id"]),
            card=self.cards_by_id[uuid.UUID(rawprinting["card"])],
            suffix=rawprinting.get("suffix"),
            rarity=CardRarity(rawprinting["rarity"])
            if "rarity" in rawprinting
            else None,
            only_in_box=SetBoxType(rawprinting["onlyInBox"])
            if "onlyInBox" in rawprinting
            else None,
            price=rawprinting.get("price"),
            language=rawprinting.get("language"),
            image=self.card_images_by_id[uuid.UUID(rawprinting["imageID"])]
            if "imageID" in rawprinting
            else None,
            replica=rawprinting["replica"] if "replica" in rawprinting else False,
            qty=rawprinting["qty"] if "qty" in rawprinting else 1,
        )
        printings[result.id] = result
        return result

    def _load_set(self, rawset: typing.Dict[str, typing.Any]) -> Set:
        printings: typing.Dict[uuid.UUID, CardPrinting] = {}

        contents: typing.List[typing.Tuple[SetContents, typing.List[str]]] = []
        for content in rawset["contents"]:
            contents.append(
                (
                    SetContents(
                        formats=[Format(v) for v in content["formats"]],
                        distrobution=(
                            SpecialDistroType(content["distrobution"])
                            if content["distrobution"]
                            in SpecialDistroType._value2member_map_
                            else uuid.UUID(content["distrobution"])
                        )
                        if content.get("distrobution")
                        and content["distrobution"]
                        in SpecialDistroType._value2member_map_
                        else None,
                        packs_per_box=content.get("packsPerBox"),
                        has_hobby_retail_differences=content.get(
                            "hasHobbyRetailDifferences", False
                        ),
                        editions=[SetEdition(v) for v in content.get("editions", [])],
                        image=content.get("image"),
                        box_image=content.get("boxImage"),
                        cards=[
                            self._load_printing(v, printings) for v in content["cards"]
                        ],
                        removed_cards=[
                            self._load_printing(v, printings)
                            for v in content.get("removedCards", [])
                        ],
                        ygoprodeck=content["externalIDs"]["ygoprodeck"]
                        if "ygoprodeck" in content["externalIDs"]
                        else None,
                    ),
                    content.get("locales", []),
                )
            )

        locales = {
            k: SetLocale(
                key=k,
                language=v["language"],
                prefix=v.get("prefix"),
                date=datetime.date.fromisoformat(v["date"]) if "date" in v else None,
                image=v.get("image"),
                box_image=v.get("boxImage"),
                card_images={
                    SetEdition(k): {
                        printings[uuid.UUID(kk)]: vv
                        for kk, vv in v.items()
                        if uuid.UUID(kk) in printings
                    }
                    for k, v in v.get("cardImages", {}).items()
                },
                db_ids=v["externalIDs"].get("dbIDs"),
            )
            for k, v in rawset.get("locales", {}).items()
        }

        for content, locale_names in contents:
            content.locales = [
                locales[locale_name]
                for locale_name in locale_names
                if locale_name in locales
            ]

        return Set(
            id=uuid.UUID(rawset["id"]),
            date=datetime.date.fromisoformat(rawset["date"])
            if "date" in rawset
            else None,
            name=rawset["name"],
            locales=locales.values(),
            contents=[v[0] for v in contents],
            yugipedia=ExternalIdPair(
                rawset["externalIDs"]["yugipedia"]["name"],
                rawset["externalIDs"]["yugipedia"]["id"],
            )
            if "yugipedia" in rawset["externalIDs"]
            else None,
        )

    def _load_setlist(self) -> typing.List[uuid.UUID]:
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None

        if not os.path.exists(os.path.join(self.individuals_dir, SETLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, SETLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _load_series(self, rawseries: typing.Dict[str, typing.Any]) -> Series:
        return Series(
            id=uuid.UUID(rawseries["id"]),
            name=rawseries["name"],
            archetype=rawseries["archetype"],
            members={self.cards_by_id[uuid.UUID(x)] for x in rawseries["members"]},
            yugipedia=ExternalIdPair(
                rawseries["externalIDs"]["yugipedia"]["name"],
                rawseries["externalIDs"]["yugipedia"]["id"],
            )
            if "yugipedia" in rawseries["externalIDs"]
            else None,
        )

    def _load_serieslist(self) -> typing.List[uuid.UUID]:
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        if not os.path.exists(os.path.join(self.individuals_dir, SERIESLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, SERIESLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _save_distro(self, distro: PackDistrobution):
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        with open(
            os.path.join(
                self.individuals_dir, DISTROS_DIRNAME, str(distro.id) + ".json"
            ),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(distro._to_json(), outfile, indent=2)

    def _load_distro(self, rawdistro: typing.Dict[str, typing.Any]) -> PackDistrobution:
        return PackDistrobution(
            id=uuid.UUID(rawdistro["id"]),
            name=rawdistro["name"] if rawdistro.get("name") else None,
            slots=[
                DISTRO_SLOT_TYPES[x["type"]]._from_json(self, x)
                for x in rawdistro["slots"]
            ],
        )

    def _load_distrolist(self) -> typing.List[uuid.UUID]:
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        if not os.path.exists(os.path.join(self.individuals_dir, DISTROLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, DISTROLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _load_product(self, rawproduct: typing.Dict[str, typing.Any]) -> SealedProduct:
        locales = {
            k: SealedProductLocale(
                key=k,
                date=datetime.date.fromisoformat(rawlocale["date"])
                if rawlocale.get("date")
                else None,
                image=rawlocale.get("image"),
                db_ids=rawlocale["externalIDs"].get("dbIDs", []),
            )
            for k, rawlocale in rawproduct.get("locales", {}).items()
        }

        return SealedProduct(
            id=uuid.UUID(rawproduct["id"]),
            name=rawproduct["name"],
            date=datetime.date.fromisoformat(rawproduct["date"])
            if rawproduct.get("date")
            else None,
            locales=locales,
            contents=[
                SealedProductContents(
                    image=rawcontents.get("image"),
                    locales=[locales[x] for x in rawcontents.get("locales", [])],
                    packs={
                        SealedProductPack(
                            set=self.sets_by_id[uuid.UUID(rawpack["set"])],
                            card=self.cards_by_id[uuid.UUID(rawpack["card"])]
                            if "card" in rawpack
                            else None,
                        ): rawpack.get("qty", 1)
                        for rawpack in rawcontents["packs"]
                    },
                )
                for rawcontents in rawproduct["contents"]
            ],
            yugipedia=ExternalIdPair(
                rawproduct["externalIDs"]["yugipedia"]["name"],
                rawproduct["externalIDs"]["yugipedia"]["id"],
            )
            if "yugipedia" in rawproduct.get("externalIDs", {})
            else None,
        )

    def _load_productlist(self) -> typing.List[uuid.UUID]:
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        if not os.path.exists(os.path.join(self.individuals_dir, PRODUCTLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, PRODUCTLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _save_product(self, product: SealedProduct):
        if typing.TYPE_CHECKING:
            assert self.individuals_dir is not None
        with open(
            os.path.join(
                self.individuals_dir, PRODUCTS_DIRNAME, str(product.id) + ".json"
            ),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(product._to_json(), outfile, indent=2)


def load_from_file(
    *,
    individuals_dir: typing.Optional[str] = None,
    aggregates_dir: typing.Optional[str] = None,
) -> Database:
    """Load a :class:`ygojson.database.Database` from file.

    :param individuals_dir: A directory containing individuals, defaults to None
    :param aggregates_dir: A directory containing aggregates, defaults to None
    """

    if aggregates_dir is None and individuals_dir is None:
        raise Exception("load_from_file requires at least one data directory!")

    result = Database(aggregates_dir=aggregates_dir, individuals_dir=individuals_dir)

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, META_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, META_FILENAME), encoding="utf-8"
        ) as outfile:
            result._load_meta_json(json.load(outfile))
    elif individuals_dir is not None and os.path.exists(
        os.path.join(individuals_dir, META_FILENAME)
    ):
        with open(
            os.path.join(individuals_dir, META_FILENAME), encoding="utf-8"
        ) as outfile:
            result._load_meta_json(json.load(outfile))

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, AGG_CARDS_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, AGG_CARDS_FILENAME), encoding="utf-8"
        ) as outfile:
            for card_json in tqdm.tqdm(json.load(outfile), desc="Loading cards"):
                card = result._load_card(card_json)
                result.add_card(card)
    elif individuals_dir is not None:
        for card_id in tqdm.tqdm(result._load_cardlist(), desc="Loading cards"):
            with open(
                os.path.join(individuals_dir, CARDS_DIRNAME, str(card_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                card = result._load_card(json.load(outfile))
            result.add_card(card)

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, AGG_SETS_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, AGG_SETS_FILENAME), encoding="utf-8"
        ) as outfile:
            for set_json in tqdm.tqdm(json.load(outfile), desc="Loading sets"):
                set_ = result._load_set(set_json)
                result.add_set(set_)
    elif individuals_dir is not None:
        for set_id in tqdm.tqdm(result._load_setlist(), desc="Loading sets"):
            with open(
                os.path.join(individuals_dir, SETS_DIRNAME, str(set_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                set_ = result._load_set(json.load(outfile))
            result.add_set(set_)

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, AGG_SERIES_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, AGG_SERIES_FILENAME), encoding="utf-8"
        ) as outfile:
            for series_json in tqdm.tqdm(json.load(outfile), desc="Loading series"):
                series = result._load_series(series_json)
                result.add_series(series)
    elif individuals_dir is not None:
        for series_id in tqdm.tqdm(result._load_serieslist(), desc="Loading series"):
            with open(
                os.path.join(individuals_dir, SERIES_DIRNAME, str(series_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                series = result._load_series(json.load(outfile))
            result.add_series(series)

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, AGG_DISTROS_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, AGG_DISTROS_FILENAME), encoding="utf-8"
        ) as outfile:
            for distro_json in tqdm.tqdm(
                json.load(outfile), desc="Loading pack distributions"
            ):
                distro = result._load_distro(distro_json)
                result.add_distro(distro)
    elif individuals_dir is not None:
        for series_id in tqdm.tqdm(
            result._load_distrolist(), desc="Loading pack distributions"
        ):
            with open(
                os.path.join(
                    individuals_dir, DISTROS_DIRNAME, str(series_id) + ".json"
                ),
                encoding="utf-8",
            ) as outfile:
                distro = result._load_distro(json.load(outfile))
            result.add_distro(distro)

    if aggregates_dir is not None and os.path.exists(
        os.path.join(aggregates_dir, AGG_PRODUCTS_FILENAME)
    ):
        with open(
            os.path.join(aggregates_dir, AGG_PRODUCTS_FILENAME), encoding="utf-8"
        ) as outfile:
            for product_json in tqdm.tqdm(
                json.load(outfile), desc="Loading sealed products"
            ):
                product = result._load_product(product_json)
                result.add_product(product)
    elif individuals_dir is not None:
        for series_id in tqdm.tqdm(
            result._load_productlist(), desc="Loading sealed products"
        ):
            with open(
                os.path.join(
                    individuals_dir, PRODUCTS_DIRNAME, str(series_id) + ".json"
                ),
                encoding="utf-8",
            ) as outfile:
                product = result._load_product(json.load(outfile))
            result.add_product(product)

    return result


REPOSITORY = (
    f"https://github.com/iconmaster5326/YGOJSON/releases/download/v{SCHEMA_VERSION}"
)
LAST_MODIFIED_HEADER = "Last-Modified"


def load_from_internet(
    *,
    individuals_dir: typing.Optional[str] = None,
    aggregates_dir: typing.Optional[str] = None,
    repository: str = REPOSITORY,
) -> Database:
    """Load a :class:`ygojson.database.Database` from Internet sources.
    This places files into the :arg:`individuals_dir` and :arg:`aggregates_dir` specified.
    This also produces ZIP files in your temporary directory, and tries not to redownload up-to-date files.

    :param individuals_dir: A directory where the individualized data will go, defaults to None
    :param aggregates_dir: A directory where the aggregated data will go, defaults to None
    :param url: The URL to get the data ZIP files from, defaults to the official YGOJSON URL
    """

    def getzip(name: str, dest: str):
        with tqdm.tqdm(
            total=3, desc=f"Downloading {name}s from server"
        ) as progress_bar:
            zipname = name + ".zip"
            zippath = os.path.join(TEMP_DIR, zipname)
            last_modified = datetime.datetime.now()
            zip_already_exists = os.path.exists(zippath)

            if zip_already_exists:
                response = requests.head(repository + "/" + zipname, stream=True)
                if not response.ok:
                    response.raise_for_status()
                if LAST_MODIFIED_HEADER in response.headers:
                    last_modified = datetime.datetime.fromisoformat(
                        response.headers[LAST_MODIFIED_HEADER]
                    )
            progress_bar.update(1)

            if (
                not zip_already_exists
                or last_modified.timestamp() > os.stat(zippath).st_mtime
            ):
                response = requests.get(repository + "/" + zipname, stream=True)
                if not response.ok:
                    response.raise_for_status()
                with open(zippath, "wb") as file:
                    for chunk in response.iter_content(chunk_size=None):
                        file.write(chunk)
            progress_bar.update(1)

            with open(zippath, "rb") as file, zipfile.ZipFile(file) as zip:
                zip.extractall(dest)
            progress_bar.update(1)

    if individuals_dir is not None:
        getzip("individual", individuals_dir)

    if aggregates_dir is not None:
        getzip("aggregate", aggregates_dir)

    return load_from_file(
        individuals_dir=individuals_dir, aggregates_dir=aggregates_dir
    )
