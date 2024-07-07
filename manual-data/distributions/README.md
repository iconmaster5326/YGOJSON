# Pack Distributions

In here goes all the pack distributions used to indicate to users how packs are laid out and can be pulled from.

These files are named by thier name, rather than by their ID, for easier editing.

For the schema these files need to take, see [the JSON schema file](../../schema/v1/distribution.json).

## Example Pack Distribution

```json
{
  "$schema": "https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/schema/v1/distribution.json",
  "id": "02952b2c-8cfa-42a7-8e26-6a7759543e16",
  "name": "test",
  "slots": [
    {
      "type": "pool",
      "qty": 3,
      "rarity": [
        { "chance": 2, "rarities": ["rare"] },
        { "rarities": ["common", "shortprint"] }
      ]
    },
    {
      "type": "guaranteedPrintings",
      "printings": ["a202f7ef-47e9-43fb-aced-127d30de6003"]
    }
  ]
}
```
