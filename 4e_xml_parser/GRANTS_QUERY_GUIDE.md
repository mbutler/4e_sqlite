# 4e_grants.db Query Guide

A practical guide for querying `4e_grants.db` in conjunction with `4e_compendium.db`. Use this when integrating grants data into another system.

---

## Overview

| Database | Purpose |
|----------|---------|
| **4e_grants.db** | Grant relationships and rule data: what grants what, stat bonuses, modifications. Derived from XML. |
| **4e_compendium.db** | Full compendium content: powers, feats, items, classes, etc. See `compendium_db.md`. |

The two databases are **separate files**. Joins happen at query time by attaching one to the other.

---

## Tables in 4e_grants.db

### grants

What grants what: feats→powers, items→powers, class features→powers, etc.

| Column | Type | Description |
|--------|------|-------------|
| `granter_xml_id` | TEXT | Source of truth. Always populated (e.g. `ID_FMP_FEAT_1470`). |
| `granter_compendium_id` | TEXT | Resolved compendium ID when available (e.g. `feat1470`). May be NULL. |
| `granter_type` | TEXT | e.g. Feat, Magic Item, Class Feature, Paragon Path |
| `granter_name` | TEXT | Display name from XML |
| `granted_xml_id` | TEXT | What is granted (e.g. `ID_FMP_POWER_435`) |
| `granted_compendium_id` | TEXT | Resolved compendium ID when available. May be NULL. |
| `granted_type` | TEXT | e.g. Power, Class Feature, Proficiency |
| `granted_name` | TEXT | Display name of granted thing |
| `requires` | TEXT | Condition (e.g. `!ID_FMP_POWER_435` = "must not have this"). Pipe-separated for OR. |
| `level` | TEXT | Level restriction if any |

**Indexes:** `granter_xml_id`, `granted_xml_id`, `granter_compendium_id`

---

### stat_additions

Structured bonuses granted by feats, races, items, etc.

| Column | Type | Description |
|--------|------|-------------|
| `granter_xml_id` | TEXT | Source of the bonus |
| `granter_compendium_id` | TEXT | Resolved compendium ID when available |
| `granter_type` | TEXT | e.g. Race, Feat, Magic Item |
| `granter_name` | TEXT | Display name |
| `stat_name` | TEXT | What stat (e.g. `AC`, `resist:fire`, `ID_FMP_ITEM_SET_22 Set Count`) |
| `value` | TEXT | Bonus value (e.g. `+2`, `+5`, `+1`) |
| `bonus_type` | TEXT | Optional type qualifier |
| `requires` | TEXT | Condition for the bonus to apply |

---

### modifies

Alterations to other elements (e.g. a feat modifies how a power works).

| Column | Type | Description |
|--------|------|-------------|
| `granter_xml_id` | TEXT | Source of the modification |
| `granter_compendium_id` | TEXT | Resolved compendium ID when available |
| `granter_type` | TEXT | e.g. Feat, Class Feature |
| `granter_name` | TEXT | Display name |
| `target_name` | TEXT | Name of the element being modified |
| `target_type` | TEXT | e.g. Power |
| `field` | TEXT | Which field is modified |
| `value` | TEXT | New value |
| `list_addition` | TEXT | If adding to a list |
| `requires` | TEXT | Condition |

---

### _id_resolution_log

Tracks which XML IDs resolved to compendium IDs. Use for debugging or fallback lookups.

| Column | Description |
|--------|-------------|
| `xml_id` | Original XML ID |
| `resolved_compendium_id` | Compendium ID if matched |
| `status` | `matched`, `matched_name_search`, `not_found`, `unmappable` |
| `as_granter_in_grants`, `as_granted_in_grants`, `in_statadd_count`, `in_modify_count` | Usage counts |

---

## ID Columns: When to Use Which

| Column | Source | Use When |
|--------|--------|----------|
| `*_xml_id` | XML (always) | Cross-referencing grants with XML, auditing, fallback |
| `*_compendium_id` | Resolve script | Joining to compendium tables for names, HTML, details |

**Compendium ID format:** Prefix + number, e.g. `power435`, `feat1470`, `item112`, `weapon2006`. The prefix maps to a compendium table:

| Prefix | Compendium Table |
|--------|------------------|
| power | powers |
| feat | feats |
| class | classes |
| item | items |
| weapon | weapons |
| armor | armor |
| implement | implements |
| poison | poisons |
| race | races |
| paragonpath | paragon_paths |
| epicdestiny | epic_destinies |
| theme | themes |
| ritual | rituals |
| companion | companions |

---

## Joining with 4e_compendium.db

### ATTACH (recommended)

```sql
ATTACH DATABASE '4e_compendium.db' AS comp;

-- Grants with power details
SELECT
  g.granter_name,
  g.granted_name,
  g.requires,
  p.name   AS power_name,
  p.level  AS power_level,
  p.power_usage
FROM grants g
LEFT JOIN comp.powers p ON p.id = g.granted_compendium_id
WHERE g.granted_type = 'Power'
  AND g.granter_compendium_id IS NOT NULL;
```

### Same directory

If both DBs are in the same directory:

```sql
ATTACH DATABASE '4e_compendium.db' AS comp;
```

### From 4e_xml_parser (compendium in project root)

The compendium DB lives in the project root; grants DB is in `4e_xml_parser/`:

```sql
ATTACH DATABASE '../4e_compendium.db' AS comp;
```

### Different paths

Use an absolute or relative path:

```sql
ATTACH DATABASE '/path/to/4e_compendium.db' AS comp;
```

---

## Common Query Patterns

### 1. What does a feat grant?

```sql
SELECT granter_name, granted_type, granted_name, requires
FROM grants
WHERE granter_name = 'Solar Enemy' AND granter_type = 'Feat';
```

### 2. Grants with full compendium details

```sql
ATTACH DATABASE '4e_compendium.db' AS comp;

SELECT
  g.granter_name,
  g.granter_type,
  g.granted_name,
  g.granted_type,
  g.requires,
  p.name   AS comp_power_name,
  p.level  AS comp_power_level
FROM grants g
LEFT JOIN comp.powers p ON p.id = g.granted_compendium_id AND g.granted_type = 'Power'
WHERE g.granter_name LIKE '%Dragonborn%';
```

### 3. Stat bonuses from a race

```sql
SELECT stat_name, value, bonus_type, requires
FROM stat_additions
WHERE granter_name = 'Dragonborn' AND granter_type = 'Race';
```

### 4. Item-granted powers (for character sheet / builder)

```sql
ATTACH DATABASE '4e_compendium.db' AS comp;

SELECT
  g.granter_name       AS item_name,
  g.requires           AS equip_condition,
  p.name               AS power_name,
  p.level,
  p.power_usage,
  p.html_body
FROM grants g
JOIN comp.powers p ON p.id = g.granted_compendium_id
WHERE g.granter_type = 'Magic Item'
  AND g.granted_type = 'Power'
  AND g.granted_compendium_id IS NOT NULL;
```

### 5. Feats that modify a specific power

```sql
SELECT granter_name, field, value, requires
FROM modifies
WHERE target_type = 'Power'
  AND target_name LIKE '%Twin Strike%';
```

### 6. All grants for a compendium entry (by compendium ID)

```sql
SELECT *
FROM grants
WHERE granter_compendium_id = 'feat1470'
   OR granted_compendium_id = 'feat1470';
```

### 7. Fallback when compendium_id is NULL

Use `*_name` columns (from XML) when `*_compendium_id` is NULL:

```sql
SELECT
  granter_name,
  granted_name,
  COALESCE(granted_compendium_id, granted_xml_id) AS resolved_id
FROM grants
WHERE granter_type = 'Feat';
```

### 8. Join by compendium table (dynamic)

Powers, feats, and items use different compendium tables. A single query can join to the appropriate table based on type:

```sql
ATTACH DATABASE '4e_compendium.db' AS comp;

SELECT
  g.granter_name,
  g.granted_name,
  g.granted_type,
  g.granted_compendium_id,
  COALESCE(p.name, f.name, i.name) AS comp_name
FROM grants g
LEFT JOIN comp.powers p   ON p.id = g.granted_compendium_id AND g.granted_type = 'Power'
LEFT JOIN comp.feats f   ON f.id = g.granted_compendium_id AND g.granted_type = 'Feat'
LEFT JOIN comp.items i   ON i.id = g.granted_compendium_id AND g.granted_type IN ('Magic Item', 'Item');
```

---

## Performance Notes

- **Indexes:** Use `granter_xml_id`, `granted_xml_id`, or `granter_compendium_id` in WHERE clauses when possible.
- **ATTACH:** Attaching the compendium adds minimal overhead; SQLite handles cross-database joins efficiently.
- **Large result sets:** For batch processing, filter by `granter_type`, `granted_type`, or a specific `granter_compendium_id` to limit rows.

---

## Data Volume (typical)

| Table | Rows |
|-------|------|
| grants | ~17,000 |
| stat_additions | ~19,000 |
| modifies | ~14,000 |

---

## Files Reference

| File | Purpose |
|------|---------|
| `4e_grants.db` | Grants database (this guide) |
| `4e_compendium.db` | Compendium content; see `compendium_db.md` |
| `extract_grants.py` | Builds 4e_grants.db from XML |
| `resolve_compendium_ids.py` | Populates `*_compendium_id` columns |
| `manual_id_mappings.csv` | Override mappings for difficult IDs |
