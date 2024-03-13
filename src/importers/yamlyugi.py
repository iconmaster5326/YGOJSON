# Import data from Yaml Yugi (https://github.com/DawnbrandBots/yaml-yugi).

import json
import os.path
import typing
import uuid

import requests

from ..database import *

DOWNLOAD_URL = "https://github.com/DawnbrandBots/yaml-yugi/raw/aggregate/"
INPUT_CARDS_FILE = os.path.join(TEMP_DIR, "yamlyugi_cards.json")

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
    "Limited 3": Legality.UNLIMITED,
    "Unlimited": Legality.UNLIMITED,
    "Limited 2": Legality.SEMILIMITED,
    "Semi-Limited": Legality.SEMILIMITED,
    "Limited 1": Legality.LIMITED,
    "Limited": Legality.LIMITED,
    "Limited 0": Legality.FORBIDDEN,
    "Forbidden": Legality.FORBIDDEN,
    "Not yet released": Legality.UNRELEASED,
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


def _write_card(in_json: typing.Dict[str, typing.Any], card: Card) -> Card:
    """
    Converts a Yaml Yugi card into a YGOJSON card.
    Overwrites any fields that have changed.
    Use an empty dict to represent a new card.
    """

    for lang, text in in_json["name"].items():
        if "_" not in lang and text is not None:
            if lang not in card.text:
                card.text[lang] = CardText(name=text)
            else:
                card.text[lang].name = text
    for lang, text in in_json.get("text", {}).items():
        if "_" not in lang and text is not None:
            card.text[lang].effect = text
    for lang, text in in_json.get("pendulum_effect", {}).items():
        if "_" not in lang and text is not None:
            card.text[lang].pendulum_effect = text
    # TODO: translation's status as official

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
            print(
                f"warning: card {card.text['en'].name} has no race! Typeline: {in_json['monster_type_line']}"
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
        # TODO: don't rely on string manip here
        card.subcategory = SubCategory(
            in_json.get("property", "normal").lower().replace("-", "")
        )

    if (
        in_json["password"] and in_json["password"] <= MAX_REAL_PASSWORD
    ):  # exclude fake passwords
        password = "%08u" % (in_json["password"],)
        if password not in card.passwords:
            card.passwords.append(password)

    # TODO: images, sets

    for k, v in (in_json["limit_regulation"] or {}).items():
        if not v:
            continue
        if Format(k) in card.legality:
            card.legality[Format(k)].current = LEGALITIES[v]
        else:
            card.legality[Format(k)] = CardLegality(current=LEGALITIES[v])

    if "master_duel_rarity" in in_json:
        card.master_duel_rarity = VideoGameRaity(in_json["master_duel_rarity"].lower())
        # TODO: craftable?

    # TODO: duel links

    card.yugipedia_id = in_json["yugipedia_page_id"]
    card.db_id = in_json["konami_id"]
    card.yamlyugi_id = in_json["password"]
    # TODO: the other IDs

    # TODO: errata, series

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


def import_from_yaml_yugi(
    db: Database,
    *,
    progress_monitor: typing.Optional[typing.Callable[[Card, bool], None]] = None,
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
        db.add_card(card)
        if progress_monitor:
            progress_monitor(card, found)

    db.last_yamlyugi_read = datetime.datetime.now()

    return n_existing, n_new
