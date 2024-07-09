# YGOJSON

YGOJSON aims to be the ultimate Yugioh database - a set of machine-readable [JSON](https://www.json.org/json-en.html) files detailing:

* Cards, including tokens and skill cards
* Sets, including Duel Links and Master Duel sets
* Archetypes and series information
* Pack odds
* Sealed products, such as tin contents

# Data Sources

We gather our data from the following sources:

* [YGOPRODECK](https://ygoprodeck.com/)
* [Yaml Yugi](https://github.com/DawnbrandBots/yaml-yugi)
* [Yugipedia](https://yugipedia.com/)

Special thanks goes out to [YGO Prog](https://www.ygoprog.com/) for their tireless work on discovering pack odds.

# Using the Database

There are several methods of consuming the database. To get the files, you can either:

* Download a ZIP file [here](https://github.com/iconmaster5326/YGOJSON/releases/latest)
* Download the raw JSON files on the [indiviual](https://github.com/iconmaster5326/YGOJSON/tree/v1/individual) and [aggregate](https://github.com/iconmaster5326/YGOJSON/tree/v1/aggregate) branches

To get the ZIP files in an automated fashion, fetch the following URLs:

* For a individualized ZIP file: https://github.com/iconmaster5326/YGOJSON/releases/download/v1/individual.zip
* For a aggregated ZIP file: https://github.com/iconmaster5326/YGOJSON/releases/download/v1/aggregate.zip

If you don't want everything, or don't want to unzip things, just fetch the following URLs for indiviudal things, with `cards` replaced by the type of things you want, and the UUID replaced with your UUID:

* For individual card JSON files: https://raw.githubusercontent.com/iconmaster5326/YGOJSON/v1/individual/cards/00045021-f0d3-4473-8bbc-8aa6504d3562.json
* For a list of all card UUIDs: https://raw.githubusercontent.com/iconmaster5326/YGOJSON/v1/individual/cards.json
* For all information for all cards: https://raw.githubusercontent.com/iconmaster5326/YGOJSON/v1/aggregate/cards.json

You may have noticed the two different ways of getting the data: individual and aggregate. The differences between the two are as follows:

* `individual`: Each card, set, etc. is in its own JSON file, whose filename is its UUID.
* `aggregate`: Every card, set, etc. is in one JSON file.

Within each folder should be the data you need. Check out the [JSON schema](https://json-schema.org/) for all this data [here](schema/v1/).

We have the following things available for you:

* `cards`: Yugioh cards. This includes tokens and Speed Duel skill cards. This does NOT include Rush Duel cards, and does NOT include video-game exclusive cards.
* `sets`: Yugioh products such as booster packs, decks, and sets of promotional cards.
* `series`: Information about archetypes and series.
* `sealedProducts`: Sealed products are things like booster boxes, tins, and other things that consist of a mix of packs.
* `distributions`: Pack odds information for sets. You can use this to figure out how to make random packs of sets accurately.

The data is regenerated from our sources every day at midnight. So if you don't see the latest new cards in the database yet, wait a bit!

## Using the YGOJSON API

The API we use to make the database has facilities for you to load any YGOJSON database and manipulate it using a convientient [Python](https://www.python.org/) API. To get our API from [PyPI](https://pypi.org), you can simply do the following:

```bash
python3 -m pip install ygojson
```

From there, you can write Python code to load the database and have fun with it:

```python
# you'll need to specify where the database goes on your filesystem
INDIVIDUALS_DIR = "path/to/unzipped/individuals/dir"
AGGREGATES_DIR = "path/to/unzipped/aggregates/dir"

# import only the code that deals with the database schema
import ygojson.database

# construct the database; you can omit one if you don't have both downloaded
# (there is also load_from_file if you already have the files)
db = ygojson.database.load_from_internet(individuals_dir=INDIVIDUALS_DIR, aggregates_dir=AGGREGATES_DIR)

# print the name of every card
for card in db.cards:
    print(card.text["en"].name)
```

# Generating the Database

You'll need a modern version of Python, at least 3.8, to run this code. To install YGOJSON:

```bash
python3 -m pip install -e .
```

Then you can run the database generator via the `ygojson` command, or by `python3 -m ygojson`. Here are the command-line arguments I usually pass when testing:

```bash
ygojson --download --individuals "" --no-individuals
```

Try `-h` or `--help` for more command-line options.

By default, it will place the generated JSON files in the `data` folder. It will also create a `temp` folder, containing things like the Yugipedia cache. (Yugipedia takes several hours to download from a fresh cache, and hammers their servers a bit more than I'd like, so only delete that cache when absolutely necesary!)

The [`manual-data`](manual-data) folder contains all the things that aren't covered nicely by any of our data sources. This includes things like pack odds and sealed products, as well as some set information.

# Contributing

The biggest thing you can do is report bad data. Something we have in our database incorrect? Tell us via our issue tracker! Before you do, though, please look at our data sources if you can, to see if the problem lies with their data or not. If it's with them, bring it up with them!

Another thing you can do is submit additions to [`manual-data`](manual-data) when new things come out. That's also extremly helpful. Check out the READMEs in the subdirectories for more details.

If you want to contribute code changes or test your manual fixup changes, you can install YGOJSON for editing and testing like so:

```bash
python3 -m pip install -e .[dev,test]
pre-commit install
```

From there, you can run YGOJSON as you will, and there are some tests you can run before making your pull requests like so:

```bash
python3 test/validate_data.py # runs a JSON schema validator against everything in the data/ folder
```

# Schema Changelog

## v1

Initial release.

# Python API Changelog

## 0.1.0

Initial release.
