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

*(TODO: download instructions?)*
*(TODO: how often is the database generated?)*

Depending on how you downloaded it, you may have access to two different folders:

* `individual`: Each card, set, etc. is in its own JSON file, whose filename is its UUID.
* `aggregate`: Every card, set, etc. is in one JSON file.

Within each folder should be the data you need. Check out the [JSON schema](https://json-schema.org/) for all this data [here](schema/v1/).

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
