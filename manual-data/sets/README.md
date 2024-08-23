# Set fixup data

This folder contains set fixup data, used to enhance the information we pull from Yugipedia for sets.

Each file here is a JSON file with the following sort of format:

```json
{
    "sets": [ // the sets to modify; each field is optional, but at least one field is needed to look up a set
        {"id": "00000000-0000-0000-0000-000000000000", "name": "Example Set One"},
        {"id": "00000000-0000-0000-0000-000000000000", "name": "Example Set Two"},
    ],
    "contents": [
        {
            "locales": ["en"], // optional; if omitted, will apply to all locales
            "distribution": {"name": "Basic Pack"}, // optional
            "box": { // optional
                "nPacks": 30, // required
                "hasHobbyRetailDifferences": true, // optional
                "image": "https://example.com/image.png", // optional
            },
            "perSet": [ // per-set data to modify; order is in the same order as 'sets' above
                {
                    "ygoprodeck": "Example Set 1" // optional
                },
            ]
        },
    ],
    "perSet": [ // per-set data to modify; order is in the same order as 'sets' above
        {
            "boxImages": { // optional; only if 'box' was specified
                "en": "https://example.com/image.png",
            },
        },
    ]
}
```
