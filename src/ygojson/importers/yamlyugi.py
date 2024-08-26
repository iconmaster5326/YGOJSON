# Import data from Yaml Yugi (https://github.com/DawnbrandBots/yaml-yugi).

import json
import logging
import os.path
import time
import typing
import uuid

import requests
import tqdm

from ..database import *

DOWNLOAD_URL = "https://github.com/DawnbrandBots/yaml-yugi/raw/"
AGGREGATES_DOWNLOAD_URL = DOWNLOAD_URL + "aggregate/"
RAW_DOWNLOAD_URL = DOWNLOAD_URL + "/master/data/"
INPUT_CARDS_FILE = os.path.join(TEMP_DIR, "yamlyugi_cards.json")
INPUT_SERIES_FILE = os.path.join(TEMP_DIR, "yamlyugi_series.json")
REFRESH_TIMER = 4 * 60 * 60

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
LINK_ARROWS = {
    "↖": LinkArrow.TOPLEFT,
    "⬆": LinkArrow.TOPCENTER,
    "↗": LinkArrow.TOPRIGHT,
    "⬅": LinkArrow.MIDDLELEFT,
    "➡": LinkArrow.MIDDLERIGHT,
    "↙": LinkArrow.BOTTOMLEFT,
    "⬇": LinkArrow.BOTTOMCENTER,
    "↘": LinkArrow.BOTTOMRIGHT,
}
LEGALITIES = {
    "Limited 3": Legality.LIMIT3,
    "Unlimited": Legality.UNLIMITED,
    "Limited 2": Legality.LIMIT2,
    "Semi-Limited": Legality.SEMILIMITED,
    "Limited 1": Legality.LIMIT1,
    "Limited": Legality.LIMITED,
    "Limited 0": Legality.FORBIDDEN,
    "Forbidden": Legality.FORBIDDEN,
    "Not yet released": Legality.UNRELEASED,
}
MAX_REAL_PASSWORD = 99999999

_cached_yamlyugi_cards = None
_cached_yamlyugi_series = None


def _get_yaml_yugi_cards() -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Gets the input Yaml Yugi raw JSON data for all cards.
    Caches the value if possible.
    """
    global _cached_yamlyugi_cards
    if _cached_yamlyugi_cards is not None:
        return _cached_yamlyugi_cards
    if os.path.exists(INPUT_CARDS_FILE):
        if os.stat(INPUT_CARDS_FILE).st_mtime >= time.time() - REFRESH_TIMER:
            with open(INPUT_CARDS_FILE, encoding="utf-8") as in_cards_file:
                _cached_yamlyugi_cards = json.load(in_cards_file)
            return _cached_yamlyugi_cards
    os.makedirs(TEMP_DIR, exist_ok=True)
    with tqdm.tqdm(total=1, desc="Downloading Yaml Yugi card list") as progress_bar:
        response = requests.get(
            AGGREGATES_DOWNLOAD_URL + "cards.json",
            headers={
                "User-Agent": USER_AGENT,
            },
        )
        if response.ok:
            with open(INPUT_CARDS_FILE, "w", encoding="utf-8") as in_cards_file:
                _cached_yamlyugi_cards = response.json()
                json.dump(_cached_yamlyugi_cards, in_cards_file, indent=2)
            progress_bar.update(1)
            return _cached_yamlyugi_cards
        response.raise_for_status()
        assert False


def _get_yaml_yugi_series() -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Gets the input Yaml Yugi raw JSON data for all series.
    Caches the value if possible.
    """
    global _cached_yamlyugi_series
    if _cached_yamlyugi_series is not None:
        return _cached_yamlyugi_series
    if os.path.exists(INPUT_SERIES_FILE):
        if os.stat(INPUT_SERIES_FILE).st_mtime >= time.time() - REFRESH_TIMER:
            with open(INPUT_SERIES_FILE, encoding="utf-8") as in_series_file:
                _cached_yamlyugi_series = json.load(in_series_file)
            return _cached_yamlyugi_series
    os.makedirs(TEMP_DIR, exist_ok=True)
    with tqdm.tqdm(total=1, desc="Downloading Yaml Yugi series list") as progress_bar:
        response = requests.get(
            RAW_DOWNLOAD_URL + "series/list.json",
            headers={
                "User-Agent": USER_AGENT,
            },
        )
        if response.ok:
            with open(INPUT_SERIES_FILE, "w", encoding="utf-8") as in_series_file:
                _cached_yamlyugi_series = response.json()
                json.dump(_cached_yamlyugi_series, in_series_file, indent=2)
            progress_bar.update(1)
            return _cached_yamlyugi_series
        response.raise_for_status()
        assert False


def _write_card(
    db: Database,
    in_json: typing.Dict[str, typing.Any],
    card: Card,
    series_map: typing.Dict[str, typing.List[Card]],
) -> Card:
    """
    Converts a Yaml Yugi card into a YGOJSON card.
    Overwrites any fields that have changed.
    Use an empty dict to represent a new card.
    """

    for rawlang, text in in_json["name"].items():
        if "_" in rawlang:
            continue
        lang = Language.normalize(rawlang)
        if text is not None:
            if lang not in card.text:
                card.text[lang] = CardText(name=text)
            else:
                card.text[lang].name = text
    for rawlang, text in in_json.get("text", {}).items():
        if "_" in rawlang:
            continue
        lang = Language.normalize(rawlang)
        if text is not None:
            card.text[lang].effect = text
    for rawlang, text in in_json.get("pendulum_effect", {}).items():
        if "_" in rawlang:
            continue
        lang = Language.normalize(rawlang)
        if text is not None:
            card.text[lang].pendulum_effect = text

    if card.card_type == CardType.MONSTER:
        # monster
        typeline = [s.strip() for s in in_json["monster_type_line"].split(" / ")]

        card.attribute = Attribute(in_json["attribute"].lower())

        card.monster_card_types = []
        for k, v in MONSTER_CARD_TYPES.items():
            if k in typeline:
                card.monster_card_types.append(v)

        card.type = None
        for k, v in TYPES.items():
            if k in typeline:
                card.type = v
                break
        if not card.type:
            logging.warn(
                f"Card {card.text[Language.ENGLISH].name} has no race! Typeline: {in_json['monster_type_line']}"
            )
            card.type = Race.CREATORGOD

        card.classifications = []
        for k, v in CLASSIFICATIONS.items():
            if k in typeline:
                card.classifications.append(v)

        card.abilities = []
        for k, v in ABILITIES.items():
            if k in typeline:
                card.abilities.append(v)

        if "level" in in_json:
            card.level = in_json["level"]
        if "rank" in in_json:
            card.rank = in_json["rank"]
        card.atk = in_json["atk"]
        if "def" in in_json:
            card.def_ = in_json["def"]
        if "pendulum_scale" in in_json:
            card.scale = in_json["pendulum_scale"]
        if "link_arrows" in in_json:
            card.link_arrows = [LINK_ARROWS[x] for x in in_json["link_arrows"]]
    else:
        # spell/trap
        card.subcategory = SubCategory(
            in_json.get("property", "normal").lower().replace("-", "")
        )

    if (
        in_json["password"]
        and in_json["password"] > 0
        and in_json["password"] <= MAX_REAL_PASSWORD
    ):  # exclude fake passwords
        password = "%08u" % (in_json["password"],)
        if password not in card.passwords:
            card.passwords.append(password)

    # we skip images here:
    # they're just links to unresolved Yugipedia images,
    # which is (a) unhelpful and (b) handled by the Yugipedia importer anyways.

    for k, v in (in_json["limit_regulation"] or {}).items():
        if not v:
            continue
        if v not in LEGALITIES:
            logging.warn(
                f"Card {card.text[Language.ENGLISH].name} has unknown legality in format {k}: {v}"
            )
            continue
        if k not in Format._value2member_map_:
            logging.warn(
                f"Found unknown legality format in {card.text[Language.ENGLISH].name}: {k}"
            )
            continue
        fmt = Format(k)
        if fmt in card.legality:
            card.legality[fmt].current = LEGALITIES[v]
        else:
            card.legality[fmt] = CardLegality(current=LEGALITIES[v])

    if "master_duel_rarity" in in_json:
        card.master_duel_rarity = VideoGameRaity(in_json["master_duel_rarity"].lower())

    yugipedia_id = in_json["yugipedia_page_id"]
    if not card.yugipedia_pages:
        card.yugipedia_pages = []
    if not any(x.id == yugipedia_id for x in card.yugipedia_pages):
        # TODO: validate that none of these ""s are left after Yugipedia runs
        card.yugipedia_pages.append(ExternalIdPair("", yugipedia_id))
    card.db_id = in_json["konami_id"]
    card.yamlyugi_id = in_json["password"]

    for series in in_json.get("series", []):
        series_map.setdefault(series, [])
        series_map[series].append(card)

    return card


def _import_card(
    in_json: typing.Dict[str, typing.Any],
    db: Database,
) -> typing.Tuple[bool, Card]:
    """
    Searches for a matching card in the database, or creates a new card.
    """

    if "konami_id" in in_json and in_json["konami_id"] in db.cards_by_konami_cid:
        return True, db.cards_by_konami_cid[in_json["konami_id"]]
    if (
        "yugipedia_page_id" in in_json
        and in_json["yugipedia_page_id"] in db.cards_by_yugipedia_id
    ):
        return True, db.cards_by_yugipedia_id[in_json["yugipedia_page_id"]]
    if "password" in in_json and in_json["password"] in db.cards_by_yamlyugi:
        return True, db.cards_by_yamlyugi[in_json["password"]]
    if (
        "password" in in_json
        and in_json["password"]
        and "%08u" % (in_json["password"],) in db.cards_by_password
    ):
        return True, db.cards_by_password["%08u" % (in_json["password"],)]
    if (
        "name" in in_json
        and "en" in in_json["name"]
        and in_json["name"]["en"] in db.cards_by_en_name
    ):
        return True, db.cards_by_en_name[in_json["name"]["en"]]

    return False, Card(
        id=uuid.uuid4(), card_type=CardType(in_json["card_type"].lower())
    )


def _import_series(
    in_series: typing.Dict[str, typing.Any], db: Database
) -> typing.Tuple[bool, typing.Optional[Series]]:
    if "en" not in in_series:
        # series never lack english names, but we play it safe here
        return False, None

    name = in_series["en"]
    if name in db.series_by_en_name:
        return True, db.series_by_en_name[name]
    return False, Series(id=uuid.uuid4())


def _write_series(
    db: Database,
    in_series: typing.Dict[str, typing.Any],
    series: Series,
    series_map: typing.Dict[str, typing.List[Card]],
) -> Series:
    name = in_series["en"]

    for k, v in in_series.items():
        if v:
            series.name[Language.normalize(k)] = v

    for card in series_map.get(name, []):
        series.members.add(card)

    return series


def import_from_yaml_yugi(
    db: Database,
    *,
    import_cards: bool = True,
    import_sets: bool = True,
    import_series: bool = True,
) -> typing.Tuple[int, int]:
    """
    Import card data from Yaml Yugi into the given database.
    Returns the number of existing and new cards found in Yaml Yugi.
    """

    n_existing = 0
    n_new = 0
    yamlyugi_cards = _get_yaml_yugi_cards()
    yamlyugi_series = _get_yaml_yugi_series()
    series_map: typing.Dict[str, typing.List[Card]] = {}

    if import_cards:
        for in_card in tqdm.tqdm(yamlyugi_cards, desc="Importing cards from Yaml Yugi"):
            found, card = _import_card(in_card, db)
            if found:
                n_existing += 1
            else:
                n_new += 1
            card = _write_card(db, in_card, card, series_map)
            db.add_card(card)

    if import_series:
        for in_series in tqdm.tqdm(
            yamlyugi_series, desc="Importing series from Yaml Yugi"
        ):
            found, series = _import_series(in_series, db)
            if series:
                if found:
                    n_existing += 1
                else:
                    n_new += 1
                card = _write_series(db, in_series, series, series_map)
                db.add_series(series)

    db.last_yamlyugi_read = datetime.datetime.now()

    return n_existing, n_new
