from src.database import Database, Card, load_database
from src.importers.yamlyugi import import_from_yaml_yugi

import sys
import typing

def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv
        
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
    db.save(progress_monitor=dbpm)
    print()
    print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
