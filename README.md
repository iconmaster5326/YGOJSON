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

*(TODO: how often is the database generated?)*

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

# Generating the Database

You'll need a modern version of [Python](https://www.python.org/) to run this code. To install YGOJSON:

```bash
pip3 install -e .
```

Then you can run the database generator via:

```bash
ygojson
```

Try `-h` or `--help` for command-line options.

By default, it will place the generated JSON files in the `data` folder. It will also create a `temp` folder, containing things like the Yugipedia cache. (Yugipedia takes several hours to download from a fresh cache, and hammers their servers a bit more than I'd like, so only delete that cache when absolutely necesary!)

The `manual-data` folder contains all the things that aren't covered nicely by any of our data sources. This includes things like pack odds and sealed products, as well as some set information.

# Contributing

The biggest thing you can do is report bad data. Something we have in our database incorrect? Tell us via our issue tracker! Before you do, though, please look at our data sources if you can, to see if the problem lies with their data or not. If it's with them, bring it up with them!

Another thing you can do is submit additions to `manual-data` when new things come out. That's also extremly helpful.

Finally, if you want to contribute code changes, be sure to have [pre-commit](https://pre-commit.com/) installed:

```bash
pip3 install pre-commit
pre-commit install
```
