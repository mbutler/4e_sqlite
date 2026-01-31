# D&D 4e Compendium SQLite Database

A single-file SQLite database containing the complete D&D 4th Edition compendium with enhanced search capabilities.

## Quick Start

```bash
# Basic query
sqlite3 4e_compendium.db "SELECT name, level FROM powers WHERE class_name='Wizard' LIMIT 5"

# With headers and formatting
sqlite3 -header -column 4e_compendium.db "SELECT name, level FROM powers LIMIT 5"

# Full-text search
sqlite3 4e_compendium.db "SELECT name FROM powers_fts WHERE powers_fts MATCH 'fire damage'"
```

---

## Database Overview

| Stat | Value |
|------|-------|
| File | `4e_compendium.db` |
| Size | ~88 MB |
| Total Entries | 25,545 |
| Categories | 20 |
| Full-Text Search | FTS5 enabled |

### Entry Counts by Category

| Category | Table Name | Count |
|----------|------------|-------|
| Powers | `powers` | 9,416 |
| Monsters | `monsters` | 5,326 |
| Feats | `feats` | 3,283 |
| Items | `items` | 1,964 |
| Backgrounds | `backgrounds` | 808 |
| Traps | `traps` | 776 |
| Implements | `implements` | 647 |
| Weapons | `weapons` | 631 |
| Paragon Paths | `paragon_paths` | 577 |
| Armor | `armor` | 493 |
| Glossary | `glossary` | 467 |
| Rituals | `rituals` | 360 |
| Companions | `companions` | 193 |
| Deities | `deities` | 134 |
| Themes | `themes` | 116 |
| Epic Destinies | `epic_destinies` | 115 |
| Classes | `classes` | 77 |
| Diseases | `diseases` | 69 |
| Races | `races` | 55 |
| Poisons | `poisons` | 38 |

---

## Table Schemas

### Powers Table (Primary)

The `powers` table is the most detailed, with enhanced parsed fields.

```sql
CREATE TABLE powers (
    id TEXT PRIMARY KEY,           -- e.g., "power6872"
    name TEXT NOT NULL,            -- e.g., "Twin Strike"
    class_name TEXT,               -- e.g., "Ranger"
    level INTEGER,                 -- Parsed integer (NULL if unparseable)
    level_raw TEXT,                -- Original value from source
    type TEXT,                     -- e.g., "Enc. Attack"
    type_raw TEXT,                 -- Original type string
    action TEXT,                   -- e.g., "Standard"
    keywords_raw TEXT,             -- e.g., "Martial, Weapon"
    source_book TEXT,              -- e.g., "PHB"
    html_body TEXT,                -- Full HTML content
    search_text TEXT,              -- Plain text for searching
    
    -- Enhanced parsed fields
    power_usage TEXT,              -- "At-Will", "Encounter", or "Daily"
    defense_targeted TEXT,         -- "AC", "Fortitude", "Reflex", or "Will"
    range_type TEXT,               -- "Melee", "Ranged", "Close", or "Area"
    range_value INTEGER,           -- e.g., 10 for "Ranged 10"
    area_type TEXT,                -- "burst", "blast", or "wall"
    area_size INTEGER              -- e.g., 5 for "Close burst 5"
);
```

### Other Core Tables

All tables share these common columns:
- `id` - Primary key (e.g., "feat123", "monster456")
- `name` - Display name
- `source_book` - Source publication
- `html_body` - Full HTML content
- `search_text` - Plain text for searching

#### Classes
```sql
id, name, role, power_source, key_abilities, source_book, html_body, search_text
```

#### Feats
```sql
id, name, tier, prerequisite, source_book, html_body, search_text
```

#### Monsters
```sql
id, name, level, level_raw, combat_role, group_role, size, creature_type, source_book, html_body, search_text
```

#### Items
```sql
id, name, category, type, level, level_raw, cost, rarity, source_book, html_body, search_text
```

#### Races
```sql
id, name, origin, description, size, source_book, html_body, search_text
```

#### Paragon Paths / Epic Destinies / Themes
```sql
id, name, prerequisite, source_book, html_body, search_text
```

### Tag Tables (Many-to-Many)

```sql
-- Keywords extracted from powers
CREATE TABLE power_keywords (
    power_id TEXT,
    keyword TEXT,
    PRIMARY KEY (power_id, keyword)
);

-- Damage types (fire, cold, radiant, etc.)
CREATE TABLE power_damage_types (
    power_id TEXT,
    damage_type TEXT,
    PRIMARY KEY (power_id, damage_type)
);

-- Conditions inflicted (dazed, stunned, prone, etc.)
CREATE TABLE power_conditions (
    power_id TEXT,
    condition TEXT,
    PRIMARY KEY (power_id, condition)
);
```

### Utility Tables

```sql
-- Global name lookup (for cross-referencing)
CREATE TABLE name_index (
    name_lower TEXT,    -- Lowercased name
    entry_id TEXT       -- e.g., "power123", "feat456"
);

-- Parse audit log
CREATE TABLE _parse_log (
    id INTEGER PRIMARY KEY,
    entry_id TEXT,      -- Which entry
    field TEXT,         -- Which field was parsed
    value TEXT,         -- What value was extracted
    source TEXT,        -- Where it came from (keyword, pattern, regex)
    confidence TEXT,    -- "high" or "medium"
    timestamp TEXT
);

-- Category metadata
CREATE TABLE _categories (
    name TEXT PRIMARY KEY,
    entry_count INTEGER,
    table_name TEXT
);

-- Build metadata
CREATE TABLE _meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

---

## Full-Text Search (FTS5)

Every table has a corresponding `_fts` virtual table for fast full-text search.

### FTS Tables
- `powers_fts`
- `feats_fts`
- `monsters_fts`
- `items_fts`
- `classes_fts`
- `races_fts`
- `paragon_paths_fts`
- `epic_destinies_fts`
- `themes_fts`
- `rituals_fts`
- `backgrounds_fts`
- `traps_fts`
- `diseases_fts`
- `poisons_fts`
- `deities_fts`
- `companions_fts`
- `glossary_fts`
- `armor_fts`
- `weapons_fts`
- `implements_fts`

### FTS5 Search Syntax

```sql
-- Simple search
SELECT * FROM powers_fts WHERE powers_fts MATCH 'fire';

-- AND (both terms required)
SELECT * FROM powers_fts WHERE powers_fts MATCH 'fire AND damage';

-- OR (either term)
SELECT * FROM powers_fts WHERE powers_fts MATCH 'fire OR cold';

-- Phrase search
SELECT * FROM powers_fts WHERE powers_fts MATCH '"fire damage"';

-- Prefix search (wildcard)
SELECT * FROM powers_fts WHERE powers_fts MATCH 'tele*';

-- NOT (exclude term)
SELECT * FROM powers_fts WHERE powers_fts MATCH 'fire NOT cold';

-- Column-specific search
SELECT * FROM powers_fts WHERE powers_fts MATCH 'name:strike';
```

### Joining FTS Results to Full Data

FTS tables have limited columns. Join back to the main table for full data:

```sql
SELECT p.name, p.class_name, p.level, p.power_usage, p.html_body
FROM powers p
WHERE p.id IN (
    SELECT id FROM powers_fts WHERE powers_fts MATCH 'teleport AND radiant'
)
ORDER BY p.level;
```

---

## Sample Queries

### Basic Queries

```sql
-- All Wizard powers
SELECT name, level, power_usage FROM powers WHERE class_name = 'Wizard' ORDER BY level;

-- All Heroic tier feats
SELECT name, prerequisite FROM feats WHERE tier = 'Heroic';

-- All Striker classes
SELECT name, power_source, key_abilities FROM classes WHERE role = 'Striker';

-- Monsters level 5-10
SELECT name, level, combat_role, creature_type FROM monsters WHERE level BETWEEN 5 AND 10;
```

### Using Enhanced Fields

```sql
-- Powers that target Will defense
SELECT name, class_name, level FROM powers WHERE defense_targeted = 'Will';

-- Daily powers with Area attacks
SELECT name, class_name, level, area_type, area_size 
FROM powers 
WHERE power_usage = 'Daily' AND range_type = 'Area';

-- Melee encounter powers
SELECT name, class_name, level 
FROM powers 
WHERE power_usage = 'Encounter' AND range_type = 'Melee';
```

### Using Tag Tables

```sql
-- All fire damage powers
SELECT p.name, p.class_name, p.level
FROM powers p
JOIN power_damage_types d ON p.id = d.power_id
WHERE d.damage_type = 'fire';

-- Powers that cause 'stunned'
SELECT p.name, p.class_name, p.level
FROM powers p
JOIN power_conditions c ON p.id = c.power_id
WHERE c.condition = 'stunned';

-- Powers with 'Reliable' keyword
SELECT p.name, p.class_name, p.level
FROM powers p
JOIN power_keywords k ON p.id = k.power_id
WHERE k.keyword = 'Reliable';

-- Powers that deal BOTH fire AND radiant
SELECT p.name, p.class_name, p.level
FROM powers p
WHERE p.id IN (SELECT power_id FROM power_damage_types WHERE damage_type = 'fire')
  AND p.id IN (SELECT power_id FROM power_damage_types WHERE damage_type = 'radiant');
```

### Cross-Category Queries

```sql
-- Paragon Paths for Rogues with their powers
SELECT pp.name AS paragon_path, p.name AS power_name, p.level, p.power_usage
FROM paragon_paths pp
JOIN powers p ON p.class_name = pp.name
WHERE pp.prerequisite LIKE '%Rogue%'
ORDER BY pp.name, p.level;

-- Classes and their power counts
SELECT c.name, c.role, COUNT(p.id) AS power_count
FROM classes c
LEFT JOIN powers p ON p.class_name = c.name
GROUP BY c.id
ORDER BY power_count DESC;
```

### Aggregate Analysis

```sql
-- Damage type distribution
SELECT damage_type, COUNT(*) AS count
FROM power_damage_types
GROUP BY damage_type
ORDER BY count DESC;

-- Condition distribution
SELECT condition, COUNT(*) AS count
FROM power_conditions
GROUP BY condition
ORDER BY count DESC;

-- Classes with the most 'dominated' powers
SELECT p.class_name, COUNT(*) AS dominate_powers
FROM powers p
JOIN power_conditions c ON p.id = c.power_id
WHERE c.condition = 'dominated'
GROUP BY p.class_name
ORDER BY dominate_powers DESC
LIMIT 10;

-- Power counts by level and usage type
SELECT level, power_usage, COUNT(*) AS count
FROM powers
WHERE class_name = 'Wizard'
GROUP BY level, power_usage
ORDER BY level;
```

### Character Building Queries

```sql
-- Level 1 Wizard cold at-wills
SELECT p.name, p.keywords_raw, p.defense_targeted, p.range_type
FROM powers p
JOIN power_damage_types d ON p.id = d.power_id
WHERE p.class_name = 'Wizard'
  AND p.level = 1
  AND p.power_usage = 'At-Will'
  AND d.damage_type = 'cold';

-- Find feats for a fire-themed build
SELECT name, tier, prerequisite
FROM feats
WHERE name LIKE '%fire%' OR prerequisite LIKE '%fire%'
ORDER BY tier, name;

-- Striker daily powers level 15-20 with fire damage targeting Reflex
SELECT p.name, p.class_name, p.level, d.damage_type
FROM powers p
JOIN power_damage_types d ON p.id = d.power_id
JOIN classes c ON p.class_name = c.name
WHERE c.role = 'Striker'
  AND p.power_usage = 'Daily'
  AND p.level BETWEEN 15 AND 20
  AND d.damage_type = 'fire'
  AND p.defense_targeted = 'Reflex';
```

---

## Data Quality Notes

### Original Data Preserved

All original data is preserved in `*_raw` columns and `html_body`/`search_text` fields. Enhanced fields are **additions**, not replacements.

### Enhanced Field Confidence

| Field | Source | Confidence |
|-------|--------|------------|
| `defense_targeted` | Regex on "vs. Defense" | High |
| `power_usage` | Type column parsing | High |
| `range_type` | HTML body patterns | High |
| Damage types | Keywords field | High |
| Conditions | Pattern matching on hit text | Medium |

### Audit Log

Check the `_parse_log` table to review extraction decisions:

```sql
-- See all extractions for a specific power
SELECT * FROM _parse_log WHERE entry_id = 'power6872';

-- Review medium-confidence extractions
SELECT entry_id, field, value, source 
FROM _parse_log 
WHERE confidence = 'medium'
LIMIT 50;

-- Count extractions by confidence
SELECT field, confidence, COUNT(*) 
FROM _parse_log 
GROUP BY field, confidence;
```

### Fallback Strategy

If enhanced fields miss something, use FTS or LIKE on raw fields:

```sql
-- Structured query might miss some
SELECT name FROM powers WHERE defense_targeted = 'Will';

-- Fallback: search the raw text
SELECT name FROM powers WHERE html_body LIKE '%vs. Will%';

-- Or use FTS
SELECT name FROM powers_fts WHERE powers_fts MATCH 'vs Will';
```

---

## Rebuilding the Database

If you modify the source JSONP files in `4e_database_files/`, rebuild:

```bash
python3 build_compendium_db.py
```

The script:
1. Deletes the existing `4e_compendium.db`
2. Parses all JSONP files
3. Creates tables and indexes
4. Extracts enhanced fields
5. Builds FTS5 indexes
6. Outputs stats

Takes ~4 seconds.

---

## Tips

### Formatting Output

```bash
# Headers + columns
sqlite3 -header -column 4e_compendium.db "SELECT ..."

# CSV output
sqlite3 -header -csv 4e_compendium.db "SELECT ..." > output.csv

# JSON output (SQLite 3.33+)
sqlite3 -json 4e_compendium.db "SELECT ..." 
```

### Interactive Mode

```bash
sqlite3 4e_compendium.db
sqlite> .headers on
sqlite> .mode column
sqlite> SELECT * FROM classes LIMIT 5;
sqlite> .quit
```

### Using from Python

```python
import sqlite3

conn = sqlite3.connect('4e_compendium.db')
conn.row_factory = sqlite3.Row  # Access columns by name

cursor = conn.execute("""
    SELECT name, level, power_usage 
    FROM powers 
    WHERE class_name = ? AND level <= ?
""", ('Wizard', 5))

for row in cursor:
    print(f"{row['name']} (Level {row['level']}, {row['power_usage']})")

conn.close()
```

### Using from Node.js

```javascript
const Database = require('better-sqlite3');
const db = new Database('4e_compendium.db', { readonly: true });

const powers = db.prepare(`
    SELECT name, level, power_usage 
    FROM powers 
    WHERE class_name = ? AND level <= ?
`).all('Wizard', 5);

powers.forEach(p => console.log(`${p.name} (Level ${p.level})`));
```

---

## Known Limitations

1. **Some index files had parsing issues** - Feats, classes, and themes have data but may be missing `search_text` for some entries. The `html_body` is still available.

2. **Condition extraction is pattern-based** - May miss unusual phrasings. Use FTS fallback for comprehensive searches.

3. **No monster stat block parsing** - Monster HTML is preserved but not parsed into individual stats (HP, AC, etc.).

4. **Prerequisites are strings** - Not parsed into structured data. Use LIKE queries.

---

## File Structure Reference

```
4e_compendium.db          # The database (this file documents it)
build_compendium_db.py    # Script to rebuild from source
COMPENDIUM_DB.md          # This documentation
4e_database_files/        # Source JSONP files
  catalog.js
  index.js
  <category>/
    _listing.js
    _index.js
    data0.js ... data19.js
```
