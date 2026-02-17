#!/usr/bin/env python3
"""
Extract grant relationships and rule data from D&D 4E XML into 4e_grants.db.

Reads combined.dnd40.merged.xml, creates standalone 4e_grants.db with:
  - grants: what grants what (feats→powers, items→powers, etc.)
  - stat_additions: structured bonuses (resist:fire +5, etc.)
  - modifies: alterations to other elements

No dependency on compendium DB. Uses parameterized queries and XML parser
for robust handling of quotes, entities, and special characters.
"""

import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes for 4e_grants.db."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS _meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR REPLACE INTO _meta VALUES ('source', 'combined.dnd40.merged.xml');

        CREATE TABLE IF NOT EXISTS grants (
            id INTEGER PRIMARY KEY,
            granter_xml_id TEXT NOT NULL,
            granter_compendium_id TEXT,
            granter_type TEXT NOT NULL,
            granter_name TEXT,
            granted_xml_id TEXT NOT NULL,
            granted_compendium_id TEXT,
            granted_type TEXT NOT NULL,
            granted_name TEXT,
            requires TEXT,
            level TEXT,
            ordinal INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_grants_granter ON grants(granter_xml_id);
        CREATE INDEX IF NOT EXISTS idx_grants_granted ON grants(granted_xml_id);
        CREATE INDEX IF NOT EXISTS idx_grants_granter_comp ON grants(granter_compendium_id);

        CREATE TABLE IF NOT EXISTS stat_additions (
            id INTEGER PRIMARY KEY,
            granter_xml_id TEXT NOT NULL,
            granter_compendium_id TEXT,
            granter_type TEXT NOT NULL,
            granter_name TEXT,
            stat_name TEXT NOT NULL,
            value TEXT NOT NULL,
            bonus_type TEXT,
            requires TEXT,
            ordinal INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_statadd_granter ON stat_additions(granter_xml_id);

        CREATE TABLE IF NOT EXISTS modifies (
            id INTEGER PRIMARY KEY,
            granter_xml_id TEXT NOT NULL,
            granter_compendium_id TEXT,
            granter_type TEXT NOT NULL,
            granter_name TEXT,
            target_name TEXT NOT NULL,
            target_type TEXT,
            field TEXT NOT NULL,
            value TEXT,
            list_addition TEXT,
            requires TEXT,
            ordinal INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_modifies_granter ON modifies(granter_xml_id);
    """)


def safe_str(val) -> str | None:
    """Return value for SQL; None stays None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def process_rules_element(
    elem: ET.Element, conn: sqlite3.Connection, id_to_name: dict[str, str]
) -> tuple[int, int, int]:
    """
    Process a single RulesElement, extract grants/statadds/modifies.
    Returns (grants_count, statadds_count, modifies_count).
    """
    granter_xml_id = safe_str(elem.get("internal-id"))
    granter_type = safe_str(elem.get("type"))
    granter_name = safe_str(elem.get("name"))

    if not granter_xml_id or not granter_type:
        return (0, 0, 0)

    rules = elem.find("rules")
    if rules is None:
        return (0, 0, 0)

    cursor = conn.cursor()
    grant_count = statadd_count = modify_count = 0
    ordinal = 0

    for child in rules:
        tag = child.tag.lower() if child.tag else ""

        if tag == "grant":
            granted_xml_id = safe_str(child.get("name"))
            granted_type = safe_str(child.get("type"))
            if granted_xml_id and granted_type:
                granted_name = id_to_name.get(granted_xml_id) if granted_xml_id else None
                cursor.execute(
                    """INSERT INTO grants (
                        granter_xml_id, granter_compendium_id, granter_type, granter_name,
                        granted_xml_id, granted_compendium_id, granted_type, granted_name,
                        requires, level, ordinal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        granter_xml_id,
                        None,
                        granter_type,
                        granter_name,
                        granted_xml_id,
                        None,
                        granted_type,
                        granted_name,
                        safe_str(child.get("requires")),
                        safe_str(child.get("Level")),
                        ordinal,
                    ),
                )
                grant_count += 1
                ordinal += 1

        elif tag == "statadd":
            stat_name = safe_str(child.get("name"))
            value = safe_str(child.get("value"))
            if stat_name is not None and value is not None:
                cursor.execute(
                    """INSERT INTO stat_additions (
                        granter_xml_id, granter_compendium_id, granter_type, granter_name,
                        stat_name, value, bonus_type, requires, ordinal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        granter_xml_id,
                        None,
                        granter_type,
                        granter_name,
                        stat_name,
                        value,
                        safe_str(child.get("type")),
                        safe_str(child.get("requires")),
                        ordinal,
                    ),
                )
                statadd_count += 1
                ordinal += 1

        elif tag == "modify":
            target_name = safe_str(child.get("name"))
            field = safe_str(child.get("Field") or child.get("field"))
            if target_name is not None and field is not None:
                cursor.execute(
                    """INSERT INTO modifies (
                        granter_xml_id, granter_compendium_id, granter_type, granter_name,
                        target_name, target_type, field, value, list_addition, requires, ordinal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        granter_xml_id,
                        None,
                        granter_type,
                        granter_name,
                        target_name,
                        safe_str(child.get("type")),
                        field,
                        safe_str(child.get("value")),
                        safe_str(child.get("list-addition")),
                        safe_str(child.get("requires")),
                        ordinal,
                    ),
                )
                modify_count += 1
                ordinal += 1

    return (grant_count, statadd_count, modify_count)


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    xml_path = script_dir / "combined.dnd40.merged.xml"
    db_path = script_dir / "4e_grants.db"

    if not xml_path.exists():
        print(f"Error: XML file not found: {xml_path}", file=sys.stderr)
        return 1

    print(f"Parsing {xml_path}...")
    print(f"Writing to {db_path}...")

    # Remove existing DB for clean build
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    create_schema(conn)

    total_grants = total_statadds = total_modifies = 0
    rules_elements_processed = 0
    errors = []

    tree = ET.parse(xml_path, parser=ET.XMLParser(encoding="utf-8"))
    root = tree.getroot()

    # Build xml_id -> name map for granted_name lookups
    id_to_name: dict[str, str] = {}
    for elem in root.findall("RulesElement"):
        xml_id = elem.get("internal-id")
        name = elem.get("name")
        if xml_id and name:
            id_to_name[xml_id] = name.strip()

    for elem in root.findall("RulesElement"):
        try:
            g, s, m = process_rules_element(elem, conn, id_to_name)
            total_grants += g
            total_statadds += s
            total_modifies += m
            rules_elements_processed += 1
        except Exception as ex:
            xml_id = elem.get("internal-id", "?")
            errors.append((xml_id, str(ex)))

    conn.commit()

    # Update metadata
    conn.execute(
        "INSERT OR REPLACE INTO _meta VALUES ('extracted_at', datetime('now'))"
    )
    conn.commit()

    # Report
    print(f"\nDone. Processed {rules_elements_processed} RulesElements.")
    print(f"  Grants:       {total_grants:,}")
    print(f"  Stat adds:    {total_statadds:,}")
    print(f"  Modifies:     {total_modifies:,}")

    if errors:
        print(f"\n{len(errors)} element(s) had errors:")
        for xml_id, err in errors[:10]:
            print(f"  {xml_id}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    conn.close()
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
