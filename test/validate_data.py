import json
import os.path
import pathlib
import sys
import typing

import jsonschema
import referencing
import referencing.exceptions
import tqdm

import ygojson

SCHEMA_DIR = os.path.join(ygojson.ROOT_DIR, "schema")
SCHEMA_URI = "https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/"


def removeprefix(self, prefix):
    if self.startswith(prefix):
        return self[len(prefix) :]
    return self


def retrieve_from_filesystem(uri: str):
    if not uri.startswith(SCHEMA_URI):
        raise referencing.exceptions.NoSuchResource(ref=uri)
    path = pathlib.Path(SCHEMA_DIR) / pathlib.Path(removeprefix(uri, SCHEMA_URI))
    return referencing.Resource.from_contents(json.loads(path.read_text()))


REGISTRY = referencing.Registry(retrieve=retrieve_from_filesystem)


def validate(in_json):
    if type(in_json) is dict:
        if "$schema" in in_json:
            resource = REGISTRY.get_or_retrieve(in_json["$schema"])
            if resource and resource.value and resource.value.contents:
                jsonschema.Draft202012Validator(
                    schema=resource.value.contents, registry=REGISTRY
                ).validate(in_json)
            else:
                raise ValueError(f"Could not resolve schema: {in_json['$schema']}")
        else:
            for v in in_json.values():
                validate(v)
    elif type(in_json) is list:
        for v in in_json:
            validate(v)


def main(argv: typing.List[str]) -> int:
    filepaths = [*pathlib.Path(ygojson.DATA_DIR).rglob("*.json")]
    for filepath in tqdm.tqdm(filepaths, desc="Validating data JSON"):
        with filepath.open(encoding="utf-8") as file:
            try:
                validate(json.load(file))
            except Exception:
                print(f"Error in validating {filepath}:")
                raise
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
