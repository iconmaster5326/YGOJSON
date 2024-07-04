import argparse
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
    args = parser.parse_args(argv[1:])

    n = 0

    def dbpm(c: typing.Union[Card, Set], f: bool = True):
        nonlocal n
        n += 1
        if n % 250 == 0:
            print("|", end="", flush=True)

    print("Loading database...")
    db = load_database(
        progress_monitor=dbpm,
        individuals_dir=args.individuals,
        aggregates_dir=args.aggregates,
    )
    print()

    if not args.no_ygoprodeck:
        print("Importing YGOProDeck data...")
        n_old, n_new = import_from_ygoprodeck(
            db,
            progress_monitor=dbpm,
            import_cards=not args.no_cards,
            import_sets=args.no_sets,
        )
        print()
        print(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_yamlyugi:
        print("Importing Yaml Yugi data...")
        n_old, n_new = import_from_yaml_yugi(
            db,
            progress_monitor=dbpm,
            import_cards=not args.no_cards,
            import_sets=args.no_sets,
        )
        print()
        print(f"Added {n_new} cards and updated {n_old} cards.")

    if not args.no_yugipedia:
        print("Importing Yugipedia data...")
        n_old, n_new = import_from_yugipedia(
            db,
            progress_monitor=dbpm,
            import_cards=not args.no_cards,
            import_sets=args.no_sets,
        )
        print()
        print(f"Added {n_new} cards and updated {n_old} cards.")

    print("Saving database...")
    db.save(
        progress_monitor=dbpm,
        generate_individuals=not args.no_individuals,
        generate_aggregates=not args.no_aggregates,
    )
    print()
    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
