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

from .version import __version__

SCHEMA_VERSION = 1
"""The version of the JSON schema we are currently at."""

USER_AGENT = f"YGOJSON/{__version__} (https://github.com/iconmaster5326/YGOJSON)"
"""The User-Agent string we use when making requests."""

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
"""The directory at which YGOJSON is installed."""

TEMP_DIR = os.path.join(ROOT_DIR if os.access(ROOT_DIR, os.W_OK) else os.curdir, "temp")
"""A temporary directory in which to place cache files. Very important for caching Yugipedia!"""

DATA_DIR = os.path.join(ROOT_DIR if os.access(ROOT_DIR, os.W_OK) else os.curdir, "data")
"""The default directory JSON data is placed into."""

MANUAL_DATA_DIR = os.path.join(ROOT_DIR, "manual-data")
"""The root directory of manual fixups."""

INDIVIDUAL_DIR = os.path.join(DATA_DIR, "individual")
"""The default directory individualized JSON data is placed into."""

AGGREGATE_DIR = os.path.join(DATA_DIR, "aggregate")
"""The default directory aggregated JSON data is placed into."""

META_FILENAME = "meta.json"
"""The filename of the meta JSON, containing meta-information for the database."""

CARDLIST_FILENAME = "cards.json"
"""The filename of the card list, for individualized JSON output."""

CARDS_DIRNAME = "cards"
"""The sub-directory of `INDIVIDUAL_DIR` in which individualized card JSON is placed."""

AGG_CARDS_FILENAME = "cards.json"
"""The filename of the card list, for aggregated JSON output."""

SETLIST_FILENAME = "sets.json"
"""The filename of the set list, for individualized JSON output."""

SETS_DIRNAME = "sets"
"""The sub-directory of `INDIVIDUAL_DIR` in which individualized set JSON is placed."""

AGG_SETS_FILENAME = "sets.json"
"""The filename of the set list, for aggregated JSON output."""

SERIESLIST_FILENAME = "series.json"
"""The filename of the series list, for individualized JSON output."""

SERIES_DIRNAME = "series"
"""The sub-directory of `INDIVIDUAL_DIR` in which individualized series JSON is placed."""

AGG_SERIES_FILENAME = "series.json"
"""The filename of the series list, for aggregated JSON output."""

DISTROLIST_FILENAME = "distributions.json"
"""The filename of the distribution list, for individualized JSON output."""

DISTROS_DIRNAME = "distributions"
"""The sub-directory of `INDIVIDUAL_DIR` in which individualized distribution JSON is placed."""

AGG_DISTROS_FILENAME = "distributions.json"
"""The filename of the distribution list, for aggregated JSON output."""

PRODUCTLIST_FILENAME = "sealedProducts.json"
"""The filename of the sealed product list, for individualized JSON output."""

PRODUCTS_DIRNAME = "sealedProducts"
"""The sub-directory of `INDIVIDUAL_DIR` in which individualized sealed product JSON is placed."""

AGG_PRODUCTS_FILENAME = "sealedProducts.json"
"""The filename of the sealed product list, for aggregated JSON output."""

MANUAL_SETS_DIR = os.path.join(MANUAL_DATA_DIR, "sets")
"""The directory containing manual set fixup data."""

MANUAL_DISTROS_DIR = os.path.join(MANUAL_DATA_DIR, "distributions")
"""The directory containing manual distribution fixup data."""

MANUAL_PRODUCTS_DIR = os.path.join(MANUAL_DATA_DIR, "sealed-products")
"""The directory containing manual sealed product fixup data."""


class CardType(enum.Enum):
    """The overarching type of :class:`Card`: Monster, spell, trap, etc."""

    MONSTER = "monster"
    SPELL = "spell"
    TRAP = "trap"
    TOKEN = "token"
    SKILL = "skill"


class Attribute(enum.Enum):
    """The attribute of monster/token :class:`Card`s."""

    LIGHT = "light"
    DARK = "dark"
    FIRE = "fire"
    WATER = "water"
    WIND = "wind"
    EARTH = "earth"
    DIVINE = "divine"


class MonsterCardType(enum.Enum):
    """The summoning type of a monster :class:`Card`: Ritual, fusion, xyz, etc."""

    RITUAL = "ritual"
    FUSION = "fusion"
    SYNCHRO = "synchro"
    XYZ = "xyz"
    PENDULUM = "pendulum"
    LINK = "link"


class Race(enum.Enum):
    """The type of a monster :class:`Card`: Beast, zombie, cyberse, etc."""

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
    """A classification of a monster :class:`Card`: Normal, effect, tuner, etc."""

    NORMAL = "normal"
    EFFECT = "effect"
    PENDULUM = "pendulum"
    TUNER = "tuner"
    SPECIALSUMMON = "specialsummon"


class Ability(enum.Enum):
    """An ability word of a monster :class:`Card`: Toon, spirit, etc."""

    TOON = "toon"
    SPIRIT = "spirit"
    UNION = "union"
    GEMINI = "gemini"
    FLIP = "flip"


class LinkArrow(enum.Enum):
    """A link arrow in `MonsterCardType.LINK` monster :class:`Card`s."""

    TOPLEFT = "topleft"
    TOPCENTER = "topcenter"
    TOPRIGHT = "topright"
    MIDDLELEFT = "middleleft"
    MIDDLERIGHT = "middleright"
    BOTTOMLEFT = "bottomleft"
    BOTTOMCENTER = "bottomcenter"
    BOTTOMRIGHT = "bottomright"


class SubCategory(enum.Enum):
    """A category of spell/trap :class:`Card`s."""

    NORMAL = "normal"
    CONTINUOUS = "continuous"
    EQUIP = "equip"
    QUICKPLAY = "quickplay"
    FIELD = "field"
    RITUAL = "ritual"
    COUNTER = "counter"


class Legality(enum.Enum):
    """The state of legality for a :class:`Card` in a particular format."""

    UNLIMITED = "unlimited"
    """Allowed at 3 copies."""

    SEMILIMITED = "semilimited"
    """Allowed at 2 copies."""

    LIMITED = "limited"
    """Allowed at 1 copy."""

    FORBIDDEN = "forbidden"
    """Banned, illegal, or otherwise unable to be played."""

    LIMIT1 = "limit1"
    """A maximum of one Limit 1 card can be in a deck. Speed Duel / Duel Links only."""

    LIMIT2 = "limit2"
    """A maximum of two Limit 1 cards can be in a deck. Speed Duel / Duel Links only."""

    LIMIT3 = "limit3"
    """A maximum of three Limit 1 cards can be in a deck. Speed Duel / Duel Links only."""

    UNRELEASED = "unreleased"
    """It will be in this format when it releases, but it is not yet released."""


class Format(enum.Enum):
    """A format in which Yugioh :class:`CardPrinting`s are printed into."""

    OCG = "ocg"  # Japanese OCG.
    OCG_AE = "ocg-ae"  # Asian-English OCG.
    OCG_KR = "ocg-kr"  # Korean OCG.
    OCG_SC = "ocg-sc"  # Simplified Chinese OCG.
    TCG = "tcg"  # TCG.
    SPEED = "speed"  # TCG Speed Duels.
    DUELLINKS = "duellinks"  # Worldwide Duel Links.
    MASTERDUEL = "masterduel"  # Worldwide Master Duel.

    @property
    def parent(self) -> typing.Optional["Format"]:
        """Returns the 'parent format' of this format.
        Cards printed in a child format are also considered printed in parent formats.
        """
        if self in FORMAT_PARENTS:
            return FORMAT_PARENTS[self]
        return None

    @property
    def subformats(self) -> typing.Iterable["Format"]:
        """Returns any child formats of this format.
        Cards printed in a child format are also considered printed in parent formats.
        """
        return [k for k, v in FORMAT_PARENTS.items() if v == self]

    @property
    def locales(self) -> typing.Iterable["Locale"]:
        """Returns all locales that print cards into this format."""
        return [k for k, v in LOCALE_FORMATS.items() if self in v]


FORMAT_PARENTS = {
    Format.OCG_AE: Format.OCG,
    Format.OCG_KR: Format.OCG,
    Format.OCG_SC: Format.OCG,
    Format.SPEED: Format.TCG,
}


class Language(enum.Enum):
    """A language in which a card was printed."""

    GERMAN = "de"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    ITALIAN = "it"
    JAPANESE = "ja"
    KOREAN = "ko"
    PORTUGESE = "pt"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"
    # the following are not real languages, but are used to store sub-information about text in a language.
    # TODO: get rid of these or move them somewhere more appropriate
    JAPANESE_ROMAJI = "ja_romaji"
    KOREAN_ROMANIZED = "ko_rr"

    @classmethod
    def normalize(cls, s: str) -> "Language":
        """Attempt to parse a language/locale code to produce a Language enum."""
        if s in Language._value2member_map_:
            return Language(s)
        if s in Locale._value2member_map_:
            return Locale(s).language
        if s == "au":
            return Language.ENGLISH
        raise ValueError(f"Bad language: {s}")

    @property
    def locales(self) -> typing.Iterable["Locale"]:
        """Returns the locales cards of this language are printed in by default."""
        return [k for k, v in LOCALE_LANGS.items() if self == v]


class Locale(enum.Enum):
    """The locale in which a product was printed.
    Either a language, or a part of the world within a language.
    """

    ASIAN_ENGLISH = "ae"
    GERMAN = "de"
    ENGLISH = "en"
    SPANISH = "sp"
    ENGLISH_EUROPE = "eu"
    FRENCH_CANADA = "fc"
    FRENCH = "fr"
    ITALIAN = "it"
    JAPANESE = "jp"
    KOREAN = "kr"
    ENGLISH_AMERICA = "na"
    ENGLISH_OCEANIA = "oc"
    PORTUGESE = "pt"
    CHINESE_SIMPLIFIED = "sc"
    CHINESE_TRADITIONAL = "tc"

    @classmethod
    def normalize(cls, s: str) -> "Locale":
        """Attempt to parse a language/locale code to produce a Locale enum."""
        if s in Locale._value2member_map_:
            return Locale(s)
        if s in Language._value2member_map_:
            locales = [*Language(s).locales]
            if len(locales) != 1:
                raise ValueError(f"Ambiguous locale: {s}")
            return locales[0]
        if s == "au":
            return Locale.ENGLISH_OCEANIA
        raise ValueError(f"Bad locale: {s}")

    @property
    def parent(self) -> typing.Optional["Locale"]:
        """Get the parent locale. Some locales are part of a larger locale; for example, 'na' being part of 'en'."""
        return LOCALE_PARENTS.get(self)

    @property
    def sublocales(self) -> typing.Iterable["Locale"]:
        """Get the child locales. Some locales are part of a larger locale; for example, 'na' being part of 'en'."""
        return [k for k, v in LOCALE_PARENTS.items() if self == v]

    @property
    def language(self) -> Language:
        """Return the language cards in this locale are printed in by default."""
        return LOCALE_LANGS[self]

    @property
    def formats(self) -> typing.Iterable[Format]:
        """Return a list of possible formats that this locale prints cards into."""
        if self not in LOCALE_FORMATS:
            parent = self.parent
            if parent:
                return parent.formats
            else:
                return []
        return LOCALE_FORMATS[self]


LOCALE_PARENTS = {
    Locale.ENGLISH_EUROPE: Locale.ENGLISH,
    Locale.FRENCH_CANADA: Locale.ENGLISH_AMERICA,
    Locale.ENGLISH_AMERICA: Locale.ENGLISH,
    Locale.ENGLISH_OCEANIA: Locale.ENGLISH,
}


LOCALE_LANGS = {
    Locale.ASIAN_ENGLISH: Language.ENGLISH,
    Locale.GERMAN: Language.GERMAN,
    Locale.ENGLISH: Language.ENGLISH,
    Locale.SPANISH: Language.SPANISH,
    Locale.ENGLISH_EUROPE: Language.ENGLISH,
    Locale.FRENCH_CANADA: Language.FRENCH,
    Locale.FRENCH: Language.FRENCH,
    Locale.ITALIAN: Language.ITALIAN,
    Locale.JAPANESE: Language.JAPANESE,
    Locale.KOREAN: Language.KOREAN,
    Locale.ENGLISH_AMERICA: Language.ENGLISH,
    Locale.ENGLISH_OCEANIA: Language.ENGLISH,
    Locale.PORTUGESE: Language.PORTUGESE,
    Locale.CHINESE_SIMPLIFIED: Language.CHINESE_SIMPLIFIED,
    Locale.CHINESE_TRADITIONAL: Language.CHINESE_TRADITIONAL,
}


LOCALE_FORMATS = {
    Locale.ASIAN_ENGLISH: [Format.OCG_AE],
    Locale.GERMAN: [Format.TCG, Format.SPEED],
    Locale.ENGLISH: [Format.TCG, Format.SPEED],
    Locale.SPANISH: [Format.TCG, Format.SPEED],
    Locale.FRENCH: [Format.TCG, Format.SPEED],
    Locale.ITALIAN: [Format.TCG, Format.SPEED],
    Locale.JAPANESE: [Format.OCG],
    Locale.KOREAN: [Format.OCG_KR],
    Locale.PORTUGESE: [Format.TCG, Format.SPEED],
    Locale.CHINESE_SIMPLIFIED: [Format.OCG_SC],
    Locale.CHINESE_TRADITIONAL: [Format.OCG],
}


class VideoGameRaity(enum.Enum):
    """The rarity of a :class:`Card` in Master Duel and/or Duel Links."""

    NORMAL = "n"
    RARE = "r"
    SUPER = "sr"
    ULTRA = "ur"


class SetEdition(enum.Enum):
    """The edition a :class:`Set` can be found in."""

    FIRST = "1st"
    UNLIMTED = "unlimited"
    LIMITED = "limited"
    NONE = ""
    """not part of the enum proper, but used when a set has no editions."""


class SpecialDistroType(enum.Enum):
    """Some types of :class:`PackDistrobution` are hard-coded. These are those distributions."""

    PRECON = "preconstructed"
    """Indicates that this is a starter deck or other non-randomized set of cards."""


class SetBoxType(enum.Enum):
    """Some booster boxes have different contents depending if they were sold for hobby stores or for retail."""

    HOBBY = "hobby"
    RETAIL = "retail"


class CardRarity(enum.Enum):
    """The rarity of a :class:`Card`.
    We use the TCG name of a rarity here if there is an equivalent OCG rarity with a different name.
    Some rarities, such as Super Short Print, aren't real, and a few others were never printed on real cards; those have been omitted here.
    """

    COMMON = "common"
    """Common."""
    SHORTPRINT = "shortprint"
    """Short Print or Super Short Print."""
    RARE = "rare"
    """Rare."""
    SUPER = "super"
    """Super Rare."""
    ULTRA = "ultra"
    """Ultra Rare."""
    ULTIMATE = "ultimate"
    """Ultimate Rare."""
    SECRET = "secret"
    """Secret Rare."""
    ULTRASECRET = "ultrasecret"
    """Ultra Secret Rare."""
    PRISMATICSECRET = "prismaticsecret"
    """Prismatic Secret Rare."""
    GHOST = "ghost"
    """Ghost Rare or Holographic Rare."""
    PARALLEL = "parallel"
    """Parellel Rare."""
    COMMONPARALLEL = "commonparallel"
    """Parallel Common or Normal Parallel Rare."""
    RAREPARALLEL = "rareparallel"
    """Rare Parallel Rare."""
    SUPERPARALLEL = "superparallel"
    """Super Parallel Rare."""
    ULTRAPARALLEL = "ultraparallel"
    """Ultra Parallel Rare."""
    DTPC = "dtpc"
    """Duel Terminal Parallel Common or Duel Terminal Normal Parallel Rare."""
    DTPSP = "dtpsp"
    """Duel Terminal Parallel Short Print or Duel Terminal Normal Rare Parallel Rare."""
    DTRPR = "dtrpr"
    """Duel Terminal Rare Parallel Rare."""
    DTSPR = "dtspr"
    """Duel Terminal Super Parallel Rare."""
    DTUPR = "dtupr"
    """Duel Terminal Ultra Parallel Rare."""
    DTSCPR = "dtscpr"
    """Duel Terminal Secret Parallel Rare."""
    GOLD = "gold"
    """Gold Rare."""
    TENTHOUSANDSECRET = "10000secret"
    """10,000 Secret Rare."""
    TWENTITHSECRET = "20thsecret"
    """20th Anniversary Secret Rare."""
    COLLECTORS = "collectors"
    """Collector's Rare."""
    EXTRASECRET = "extrasecret"
    """Extra Secret Rare."""
    EXTRASECRETPARALLEL = "extrasecretparallel"
    """Extra Secret Parallel Rare."""
    GOLDGHOST = "goldghost"
    """Gold/Ghost Rare."""
    GOLDSECRET = "goldsecret"
    """Gold Secret Rare."""
    STARFOIL = "starfoil"
    """Starfoil Rare."""
    MOSAIC = "mosaic"
    """Mosaic Rare."""
    SHATTERFOIL = "shatterfoil"
    """Shatterfoil Rare."""
    GHOSTPARALLEL = "ghostparallel"
    """Ghost Parallel Rare."""
    PLATINUM = "platinum"
    """Platinum Rare."""
    PLATINUMSECRET = "platinumsecret"
    """Platinum Secret Rare."""
    PREMIUMGOLD = "premiumgold"
    """Premium Gold Rare."""
    TWENTYFIFTHSECRET = "25thsecret"
    """25th Anniversary Secret Rare."""
    SECRETPARALLEL = "secretparallel"
    """Parallel Secret Rare."""
    STARLIGHT = "starlight"
    """Starlight Rare or Alternate Rare."""
    PHARAOHS = "pharaohs"
    """Pharaoh's Ultra Rare."""
    KCCOMMON = "kccommon"
    """Kaiba Corporation Common."""
    KCRARE = "kcrare"
    """Kaiba Corporation Rare."""
    KCSUPER = "kcsuper"
    """Kaiba Corporation Super Rare."""
    KCULTRA = "kcultra"
    """Kaiba Corporation Ultra Rare."""
    KCSECRET = "kcsecret"
    """Kaiba Corporation Secret Rare."""
    MILLENIUM = "millenium"
    """Millenium Rare."""
    MILLENIUMSUPER = "milleniumsuper"
    """Millenium Super Rare."""
    MILLENIUMULTRA = "milleniumultra"
    """Millenium Ultra Rare."""
    MILLENIUMSECRET = "milleniumsecret"
    """Millenium Secret Rare."""
    MILLENIUMGOLD = "milleniumgold"
    """Millenium Gold Rare."""


class CardText:
    """Localized text that appears on a :class:`Card`."""

    name: str
    """The name of this card in this locale."""

    effect: typing.Optional[str]
    """The effect text or lore of this card in this locale."""

    pendulum_effect: typing.Optional[str]
    """The upper box's effect text of this card in this locale. Only applicable to pendulum cards."""

    official: bool
    """Whether or not this localization is official."""

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
    """A single possible art treatment of a :class:`Card`.
    This is NOT for the image of each printing of a card;
    this is for tracking when cards have multiple art treatments across multiple printings!
    """

    id: uuid.UUID
    """The UUID of this card's art treatment."""

    password: typing.Optional[str]
    """The password this art treatment can be found on. May be None if it's on multiple passwords or the card has no password."""

    crop_art: typing.Optional[str]
    """A URL to an image depicting an art crop of the particular art treatment."""

    card_art: typing.Optional[str]
    """A URL to a generic image of the card with this art treatment.
    This should be a generic image, like generated by YGOPRODECK,
    and the individual card printing's image should be used instead of this one where possible.
    """

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
    """A period of time in which a :class:`Card` was of a certain :class:`Legality`."""

    legality: Legality
    """The legality of the card."""

    date: datetime.date
    """The date on which this legalty came into effect."""

    def __init__(
        self,
        *,
        legality: Legality,
        date: datetime.date,
    ):
        self.legality = legality
        self.date = date


class CardLegality:
    """Current and historical legality information for a :class:`Card`."""

    current: Legality
    """What legality is this card currently?
    This may be present even if the card has no history;
    prefer this when you need to see the current legality, rather than looking up history.
    """

    history: typing.List[LegalityPeriod]
    """The history of limitations and unlimiations for this card."""

    def __init__(
        self,
        *,
        current: Legality,
        history: typing.Optional[typing.List[LegalityPeriod]] = None,
    ):
        self.current = current
        self.history = history or []


class ExternalIdPair:
    """A name and ID pair, used on sites like Yugipedia and (occasionally) YGOPRODECK."""

    name: str
    id: int

    def __init__(self, name: str, id: int) -> None:
        self.name = name
        self.id = id


class Card:
    """A single Yugioh card or token. For information on printings of a card, see :class:`CardPrinting`."""

    id: uuid.UUID
    """The UUID of the card."""

    text: typing.Dict[Language, CardText]
    """Localized text for the card, including the name, the effect/lore, and so on.
    Keys are locale abbreviations: en, fr, ja, zh-CN, etc.
    """

    card_type: CardType
    """The type of this card: Monster, spell, trap, etc."""

    attribute: typing.Optional[Attribute]
    """The attribute of this monster/token card, if known."""

    monster_card_types: typing.Optional[typing.List[MonsterCardType]]
    """The summoning types of this monster card, if known: Ritual, fusion, xyz, etc."""

    type: typing.Optional[Race]
    """The type of this monster/token card, if known: Beast, spellcaster, cyberse, etc."""

    classifications: typing.Optional[typing.List[Classification]]
    """Any classifiers for this monster/token card, if known: Normal, effect, tuner, etc."""

    abilities: typing.Optional[typing.List[Ability]]
    """Any abilities for this monster/token card, if known: Normal, toon, spirit, etc."""

    level: typing.Optional[int]
    """The level of this monster/token card, if known. For XYZ monsters, see `Card.rank`."""

    rank: typing.Optional[int]
    """The rank of this monster/token card, if known. For non-XYZ monsters, see `Card.level`."""

    atk: typing.Union[int, str, None]
    """The ATK of this monster/token card, if known."""

    def_: typing.Union[int, str, None]
    """The DEF of this monster/token card, if known. Not present on Link monsters."""

    scale: typing.Optional[int]
    """The pendulum of this pendulum monster card, if known."""

    link_arrows: typing.Optional[typing.List[LinkArrow]]
    """The link arrows on this link monster, if known."""

    subcategory: typing.Optional[SubCategory]
    """The category of this spell/trap card, if known."""

    character: typing.Optional[str]
    """The character this skill card corresponds to, if known."""

    skill_type: typing.Optional[str]
    """The type of this skill card, if known."""

    passwords: typing.List[str]
    """A list of all 8-digit passwords this card has been printed with."""

    images: typing.List[CardImage]
    """All art treatments this card has been known to have been printed with."""

    sets: typing.List["Set"]
    """Sets in which this card has appeared."""

    illegal: bool
    """True if this card has been declared illegal in all formats.
    Match winners, original god cards, etc. are illegal.
    """

    legality: typing.Dict[Format, CardLegality]
    """Current legality status and legality history for the various formats: tcg, ocg, ocg-kr, masterduel, etc."""

    master_duel_rarity: typing.Optional[VideoGameRaity]
    """The rarity of this card in Master Duel, if it is in Master Duel."""

    master_duel_craftable: typing.Optional[bool]
    """If this card is craftable using dust or not, if it is in Master Duel."""

    duel_links_rarity: typing.Optional[VideoGameRaity]
    """The rarity of this card in Duel Links, if it is in Duel Links."""

    yugipedia_pages: typing.Optional[typing.List[ExternalIdPair]]
    """The Yugipedia page you can find this card on."""

    ygoprodeck: typing.Optional[ExternalIdPair]
    """The YGOPRODECK page you can find this card on."""

    db_id: typing.Optional[int]
    """The offiicial Konami ID for this card."""

    yugiohprices_name: typing.Optional[str]
    """The YugiohPrices page you can find this card on. Not yet implemented."""

    yamlyugi_id: typing.Optional[int]
    """The Yaml Yugi page you can find this card on."""

    series: typing.List["Series"]
    """Any series or archetypes this card belongs to."""

    def __init__(
        self,
        *,
        id: uuid.UUID,
        text: typing.Optional[typing.Dict[Language, CardText]] = None,
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
        legality: typing.Optional[typing.Dict[Format, CardLegality]] = None,
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

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/card.json",
            "id": str(self.id),
            "text": {
                k.value: {
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
    """A probability of finding a certain rarity of card."""

    rarities: typing.List[CardRarity]
    """The rarities to draw from. If empty, draws from all rarities."""

    chance: int
    """The chance of pulling this rarity, as a 1:X odds.
    For example, a chance of 6 means you have a 1:6 chance of this card slot being this rarity.
    Default 1, for a 1:1 (that is, guaranteed) chance.
    """

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
    """The base class for the different kinds of slots that can appear in a :class:`PackDistrobution`."""

    _slot_type_name: typing.ClassVar[str]

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        raise NotImplementedError

    @classmethod
    def _from_json(
        cls, db: "Database", in_json: typing.Dict[str, typing.Any]
    ) -> "PackDistroSlot":
        raise NotImplementedError


class PackDistroSlotPool(PackDistroSlot):
    """This slot represents a pool of cards of certain rarities to randomly pick from in a :class:`PackDistrobution`."""

    _slot_type_name = "pool"

    set: typing.Optional["Set"]
    """Overrides the set you are pulling cards from.
    Used in palces like Master Duel Secret Packs, which have slots from Master packs.
    """

    rarity: typing.List[PackDistroWeight]
    """The rarities and the chances of pulling a card from each rarity."""

    qty: int
    """The number of cards pulled to form this slot. Default 1."""

    card_types: typing.List[CardType]
    """Some sets (old reprint sets, for one) only had monsters, spells, or traps in certain slots.
    If one or more types are provided, we will only generate cards of the given types in this slot.
    """

    duplicates: bool
    """Most of the time, you can't get the same card twice at the same rarity in a pack, even if it's common.
    (In physical sets, this is due to how printing sheets work, so it's not a 100% chance, but it might as well be for our purposes.)
    If you want to override this deduplication behaviour, set this to `True`.
    """

    proportionate: bool
    """Normally, the probability table doesn't take into account the relative sizes of each pool.
    When this field is `True`, the chances will be changed so that the probabilities will take into account said relative sizes.
    This is used for dual common/short-print slots, for example.
    """

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
    """This slot represents a guaranteed set of cards that appear in the pack.
    If you want a whole set to appear here, use :class:`PackDistroSlotSet` instead.
    """

    _slot_type_name = "guaranteedPrintings"

    cards: typing.List["CardPrinting"]
    """The card printing(s) that appear in this slot."""

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
    """This slot represents a guaranteed set of cards that appear in the pack.
    If you want less than the whole set to appear here, use :class:`PackDistroSlotCards` instead.
    """

    _slot_type_name = "guaranteedSet"

    set: "Set"
    """The set that appears in this slot."""

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
"""A mapping of JSON distribtution slot names to classes."""


class PackDistrobution:
    """A pack distribution represents information on how packs of :class:`Set`s are pulled.
    You can use this to simulate opening packs, boxes, and so on."""

    id: uuid.UUID
    """The UUID of this pack distribution."""

    name: typing.Optional[str]
    """The optional name of this pack distribution. Used only for human reference purposes, and means nothing."""

    quotas: typing.Dict[CardType, int]
    """Some sets (old reprint sets, for one) had an exact number of
    monsters, spells, and traps in each pack, regardless of rarities.
    This is a map of card types to the number of cards that must be generated,
    at minimum, of that type.
    """

    slots: typing.List[PackDistroSlot]
    """Slots of cards in this pack."""

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[str] = None,
        quotas: typing.Optional[typing.Dict[CardType, int]] = None,
        slots: typing.Optional[typing.List[PackDistroSlot]] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.quotas = quotas or {}
        self.slots = slots or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "$schema": f"https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v{SCHEMA_VERSION}/distribution.json",
            "id": str(self.id),
            **({"name": self.name} if self.name else {}),
            **(
                {"quotas": {k.value: v for k, v in self.quotas.items()}}
                if self.quotas
                else {}
            ),
            "slots": [x._to_json() for x in self.slots],
        }


class SealedProductLocale:
    """A locale in which a :class:`SealedProduct` was released."""

    key: Locale
    """The short language code for this locale: en, fr, ae, etc."""

    date: typing.Optional[datetime.date]
    """The date on which this product was released in this locale."""

    image: typing.Optional[str]
    """A URL to an image of this product in this locale."""

    db_ids: typing.List[int]
    """Any Konami official database IDs for this product in this locale."""

    has_hobby_retail_differences: bool
    """Set this to true if this box has hobby and retail booster boxes,
    and thier contents may differ with regard to thier secret/ultimate rares.
    """

    def __init__(
        self,
        *,
        key: Locale,
        date: typing.Optional[datetime.date] = None,
        image: typing.Optional[str] = None,
        db_ids: typing.Optional[typing.List[int]] = None,
        has_hobby_retail_differences: bool = False,
    ) -> None:
        self.key = key
        self.date = date
        self.image = image
        self.db_ids = db_ids or []
        self.has_hobby_retail_differences = has_hobby_retail_differences

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            **({"date": self.date.isoformat()} if self.date else {}),
            **({"image": self.image} if self.image else {}),
            **(
                {"hasHobbyRetailDifferences": True}
                if self.has_hobby_retail_differences
                else {}
            ),
            "externalIDs": {
                **({"dbIDs": self.db_ids} if self.db_ids else {}),
            },
        }


class SealedProductPack:
    """A single component of a :class:`SealedProduct`, either a pack or a predetermined card."""

    set: "Set"
    """The :class:`Set` the pack is from, or if `SealedProductPack.card` is specified, the set the card is from."""

    card: typing.Optional["Card"]
    """If specified, then this is a single pretermined card rather than a whole pack."""

    def __init__(self, *, set: "Set", card: typing.Optional["Card"] = None) -> None:
        self.set = set
        self.card = card


class SealedProductContents:
    """The contents of a :class:`SealedProduct` across a given list of :class:`SealedProductLocale`s."""

    locales: typing.List[SealedProductLocale]
    """The locales in which this product has these contents.
    May be empty in the case of video-game-only products.
    """

    image: typing.Optional[str]
    """A URL to a generic image of this product.
    Prefer per-locale images over this image!
    """

    packs: typing.Dict[SealedProductPack, int]
    """The contents of this product. Keys are packs. Values are how many of this pack appeared in this product."""

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
            **(
                {"locales": [x.key.value for x in self.locales]} if self.locales else {}
            ),
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
    """A sealed product, such as a special booster box, collectible tin,
    or other mixes of packs and cards.
    """

    id: uuid.UUID
    """The UUID of this sealed product."""

    date: typing.Optional[datetime.date]
    """The date this product was released. Only used in video-game-only products."""

    name: typing.Dict[Language, str]
    """The localized name of this product."""

    locales: typing.Dict[Locale, SealedProductLocale]
    """The locales in which this product was released."""

    contents: typing.List[SealedProductContents]
    """The contents of this product in various locales. Video game products only have one entry here."""

    yugipedia: typing.Optional[ExternalIdPair]
    """The Yugipedia page of this product, if known."""

    box_of: typing.List["Set"]
    """Is this product considered a booster box (or case, etc.) of certain packs (or decks, etc.)?
    If so, the involved sets are listed here.
    """

    def __init__(
        self,
        *,
        id: uuid.UUID,
        date: typing.Optional[datetime.date] = None,
        name: typing.Optional[typing.Dict[Language, str]] = None,
        locales: typing.Optional[typing.Dict[Locale, SealedProductLocale]] = None,
        contents: typing.Optional[typing.List[SealedProductContents]] = None,
        yugipedia: typing.Optional[ExternalIdPair] = None,
        box_of: typing.Optional[typing.List["Set"]] = None,
    ) -> None:
        self.id = id
        self.date = date
        self.name = name or {}
        self.locales = locales or {}
        self.contents = contents or []
        self.yugipedia = yugipedia
        self.box_of = box_of or []

    def _to_json(self) -> typing.Dict[str, typing.Any]:
        return {
            "id": str(self.id),
            **({"date": self.date.isoformat()} if self.date else {}),
            "name": {k.value: v for k, v in self.name.items()},
            **({"boxOf": [str(x.id) for x in self.box_of]} if self.box_of else {}),
            **(
                {"locales": {k.value: v._to_json() for k, v in self.locales.items()}}
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
    """This represents a series or archetype :class:`Card`s can belong to."""

    id: uuid.UUID
    """The UUID of this series/archetype."""

    name: typing.Dict[Language, str]
    """The (sometimes unofficial) name of this series/archetype."""

    archetype: bool
    """`True` if this represents an archetype (that is, cards that share a common name),
    and `False` if it represents a series (cards that share a common theme, but do not refer to each other by archetype).
    """

    members: typing.Set[Card]
    """The members of this series/archetype."""

    yugipedia: typing.Optional[ExternalIdPair]
    """The Yugipedia page of this series/archetype, if known."""

    def __init__(
        self,
        *,
        id: uuid.UUID,
        name: typing.Optional[typing.Dict[Language, str]] = None,
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
            "name": {k.value: v for k, v in self.name.items()},
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
    """A single printing of a :class:`Card` in a :class:`Set`."""

    id: uuid.UUID
    """The UUID of this printing."""

    card: Card
    """The card this printing represents."""

    suffix: typing.Optional[str]
    """The suffix of the set code for this printing.
    See `SetLocale.prefix` for the prefix of this set code,
    which can be combined to form the full set code for this card.
    Not present in video game sets.
    """

    rarity: typing.Optional[CardRarity]
    """The rarity of this card, if known. Not present in video game sets."""

    only_in_box: typing.Optional[SetBoxType]
    """What kinds of booster boxes this printing appeared in.
    (Some old sets only had some secret/ultimate rares in some types of booster box.)
    Empty if not applicable.
    """

    price: typing.Optional[float]
    """Price information for this printing, if available.
    All prices are the most recent available as of the creation of this database, and are normalized to USD.
    No guarantees are made that this price is accurate, or that all sites were considered, or that all languages of this printing were considered.
    NYI.
    """

    language: typing.Optional[Language]
    """An override for the language this card was printed in.
    This may be different than the locale's language in some very rare cases.
    NYI.
    """

    image: typing.Optional[CardImage]
    """A URL to an image of this printing of this card."""

    replica: bool
    """Some old sets included replicas of past cards.
    If `True`, this card is a replica. Replicas are illegal for play.
    """

    qty: int
    """How many of this card was in this set.
    Only useful for sets with the `SpecialDistroType.PRECON` distribution method.
    Default 1.
    """

    def __init__(
        self,
        *,
        id: uuid.UUID,
        card: Card,
        suffix: typing.Optional[str] = None,
        rarity: typing.Optional[CardRarity] = None,
        only_in_box: typing.Optional[SetBoxType] = None,
        price: typing.Optional[float] = None,
        language: typing.Optional[Language] = None,
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
            **({"language": self.language.value} if self.language else {}),
            **({"imageID": str(self.image.id)} if self.image else {}),
            **({"replica": True} if self.replica else {}),
            **({"qty": self.qty} if self.qty != 1 else {}),
        }


class SetContents:
    """The contents of a :class:`Set` across a given list of :class:`SetLocale`s."""

    locales: typing.List["SetLocale"]
    """The locales in which this product has these contents.
    May be empty in the case of video-game-only products.
    """

    formats: typing.List[Format]
    """What formats this product was released in: TCG, OCG, Master Duel, etc.
    Deprectated; use the locale's list of formats instead.
    """

    distrobution: typing.Union[None, SpecialDistroType, uuid.UUID]
    """The pack distribution used to make packs of this set, if known.
    A UUID of a :class:`PackDistrobution`, or a :class:`SpecialDistroType`.
    """

    packs_per_box: typing.Optional[int]
    """If this is a booster pack, this represents the number of packs of this that came in each booster box.
    Deprecated; find the :class:`SealedProduct` with the ``boxOf`` property set to this set instead.
    """

    has_hobby_retail_differences: bool
    """If this is a booster pack, this represents whether or not booster boxes made for retail sale were different than boxes made for hobby-shop sale.
    Deprecated; find the :class:`SealedProduct` with the ``boxOf`` property set to this set instead.
    """

    editions: typing.List[SetEdition]
    """What editions this product was released in: 1st Edition, Unlimited, etc. Empty for most OCG sets.
    Deprectated; use the locale's list of editions instead.
    """

    image: typing.Optional[str]
    """A URL to a generic image of this product.
    Prefer per-locale images over this image!
    """

    box_image: typing.Optional[str]
    """If this is a booster pack, this is a URL to a generic image of this product's booster box.
    Prefer per-locale images over this image!
    Deprecated; find the :class:`SealedProduct` with the ``boxOf`` property set to this set instead.
    """

    cards: typing.List[CardPrinting]
    """The cards printed in this set."""

    removed_cards: typing.List[CardPrinting]
    """In video-game-only sets, Konami may add or remove cards from sets on a whim.
    This represents cards that are no longer part of this set.
    NYI.
    """

    ygoprodeck: typing.Optional[str]
    """The YGOPRODECK URL slug for this set, if known.
    Beware: YGOPRODECK gets set contents wrong a lot! Don't trust them!
    """

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
        distro = self.distrobution
        if type(self.distrobution) is SpecialDistroType:
            distro = self.distrobution.value
        elif type(self.distrobution) is PackDistrobution:
            distro = str(self.distrobution.id)
        elif type(self.distrobution) is uuid.UUID:
            distro = str(self.distrobution)

        return {
            **(
                {"locales": [l.key.value for l in self.locales]} if self.locales else {}
            ),
            "formats": [f.value for f in self.formats],
            **({"distrobution": distro} if distro else {}),
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
    """A locale in which a :class:`Set` was released."""

    key: Locale
    """The locale code."""

    language: str
    """The language this set was printed in, as a short language code: en, fr, ae, etc.
    This may be different from `SetLocale.key` in some rare cases.
    """

    prefix: typing.Optional[str]
    """The prefix of the set code for :class:`CardPrinting`s in this set.
    Combine with `CardPrinting.suffix` to produce a whole set code.
    """

    date: typing.Optional[datetime.date]
    """The date on which this product was released in this locale."""

    image: typing.Optional[str]
    """A URL to an image of this product in this locale."""

    box_image: typing.Optional[str]
    """If this is a booster pack, this is a URL to an image of this product's booster box in this locale."""

    card_images: typing.Dict[SetEdition, typing.Dict[CardPrinting, str]]
    """Images of printings of cards in this locale. Keys are edition and printings. Values are URLs to images."""

    db_ids: typing.List[int]
    """Any Konami official database IDs for this product in this locale."""

    formats: typing.List[Format]
    """What formats this product was released in: TCG, OCG, Master Duel, etc."""

    editions: typing.List[SetEdition]
    """What editions this product was released in: 1st Edition, Unlimited, etc. Empty for most OCG sets."""

    def __init__(
        self,
        *,
        key: Locale,
        language: str,
        prefix: typing.Optional[str] = None,
        date: typing.Optional[datetime.date] = None,
        image: typing.Optional[str] = None,
        box_image: typing.Optional[str] = None,
        card_images: typing.Optional[
            typing.Dict[SetEdition, typing.Dict[CardPrinting, str]]
        ] = None,
        db_ids: typing.Optional[typing.List[int]] = None,
        formats: typing.Optional[typing.List[Format]] = None,
        editions: typing.Optional[typing.List[SetEdition]] = None,
    ) -> None:
        self.key = key
        self.language = language
        self.prefix = prefix
        self.date = date
        self.image = image
        self.box_image = box_image
        self.card_images = card_images or {}
        self.db_ids = db_ids or []
        self.formats = formats or []
        self.editions = editions or []

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
            **({"formats": [x.value for x in self.formats]} if self.formats else {}),
            **({"editions": [x.value for x in self.editions]} if self.editions else {}),
            "externalIDs": {
                **({"dbIDs": self.db_ids} if self.db_ids else {}),
            },
        }


class Set:
    """A set of cards printed into one or more Yugioh formats.
    This represents booster packs, starter decks, promotional card sets, etc.
    """

    id: uuid.UUID
    """The UUID of this set."""

    date: typing.Optional[datetime.date]
    """The date this product was released. Only used in video-game-only products."""

    name: typing.Dict[Language, str]
    """The localized name of this product."""

    locales: typing.Dict[Locale, SetLocale]
    """The locales in which this product was released."""

    contents: typing.List[SetContents]
    """The contents of this product in various locales. Video game products only have one entry here."""

    yugipedia: typing.Optional[ExternalIdPair]
    """The Yugipedia page of this product, if known."""

    yugiohprices: typing.Optional[str]
    """The YugiohPrices page of this product, if known. NYI."""

    def __init__(
        self,
        *,
        id: uuid.UUID,
        date: typing.Optional[datetime.date] = None,
        name: typing.Optional[typing.Dict[Language, str]] = None,
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
            "name": {k.value: v for k, v in self.name.items()},
            **(
                {"locales": {k.value: v._to_json() for k, v in self.locales.items()}}
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
    """A Manual Fixup Idenfier, or MFI, helps label and locate various things when manually fixing up data.
    See manual-data/README.md in this module's repository for details.
    """

    id: typing.Optional[uuid.UUID]
    """A UUID to look up."""

    name: typing.Optional[str]
    """A case-sensitive English name to look up."""

    konami_id: typing.Optional[int]
    """A Konami official database ID to look up."""

    ygoprodeck_id: typing.Optional[int]
    """A YGOPRODECK password to look up."""

    ygoprodeck_name: typing.Optional[str]
    """A YGOPRODECK URL slug to look up."""

    yugipedia_id: typing.Optional[int]
    """A Yugipedia page ID to look up."""

    yugipedia_name: typing.Optional[str]
    """A Yugipedia page title to look up."""

    yamlyugi: typing.Optional[int]
    """A Yaml Yugi password to look up."""

    set: typing.Optional["ManualFixupIdentifier"]
    """A :class:`Set` to look up. Only used in looking up :class:`CardPrinting`s."""

    locale: typing.Optional[Locale]
    """A locale short code to look up. Only used in looking up :class:`CardPrinting`s."""

    edition: typing.Optional[SetEdition]
    """An edition to look up. Only used in looking up :class:`CardPrinting`s."""

    rarity: typing.Optional[CardRarity]
    """A rarity to look up. Only used in looking up :class:`CardPrinting`s."""

    code: typing.Optional[str]
    """A full set code to look up. Only used in looking up :class:`CardPrinting`s."""

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
            self.locale = (
                Locale.normalize(in_json["locale"]) if "locale" in in_json else None
            )
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
            **({"locale": self.locale.value} if self.locale else {}),
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
    """A YGOJSON database.
    Constructing a new :class:`Database` does not initialize it with data.
    If you want data, see `load_from_internet` or `load_from_file`."""

    individuals_dir: typing.Optional[str]
    """The directory individualized JSON is stored in."""

    aggregates_dir: typing.Optional[str]
    """The directory aggregated JSON is stored in."""

    increment: int
    """How many times this database has been modified."""

    last_yamlyugi_read: typing.Optional[datetime.datetime]
    """The last time Yaml Yugi was read from to produce this database."""

    last_yugipedia_read: typing.Optional[datetime.datetime]
    """The last time Yugipedia was read from to produce this database."""

    last_ygoprodeck_read: typing.Optional[datetime.datetime]
    """The last time YGOPRODECK was read from to produce this database."""

    cards: typing.List[Card]
    """Cards in this database."""

    cards_by_id: typing.Dict[uuid.UUID, Card]
    """You may use this to look up cards by their UUID."""

    cards_by_password: typing.Dict[str, Card]
    """You may use this to look up cards by their 8-digit password.
    The string MUST be 8 digits long, 0-padded!
    """

    cards_by_yamlyugi: typing.Dict[int, Card]
    """You may use this to look up cards by their Yaml Yugi password."""

    cards_by_en_name: typing.Dict[str, Card]
    """You may use this to look up cards by their case-sensitive English name."""

    cards_by_konami_cid: typing.Dict[int, Card]
    """You may use this to look up cards by their Konami official databse ID."""

    cards_by_yugipedia_id: typing.Dict[int, Card]
    """You may use this to look up cards by their Yugipedia page ID."""

    cards_by_ygoprodeck_id: typing.Dict[int, Card]
    """You may use this to look up cards by their YGOPRODECK password."""

    card_images_by_id: typing.Dict[uuid.UUID, CardImage]
    """You may use this to look up cards' art treatments by their UUID."""

    sets: typing.List[Set]
    """Sets in this database."""

    sets_by_id: typing.Dict[uuid.UUID, Set]
    """You may use this to look up sets by their UUID."""

    sets_by_en_name: typing.Dict[str, Set]
    """You may use this to look up sets by their case-sensitive English names."""

    sets_by_konami_sid: typing.Dict[int, Set]
    """You may use this to look up sets by their Konami official database ID."""

    sets_by_yugipedia_id: typing.Dict[int, Set]
    """You may use this to look up sets by their Yugipedia page ID."""

    sets_by_yugipedia_name: typing.Dict[str, Set]
    """You may use this to look up sets by their Yugipedia page name."""

    sets_by_ygoprodeck_id: typing.Dict[str, Set]
    """You may use this to look up sets by their YGOPRODECK password."""

    printings_by_id: typing.Dict[uuid.UUID, CardPrinting]
    """You may use this to look up card printings by their UUID."""

    printings_by_code: typing.Dict[str, typing.List[CardPrinting]]
    """You may use this to look up card printings by their full set code."""

    series: typing.List[Series]
    """Series/archetypes in this database."""

    series_by_id: typing.Dict[uuid.UUID, Series]
    """You may use this to look up series/archetypes by their UUID."""

    series_by_en_name: typing.Dict[str, Series]
    """You may use this to look up series/archetypes by their case-sensitive English names."""

    series_by_yugipedia_id: typing.Dict[int, Series]
    """You may use this to look up series/archetypes by their Yugipedia page ID."""

    distros: typing.List[PackDistrobution]
    """Pack distributions in this database."""

    distros_by_id: typing.Dict[uuid.UUID, PackDistrobution]
    """You may use this to look up pack distributions by their UUID."""

    distros_by_name: typing.Dict[str, PackDistrobution]
    """You may use this to look up pack distributions by their name."""

    products: typing.List[SealedProduct]
    """Sealed products in this database."""

    products_by_id: typing.Dict[uuid.UUID, SealedProduct]
    """You may use this to look up sealed products by their UUID."""

    products_by_en_name: typing.Dict[str, SealedProduct]
    """You may use this to look up pack distributions by their case-sensitive English names."""

    products_by_yugipedia_id: typing.Dict[int, SealedProduct]
    """You may use this to look up sealed products by their Yugipedia page ID."""

    products_by_konami_pid: typing.Dict[int, SealedProduct]
    """You may use this to look up sealed products by their Konami official database ID."""

    products_by_pack_id: typing.Dict[uuid.UUID, SealedProduct]
    """You may use this to look up sealed products by what packs they are a booster box of."""

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
        self.sets_by_yugipedia_name = {}
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
        self.products_by_pack_id = {}

    def add_card(self, card: Card):
        """Adds a card to this database, or updated its lookup information if it's already in the database."""

        if card.id not in self.cards_by_id:
            self.cards.append(card)

        self.cards_by_id[card.id] = card
        for pw in card.passwords:
            self.cards_by_password[pw] = card
        if card.yamlyugi_id:
            self.cards_by_yamlyugi[card.yamlyugi_id] = card
        if Language.ENGLISH in card.text:
            self.cards_by_en_name[card.text[Language.ENGLISH].name] = card
        if card.db_id:
            self.cards_by_konami_cid[card.db_id] = card
        for page in card.yugipedia_pages or []:
            self.cards_by_yugipedia_id[page.id] = card
        if card.ygoprodeck:
            self.cards_by_ygoprodeck_id[card.ygoprodeck.id] = card

        for image in card.images:
            self.card_images_by_id[image.id] = image

    def add_set(self, set_: Set):
        """Adds a set to this database, or updated its lookup information if it's already in the database."""

        if set_.id not in self.sets_by_id:
            self.sets.append(set_)

        self.sets_by_id[set_.id] = set_
        if Language.ENGLISH in set_.name:
            self.sets_by_en_name[set_.name[Language.ENGLISH]] = set_
        if set_.yugipedia:
            self.sets_by_yugipedia_id[set_.yugipedia.id] = set_
            self.sets_by_yugipedia_name[set_.yugipedia.name] = set_
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
        """Adds a series or archetype to this database, or updated its lookup information if it's already in the database."""

        if series.id not in self.series_by_id:
            self.series.append(series)
            self.series_by_id[series.id] = series
        if Language.ENGLISH in series.name:
            self.series_by_en_name[series.name[Language.ENGLISH]] = series
        if series.yugipedia:
            self.series_by_yugipedia_id[series.yugipedia.id] = series

    def add_distro(self, distro: PackDistrobution):
        """Adds a pack distribution to this database, or updated its lookup information if it's already in the database."""

        if distro.id not in self.distros_by_id:
            self.distros.append(distro)
            self.distros_by_id[distro.id] = distro
        if distro.name:
            self.distros_by_name[distro.name] = distro

    def add_product(self, product: SealedProduct):
        """Adds a sealed product to this database, or updated its lookup information if it's already in the database."""

        if product.id not in self.products_by_id:
            self.products.append(product)

        self.products_by_id[product.id] = product
        if Language.ENGLISH in product.name:
            self.products_by_en_name[product.name[Language.ENGLISH]] = product
        if product.yugipedia:
            self.products_by_yugipedia_id[product.yugipedia.id] = product
        for locale in product.locales.values():
            for db_id in locale.db_ids:
                self.products_by_konami_pid[db_id] = product
        for pack in product.box_of:
            self.products_by_pack_id[pack.id] = product

    def regenerate_backlinks(self):
        """This does the following fixups:
        * sets `Card.sets` based on what printings are in what sets
        * sets `Card.series` based on what series or archetypes list it as a member
        """

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
        """Looks up a set from an MFI."""

        result = None
        if not result and mfi.id:
            result = self.sets_by_id.get(mfi.id, result)
        if not result and mfi.konami_id:
            result = self.sets_by_konami_sid.get(mfi.konami_id, result)
        if not result and mfi.ygoprodeck_name:
            result = self.sets_by_ygoprodeck_id.get(mfi.ygoprodeck_name, result)
        if not result and mfi.yugipedia_id:
            result = self.sets_by_yugipedia_id.get(mfi.yugipedia_id, result)
        if not result and mfi.yugipedia_name:
            result = self.sets_by_yugipedia_name.get(mfi.yugipedia_name, result)
        if not result and mfi.name:
            result = self.sets_by_en_name.get(mfi.name, result)
        return result

    def lookup_distro(
        self, mfi: ManualFixupIdentifier
    ) -> typing.Optional[PackDistrobution]:
        """Looks up a pack distribution from an MFI."""

        result = None
        if not result and mfi.id:
            result = self.distros_by_id.get(mfi.id, result)
        if not result and mfi.name:
            result = self.distros_by_name.get(mfi.name, result)
        return result

    def lookup_printing(
        self, mfi: ManualFixupIdentifier
    ) -> typing.Optional[CardPrinting]:
        """Looks up a printing of a card from an MFI."""

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
        """Looks up a card from an MFI."""

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
        """Applies all set manual fixups to this database."""

        class BoxInfo(typing.NamedTuple):
            locales: typing.List[Locale]
            n_packs: int
            has_hobby_retail_differences: bool
            image: typing.Optional[str]

        for filename in tqdm.tqdm(
            os.listdir(MANUAL_SETS_DIR), desc="Applying manual fixups to sets"
        ):
            if filename.endswith(".json"):
                with open(
                    os.path.join(MANUAL_SETS_DIR, filename), encoding="utf-8"
                ) as file:
                    in_json = json.load(file)
                    box_info: typing.Dict[Set, typing.List[BoxInfo]] = {}
                    box_images: typing.Dict[Set, typing.Dict[Locale, str]] = {}

                    for i, mfi in enumerate(
                        ManualFixupIdentifier(x) for x in in_json["sets"]
                    ):
                        set_ = self.lookup_set(mfi)
                        if not set_:
                            logging.warn(f"Unknown set to fixup: {mfi}")
                            continue

                        for in_contents in in_json["contents"]:
                            in_locales: typing.List[Locale] = [
                                Locale.normalize(x)
                                for x in in_contents.get("locales", [])
                            ]

                            box = None
                            if "box" in in_contents:
                                in_box = in_contents["box"]
                                box = BoxInfo(
                                    in_locales,
                                    in_box.get("nPacks", 1),
                                    in_box.get("hasHobbyRetailDifferences", False),
                                    in_box.get("image"),
                                )
                                box_info.setdefault(set_, [])
                                box_info[set_].append(box)

                            for contents in set_.contents:
                                if (
                                    not in_locales
                                    or not contents.locales
                                    or any(
                                        x.key in in_locales for x in contents.locales
                                    )
                                ):
                                    # apply distro
                                    distro = in_contents.get("distribution")
                                    if distro:
                                        if (
                                            type(distro) is str
                                            and distro
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

                                    # apply box
                                    if box:
                                        contents.packs_per_box = box.n_packs
                                        contents.has_hobby_retail_differences = (
                                            box.has_hobby_retail_differences
                                        )

                                    if "perSet" in in_contents and i < len(
                                        in_contents["perSet"]
                                    ):
                                        in_per_set = in_contents["perSet"][i]

                                        # apply ygoprodeck
                                        if "ygoprodeck" in in_per_set:
                                            contents.ygoprodeck = in_per_set[
                                                "ygoprodeck"
                                            ]

                        if "perSet" in in_json:
                            per_set_info = (
                                in_json["perSet"][i]
                                if i < len(in_json["perSet"])
                                else {}
                            )
                            if "boxImages" in per_set_info:
                                box_images[set_] = {
                                    Locale.normalize(k): v
                                    for k, v in per_set_info["boxImages"].items()
                                }

                    # generate sealed products based on booster boxes
                    for set_, bis in box_info.items():
                        product = self.products_by_pack_id.get(set_.id)
                        if not product:
                            product = SealedProduct(id=uuid.uuid4())

                        product.date = set_.date
                        product.name = {k: f"{v} (Box)" for k, v in set_.name.items()}
                        product.locales.clear()
                        for locale in set_.locales.values():
                            product.locales[locale.key] = SealedProductLocale(
                                key=locale.key,
                                date=locale.date,
                                db_ids=locale.db_ids,
                                image=box_images.get(set_, {}).get(locale.key),
                            )
                        product.contents.clear()
                        product.yugipedia = set_.yugipedia
                        product.box_of = [set_]

                        for i, bi in enumerate(bis):
                            other_bis = bis[i + 1 :]
                            locales = (
                                [
                                    x
                                    for x in product.locales.values()
                                    if x.key in bi.locales
                                ]
                                if bi.locales
                                else [*product.locales.values()]
                            )
                            locales = [
                                x
                                for x in locales
                                if all(
                                    x.key not in other_bi.locales
                                    for other_bi in other_bis
                                )
                            ]
                            if not locales:
                                continue
                            for locale in locales:
                                locale.has_hobby_retail_differences = (
                                    bi.has_hobby_retail_differences
                                )
                            product.contents.append(
                                SealedProductContents(
                                    locales=locales,
                                    packs={SealedProductPack(set=set_): bi.n_packs},
                                    image=bi.image,
                                )
                            )

                        self.add_product(product)

    def manually_fixup_distros(self):
        """Applies all pack distribution manual fixups to this database."""

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
        """Applies all sealed product manual fixups to this database."""

        for filename in tqdm.tqdm(
            os.listdir(MANUAL_PRODUCTS_DIR), desc="Importing sealed products"
        ):
            if filename.endswith(".json"):
                with open(
                    os.path.join(MANUAL_PRODUCTS_DIR, filename), encoding="utf-8"
                ) as infile:
                    in_json = json.load(infile)

                    if "boxOf" in in_json:
                        in_json["boxOf"] = [
                            str(self.lookup_set(ManualFixupIdentifier(in_set)).id)
                            for in_set in in_json["boxOf"]
                        ]

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

                            if "card" in in_pack:
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
        """Saves this database to disk.

        :param generate_individuals: Whether or not to generate individualized JSON files.
        :param generate_aggregates: Whether or not to generate aggregated JSON files.
        """

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
                            (x._to_json() for x in self.cards),
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
            json.dump(card._to_json(), outfile, indent=2)

    def _load_card(self, rawcard: typing.Dict[str, typing.Any]) -> Card:
        return Card(
            id=uuid.UUID(rawcard["id"]),
            text={
                Language.normalize(k): CardText(
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
                Format(k): CardLegality(
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
            language=Language.normalize(rawprinting["language"])
            if "language" in rawprinting
            else None,
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
            Locale.normalize(k): SetLocale(
                key=Locale.normalize(k),
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
                formats=[Format(x) for x in v.get("formats", [])],
                editions=[SetEdition(x) for x in v.get("editions", [])],
                db_ids=v["externalIDs"].get("dbIDs"),
            )
            for k, v in rawset.get("locales", {}).items()
        }

        for content, locale_names in contents:
            content.locales = [
                locales[Locale.normalize(locale_name)]
                for locale_name in locale_names
                if Locale.normalize(locale_name) in locales
            ]

        return Set(
            id=uuid.UUID(rawset["id"]),
            date=datetime.date.fromisoformat(rawset["date"])
            if "date" in rawset
            else None,
            name={Language.normalize(k): v for k, v in rawset["name"].items()},
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
            name={Language.normalize(k): v for k, v in rawseries["name"].items()},
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
            quotas={CardType(k): v for k, v in rawdistro["quotas"].items()}
            if "quotas" in rawdistro
            else None,
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
            Locale.normalize(k): SealedProductLocale(
                key=Locale.normalize(k),
                date=datetime.date.fromisoformat(rawlocale["date"])
                if rawlocale.get("date")
                else None,
                image=rawlocale.get("image"),
                db_ids=rawlocale["externalIDs"].get("dbIDs", []),
                has_hobby_retail_differences=rawlocale["hasHobbyRetailDifferences"]
                if "hasHobbyRetailDifferences" in rawlocale
                else False,
            )
            for k, rawlocale in rawproduct.get("locales", {}).items()
        }

        return SealedProduct(
            id=uuid.UUID(rawproduct["id"]),
            name={Language.normalize(k): v for k, v in rawproduct["name"].items()},
            date=datetime.date.fromisoformat(rawproduct["date"])
            if rawproduct.get("date")
            else None,
            locales=locales,
            contents=[
                SealedProductContents(
                    image=rawcontents.get("image"),
                    locales=[
                        locales[Locale.normalize(x)]
                        for x in rawcontents.get("locales", [])
                    ],
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
            box_of=[self.sets_by_id[uuid.UUID(x)] for x in rawproduct.get("boxOf", [])],
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

    def _deduplicate(
        self, list_: typing.List[typing.Any], dict_: typing.Dict[uuid.UUID, typing.Any]
    ):
        for i, thing in enumerate(list_):
            if dict_.get(thing.id) != thing:
                del list_[i]
                return self._deduplicate(list_, dict_)

    def deduplicate(self):
        with tqdm.tqdm(total=5, desc="Deduplicating database") as progress_bar:
            self._deduplicate(self.cards, self.cards_by_id)
            progress_bar.update(1)
            self._deduplicate(self.sets, self.sets_by_id)
            progress_bar.update(1)
            self._deduplicate(self.series, self.series_by_id)
            progress_bar.update(1)
            self._deduplicate(self.distros, self.distros_by_id)
            progress_bar.update(1)
            self._deduplicate(self.products, self.products_by_id)
            progress_bar.update(1)


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
"""The default repository for the data ZIP files."""

LAST_MODIFIED_HEADER = "Last-Modified"
"""The HTTP header to get when the ZIP files on the server were last modified."""


def load_from_internet(
    *,
    individuals_dir: typing.Optional[str] = None,
    aggregates_dir: typing.Optional[str] = None,
    repository: str = REPOSITORY,
) -> Database:
    """Load a :class:`ygojson.database.Database` from Internet sources.
    This places files into the ``individuals_dir`` and ``aggregates_dir`` specified.
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
                response = requests.get(
                    repository + "/" + zipname,
                    stream=True,
                    headers={
                        "User-Agent": USER_AGENT,
                    },
                )
                if not response.ok:
                    response.raise_for_status()
                with open(zippath, "wb") as file:
                    for chunk in response.iter_content(chunk_size=None):
                        file.write(chunk)
            progress_bar.update(1)

            with open(zippath, "rb") as file, zipfile.ZipFile(file) as zip:
                zip.extractall(dest)
            progress_bar.update(1)

    os.makedirs(TEMP_DIR, exist_ok=True)

    if individuals_dir is not None:
        getzip("individual", individuals_dir)

    if aggregates_dir is not None:
        getzip("aggregate", aggregates_dir)

    return load_from_file(
        individuals_dir=individuals_dir, aggregates_dir=aggregates_dir
    )
