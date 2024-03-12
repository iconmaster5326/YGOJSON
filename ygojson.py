from src.database import Database, Card, load_database
from src.importers.yamlyugi import import_from_yaml_yugi

import argparse
import sys
import typing

def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    argv = argv or sys.argv
    parser = argparse.ArgumentParser(
        argv[0], description="Generates and queries the YGOJSON database"
    )
    parser.add_argument("--no-individuals", action="store_true", help="Don't generate individual card/set/etc JSONs")
    parser.add_argument("--no-aggregates", action="store_true", help="Don't generate aggregate card/set/etc JSONs")
    args = parser.parse_args(argv[1:])

    n = 0

    def dbpm(c: Card, f: bool = True):
        nonlocal n
        n += 1
        if n % 250 == 0:
            print("|", end="", flush=True)

    print("Loading database...")
    db = load_database(progress_monitor=dbpm)
    print()
    print("Importing Yaml Yugi data...")
    n_old, n_new = import_from_yaml_yugi(db, progress_monitor=dbpm)
    print()
    print(f"Added {n_new} cards and updated {n_old} cards.")
    print("Saving cards...")
    db.save(
        progress_monitor=dbpm,
        generate_individuals=not args.no_individuals,
        generate_aggregates=not args.no_aggregates
    )
    print()
    print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
