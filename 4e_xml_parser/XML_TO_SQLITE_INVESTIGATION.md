# D&D 4E XML to SQLite Conversion — Investigation Report

## Executive Summary

The `combined.dnd40.merged.xml` file is a **~640K line** D&D 4th Edition rules database. It is **well-formed XML** with **38,339 `RulesElement`** entries. A reliable conversion requires careful handling of:

- **Mixed content** (free text between elements)
- **Variable schema** (type-specific `specific` keys)
- **Duplicate keys** (multiple `<specific name="Property">` per element)
- **Rich cross-references** (internal-id references)
- **Case sensitivity** (`grant` vs `Grant`)

---

## 1. File Structure

### 1.1 Root

```xml
<D20Rules game-system="D&D4E">
  <RulesElement ... />
  ...
</D20Rules>
```

- **Root**: `D20Rules` with attribute `game-system="D&D4E"`
- **Direct children**: 38,339 `RulesElement` elements only

### 1.2 RulesElement Attributes

| Attribute      | Required | Notes                                                                 |
|----------------|----------|-----------------------------------------------------------------------|
| `internal-id`  | Yes      | Unique identifier, e.g. `ID_FMP_RACE_1`, `ID_FMP_POWER_5594`          |
| `name`         | Yes      | Display name                                                          |
| `type`         | Yes      | Type/category (see §2)                                                |
| `source`       | Yes      | Source book(s), comma-separated                                       |
| `revision-date`| No       | ~19,750 have it; many omit it (e.g. "Dungeon Survival Handbook")      |

---

## 2. RulesElement Types (by frequency)

*Counts from `RulesElement` `type` attribute only (not grant/modify type).*

| Type                   | Count  | Description                    |
|------------------------|--------|--------------------------------|
| Power                  | 10,853 | Spells, attacks, abilities     |
| Magic Item             | 10,330 | Weapons, armor, items          |
| Class Feature          | 5,462  | Class abilities                |
| Feat                   | 3,708  | Feats                          |
| Companion              | 1,827  | Familiar/companion rules       |
| Background             | 868    | Background definitions         |
| Paragon Path           | 579    | Paragon paths                  |
| Ritual                 | 371    | Rituals                        |
| Ritual Scroll          | 353    | Ritual scroll items            |
| Racial Trait           | 342    | Race traits                    |
| Category               | 295    | Classification metadata        |
| Proficiency            | 294    | Weapon/armor proficiencies     |
| Weapon                 | 249    | Weapon definitions             |
| Gear                   | 244    | Mundane gear                   |
| Epic Destiny           | 115    | Epic destinies                 |
| Theme                  | 119    | Character themes               |
| …                      | …      | 50+ other types                |

---

## 3. Child Element Hierarchy

### 3.1 Direct Children of RulesElement

| Element        | Count  | Content                         | Notes                               |
|----------------|--------|----------------------------------|-------------------------------------|
| `<specific>`   | 378,316| Key-value via `name` attribute   | Same name can repeat (e.g. Property)|
| `<rules>`      | 16,800 | Container for rule sub-elements  |                                     |
| `<Flavor>`     | 23,353 | Flavor text                      |                                     |
| `<Category>`   | 16,964 | Comma-separated category IDs     |                                     |
| `<Prereqs>`    | 11,492 | Prerequisite text                |                                     |
| `<print-prereqs>` | 4,882| Formatted prereq text            |                                     |
| `<flavor>`     | 54     | Lowercase variant                |                                     |
| `<Grant>`      | 18     | Capital G variant of grant       |                                     |
| `<prereqs>`    | 1      | Lowercase variant                |                                     |

### 3.2 Children of `<rules>`

| Element     | Count  | Attributes                            | Notes                                  |
|-------------|--------|----------------------------------------|----------------------------------------|
| `<statadd>` | 18,610 | `name`, `value`, `type`, `requires`    | Stat modifications                     |
| `<grant>`   | 16,838 | `name`, `type`, `Level`, `requires`    | Grant other elements                   |
| `<modify>`  | 13,902 | `name`, `type`, `Field`, `value`, `list-addition`, `requires` | Modify other elements     |
| `<select>`  | 1,213  | `type`, `number`, `Category`, `name`, `existing` | Choice/selection rules    |
| `<textstring>` | 1,301| `name`, `value`                        | Text values                            |
| `<suggest>` | 1,716  | `name`, `type`                         | Suggested options                      |
| `<replace>` | 394    | `name`, `Level`, `requires`, `multiclass`, `optional` | Replacement rules    |
| `<drop>`    | 9      | `select`, or `name`+`type`             | Drop/remove selections or features     |
| `<statalias>` | 10    | `name`, `alias`                        | Stat name aliases (e.g. str→Strength)  |

### 3.3 `<select>` Element Variations

- **Self-closing**: `<select type="Race Ability Bonus" number="1" Category="Strength|Wisdom" />`
- **With content**: Multi-line text between tags:
  ```xml
  <select type="Familiar" number="1">
  Familiar Type
  </select>
  ```

---

## 4. Critical: Mixed Content

**RulesElement contains free text that is not inside any child element.**

This text appears as the `.tail` of the last significant child (typically `</rules>`). Example:

```xml
<RulesElement ...>
  ...
  <rules>
    <grant name="..." type="Power" />
  </rules>
Born to fight, dragonborn are a race of wandering mercenaries...
✦ to look like a dragon.
✦ to be the proud heir...
</RulesElement>
```

- The paragraphs and bullet points after `</rules>` are **not** in a wrapper element.
- They are stored as `rules.tail` (and possibly `tail` of deeper elements) in an XML parser.
- **Any parser must explicitly capture and persist this text** or it will be lost.

Python’s `xml.etree.ElementTree` does preserve `tail`; we must ensure it is written to the database.

---

## 5. `<specific>` Element — Key Challenges

### 5.1 Structure

```xml
<specific name="Level"> 7 </specific>
<specific name="Property"> When you assume a guardian form... </specific>
<specific name="Property"> Divine characters can use... </specific>   <!-- DUPLICATE KEY -->
<specific name="Duration" />   <!-- Empty / self-closing -->
```

### 5.2 Challenges

1. **Duplicate keys**: Same `name` can appear multiple times (e.g. `Property` — 7,091 instances, many in multi-property items).
2. **Order matters**: When a key repeats, order must be preserved (e.g. first vs second Property).
3. **Empty values**: Self-closing `<specific name="Tier" />` should be stored as `name → NULL` or empty string.
4. **~60+ distinct keys**: `Level`, `Special`, `Tier`, `Short Description`, `Property`, `Effect`, etc. (see Appendix A).

### 5.3 Recommendation

Store as **normalized table** with `(rules_element_id, name, value, ordinal)` so:

- Multiple rows can share the same `name`.
- Order is preserved via `ordinal`.

---

## 6. Special Content

### 6.1 Escaped/HTML-like Content

- `&lt;table&gt;` … `&lt;/table&gt;` for in-text tables (463 occurrences).
- `&quot;` for quotes.
- `&amp;` for ampersand.

Decode standard XML entities; tables can be stored as-is or parsed later.

### 6.2 Cross-References

IDs like `ID_FMP_POWER_8196`, `ID_FMP_CLASS_134`, `ID_FMP_RACIAL_TRAIT_1066` appear in:

- `<Category>` (comma-separated list)
- `<grant name="...">`
- `<specific>` values (e.g. Racial Traits, Class, _DisplayPowers)
- `requires` attributes

The schema should support easy joins and lookups on these IDs.

---

## 7. Attribute Variations

### 7.1 `statadd`

- `name`, `value` — always
- `type` — e.g. `Feat`, `Enhancement`, `resist`
- `requires` — conditional (e.g. `requires="Paragon Tier"`)

### 7.2 `modify`

- `name`, `type`, `Field`, `value` — common
- `list-addition` — for list-style changes
- `requires` — conditional

### 7.3 `grant`

- `name`, `type` — always
- `Level` — e.g. `Level="11"`
- `requires` — complex expressions with `|` (OR)

### 7.4 Case Variants

- `grant` (16,838) vs `Grant` (18) — treat as same logical element, preserve actual tag if needed for round-trip.

---

## 8. Suggested SQLite Schema (High Level)

### 8.1 Core Tables

```sql
-- Root metadata
CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT
);

-- Main rules elements
CREATE TABLE rules_elements (
  id INTEGER PRIMARY KEY,
  internal_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  source TEXT,
  revision_date TEXT,
  flavor TEXT,
  prereqs TEXT,
  print_prereqs TEXT,
  category_ids TEXT,           -- Comma-separated from Category elements
  body_text TEXT               -- Mixed content (tail text)
);

-- Specific key-value pairs (handles duplicates and order)
CREATE TABLE specific_values (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL REFERENCES rules_elements(id),
  name TEXT NOT NULL,
  value TEXT,
  ordinal INTEGER NOT NULL,
  UNIQUE(rules_element_id, name, ordinal)
);
CREATE INDEX idx_specific_re ON specific_values(rules_element_id);
CREATE INDEX idx_specific_name ON specific_values(name);

-- Rules block children
CREATE TABLE rule_grants (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL REFERENCES rules_elements(id),
  ordinal INTEGER NOT NULL,
  grant_name TEXT,
  grant_type TEXT,
  level TEXT,
  requires TEXT
);

CREATE TABLE rule_statadds (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL REFERENCES rules_elements(id),
  ordinal INTEGER NOT NULL,
  name TEXT,
  value TEXT,
  type TEXT,
  requires TEXT
);

CREATE TABLE rule_modifies (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL REFERENCES rules_elements(id),
  ordinal INTEGER NOT NULL,
  target_name TEXT,
  target_type TEXT,
  field TEXT,
  value TEXT,
  list_addition TEXT,
  requires TEXT
);

CREATE TABLE rule_selects (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL REFERENCES rules_elements(id),
  ordinal INTEGER NOT NULL,
  select_type TEXT,
  number TEXT,
  category TEXT,
  select_name TEXT,
  existing TEXT,
  content TEXT   -- For select elements with body content
);

-- Similar for: textstring, suggest, replace, drop, statalias
```

### 8.2 Full Attribute Capture

For maximum fidelity, consider an **attribute table**:

```sql
CREATE TABLE rule_element_attributes (
  id INTEGER PRIMARY KEY,
  rules_element_id INTEGER NOT NULL,
  element_type TEXT NOT NULL,  -- 'grant', 'statadd', 'modify', etc.
  ordinal INTEGER NOT NULL,
  attribute_name TEXT NOT NULL,
  attribute_value TEXT
);
```

This keeps every attribute even if the schema changes or new ones appear.

---

## 9. Parsing Strategy

### 9.1 Parser Choice

1. **Python `xml.etree.ElementTree`** (recommended)
   - Preserves `text` and `tail` (mixed content).
   - Streaming (`iterparse`) possible for memory efficiency.
   - Good for 640K-line file.

2. **`lxml`**
   - Same API, faster, supports `iterparse`.
   - Useful if performance is an issue.

### 9.2 Parsing Steps

1. **Stream parse** with `iterparse` to handle large file.
2. **For each `RulesElement`**:
   - Extract attributes: `internal-id`, `name`, `type`, `source`, `revision-date`.
   - For each child:
     - `Category`: concatenate text, store in `category_ids` or separate table.
     - `Prereqs`, `Flavor`, `print-prereqs`: store text (strip whitespace).
     - `specific`: store each with `(name, value, ordinal)`.
     - `rules`: recurse and capture all sub-elements and their attributes.
   - **Mixed content**: collect `tail` from last child (and any other `tail` segments) into `body_text`.
3. **Validation**:
   - Re-parse XML and compare element counts.
   - Spot-check: sample RulesElements by type, compare DB content vs raw XML.

### 9.3 Robustness

- Use `try/except` around each RulesElement so one bad element does not stop the run.
- Log problematic elements and line numbers.
- Run checksums: e.g. count of RulesElements, `specific`, `grant`, etc. in XML vs DB.

---

## 10. Validation Plan

| Check | Method |
|-------|--------|
| RulesElement count | `SELECT COUNT(*)` vs 38,339 |
| Per-type counts | Compare type distribution in XML vs DB |
| Mixed content | Verify `body_text` for known examples (e.g. Dragonborn) |
| Specific duplicates | For elements with 2+ Property, ensure 2+ rows with correct order |
| Cross-ref integrity | Sample internal-ids, ensure they exist in `rules_elements` |
| Rule children | Compare counts of grant, statadd, modify, etc. |

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mixed content loss | Explicitly capture and store `tail` |
| Duplicate `specific` keys | Use `(name, ordinal)` or equivalent |
| Large file size | Stream parsing (`iterparse`) |
| Malformed sub-tree | Parse per RulesElement with error handling |
| Unknown future elements | Generic attribute table or flexible schema |
| Case differences (`grant` vs `Grant`) | Normalize tag names when storing |

---

## Appendix A: Top 30 `specific` Keys

| Key | Count |
|-----|-------|
| Level | 25,032 |
| Special | 13,689 |
| Tier | 13,180 |
| Short Description | 11,217 |
| Gold | 10,885 |
| Power Usage | 10,856 |
| Action Type | 10,789 |
| Class | 10,710 |
| Attack Type | 10,676 |
| Keywords | 10,665 |
| Display | 10,654 |
| Requirement | 10,540 |
| Magic Item Type | 10,334 |
| Rarity | 10,270 |
| Item Slot | 10,114 |
| Power Type | 9,962 |
| Power | 9,643 |
| Critical | 9,643 |
| Weapon | 9,402 |
| … | … |

---

## Appendix B: File Statistics

- **Total lines**: 640,726
- **RulesElements**: 38,339
- **XML well-formed**: Yes
- **Has mixed content**: Yes
- **Largest type**: Power (10,853)
