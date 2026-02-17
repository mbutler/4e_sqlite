#!/usr/bin/env python3
"""
Optional: Resolve XML IDs to compendium IDs in 4e_grants.db.

Reads 4e_compendium.db and updates granter_compendium_id / granted_compendium_id
in 4e_grants.db only when the compendium actually contains that ID.
Skips IDs that don't map or have no compendium match (leaves NULL).

Also populates _id_resolution_log to track:
  - matched: resolved via direct ID lookup
  - matched_name_search: resolved via name search (ID patterns differ)
  - not_found: attempted but compendium lacked it (potential gap/false negative)
  - unmappable: couldn't derive compendium ID (e.g. ID_INTERNAL_*, unknown type)

When direct ID lookup fails, tries name search against compendium name_index.
"""

import re
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

# XML type suffix -> (compendium_table, id_prefix) for direct ID lookup
# e.g. ID_FMP_POWER_435 -> powers table, id "power435"
TYPE_MAP = {
    "POWER": ("powers", "power"),
    "FEAT": ("feats", "feat"),
    "CLASS": ("classes", "class"),
    "RACE": ("races", "race"),
    "MAGIC_ITEM": ("items", "item"),
    "ITEM": ("items", "item"),
    "PARAGON_PATH": ("paragon_paths", "paragonpath"),
    "EPIC_DESTINY": ("epic_destinies", "epicdestiny"),
    "THEME": ("themes", "theme"),
    "RITUAL": ("rituals", "ritual"),
    "BACKGROUND": ("backgrounds", "background"),
    "DEITY": ("deities", "deity"),
    "COMPANION": ("companions", "companion"),
    "RACIAL_TRAIT": (None, None),  # No direct table
    "CLASS_FEATURE": (None, None),  # No direct table
    "GRANTS": (None, None),  # Internal
    "BUILD_SUGGESTIONS": (None, None),
    "INTERNAL": (None, None),
}

# For name search: XML types can match multiple compendium categories
# (items/implements/armor/weapons/poisons overlap; companions/associates/familiars overlap)
TYPE_GROUP_PREFIXES = {
    "MAGIC_ITEM": ("item", "implement", "armor", "weapon", "poison"),
    "ITEM": ("item", "implement", "armor", "weapon", "poison"),
    "COMPANION": ("companion", "associate"),
    "FAMILIAR": ("companion", "associate"),
    "ASSOCIATE": ("companion", "associate"),
}


def xml_to_compendium_id(xml_id: str | None) -> tuple[str | None, str | None, str | None]:
    """
    Convert XML internal-id to compendium ID.
    Returns (compendium_id, compendium_table, unmappable_reason).
    unmappable_reason is None if mappable, else short reason (e.g. "non-FMP prefix").
    """
    if not xml_id or not isinstance(xml_id, str):
        return (None, None, "empty_or_invalid")

    # Skip non-FMP IDs (ID_INTERNAL_, ID_CDJ_, ID_HF_, etc.)
    if "ID_FMP_" not in xml_id:
        parts = xml_id.split("_")[:2]  # e.g. ID_INTERNAL, ID_CDJ
        prefix = "_".join(parts) if len(parts) >= 2 else (xml_id[:30] + "..." if len(xml_id) > 30 else xml_id)
        return (None, None, f"non-FMP prefix ({prefix})")

    rest = xml_id.replace("ID_FMP_", "", 1)
    parts = rest.rsplit("_", 1)
    if len(parts) != 2:
        return (None, None, "unparseable format")

    type_part, num_part = parts
    if not num_part or not num_part.isdigit():
        return (None, None, "no numeric suffix")

    entry = TYPE_MAP.get(type_part)
    if not entry or entry[0] is None:
        return (None, None, f"unknown type ({type_part})")

    table, prefix = entry
    return (f"{prefix}{num_part}", table, None)


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    grants_path = script_dir / "4e_grants.db"
    compendium_path = script_dir.parent / "4e_compendium.db"

    if not grants_path.exists():
        print(f"Error: Grants DB not found: {grants_path}", file=sys.stderr)
        return 1
    if not compendium_path.exists():
        print(f"Error: Compendium DB not found: {compendium_path}", file=sys.stderr)
        return 1

    comp = sqlite3.connect(compendium_path)
    grants = sqlite3.connect(grants_path)
    cursor = grants.cursor()

    # Build set of valid compendium IDs per table
    def get_valid_ids(table: str) -> set[str]:
        try:
            rows = comp.execute(f'SELECT id FROM "{table}"').fetchall()
            return {r[0] for r in rows}
        except sqlite3.OperationalError:
            return set()

    valid_ids: dict[str, set[str]] = {}
    for table, _ in TYPE_MAP.values():
        if table and table not in valid_ids:
            valid_ids[table] = get_valid_ids(table)
    # Item-like tables (magic items span items, implements, armor, weapons, poisons)
    for table in ("implements", "armor", "weapons", "poisons"):
        if table not in valid_ids:
            valid_ids[table] = get_valid_ids(table)

    # Build name_index: name_lower -> list of entry_ids (from compendium)
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for row in comp.execute("SELECT name_lower, entry_id FROM name_index").fetchall():
        name_to_ids[row[0]].append(row[1])

    # Build xml_id -> name from grants DB
    xml_id_to_name: dict[str, str] = {}
    for granter_xml, granter_name, granted_xml, granted_name in cursor.execute(
        "SELECT granter_xml_id, granter_name, granted_xml_id, granted_name FROM grants"
    ).fetchall():
        if granter_xml and granter_name:
            xml_id_to_name[granter_xml] = granter_name
        if granted_xml and granted_name:
            xml_id_to_name[granted_xml] = granted_name
    for granter_xml, granter_name in cursor.execute(
        "SELECT granter_xml_id, granter_name FROM stat_additions"
    ).fetchall():
        if granter_xml and granter_name:
            xml_id_to_name[granter_xml] = granter_name
    for granter_xml, granter_name in cursor.execute(
        "SELECT granter_xml_id, granter_name FROM modifies"
    ).fetchall():
        if granter_xml and granter_name:
            xml_id_to_name[granter_xml] = granter_name

    # Flatten valid_ids for quick membership check
    all_valid_ids: set[str] = set()
    for ids in valid_ids.values():
        all_valid_ids.update(ids)

    # Load manual overrides (xml_id -> compendium_id)
    manual_mappings: dict[str, str] = {}
    mappings_path = script_dir / "manual_id_mappings.csv"
    if mappings_path.exists():
        with open(mappings_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("xml_id"):
                    continue
                parts = line.split(",", 1)
                if len(parts) == 2:
                    xml_id, comp_id = parts[0].strip(), parts[1].strip()
                    if xml_id and comp_id and comp_id in all_valid_ids:
                        manual_mappings[xml_id] = comp_id

    def name_search_variants(name: str) -> list[str]:
        """Generate name variants to try against compendium (exact first, then normalized)."""
        s = name.strip().lower()
        if not s:
            return []
        seen: set[str] = {s}
        variants = [s]

        def add(v: str) -> None:
            v = re.sub(r"\s+", " ", v).strip()
            if v and v not in seen:
                seen.add(v)
                variants.append(v)

        # Strip parenthetical suffixes: (level 3), (heroic tier), (paragon tier), etc.
        base = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
        add(base)
        # Strip bracketed suffixes: [Movement Technique], [Attack Technique], etc.
        add(re.sub(r"\s*\[[^\]]*\]\s*$", "", s).strip())
        add(re.sub(r"\s*\[[^\]]*\]\s*$", "", base).strip())
        # Strip trailing " +N" (e.g. "Black Iron Armor +2")
        add(re.sub(r"\s*\+\d+\s*$", "", base))
        add(re.sub(r"\s*\+\d+\s*$", "", s))

        # CamelCase split: "SoulSword" -> "soul sword" (insert space before capitals in original)
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name.strip()).strip().lower()
        add(spaced)
        if spaced != base:
            add(re.sub(r"\s*\([^)]*\)\s*$", "", spaced))

        # Compound word split: "soulsword" -> "soul sword" (space before common substrings)
        for sub in ("sword", "blade", "armor", "shield", "weapon", "staff", "rod", "orb", "cloak"):
            if sub in s and not (f" {sub}" in s or f"{sub} " in s):
                idx = s.find(sub)
                if idx > 0:
                    split_v = f"{s[:idx]} {s[idx:]}"
                    add(split_v)

        # Strip trailing type words compendium often drops: " Attack", " Power", " (Daily)", etc.
        # Also secondary power action types: " Flight", " Teleport", " Strike", " Buffet" — part of main power
        for suffix in (
            r"\s+attack\s*$", r"\s+power\s*$", r"\s+\(daily\)\s*$", r"\s+\(encounter\)\s*$",
            r"\s+flight\s*$", r"\s+teleport\s*$", r"\s+strike\s*$", r"\s+buffet\s*$",
        ):
            stripped = re.sub(suffix, "", s, flags=re.IGNORECASE).strip()
            add(stripped)

        # "X Attack" secondary powers are usually part of "Form of the X" — try that variant
        attack_stripped = re.sub(r"\s+attack\s*$", "", s, flags=re.IGNORECASE).strip()
        if attack_stripped != s and not attack_stripped.startswith("form of"):
            add("form of the " + attack_stripped)
            add("form of " + attack_stripped)

        # Strip tier words compendium often drops: "Wayfinder Epic Badge" -> "wayfinder badge"
        for tier in (r"\bepic\b", r"\bheroic\b", r"\bparagon\b"):
            add(re.sub(r"\s+", " ", re.sub(tier, "", s, flags=re.IGNORECASE)).strip())

        # Strip equipment type suffixes — "Anakore Armor" is just "Anakore" in compendium
        for suffix in (r"\s+armor\s*$", r"\s+weapon\s*$", r"\s+shield\s*$", r"\s+ring\s*$", r"\s+boots\s*$", r"\s+cloak\s*$"):
            add(re.sub(suffix, "", s, flags=re.IGNORECASE).strip())
            base_no_plus = re.sub(r"\s*\+\d+\s*$", "", s).strip()
            add(re.sub(suffix, "", base_no_plus, flags=re.IGNORECASE).strip())

        # Strip " Secondary Power" / " Secondary Attack" — secondary powers are part of the main power
        add(re.sub(r"\s+secondary\s+power\s*$", "", s, flags=re.IGNORECASE))
        add(re.sub(r"\s+secondary\s+attack\s*$", "", s, flags=re.IGNORECASE))

        # "X Form Y Attack" (e.g. Wyrm Form Breath Attack) — compendium often has just "X form"
        if " form " in s:
            add((s.split(" form ")[0] + " form").strip())

        # Strip implement-type words compendium often drops: " Rod", " Staff", " Orb", " Wand"
        # Apply to both original and +N-stripped (e.g. "Chaos Shard Rod +1" -> "chaos shard rod" -> "chaos shard")
        for impl in (r"\s+rod\s*$", r"\s+staff\s*$", r"\s+orb\s*$", r"\s+wand\s*$"):
            add(re.sub(impl, "", s, flags=re.IGNORECASE).strip())
            base_no_plus = re.sub(r"\s*\+\d+\s*$", "", s).strip()
            add(re.sub(impl, "", base_no_plus, flags=re.IGNORECASE).strip())

        # "X - Y" compounds (e.g. Pact Blade - Raiment of Shadows) — compendium has full name in tables
        # name_index often only has "pact blade"; direct table search finds exact "pact blade - raiment of shadows"
        if " - " in s:
            base_no_plus = re.sub(r"\s*\+\d+\s*$", "", s).strip()
            add(base_no_plus)

        # "Controller's Implement" etc. — compendium has one per type (Orb, Rod, Staff, Wand, ...)
        base_no_plus = re.sub(r"\s*\+\d+\s*$", "", s).strip()
        if base_no_plus.endswith(" implement"):
            prefix = base_no_plus[: -len(" implement")].strip()
            for impl_type in ("orb", "rod", "staff", "wand", "tome", "totem", "holy symbol", "ki focus"):
                add(f"{prefix} {impl_type}")

        return variants

    # Tables to query by name when name_index misses full/compound names
    PREFIX_TO_TABLE = [
        ("weapon", "weapons"),
        ("item", "items"),
        ("armor", "armor"),
        ("implement", "implements"),
        ("poison", "poisons"),
        ("power", "powers"),
        ("feat", "feats"),
    ]

    def search_tables_by_name(name_key: str, acceptable_prefixes: tuple[str, ...]) -> str | None:
        """Direct table search when name_index misses full/compound names."""
        if not acceptable_prefixes or not name_key:
            return None
        for prefix, table in PREFIX_TO_TABLE:
            if not any(p in acceptable_prefixes for p in (prefix, prefix + "s")):
                continue
            if table not in valid_ids:
                continue
            try:
                rows = comp.execute(
                    f'SELECT id FROM "{table}" WHERE LOWER(name) = ?',
                    (name_key,),
                ).fetchall()
                for (eid,) in rows:
                    if eid in all_valid_ids and any(
                        eid.startswith(p) for p in acceptable_prefixes
                    ):
                        return eid
            except sqlite3.OperationalError:
                pass
        return None

    def search_by_name(name: str | None, type_hint: str | None) -> str | None:
        """Search compendium by name. Tries exact match, then normalized variants."""
        if not name or not name.strip():
            return None
        # Resolve acceptable prefixes for this type (flexible: items→implements/armor/weapons, etc.)
        acceptable_prefixes: tuple[str, ...] = ()
        if type_hint:
            if type_hint in TYPE_GROUP_PREFIXES:
                acceptable_prefixes = TYPE_GROUP_PREFIXES[type_hint]
            else:
                entry = TYPE_MAP.get(type_hint)
                if entry and entry[1]:
                    acceptable_prefixes = (entry[1],)

        for key in name_search_variants(name):
            candidates = name_to_ids.get(key, [])
            valid = [eid for eid in candidates if eid in all_valid_ids]
            if valid:
                if acceptable_prefixes:
                    type_matches = [
                        eid for eid in valid
                        if any(eid.startswith(p) for p in acceptable_prefixes)
                    ]
                    if type_matches:
                        return type_matches[0]
                else:
                    return valid[0]
            # name_index often lacks full/compound names; try direct table search
            if acceptable_prefixes:
                direct = search_tables_by_name(key, acceptable_prefixes)
                if direct:
                    return direct
        return None

    # Collect all xml_ids with context and occurrence count
    # id_info[xml_id] = (granter_in_grants, granted_in_grants, granter_in_statadd, granter_in_modify)
    id_info: dict[str, tuple[int, int, int, int]] = defaultdict(
        lambda: (0, 0, 0, 0)
    )

    for granter_xml, granted_xml in cursor.execute(
        "SELECT granter_xml_id, granted_xml_id FROM grants"
    ).fetchall():
        if granter_xml:
            g, a, s, m = id_info[granter_xml]
            id_info[granter_xml] = (g + 1, a, s, m)
        if granted_xml:
            g, a, s, m = id_info[granted_xml]
            id_info[granted_xml] = (g, a + 1, s, m)

    for (granter_xml,) in cursor.execute(
        "SELECT granter_xml_id FROM stat_additions"
    ).fetchall():
        if granter_xml:
            g, a, s, m = id_info[granter_xml]
            id_info[granter_xml] = (g, a, s + 1, m)

    for (granter_xml,) in cursor.execute(
        "SELECT granter_xml_id FROM modifies"
    ).fetchall():
        if granter_xml:
            g, a, s, m = id_info[granter_xml]
            id_info[granter_xml] = (g, a, s, m + 1)

    # Resolution cache: xml_id -> compendium_id or None
    resolution_cache: dict[str, str | None] = {}

    def resolve(xml_id: str | None) -> str | None:
        if xml_id is None:
            return None
        if xml_id in resolution_cache:
            return resolution_cache[xml_id]
        comp_id, table, unmappable = xml_to_compendium_id(xml_id)
        if unmappable:
            resolution_cache[xml_id] = None
            return None
        if comp_id and table and comp_id in valid_ids.get(table, set()):
            resolution_cache[xml_id] = comp_id
            return comp_id
        resolution_cache[xml_id] = None
        return None

    # Create resolution log table
    cursor.execute("DROP TABLE IF EXISTS _id_resolution_log")
    cursor.execute("""
        CREATE TABLE _id_resolution_log (
            xml_id TEXT NOT NULL,
            attempted_compendium_id TEXT,
            resolved_compendium_id TEXT,
            compendium_table TEXT,
            status TEXT NOT NULL,
            resolution_method TEXT,
            unmappable_reason TEXT,
            occurrence_count INTEGER NOT NULL,
            as_granter_in_grants INTEGER DEFAULT 0,
            as_granted_in_grants INTEGER DEFAULT 0,
            in_statadd_count INTEGER DEFAULT 0,
            in_modify_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolution_status ON _id_resolution_log(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolution_xml_id ON _id_resolution_log(xml_id)")

    # Resolve each unique xml_id and log
    log_rows: list[tuple] = []
    for xml_id, (g_count, a_count, s_count, m_count) in id_info.items():
        comp_id, table, unmappable = xml_to_compendium_id(xml_id)
        occ = g_count + a_count + s_count + m_count

        if unmappable:
            status = "unmappable"
            resolution_method = None
            resolved_id = None
            log_rows.append((
                xml_id, None, resolved_id, None, status, resolution_method,
                unmappable, occ, g_count, a_count, s_count, m_count
            ))
        elif comp_id and table and comp_id in valid_ids.get(table, set()):
            status = "matched"
            resolution_method = "id"
            resolved_id = comp_id
            log_rows.append((
                xml_id, comp_id, resolved_id, table, status, resolution_method,
                None, occ, g_count, a_count, s_count, m_count
            ))
            resolution_cache[xml_id] = comp_id
        else:
            # Check manual override first
            manual_id = manual_mappings.get(xml_id)

            if manual_id:
                status = "matched_manual"
                resolution_method = "manual"
                resolved_id = manual_id
                log_rows.append((
                    xml_id, comp_id, resolved_id, None, status, resolution_method,
                    None, occ, g_count, a_count, s_count, m_count
                ))
                resolution_cache[xml_id] = manual_id
            else:
                # Try name search when direct ID fails
                name = xml_id_to_name.get(xml_id)
                type_hint = None
                if comp_id and "ID_FMP_" in (xml_id or ""):
                    rest = (xml_id or "").replace("ID_FMP_", "", 1)
                    parts = rest.rsplit("_", 1)
                    if len(parts) == 2:
                        type_hint = parts[0]

                found_by_name = search_by_name(name, type_hint) if name else None

                if found_by_name:
                    status = "matched_name_search"
                    resolution_method = "name_search"
                    resolved_id = found_by_name
                    log_rows.append((
                        xml_id, comp_id, resolved_id, None, status, resolution_method,
                        None, occ, g_count, a_count, s_count, m_count
                    ))
                    resolution_cache[xml_id] = found_by_name
                else:
                    status = "not_found"
                    resolution_method = None
                    resolved_id = None
                    log_rows.append((
                        xml_id, comp_id, resolved_id, table or None, status, resolution_method,
                        None, occ, g_count, a_count, s_count, m_count
                    ))
                    resolution_cache[xml_id] = None

    cursor.executemany(
        """INSERT INTO _id_resolution_log (
            xml_id, attempted_compendium_id, resolved_compendium_id, compendium_table,
            status, resolution_method, unmappable_reason, occurrence_count,
            as_granter_in_grants, as_granted_in_grants, in_statadd_count, in_modify_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        log_rows,
    )

    # Update grants
    rows = cursor.execute(
        "SELECT id, granter_xml_id, granted_xml_id FROM grants"
    ).fetchall()
    granter_updated = granted_updated = 0
    for row_id, granter_xml, granted_xml in rows:
        granter_comp = resolve(granter_xml)
        granted_comp = resolve(granted_xml)
        if granter_comp is not None or granted_comp is not None:
            cursor.execute(
                """UPDATE grants SET granter_compendium_id = ?, granted_compendium_id = ?
                   WHERE id = ?""",
                (granter_comp, granted_comp, row_id),
            )
            if granter_comp:
                granter_updated += 1
            if granted_comp:
                granted_updated += 1

    # Update stat_additions (granter only)
    stat_rows = cursor.execute(
        "SELECT id, granter_xml_id FROM stat_additions"
    ).fetchall()
    stat_updated = 0
    for row_id, granter_xml in stat_rows:
        granter_comp = resolve(granter_xml)
        if granter_comp is not None:
            cursor.execute(
                "UPDATE stat_additions SET granter_compendium_id = ? WHERE id = ?",
                (granter_comp, row_id),
            )
            stat_updated += 1

    # Update modifies (granter only)
    mod_rows = cursor.execute(
        "SELECT id, granter_xml_id FROM modifies"
    ).fetchall()
    mod_updated = 0
    for row_id, granter_xml in mod_rows:
        granter_comp = resolve(granter_xml)
        if granter_comp is not None:
            cursor.execute(
                "UPDATE modifies SET granter_compendium_id = ? WHERE id = ?",
                (granter_comp, row_id),
            )
            mod_updated += 1

    grants.commit()

    # Export not_found for manual review
    csv_path = script_dir / "not_found_manual_review.csv"
    not_found_rows = cursor.execute("""
        SELECT l.xml_id, l.attempted_compendium_id, l.compendium_table, l.occurrence_count
        FROM _id_resolution_log l
        WHERE l.status = 'not_found'
        ORDER BY l.occurrence_count DESC, l.xml_id
    """).fetchall()
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("xml_id,attempted_compendium_id,compendium_table,occurrence_count,name\n")
        for row in not_found_rows:
            name = None
            for table, id_col, name_col in [
                ("grants", "granted_xml_id", "granted_name"),
                ("grants", "granter_xml_id", "granter_name"),
                ("stat_additions", "granter_xml_id", "granter_name"),
                ("modifies", "granter_xml_id", "granter_name"),
            ]:
                r = cursor.execute(
                    f"SELECT {name_col} FROM {table} WHERE {id_col} = ? LIMIT 1",
                    (row[0],),
                ).fetchone()
                if r and r[0]:
                    name = r[0]
                    break
            name_escaped = f'"{str(name).replace(chr(34), chr(34)+chr(34))}"' if name else ""
            f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{name_escaped}\n")

    # Stats
    total_grants = len(rows)
    with_granter = cursor.execute(
        "SELECT COUNT(*) FROM grants WHERE granter_compendium_id IS NOT NULL"
    ).fetchone()[0]
    with_granted = cursor.execute(
        "SELECT COUNT(*) FROM grants WHERE granted_compendium_id IS NOT NULL"
    ).fetchone()[0]

    matched = cursor.execute(
        'SELECT COUNT(*) FROM _id_resolution_log WHERE status = ?', ("matched",)
    ).fetchone()[0]
    matched_name = cursor.execute(
        'SELECT COUNT(*) FROM _id_resolution_log WHERE status = ?', ("matched_name_search",)
    ).fetchone()[0]
    matched_manual = cursor.execute(
        'SELECT COUNT(*) FROM _id_resolution_log WHERE status = ?', ("matched_manual",)
    ).fetchone()[0]
    not_found = cursor.execute(
        'SELECT COUNT(*) FROM _id_resolution_log WHERE status = ?', ("not_found",)
    ).fetchone()[0]
    unmappable = cursor.execute(
        'SELECT COUNT(*) FROM _id_resolution_log WHERE status = ?', ("unmappable",)
    ).fetchone()[0]

    print("Compendium ID resolution complete.")
    print(f"  Exported {len(not_found_rows)} not_found to {csv_path.name}")
    print(f"  Grants: {with_granter:,} granters resolved, {with_granted:,} granted resolved (of {total_grants:,})")
    print(f"  Stat additions: {stat_updated:,} granters resolved")
    print(f"  Modifies: {mod_updated:,} granters resolved")
    print(f"\n  ID resolution log (_id_resolution_log):")
    print(f"    matched (id):        {matched:,} (direct ID lookup)")
    print(f"    matched (name):      {matched_name:,} (name search fallback)")
    print(f"    matched (manual):    {matched_manual:,} (manual_id_mappings.csv)")
    print(f"    not_found:           {not_found:,} (attempted but missing)")
    print(f"    unmappable:          {unmappable:,} (couldn't derive compendium ID)")

    comp.close()
    grants.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
