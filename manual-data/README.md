# Manual Data

This consists of all the information we can't pull automatically from any of our data sources, and must make ourselves.

# Manual Fixup Identifiers

Anywhere here where you need to give a UUID to refer to another item, you can instead provide a Manual Fixup Identifier, or MFI. This is an object, which needs at least one field, but all fields are optional. This allows you to use a variety of fields to dictate exactly what you're talking about, instead of just a UUID. This is useful for making these files human-readable, and pin fixups to things not yet generated.

The fields allowable in a MFI include:

```json
{
    "id": "71535f5e-3ad4-48c2-a33a-08b434a38dc2", // UUID of something existing
    "name": "Pot of Greed",                       // English name (case sensitive)
    "konamiID": 12345678,                         // Konami official database ID
    "ygoprodeckID": 12345678,                     // YGOPRODECK password
    "ygoprodeckName": "Pot-of-Greed",             // YGOPRODECK URL slug
    "yugipediaID": 12345678,                      // Yugipedia page ID
    "yugipediaName": "Pot of Greed",              // Yugipedia page title
    "yamlyugi": 12345678,                         // Yaml Yugi password

    // The following are for locating printings ONLY.

    "set": {"name": "The Pot Collection"},        // MFI pointing to a set that contains a printing
    "locale": "en",                               // Locale a printing can be found in
    "edition": "first",                           // Edition a printing can be found in
    "rarity": "rare",                             // Rarity of a printing
    "code": "SDK-EN001",                          // Full set code of a printing
}
```
