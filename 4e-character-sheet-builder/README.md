# D&D 4e Character Cheat Sheet Builder

Generate detailed Markdown character sheets and combat cheat sheets from D&D 4th Edition Character Builder exports. The tool looks up powers, feats, and items in a local compendium database to produce richly formatted reference documents for play.

## What It Does

- **Full character sheet** — Complete character details including ability scores, defenses, skills, and full power/feat/item descriptions from the compendium
- **Combat cheat sheet** — Condensed quick-reference for powers during combat: at-wills, encounters, dailies, and utilities
- **HTML to Markdown** — Converts compendium HTML content into readable Markdown

## Requirements

- Python 3
- `4e_compendium.db` (the compendium SQLite database)

## Quick Start

1. Place your Character Builder export as `character.txt` in the project directory.

2. Run the generator:

   ```bash
   python3 generate_character_sheet.py character.txt
   ```

3. Output files are created based on your character name:
   - `YourName_sheet.md` — Full character sheet
   - `YourName_cheatsheet.md` — Combat cheat sheet

## Character Builder Export Format

Your `character.txt` should be a plain text export from the official Wizards of the Coast D&D 4e Character Builder. It starts with:

```
====== Created Using Wizards of the Coast D&D Character Builder ======
Character Name, level X
Race, Class, Paragon Path, Epic Destiny
...
FINAL ABILITY SCORES
Str X, Con X, Dex X, Int X, Wis X, Cha X.
...
FEATS
Level 1: Feat Name
...
POWERS
Class at-will 1: Power Name
Class encounter 1: Power Name
...
ITEMS
Item Name
...
```

Paste this output into `character.txt` and run the script.

## Command Line Options

```bash
python3 generate_character_sheet.py character.txt [options]
```

| Option | Description |
|--------|-------------|
| `-o FILE`, `--output FILE` | Custom output path for the character sheet |
| `--db PATH` | Path to compendium database (default: parent folder `../4e_compendium.db`) |
| `--no-cheatsheet` | Skip generating the combat cheat sheet |

### Examples

```bash
# Default: creates <Name>_sheet.md and <Name>_cheatsheet.md
python3 generate_character_sheet.py character.txt

# Custom output filename
python3 generate_character_sheet.py character.txt -o Kyros_sheet.md

# Use a different database
python3 generate_character_sheet.py character.txt --db /path/to/compendium.db

# Character sheet only (no cheat sheet)
python3 generate_character_sheet.py character.txt --no-cheatsheet
```

## Compendium Database

The generator relies on `4e_compendium.db`, a SQLite database containing the 4e compendium (powers, feats, items, monsters, etc.). By default it uses the database in the **parent project folder** (shared with the XML parser and other tools). Override with `--db` if needed.

### Rebuilding the Database

If you have the source JSONP files in `4e_database_files/` (in the project root), you can rebuild the database:

```bash
# From project root:
python3 build_compendium_db.py

# Or from this folder (writes to parent):
python3 build_compendium_db.py
```

This creates or overwrites `4e_compendium.db` in the project root. See [COMPENDIUM_DB.md](COMPENDIUM_DB.md) for the full database schema, queries, and full-text search.

## Project Structure

```
4e_sqlite/                    # Project root
├── 4e_compendium.db         # Compendium SQLite database (shared, in root)
├── 4e_database_files/       # JSONP source (for building DB)
├── 4e-character-sheet-builder/
│   ├── character.txt        # Your Character Builder export (input)
│   ├── build_compendium_db.py
│   ├── generate_character_sheet.py
│   ├── COMPENDIUM_DB.md
│   └── README.md
└── 4e_xml_parser/
```

Output files (e.g. `Elise_sheet.md`, `Elise_cheatsheet.md`) are written to the project directory.
