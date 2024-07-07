# Sealed Products

Sealed products are things like special boxes, tins, and other bundles, that consist of multiple packs of mulitple sets of things. Note that normal booster boxes are handled via the set schema; this is primarly for products with a heterogeneous mix of things, or products that aren't your standard booster boxes.

These files are named by thier name, rather than by their ID, for easier editing.

For the schema these files need to take, see [the JSON schema file](../../schema/v1/sealedProduct.json).

## Example Sealed Product

```json
{
  "$schema": "https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v1/sealedProduct.json",
  "id": "935ef40b-5691-4e5c-b96f-b71c9c4b2383",
  "name": {
    "en": "Starter Deck Box"
  },
  "locales": {
    "en": {
      "externalIDs": {}
    }
  },
  "contents": [
    {
      "locales": ["en"],
      "packs": [
        { "set": "955828a4-9966-4dab-ac20-36c2d39bf49e", "qty": 5 },
        { "set": "66382e41-4daf-4f0b-83e1-ca50b0a5f9b2", "qty": 5 }
      ]
    }
  ],
  "externalIDs": {}
}
```
