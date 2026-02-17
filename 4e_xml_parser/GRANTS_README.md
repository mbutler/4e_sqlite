# Grants Database

Standalone database of D&D 4E grant relationships and rule data, extracted from `combined.dnd40.merged.xml`.

## Quick Start

```bash
# 1. Extract grants from XML (required)
python3 extract_grants.py

# 2. Resolve IDs to compendium (optional, requires 4e_compendium.db in project root)
python3 resolve_compendium_ids.py
```

## Output: 4e_grants.db

| Table | Description |
|-------|-------------|
| `grants` | What grants what (feat→power, item→power, class→feature, etc.) |
| `stat_additions` | Structured bonuses (resist:fire +5, Armor Class +2, etc.) |
| `modifies` | Alterations to other elements (feat modifies power text, etc.) |
| `_id_resolution_log` | Tracks ID resolution (populated by resolve script) |

### _id_resolution_log (ID tracking)

Tracks every XML ID encountered and whether it resolved to the compendium:

| status | Meaning |
|--------|---------|
| `matched` | Resolved via direct ID lookup |
| `matched_manual` | Resolved via manual_id_mappings.csv override |
| `matched_name_search` | Resolved via name search (ID patterns differ between XML and compendium) |
| `not_found` | Attempted lookup but compendium lacked it — **potential gap or false negative** |
| `unmappable` | Couldn't derive compendium ID (e.g. ID_INTERNAL_*, unknown type) |

When direct ID lookup fails, the resolve script tries **name search** (name_index + direct table search, with many name-variant fallbacks) and **manual mappings** first. Uses type hints from the XML ID to avoid wrong-type matches (e.g. won't match a Power to a Class).

Use for manual lookup, monitoring discrepancies, and debugging parsing issues.

```sql
-- IDs we tried to resolve but compendium didn't have (by occurrence count)
SELECT xml_id, attempted_compendium_id, compendium_table, occurrence_count
FROM _id_resolution_log WHERE status = 'not_found' ORDER BY occurrence_count DESC;

-- Resolved via name search (ID patterns differed)
SELECT xml_id, attempted_compendium_id, resolved_compendium_id, resolution_method
FROM _id_resolution_log WHERE status = 'matched_name_search';

-- Unmappable IDs (wrong prefix, unknown type)
SELECT xml_id, unmappable_reason, occurrence_count
FROM _id_resolution_log WHERE status = 'unmappable' ORDER BY occurrence_count DESC;
```

## Sample Queries

```sql
-- What does feat "Solar Enemy" grant?
SELECT granter_name, granted_xml_id, granted_compendium_id, requires
FROM grants WHERE granter_name = 'Solar Enemy';

-- Stat bonuses from Dragonborn race
SELECT stat_name, value, bonus_type FROM stat_additions
WHERE granter_xml_id = 'ID_FMP_RACE_1';

-- Join to compendium for full power details (run from sqlite3 in 4e_xml_parser/)
-- First: ATTACH DATABASE '../4e_compendium.db' AS comp;
-- Then:
SELECT g.granter_name, g.requires, p.name, p.level, p.power_usage
FROM grants g
LEFT JOIN comp.powers p ON p.id = g.granted_compendium_id
WHERE g.granted_type = 'Power' AND g.granter_type = 'Feat'
LIMIT 10;
```

## Files

| File | Purpose |
|------|---------|
| `extract_grants.py` | Parses XML → creates 4e_grants.db (no compendium needed) |
| `resolve_compendium_ids.py` | Optional: populates compendium_id columns when compendium exists |
| `4e_grants.db` | Output database |
| `manual_id_mappings.csv` | Manual overrides: xml_id,compendium_id (one per line) |
| `not_found_manual_review.csv` | IDs that couldn't resolve (for manual lookup) |
| `GRANTS_EXTRACTION_DESIGN.md` | Full design and schema docs |
| `GRANTS_QUERY_GUIDE.md` | **Query guide for using 4e_grants.db with 4e_compendium.db** |

## ID Resolution

- **granter_xml_id / granted_xml_id** — Always populated from XML (source of truth)
- **granter_compendium_id / granted_compendium_id** — Populated by `resolve_compendium_ids.py` only when the ID exists in the compendium. Many XML IDs (ID_INTERNAL_*, ID_CDJ_*, etc.) have no compendium equivalent and correctly remain NULL.
