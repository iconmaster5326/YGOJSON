import datetime
import enum
import json
import os
import os.path
import typing
import uuid

import tqdm

SCHEMA_VERSION = 1

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TEMP_DIR = os.path.join(ROOT_DIR, "temp")
DATA_DIR = os.path.join(ROOT_DIR, "data")
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


class PackDistrobution:
    id: uuid.UUID


class Series:
    id: uuid.UUID
    name: typing.Dict[str, str]
    archetype: bool
    members: typing.Set[Card]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[typing.Dict[str, str]] = None,
        archetype: bool = False,
        members: typing.Optional[typing.Set[Card]] = None,
    ) -> None:
        self.id = id
        self.name = name or {}
        self.archetype = archetype
        self.members = members or set()

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "archetype": self.archetype,
            "members": sorted(str(c.id) for c in self.members),
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
        }


class SetContents:
    locales: typing.List["SetLocale"]
    formats: typing.List[Format]
    distrobution: typing.Union[None, PackDistrobution, SpecialDistroType]
    packs_per_box: typing.Optional[int]
    has_hobby_retail_differences: bool
    editions: typing.List[SetEdition]
    image: typing.Optional[str]
    box_image: typing.Optional[str]
    cards: typing.List[CardPrinting]
    removed_cards: typing.List[CardPrinting]
    ygoprodeck: typing.Optional[ExternalIdPair]

    def __init__(
        self,
        *,
        locales: typing.Optional[typing.List["SetLocale"]] = None,
        formats: typing.Optional[typing.List[Format]] = None,
        distrobution: typing.Union[None, PackDistrobution, SpecialDistroType] = None,
        packs_per_box: typing.Optional[int] = None,
        has_hobby_retail_differences: bool = False,
        editions: typing.Optional[typing.List[SetEdition]] = None,
        image: typing.Optional[str] = None,
        box_image: typing.Optional[str] = None,
        cards: typing.Optional[typing.List[CardPrinting]] = None,
        removed_cards: typing.Optional[typing.List[CardPrinting]] = None,
        ygoprodeck: typing.Optional[ExternalIdPair] = None,
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
                **(
                    {
                        "ygoprodeck": {
                            "name": self.ygoprodeck.name,
                            "id": self.ygoprodeck.id,
                        }
                    }
                    if self.ygoprodeck
                    else {}
                ),
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
    name: typing.Dict[str, str]
    locales: typing.Dict[str, SetLocale]
    contents: typing.List[SetContents]
    yugipedia: typing.Optional[ExternalIdPair]
    yugiohprices: typing.Optional[str]

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[typing.Dict[str, str]] = None,
        locales: typing.Optional[typing.Iterable[SetLocale]] = None,
        contents: typing.Optional[typing.List[SetContents]] = None,
        yugipedia: typing.Optional[ExternalIdPair] = None,
        yugiohprices: typing.Optional[str] = None,
    ) -> None:
        self.id = id
        self.name = name or {}
        self.locales = {locale.key: locale for locale in locales} if locales else {}
        self.contents = contents or []
        self.yugipedia = yugipedia
        self.yugiohprices = yugiohprices

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/set.json",
            "id": str(self.id),
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


class Database:
    individuals_dir: str
    aggregates_dir: str

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
    cards_by_yugipedia_name_normalized: typing.Dict[str, Card]
    cards_by_ygoprodeck_id: typing.Dict[int, Card]

    card_images_by_id: typing.Dict[uuid.UUID, CardImage]

    sets: typing.List[Set]
    sets_by_id: typing.Dict[uuid.UUID, Set]
    sets_by_en_name: typing.Dict[str, Set]
    sets_by_konami_sid: typing.Dict[int, Set]
    sets_by_yugipedia_id: typing.Dict[int, Set]
    sets_by_ygoprodeck_id: typing.Dict[int, Set]

    printings_by_id: typing.Dict[uuid.UUID, CardPrinting]
    printings_by_code: typing.Dict[str, typing.List[CardPrinting]]

    series: typing.List[Series]
    series_by_id: typing.Dict[uuid.UUID, Series]
    series_by_en_name: typing.Dict[str, Series]

    def __init__(
        self, *, individuals_dir: str = DATA_DIR, aggregates_dir: str = AGGREGATE_DIR
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
                self.sets_by_ygoprodeck_id[content.ygoprodeck.id] = set_
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
        generate_individuals: bool = True,
        generate_aggregates: bool = True,
    ):
        self.increment += 1

        if generate_individuals:
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

        if generate_aggregates:
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

    def _save_card(self, card: Card):
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
        if not os.path.exists(os.path.join(self.individuals_dir, CARDLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, CARDLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]

    def _save_set(self, set_: Set):
        with open(
            os.path.join(self.individuals_dir, SETS_DIRNAME, str(set_.id) + ".json"),
            "w",
            encoding="utf-8",
        ) as outfile:
            json.dump(set_._to_json(), outfile, indent=2)

    def _save_series(self, series: Series):
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
                        # TODO: handle distrobution when it's a UUID
                        distrobution=SpecialDistroType(content["distrobution"])
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
                        ygoprodeck=ExternalIdPair(
                            content["externalIDs"]["ygoprodeck"]["name"],
                            content["externalIDs"]["ygoprodeck"]["id"],
                        )
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
        )

    def _load_serieslist(self) -> typing.List[uuid.UUID]:
        if not os.path.exists(os.path.join(self.individuals_dir, SERIESLIST_FILENAME)):
            return []
        with open(
            os.path.join(self.individuals_dir, SERIESLIST_FILENAME), encoding="utf-8"
        ) as outfile:
            return [uuid.UUID(x) for x in json.load(outfile)]


def load_database(
    *,
    individuals_dir: str = DATA_DIR,
    aggregates_dir: str = AGGREGATE_DIR,
) -> Database:
    result = Database(aggregates_dir=aggregates_dir, individuals_dir=individuals_dir)

    if os.path.exists(os.path.join(aggregates_dir, META_FILENAME)):
        with open(
            os.path.join(aggregates_dir, META_FILENAME), encoding="utf-8"
        ) as outfile:
            result._load_meta_json(json.load(outfile))
    elif os.path.exists(os.path.join(individuals_dir, META_FILENAME)):
        with open(
            os.path.join(individuals_dir, META_FILENAME), encoding="utf-8"
        ) as outfile:
            result._load_meta_json(json.load(outfile))

    if os.path.exists(os.path.join(aggregates_dir, AGG_CARDS_FILENAME)):
        with open(
            os.path.join(aggregates_dir, AGG_CARDS_FILENAME), encoding="utf-8"
        ) as outfile:
            for card_json in tqdm.tqdm(json.load(outfile), desc="Loading cards"):
                card = result._load_card(card_json)
                result.add_card(card)
    else:
        for card_id in tqdm.tqdm(result._load_cardlist(), desc="Loading cards"):
            with open(
                os.path.join(individuals_dir, CARDS_DIRNAME, str(card_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                card = result._load_card(json.load(outfile))
            result.add_card(card)

    if os.path.exists(os.path.join(aggregates_dir, AGG_SETS_FILENAME)):
        with open(
            os.path.join(aggregates_dir, AGG_SETS_FILENAME), encoding="utf-8"
        ) as outfile:
            for set_json in tqdm.tqdm(json.load(outfile), desc="Loading sets"):
                set_ = result._load_set(set_json)
                result.add_set(set_)
    else:
        for set_id in tqdm.tqdm(result._load_setlist(), desc="Loading sets"):
            with open(
                os.path.join(individuals_dir, SETS_DIRNAME, str(set_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                set_ = result._load_set(json.load(outfile))
            result.add_set(set_)

    if os.path.exists(os.path.join(aggregates_dir, AGG_SERIES_FILENAME)):
        with open(
            os.path.join(aggregates_dir, AGG_SERIES_FILENAME), encoding="utf-8"
        ) as outfile:
            for series_json in tqdm.tqdm(json.load(outfile), desc="Loading series"):
                series = result._load_series(series_json)
                result.add_series(series)
    else:
        for series_id in tqdm.tqdm(result._load_serieslist(), desc="Loading series"):
            with open(
                os.path.join(individuals_dir, SERIES_DIRNAME, str(series_id) + ".json"),
                encoding="utf-8",
            ) as outfile:
                series = result._load_series(json.load(outfile))
            result.add_series(series)

    return result
