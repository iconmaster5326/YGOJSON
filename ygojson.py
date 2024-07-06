import argparse
import logging
import os.path
import sys
import typing

from src.database import *
from src.importers.yamlyugi import import_from_yaml_yugi
from src.importers.ygoprodeck import import_from_ygoprodeck
from src.importers.yugipedia import import_from_yugipedia


def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    argv = argv or sys.argv
    parser = argparse.ArgumentParser(
        argv[0], description="Generates and queries the YGOJSON database"
    )
    parser.add_argument(
        "--no-individuals",
        action="store_true",
        help="Don't generate individual card/set/etc JSONs",
    )
    parser.add_argument(
        "--no-aggregates",
        action="store_true",
        help="Don't generate aggregate card/set/etc JSONs",
    )
    parser.add_argument(
        "--individuals",
        type=str,
        default="data",
        metavar="DIR",
        help="Directory for individual card/set/etc JSONs",
    )
    parser.add_argument(
        "--aggregates",
        type=str,
        default=os.path.join("data", "aggregate"),
        metavar="DIR",
        help="Directory for aggregate card/set/etc JSONs",
    )
    parser.add_argument(
        "--no-ygoprodeck",
        action="store_true",
        help="Don't import from the YGOPRODECK API",
    )
    parser.add_argument(
        "--no-yamlyugi",
        action="store_true",
        help="Don't import from the Yaml Yugi API",
    )
    parser.add_argument(
        "--no-yugipedia",
        action="store_true",
        help="Don't import from the Yugipedia API",
    )
    parser.add_argument(
        "--no-cards",
        action="store_true",
        help="Don't import cards from external APIs",
    )
    parser.add_argument(
        "--no-sets",
        action="store_true",
        help="Don't import sets from external APIs",
    )
    parser.add_argument(
        "--no-series",
        action="store_true",
        help="Don't import series from external APIs",
    )
    parser.add_argument(
        "--no-regen-backlinks",
        action="store_true",
        help="Don't regenerate backlinks (for example, links from cards to sets)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Pretend we've never looked at our sources before (this does NOT delete database contents)",
    )
    parser.add_argument(
        "--logging",
        type=str,
        default="INFO",
        metavar="LEVEL",
        help="The logging level. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        format="[%(levelname)s] %(message)s",
        level=logging.getLevelName(args.logging.strip().upper()),
    )

    n = 0

    logging.info("Loading database...")
    db = load_database(
        individuals_dir=args.individuals,
        aggregates_dir=args.aggregates,
    )

    if args.fresh:
        db.last_yamlyugi_read = None
        db.last_ygoprodeck_read = None
        db.last_yugipedia_read = None

    if not args.no_ygoprodeck:
        logging.info("Importing from YGOPRODECK...")
        n_old, n_new = import_from_ygoprodeck(
            db,
            import_cards=not args.no_cards,
            import_sets=not args.no_sets,
            import_series=not args.no_series,
        )
        logging.info(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_yamlyugi:
        logging.info("Importing from Yaml Yugi...")
        n_old, n_new = import_from_yaml_yugi(
            db,
            import_cards=not args.no_cards,
            import_sets=not args.no_sets,
            import_series=not args.no_series,
        )
        logging.info(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_yugipedia:
        logging.info("Importing from Yugipedia...")
        n_old, n_new = import_from_yugipedia(
            db,
            import_cards=not args.no_cards,
            import_sets=not args.no_sets,
            import_series=not args.no_series,
        )
        logging.info(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_regen_backlinks:
        logging.info("Regenerating backlinks...")
        db.regenerate_backlinks()

    logging.info("Saving database...")
    db.save(
        generate_individuals=not args.no_individuals,
        generate_aggregates=not args.no_aggregates,
    )

    logging.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
