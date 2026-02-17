# Grants & Rule Data Extraction Design (v2)

## Overview

Extract **granting information** from `combined.dnd40.merged.xml` into a **standalone database** (`4e_grants.db`). This database is independent of `4e_compendium.db`—it never gets overwritten by compendium build scripts and can be updated separately when the XML changes.

---

## Architecture: Standalone Database

### Why Separate

- **Compendium DB** receives regular updates from outside sources; build scripts don't own it.
- **Grants DB** is derived solely from the XML; we control its schema and build process.
- Joins between the two happen at **query/application time**, not in the DB.

### How to Use Together

```sql
-- Example: grants DB has granter_xml_id, granted_xml_id
-- Compendium has power435, feat1470
-- Resolve at query time (from application or a view):

-- Option A: Application fetches grants, then looks up names from compendium by ID
-- Option B: Create a read-only "linked" view that attaches to both DBs:
--   sqlite3 "ATTACH '4e_compendium.db' AS comp; SELECT g.*, p.name FROM grants g 
--            LEFT JOIN comp.powers p ON p.id = g.granted_compendium_id WHERE ..."
```

---

## ID Mapping: Imperfect by Design

**Not all XML IDs map to compendium entries.** There are multiple ID schemes in the XML:

| Prefix | Example | Compendium? |
|--------|---------|-------------|
| `ID_FMP_*` | `ID_FMP_POWER_435`, `ID_FMP_FEAT_1470` | Often yes (powers, feats, classes) |
| `ID_INTERNAL_*` | `ID_INTERNAL_GRANTS_DRAGONBORN` | No — internal/runtime only |
| `ID_CDJ_*` | `ID_CDJ_CLASS_FEATURE_34501` | Unknown / different source |
| `ID_HF_*` | `ID_HF_RITUAL_DSH_5` | Different source |
| `ID_ATTACK_*` | `ID_ATTACK_FINESSE_HEROIC_TIER` | No |

### Design Principle

- **XML ID is the source of truth.** Every grant/statadd/modify references XML IDs.
- **Compendium ID is optional.** Populate only when we can verify a match exists.
- **No foreign keys to compendium.** The grants DB must be valid and queryable even when compendium IDs are missing or the compendium schema changes.

### Mapping Strategy

1. **Extract:** Store `granter_xml_id`, `granted_xml_id` from XML — always.
2. **Resolve (optional):** Run a separate step that attempts to map XML ID → compendium ID:
   - Apply mapping rule (e.g. `ID_FMP_POWER_435` → `power435`)
   - **Verify** the compendium actually contains that ID before storing
   - If no match, leave `compendium_id` NULL — no guesswork
3. **Graceful degradation:** Applications that need names can:
   - Use compendium_id when present
   - Fall back to XML ID or a separate lookup table
   - Handle "unmapped" as a normal case

---

## Robust Parsing: Quotes & Special Characters

The XML contains many values that break naïve parsers:

| Challenge | Example |
|-----------|---------|
| Escaped quotes in attributes | `value="6' 2&quot;-6' 8&quot;"` |
| Apostrophes in text | `dragonborn's`, `don't` |
| Ampersands | `D&D4E` → `D&amp;D4E` |
| Angle brackets in content | `&lt;table&gt;` in effect text |
| Pipe in conditions | `requires="Corellon\|Corellon (Forgotten Realms)"` |
| Mixed single/double quotes | `6' 2"-6' 8"` |

### Parsing Rules

1. **Use a real XML parser.** `xml.etree.ElementTree` or `lxml` — they decode entities and handle nesting correctly. **Never** use regex to extract attribute values or text.

2. **Use parameterized SQL.** Always:
   ```python
   cursor.execute("INSERT INTO grants (granter_xml_id, value) VALUES (?, ?)", (x, v))
   ```
   Never string formatting or concatenation. This correctly handles quotes, null bytes, and any character.

3. **Handle None explicitly.** `elem.get('attr')` returns `None` if missing. Store as SQL NULL, not the string `"None"`.

4. **Preserve text exactly.** For display/round-trip, store what the parser gives you after entity decoding. Don't "sanitize" or strip characters unless you have a clear reason.

5. **UTF-8 throughout.** Open the XML file with `encoding='utf-8'`. SQLite handles UTF-8 TEXT natively.

6. **Per-element try/except.** Wrap parsing of each `RulesElement` so one bad element doesn't abort the whole run. Log the problematic element and continue.

---

## Schema: Standalone 4e_grants.db

```sql
-- Metadata
CREATE TABLE _meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
INSERT INTO _meta VALUES ('source', 'combined.dnd40.merged.xml');
INSERT INTO _meta VALUES ('extracted_at', datetime('now'));

-- Core: grants (what grants what)
CREATE TABLE grants (
  id INTEGER PRIMARY KEY,
  granter_xml_id TEXT NOT NULL,
  granter_compendium_id TEXT,           -- NULL if unmapped
  granter_type TEXT NOT NULL,
  granter_name TEXT,                    -- From XML, for display without compendium
  granted_xml_id TEXT NOT NULL,
  granted_compendium_id TEXT,           -- NULL if unmapped
  granted_type TEXT NOT NULL,
  requires TEXT,
  level TEXT,
  ordinal INTEGER DEFAULT 0
);
CREATE INDEX idx_grants_granter ON grants(granter_xml_id);
CREATE INDEX idx_grants_granted ON grants(granted_xml_id);
CREATE INDEX idx_grants_granter_comp ON grants(granter_compendium_id) WHERE granter_compendium_id IS NOT NULL;

-- Stat additions (structured bonuses)
CREATE TABLE stat_additions (
  id INTEGER PRIMARY KEY,
  granter_xml_id TEXT NOT NULL,
  granter_compendium_id TEXT,
  granter_type TEXT NOT NULL,
  stat_name TEXT NOT NULL,
  value TEXT NOT NULL,
  bonus_type TEXT,
  requires TEXT,
  ordinal INTEGER DEFAULT 0
);
CREATE INDEX idx_statadd_granter ON stat_additions(granter_xml_id);

-- Modifies (alter other elements)
CREATE TABLE modifies (
  id INTEGER PRIMARY KEY,
  granter_xml_id TEXT NOT NULL,
  granter_compendium_id TEXT,
  target_name TEXT NOT NULL,
  target_type TEXT,
  field TEXT NOT NULL,
  value TEXT,
  list_addition TEXT,
  requires TEXT,
  ordinal INTEGER DEFAULT 0
);
CREATE INDEX idx_modifies_granter ON modifies(granter_xml_id);

-- Optional: XML ID resolution log (for debugging)
CREATE TABLE _id_resolution_log (
  xml_id TEXT,
  attempted_compendium_id TEXT,
  matched INTEGER,                      -- 1 if compendium had it, 0 if not
  compendium_table TEXT
);
```

---

## Extraction Algorithm

```
1. Open XML with encoding='utf-8'
2. Parse with ElementTree.iterparse() (streaming for large file)
3. For each RulesElement:
   a. Wrap in try/except
   b. granter_xml_id = elem.get('internal-id')
   c. granter_type = elem.get('type')
   d. granter_name = elem.get('name')
   e. rules = elem.find('rules')
   f. If rules is None: continue
   g. ordinal = 0
   h. For each child in rules:
      - tag = child.tag (normalize Grant->grant)
      - Get attributes via .get() — returns None if missing
      - INSERT with parameterized query: cursor.execute(sql, (v1, v2, ...))
      - ordinal += 1
   i. On exception: log (xml_id, error), continue
4. Commit transaction
5. Optional: Run compendium resolution pass (separate script/step)
```

---

## Compendium Resolution (Optional, Separate Pass)

Run only when compendium DB is available:

```python
# Pseudocode
for row in db.execute("SELECT id, granter_xml_id, granted_xml_id FROM grants"):
    for col in ['granter_xml_id', 'granted_xml_id']:
        xml_id = row[col]
        comp_id = xml_to_compendium_id(xml_id)  # ID_FMP_POWER_435 -> power435
        if comp_id:
            # Verify it exists in compendium
            if compendium_has_id(comp_id):
                db.execute("UPDATE grants SET ..._compendium_id = ? WHERE ...", (comp_id,))
            else:
                log_unmapped(xml_id, comp_id)
```

---

## Build Script Layout

```
4e_grants.db              # Output (standalone)
extract_grants.py         # Reads XML → writes 4e_grants.db
resolve_compendium_ids.py # Optional: reads 4e_compendium.db, updates 4e_grants.db
```

`extract_grants.py` has **no dependency** on the compendium. It only needs the XML. Resolution is a separate, optional step.

---

## Validation After Extract

- Count of grants in DB vs. `grep -c '<grant'` in XML (account for both grant and Grant)
- Spot-check 5–10 grants: compare granter/granted IDs and attribute values to raw XML
- Verify no `'` or `"` in values caused corrupt rows (parameterized queries prevent this)
- Check for any rows where critical columns are unexpectedly empty

---

## Summary

| Decision | Approach |
|----------|----------|
| Database | Standalone `4e_grants.db` — never touched by compendium builds |
| IDs | XML ID = source of truth; compendium_id = optional, verified |
| Parsing | ElementTree/lxml only; no regex for values |
| SQL | Parameterized queries only; no string concatenation |
| Mapping | Separate optional pass; tolerate NULL compendium_id |
| Errors | Per-element try/except; log and continue |
