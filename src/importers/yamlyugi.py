# Import data from Yaml Yugi (https://github.com/DawnbrandBots/yaml-yugi).

import os.path
import json
import typing
import uuid

import requests

from ..database import TEMP_DIR, Database, Card, load_database

DOWNLOAD_URL = "https://github.com/DawnbrandBots/yaml-yugi/raw/aggregate/"
INPUT_CARDS_FILE = os.path.join(TEMP_DIR, "yamlyugi_cards.json")

MONSTER_CARD_TYPES = {
    "Ritual": "ritual",
    "Fusion": "fusion",
    "Synchro": "synchro",
    "Xyz": "xyz",
    "Pendulum": "pendulum",
    "Link": "link",
}
TYPES = {
    "Beast-Warrior": "beastwarrior",
    "Zombie": "zombie",
    "Fiend": "fiend",
    "Dinosaur": "dinosaur",
    "Dragon": "dragon",
    "Beast": "beast",
    "Illusion": "illusion",
    "Insect": "insect",
    "Winged Beast": "wingedbeast",
    "Warrior": "warrior",
    "Sea Serpent": "seaserpent",
    "Aqua": "aqua",
    "Pyro": "pyro",
    "Thunder": "thunder",
    "Spellcaster": "spellcaster",
    "Plant": "plant",
    "Rock": "rock",
    "Reptile": "reptile",
    "Fairy": "fairy",
    "Fish": "fish",
    "Machine": "machine",
    "Divine-Beast": "divinebeast",
    "Psychic": "psychic",
    "Creator God": "creatorgod",
    "Wyrm": "wyrm",
    "Cyberse": "cyberse",
}
CLASSIFICATIONS = {
    "Normal": "normal",
    "Effect": "effect",
    "Pendulum": "pendulum",
    "Tuner": "tuner",
    # specialsummon omitted
}
ABILITIES = {
    "Toon": "toon",
    "Spirit": "spirit",
    "Union": "union",
    "Gemini": "gemini",
    "Flip": "flip",
}
LINK_ARROWS = {
    "↖": "topleft",
    "⬆": "topcenter",
    "↗": "topright",
    "⬅": "middleleft",
    "➡": "middleright",
    "↙": "bottomleft",
    "⬇": "bottomcenter",
    "↘": "bottomright",
}
MAX_REAL_PASSWORD = 99999999

_cached_yamlyugi = None


def _get_yaml_yugi() -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Gets the input Yaml Yugi raw JSON data for all cards.
    Caches the value if possible.
    """
    global _cached_yamlyugi
    if _cached_yamlyugi is not None:
        return _cached_yamlyugi
    if os.path.exists(INPUT_CARDS_FILE):
        with open(INPUT_CARDS_FILE, encoding="utf-8") as in_cards_file:
            _cached_yamlyugi = json.load(in_cards_file)
        return _cached_yamlyugi
    os.makedirs(TEMP_DIR, exist_ok=True)
    response = requests.get(DOWNLOAD_URL + "cards.json")
    if response.ok:
        with open(INPUT_CARDS_FILE, "w", encoding="utf-8") as in_cards_file:
            _cached_yamlyugi = response.json()
            json.dump(_cached_yamlyugi, in_cards_file, indent=2)
        return _cached_yamlyugi
    response.raise_for_status()
    assert False


def _init_obj(json, key):
    if key not in json:
        json[key] = {}


def _init_arr(json, key):
    if key not in json:
        json[key] = []


def _write_card(
    in_json: typing.Dict[str, typing.Any], out_json: typing.Dict[str, typing.Any]
) -> typing.Dict[str, typing.Any]:
    """
    Converts a Yaml Yugi card into a YGOJSON card.
    Overwrites any fields that have changed.
    Use an empty dict to represent a new card.
    """
    out_json["$schema"] = "https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v1/card.json"
    if "id" not in out_json:
        out_json["id"] = str(uuid.uuid4())

    _init_obj(out_json, "text")
    for lang, text in in_json["name"].items():
        if "_" not in lang and text is not None:
            _init_obj(out_json["text"], lang)
            out_json["text"][lang]["name"] = text
    for lang, text in in_json.get("text", {}).items():
        if "_" not in lang and text is not None:
            _init_obj(out_json["text"], lang)
            out_json["text"][lang]["effect"] = text
    for lang, text in in_json.get("pendulum_effect", {}).items():
        if "_" not in lang and text is not None:
            _init_obj(out_json["text"], lang)
            out_json["text"][lang]["pendulumEffect"] = text
    # TODO: translation's status as official

    card_type = out_json["cardType"] = in_json["card_type"].lower()

    if card_type == "monster":
        # monster
        typeline = in_json["monster_type_line"].split(" / ")

        out_json["attribute"] = in_json["attribute"].lower()

        out_json["monsterCardTypes"] = []
        for k, v in MONSTER_CARD_TYPES.items():
            if k in typeline:
                out_json["monsterCardTypes"].append(v)

        out_json["type"] = None
        for k, v in TYPES.items():
            if k in typeline:
                out_json["type"] = v
                break

        out_json["classifications"] = []
        for k, v in CLASSIFICATIONS.items():
            if k in typeline:
                out_json["classifications"].append(v)

        out_json["abilities"] = []
        for k, v in ABILITIES.items():
            if k in typeline:
                out_json["abilities"].append(v)

        if "level" in in_json:
            out_json["level"] = in_json["level"]
        if "rank" in in_json:
            out_json["rank"] = in_json["rank"]
        out_json["atk"] = in_json["atk"]
        if "def" in in_json:
            out_json["def"] = in_json["def"]
        if "pendulum_scale" in in_json:
            out_json["scale"] = in_json["pendulum_scale"]

        if "link_arrows" in in_json:
            out_json["linkArrows"] = [LINK_ARROWS[x] for x in in_json["link_arrows"]]
    else:
        # spell/trap
        out_json["subcategory"] = in_json.get("property", "normal").lower()

    _init_arr(out_json, "passwords")
    if (
        in_json["password"] and in_json["password"] <= MAX_REAL_PASSWORD
    ):  # exclude fake passwords
        password = "%08u" % (in_json["password"],)
        if password not in out_json["passwords"]:
            out_json["passwords"].append(password)

    _init_arr(out_json, "images")  # TODO
    _init_arr(out_json, "sets")  # TODO

    _init_obj(out_json, "legality")
    for k, v in (in_json["limit_regulation"] or {}).items():
        _init_obj(out_json["legality"], k)
        out_json["legality"][k]["current"] = v

    if "master_duel_rarity" in in_json:
        _init_obj(out_json, "masterDuel")
        out_json["masterDuel"]["rarity"] = in_json["master_duel_rarity"].lower()

    # TODO: duel links

    _init_obj(out_json, "externalIDs")
    out_json["externalIDs"]["yugipediaID"] = in_json["yugipedia_page_id"]
    out_json["externalIDs"]["dbID"] = in_json["konami_id"]
    out_json["externalIDs"]["yamlyugiID"] = in_json["password"]
    # TODO: the other IDs

    # TODO: errata
    _init_arr(out_json, "series")  # TODO

    return out_json


def _import_card(
    in_json: typing.Dict[str, typing.Any],
    db: Database,
) -> typing.Tuple[bool, typing.Dict[str, typing.Any]]:
    """
    Searches for a matching card in the database, or creates a new card.
    """

    if "konami_id" in in_json and in_json["konami_id"] in db.cards_by_konami_cid:
        return True, db.cards_by_konami_cid[in_json["konami_id"]]
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

    return False, {}


def import_from_yaml_yugi(
    db: Database,
    *,
    progress_monitor: typing.Optional[
        typing.Callable[[Card, bool], None]
    ] = None,
) -> typing.Tuple[int, int]:
    """
    Import card data from Yaml Yugi into the given database.
    Returns the number of existing and new cards found in Yaml Yugi.
    """
    n_existing = 0
    n_new = 0
    yamlyugi = _get_yaml_yugi()
    for in_card in yamlyugi:
        found, card = _import_card(in_card, db)
        if found:
            n_existing += 1
        else:
            n_new += 1
        card = _write_card(in_card, card)
        db.addCard(card)
        if progress_monitor:
            progress_monitor(card, found)
    return n_existing, n_new
