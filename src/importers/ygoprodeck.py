# Import data from YGOProDeck (https://ygoprodeck.com/card-database/).

import json
import os.path
import time
import typing
import uuid

import requests

from ..database import *

API_URL = "https://db.ygoprodeck.com/api/v7/"

INPUT_CARDS_FILE = os.path.join(TEMP_DIR, "ygoprodeck_cards.json")
REFRESH_TIMER = 4 * 60 * 60
MAX_REAL_PASSWORD = 99999999

MONSTER_CARD_TYPES = {
    "Ritual": MonsterCardType.RITUAL,
    "Fusion": MonsterCardType.FUSION,
    "Synchro": MonsterCardType.SYNCHRO,
    "XYZ": MonsterCardType.XYZ,
    "Pendulum": MonsterCardType.PENDULUM,
    "Link": MonsterCardType.LINK,
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
    "Top-Left": LinkArrow.TOPLEFT,
    "Top": LinkArrow.TOPCENTER,
    "Top-Right": LinkArrow.TOPRIGHT,
    "Left": LinkArrow.MIDDLELEFT,
    "Right": LinkArrow.MIDDLERIGHT,
    "Bottom-Left": LinkArrow.BOTTOMLEFT,
    "Bottom": LinkArrow.BOTTOMCENTER,
    "Bottom-Right": LinkArrow.BOTTOMRIGHT,
}

_cached_cards = None


def _get_ygoprodeck_cards() -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Gets the input YGOProDeck raw JSON data for all cards.
    Caches the value if possible.
    """
    global _cached_cards
    if _cached_cards is not None:
        return _cached_cards
    if os.path.exists(INPUT_CARDS_FILE):
        if os.stat(INPUT_CARDS_FILE).st_mtime >= time.time() - REFRESH_TIMER:
            with open(INPUT_CARDS_FILE, encoding="utf-8") as in_cards_file:
                _cached_cards = json.load(in_cards_file)
            return _cached_cards
    os.makedirs(TEMP_DIR, exist_ok=True)
    response = requests.get(API_URL + "cardinfo.php", params={"misc": "yes"})
    if response.ok:
        with open(INPUT_CARDS_FILE, "w", encoding="utf-8") as in_cards_file:
            _cached_cards = response.json()["data"]
            json.dump(_cached_cards, in_cards_file, indent=2)
        return _cached_cards
    response.raise_for_status()
    assert False


def _parse_cardtype(typeline: str) -> CardType:
    if "Monster" in typeline:
        return CardType.MONSTER
    elif "Spell" in typeline:
        return CardType.SPELL
    elif "Trap" in typeline:
        return CardType.TRAP
    elif "Skill" in typeline or "Token" in typeline:
        raise InvalidCardImport

    print(f"warning: Unknown card type: {typeline}")
    raise InvalidCardImport


class InvalidCardImport(Exception):
    pass


def _import_card(
    in_json: typing.Dict[str, typing.Any],
    db: Database,
) -> typing.Tuple[bool, Card]:
    """
    Finds an existing card in the database, if it's there.
    Otherwise creates a new card object, not added to the DB.
    """

    card = db.cards_by_ygoprodeck_id.get(in_json["id"])
    if card is not None:
        return True, card

    if "misc_info" in in_json and len(in_json["misc_info"]) == 1:
        card = db.cards_by_ygoprodeck_id.get(in_json["misc_info"][0].get("beta_id"))
        if card is not None:
            return True, card

        card = db.cards_by_konami_cid.get(in_json["misc_info"][0].get("konami_id"))
        if card is not None:
            return True, card

    card = db.cards_by_password.get(in_json["id"])
    if card is not None:
        return True, card

    card = db.cards_by_en_name.get(in_json["name"])
    if card is not None:
        return True, card

    if "misc_info" in in_json and len(in_json["misc_info"]) == 1:
        card = db.cards_by_en_name.get(in_json["misc_info"][0].get("beta_name"))
        if card is not None:
            return True, card

    cardtype = _parse_cardtype(in_json.get("type", ""))

    # if cardtype == CardType.MONSTER:
    #     if not in_json.get("attribute"):
    #         print(f"warning: card {in_json['name']} is missing an attribute!")
    #         raise InvalidCardImport

    return False, Card(id=uuid.uuid4(), card_type=cardtype)


def _write_card(in_json: typing.Dict[str, typing.Any], card: Card) -> Card:
    """
    Converts a YGOProDeck card into a YGOJSON card.
    Overwrites any fields that have changed.
    """

    card.text.setdefault("en", CardText(name=in_json["name"]))
    en_text = card.text["en"]
    en_text.effect = in_json.get("desc") or en_text.effect
    en_text.pendulum_effect = in_json.get("pend_desc") or en_text.pendulum_effect

    if card.card_type == CardType.MONSTER:
        typeline = in_json["type"].split(" ")

        card.attribute = Attribute(in_json["attribute"].lower())
        card.monster_card_types = []
        for i, v in MONSTER_CARD_TYPES.items():
            if i in typeline:
                card.monster_card_types.append(v)
        card.type = Race(in_json["race"].lower().replace("-", "").replace(" ", ""))
        card.classifications = []
        for i, v in CLASSIFICATIONS.items():
            if i in typeline:
                card.classifications.append(v)
        card.abilities = []
        for i, v in ABILITIES.items():
            if i in typeline:
                card.abilities.append(v)
        if MonsterCardType.XYZ in (card.monster_card_types or []):
            card.rank = in_json.get("level")
        else:
            card.level = in_json.get("level")
        if "atk" in in_json:
            if type(in_json["atk"]) is int or in_json["atk"] == "?":
                card.atk = in_json["atk"]
            else:
                print(
                    f"warning: card {en_text.name} (id {card.id}) has bad ATK: {in_json.get('atk')}"
                )
        if "def" in in_json:
            if type(in_json["def"]) is int or in_json["def"] == "?":
                card.def_ = in_json["def"]
            else:
                print(
                    f"warning: card {en_text.name} (id {card.id}) has bad DEF: {in_json.get('def')}"
                )
        card.scale = in_json.get("scale")
        if MonsterCardType.LINK in (card.monster_card_types or []):
            card.link_arrows = [LINK_ARROWS[x] for x in in_json["linkmarkers"]]
    else:
        if in_json.get("race"):
            card.subcategory = SubCategory(in_json["race"].lower().replace("-", ""))

    if in_json["id"] <= MAX_REAL_PASSWORD:  # exclude fake passwords
        password = "%08u" % (in_json["id"],)
        if password not in card.passwords:
            card.passwords.append(password)

    for in_image in in_json.get("card_images") or []:
        # image IDs are either the password of the art variant,
        # or something entirely made up that fits within the 8-digit password range.
        # The later case, then, is a bit of a nightmare.
        # we try to match by password, and then by image URL.
        existing_image: typing.Union[CardImage, None] = None
        for image in card.images:
            if image.password == in_image["id"]:
                existing_image = image
                break
        if not existing_image:
            for image in card.images:
                if image.card_art == in_image["image_url"]:
                    existing_image = image
                    break
        if not existing_image:
            existing_image = CardImage(id=uuid.uuid4())
            card.images.append(existing_image)

        if in_image["id"] in card.passwords or len(card.passwords) == 1:
            # because of Dark Magician,
            # we can't associate alt arts w/o a unique password here with the primary password.
            existing_image.password = "%08u" % (in_image["id"],)
        existing_image.card_art = in_image["image_url"]
        existing_image.crop_art = in_image["image_url_cropped"]

    # TODO: sets

    card.ygoprodeck = ExternalIdPair(
        in_json["ygoprodeck_url"].replace("https://ygoprodeck.com/card/", ""),
        in_json["id"],
    )
    if "misc_info" in in_json and len(in_json["misc_info"]) > 0:
        if len(in_json["misc_info"]) == 1:
            card.db_id = in_json["misc_info"][0].get("konami_id", card.db_id)
        else:
            print(
                f"warning: card {en_text.name} (id {card.id}) has {len(in_json['misc_info'])} misc_infos!"
            )

    return card


def import_from_ygoprodeck(
    db: Database,
    *,
    progress_monitor: typing.Optional[typing.Callable[[Card, bool], None]] = None,
) -> typing.Tuple[int, int]:
    """
    Import card data from YGOProDeck into the given database.
    Returns the number of existing and new cards found in YGOProDeck.
    """

    n_existing = 0
    n_new = 0
    cardinfo = _get_ygoprodeck_cards()

    for in_card in cardinfo:
        try:
            found, card = _import_card(in_card, db)
            if found:
                n_existing += 1
            else:
                n_new += 1
            card = _write_card(in_card, card)
            db.add_card(card)
            if progress_monitor:
                progress_monitor(card, found)
        except InvalidCardImport:
            pass

    db.last_ygoprodeck_read = datetime.datetime.now()

    return n_existing, n_new
