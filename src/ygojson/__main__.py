import argparse
import logging
import os.path
import sys
import typing

from ygojson import *
from ygojson.version import __version__


def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    """The main function to the YGOJSON CLI.

    :param argv: The arguments list, as given by `sys.argv`.
    :return: The return code, as given to `sys.exit`.
    """

    argv = argv or sys.argv
    parser = argparse.ArgumentParser(
        argv[0], description="Generates and queries the YGOJSON database"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="show version number and exit",
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
        default=INDIVIDUAL_DIR,
        metavar="DIR",
        help="Directory for individual JSONs, or the empty string to disable",
    )
    parser.add_argument(
        "--aggregates",
        type=str,
        default=AGGREGATE_DIR,
        metavar="DIR",
        help="Directory for aggregate JSONs, or the empty string to disable",
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
        "--no-distros",
        action="store_true",
        help="Don't import pack distributions from external APIs",
    )
    parser.add_argument(
        "--no-products",
        action="store_true",
        help="Don't import sealed products from external APIs",
    )
    parser.add_argument(
        "--no-regen-backlinks",
        action="store_true",
        help="Don't regenerate backlinks (for example, links from cards to sets)",
    )
    parser.add_argument(
        "--no-manual",
        action="store_true",
        help="Don't process manual fixups",
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
    parser.add_argument(
        "--production",
        action="store_true",
        help="Specify this if we're in production. Mostly this prevents unnecesary Yugipedia cache clears when not specified.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the data files from the server before modifying them",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=REPOSITORY,
        metavar="URL",
        help="The download URL for data ZIP files",
    )
    args = parser.parse_args(argv[1:])

    if args.version:
        print(__version__)
        return 0

    logging.basicConfig(
        format="[%(levelname)s] %(message)s",
        level=logging.getLevelName(args.logging.strip().upper()),
    )

    logging.info("Loading database...")
    if args.download:
        db = load_from_internet(
            individuals_dir=args.individuals if args.individuals else None,
            aggregates_dir=args.aggregates if args.aggregates else None,
            repository=args.repository,
        )
    else:
        db = load_from_file(
            individuals_dir=args.individuals if args.individuals else None,
            aggregates_dir=args.aggregates if args.aggregates else None,
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
            production=args.production,
        )
        logging.info(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_regen_backlinks:
        logging.info("Regenerating backlinks...")
        db.regenerate_backlinks()

    if not args.no_manual:
        logging.info("Running manual fixups...")

        if not args.no_distros:
            logging.info("\tImporting pack distributions...")
            db.manually_fixup_distros()

        if not args.no_sets:
            logging.info("\tFixing up sets...")
            db.manually_fixup_sets()

        if not args.no_products:
            logging.info("\tImporting sealed products...")
            db.manually_fixup_products()

    logging.info("Cleaning database...")
    db.deduplicate()

    logging.info("Saving database...")
    db.save(
        generate_individuals=not args.no_individuals,
        generate_aggregates=not args.no_aggregates,
    )

    logging.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
