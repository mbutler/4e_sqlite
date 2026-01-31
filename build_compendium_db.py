#!/usr/bin/env python3
"""
Build a single SQLite database from the 4e Compendium JSONP files.

Features:
- All 20 categories with raw data preserved
- Enhanced parsed fields (damage types, conditions, defense targeted, etc.)
- FTS5 full-text search on all text content
- Many-to-many tag tables for keywords, damage types, conditions
- Audit log for uncertain/low-confidence parses

Usage:
    python3 build_compendium_db.py
    
Output:
    4e_compendium.db (single file, ~20-50MB)
"""

import sqlite3
import json
import re
import os
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime


# =============================================================================
# JSON Cleaning Utilities (handle non-standard JSONP quirks)
# =============================================================================

def clean_json_string(s):
    """
    Clean a JSON-like string to make it valid JSON.
    Handles: trailing commas, invalid escapes, etc.
    """
    # Fix trailing commas before ] or }
    s = re.sub(r',(\s*[}\]])', r'\1', s)
    
    # Fix invalid escape sequences by escaping the backslash
    # Common issues: \U \A \B \C etc that aren't valid JSON escapes
    def fix_escapes(match):
        char = match.group(1)
        if char in 'bfnrtu"\\/':
            return match.group(0)  # Valid escape, keep it
        return '\\\\' + char  # Invalid escape, double the backslash
    
    s = re.sub(r'\\([^bfnrtu"\\/])', fix_escapes, s)
    
    return s


def safe_json_loads(s):
    """Attempt to parse JSON, cleaning it first if needed."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        cleaned = clean_json_string(s)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Last resort: try to fix more aggressively
            return None


def normalize_value(val):
    """
    Normalize a value for database insertion.
    Lists become JSON strings, preserving the first element as display value.
    """
    if val is None:
        return None
    if isinstance(val, list):
        # For lists like ["360+ gp", 360, 225000], return the display string
        if len(val) > 0:
            return str(val[0])
        return None
    return val

# =============================================================================
# Configuration
# =============================================================================

DATA_PATH = Path("4e_database_files")
OUTPUT_DB = "4e_compendium.db"

# Categories and their listing columns (from README)
CATEGORY_SCHEMAS = {
    "power": ["ID", "Name", "ClassName", "Level", "Type", "Action", "Keywords", "SourceBook"],
    "feat": ["ID", "Name", "Tier", "Prerequisite", "SourceBook"],
    "monster": ["ID", "Name", "Level", "CombatRole", "GroupRole", "Size", "CreatureType", "SourceBook"],
    "item": ["ID", "Name", "Category", "Type", "Level", "Cost", "Rarity", "SourceBook"],
    "ritual": ["ID", "Name", "Level", "ComponentCost", "Price", "KeySkillDescription", "SourceBook"],
    "class": ["ID", "Name", "RoleName", "PowerSourceText", "KeyAbilities", "SourceBook"],
    "race": ["ID", "Name", "Origin", "DescriptionAttribute", "Size", "SourceBook"],
    "paragonpath": ["ID", "Name", "Prerequisite", "SourceBook"],
    "epicdestiny": ["ID", "Name", "Prerequisite", "SourceBook"],
    "theme": ["ID", "Name", "Prerequisite", "SourceBook"],
    "background": ["ID", "Name", "Type", "Campaign", "Skills", "SourceBook"],
    "armor": ["ID", "Name", "Type", "ArmorBonus", "MinEnhancementBonus", "Check", "Speed", "Price", "Weight", "SourceBook"],
    "weapon": ["ID", "Name", "WeaponCategory", "HandsRequired", "ProficiencyBonus", "Damage", "Range", "Price", "Weight", "Group", "Properties", "SourceBook"],
    "implement": ["ID", "Name", "SourceBook"],
    "trap": ["ID", "Name", "Type", "Level", "Role", "XP", "SourceBook"],
    "disease": ["ID", "Name", "Level", "SourceBook"],
    "poison": ["ID", "Name", "Level", "Cost", "SourceBook"],
    "deity": ["ID", "Name", "Alignment", "SourceBook"],
    "companion": ["ID", "Name", "Type", "SourceBook"],
    "glossary": ["ID", "Name", "Category", "Type", "SourceBook"],
}

# Known damage types in 4e
DAMAGE_TYPES = {
    'fire', 'cold', 'lightning', 'thunder', 'radiant', 'necrotic', 
    'psychic', 'poison', 'acid', 'force'
}

# Known conditions in 4e
CONDITIONS = {
    'dazed', 'stunned', 'prone', 'immobilized', 'slowed', 'dominated',
    'blinded', 'deafened', 'weakened', 'petrified', 'unconscious',
    'restrained', 'grabbed', 'marked', 'surprised', 'helpless',
    'dying', 'dead', 'bloodied'
}

# Defenses
DEFENSES = {'AC', 'Fortitude', 'Reflex', 'Will'}

# =============================================================================
# JSONP Parsing
# =============================================================================

def extract_jsonp_payload(content, callback_pattern):
    """
    Extract the JSON payload from a JSONP file.
    
    JSONP format: od.reader.callback_name(timestamp, payload)
    or: od.reader.callback_name(timestamp, "category", payload)
    """
    # Remove any BOM or whitespace
    content = content.strip()
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Find the opening parenthesis
    paren_start = content.find('(')
    if paren_start == -1:
        return None
    
    # Find the closing parenthesis (last one)
    paren_end = content.rfind(')')
    if paren_end == -1:
        return None
    
    # Extract arguments
    args_str = content[paren_start + 1:paren_end]
    
    # Parse the arguments - handle timestamp, optional category, then payload
    # This is tricky because the payload itself contains commas
    # Strategy: find the last { or [ which starts the main payload
    
    # For catalog.js: jsonp_catalog(timestamp, {catalog_object})
    # For listing: jsonp_data_listing(timestamp, "category", [columns], [rows])
    # For data: jsonp_batch_data(timestamp, "category", {id: html, ...})
    # For index: jsonp_data_index(timestamp, "category", {id: text, ...})
    # For name index: jsonp_name_index(timestamp, {name: id, ...})
    
    return args_str


def parse_catalog(content):
    """Parse catalog.js"""
    args = extract_jsonp_payload(content, 'jsonp_catalog')
    if not args:
        return {}
    
    # Find the object starting with {
    brace_start = args.find('{')
    if brace_start == -1:
        return {}
    
    json_str = args[brace_start:]
    result = safe_json_loads(json_str)
    if result is None:
        print(f"Error parsing catalog")
        return {}
    return result


def parse_listing(content):
    """
    Parse _listing.js file.
    Returns (columns, rows) where rows is a list of lists.
    """
    args = extract_jsonp_payload(content, 'jsonp_data_listing')
    if not args:
        return [], []
    
    # Format: timestamp, "category", ["columns"], [[row1], [row2], ...]
    # Find the first [ which is the columns array
    first_bracket = args.find('[')
    if first_bracket == -1:
        return [], []
    
    # Everything from first [ to end should be: ["cols"], [[rows]])
    # We need to parse this carefully
    json_part = args[first_bracket:]
    
    # Find where columns end and rows begin
    # Columns: ["ID", "Name", ...]
    # Then a comma, then rows: [["id1", ...], ["id2", ...]]
    
    bracket_depth = 0
    columns_end = -1
    for i, char in enumerate(json_part):
        if char == '[':
            bracket_depth += 1
        elif char == ']':
            bracket_depth -= 1
            if bracket_depth == 0:
                columns_end = i
                break
    
    if columns_end == -1:
        return [], []
    
    columns_str = json_part[:columns_end + 1]
    
    # Find the start of the rows array
    remaining = json_part[columns_end + 1:]
    rows_start = remaining.find('[')
    if rows_start == -1:
        return [], []
    
    rows_str = remaining[rows_start:].rstrip(')')
    
    columns = safe_json_loads(columns_str)
    rows = safe_json_loads(rows_str)
    
    if columns is None or rows is None:
        print(f"Error parsing listing")
        return [], []
    
    return columns, rows


def parse_batch_data(content):
    """
    Parse dataN.js file.
    Returns dict of {id: html_content}
    """
    args = extract_jsonp_payload(content, 'jsonp_batch_data')
    if not args:
        return {}
    
    # Find the object starting with {
    brace_start = args.find('{')
    if brace_start == -1:
        return {}
    
    json_str = args[brace_start:]
    result = safe_json_loads(json_str)
    if result is None:
        # Try a more aggressive approach for HTML content
        # Sometimes HTML has weird escape issues
        try:
            # Use a regex to extract key-value pairs
            result = {}
            pattern = r'"([^"]+)":\s*"((?:[^"\\]|\\.)*)"\s*[,}]'
            for match in re.finditer(pattern, json_str, re.DOTALL):
                key = match.group(1)
                value = match.group(2)
                # Unescape the value
                value = value.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                result[key] = value
            if result:
                return result
        except:
            pass
        print(f"Error parsing batch data")
        return {}
    return result


def parse_index(content):
    """
    Parse _index.js file.
    Returns dict of {id: search_text}
    """
    args = extract_jsonp_payload(content, 'jsonp_data_index')
    if not args:
        return {}
    
    # Find the object starting with {
    brace_start = args.find('{')
    if brace_start == -1:
        return {}
    
    json_str = args[brace_start:]
    result = safe_json_loads(json_str)
    if result is None:
        print(f"Error parsing index")
        return {}
    return result


def parse_name_index(content):
    """
    Parse index.js (global name index).
    Returns dict of {lowercased_name: id}
    """
    args = extract_jsonp_payload(content, 'jsonp_name_index')
    if not args:
        return {}
    
    brace_start = args.find('{')
    if brace_start == -1:
        return {}
    
    json_str = args[brace_start:]
    result = safe_json_loads(json_str)
    if result is None:
        print(f"Error parsing name index")
        return {}
    return result


# =============================================================================
# HTML Parsing / Text Extraction
# =============================================================================

class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML."""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        
    def handle_data(self, data):
        self.text_parts.append(data)
        
    def get_text(self):
        return ' '.join(self.text_parts)


def html_to_text(html):
    """Convert HTML to plain text."""
    if not html:
        return ""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html)
        return extractor.get_text()
    except:
        # Fallback: just strip tags with regex
        return re.sub(r'<[^>]+>', ' ', html)


# =============================================================================
# Data Extraction / Enhancement
# =============================================================================

def extract_damage_types(keywords_raw, html_body, search_text):
    """
    Extract damage types from a power/item.
    Returns (set of damage types, confidence, source)
    """
    found = set()
    sources = []
    
    # High confidence: from keywords field
    if keywords_raw:
        kw_lower = keywords_raw.lower()
        for dt in DAMAGE_TYPES:
            if dt in kw_lower:
                found.add(dt)
                sources.append(('keyword', dt, 'high'))
    
    return found, sources


def extract_conditions(html_body, search_text):
    """
    Extract conditions inflicted by a power.
    Only extract from high-confidence patterns like "target is <condition>"
    Returns (set of conditions, sources)
    """
    found = set()
    sources = []
    
    if not html_body and not search_text:
        return found, sources
    
    text = search_text or html_to_text(html_body)
    text_lower = text.lower()
    
    # High confidence patterns
    patterns = [
        r'target is (\w+)',
        r'targets? (?:are|is) (\w+)',
        r'(\w+) \(save ends\)',
        r'and (?:is |the target is )?(\w+)',
        r'knocked (\w+)',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text_lower):
            word = match.group(1)
            if word in CONDITIONS:
                found.add(word)
                sources.append(('pattern', word, 'medium'))
    
    return found, sources


def extract_defense_targeted(html_body, search_text):
    """
    Extract the defense targeted by an attack.
    Returns (defense, confidence) or (None, None)
    """
    text = search_text or html_to_text(html_body) if html_body else ""
    
    # High confidence: "vs. Defense" or "vs Defense"
    match = re.search(r'vs\.?\s*(AC|Fortitude|Reflex|Will)', text, re.IGNORECASE)
    if match:
        defense = match.group(1)
        # Normalize case
        if defense.upper() == 'AC':
            return 'AC', 'high'
        return defense.capitalize(), 'high'
    
    return None, None


def extract_range_info(action_raw, html_body):
    """
    Extract range type and value.
    Returns (range_type, range_value, area_type, area_size)
    """
    range_type = None
    range_value = None
    area_type = None
    area_size = None
    
    text = html_to_text(html_body) if html_body else ""
    
    # Check for Melee/Ranged/Close/Area patterns
    if re.search(r'\bMelee\b', text, re.IGNORECASE):
        range_type = 'Melee'
        # Melee weapon, Melee touch, Melee 1, Melee 2
        match = re.search(r'Melee\s+(\d+)', text)
        if match:
            range_value = int(match.group(1))
            
    elif re.search(r'\bRanged\b', text, re.IGNORECASE):
        range_type = 'Ranged'
        match = re.search(r'Ranged\s+(\d+)', text)
        if match:
            range_value = int(match.group(1))
            
    elif re.search(r'\bClose\b', text, re.IGNORECASE):
        range_type = 'Close'
        # Close burst 5, Close blast 3
        match = re.search(r'Close\s+(burst|blast)\s+(\d+)', text, re.IGNORECASE)
        if match:
            area_type = match.group(1).lower()
            area_size = int(match.group(2))
            
    elif re.search(r'\bArea\b', text, re.IGNORECASE):
        range_type = 'Area'
        match = re.search(r'Area\s+(burst|blast|wall)\s+(\d+)', text, re.IGNORECASE)
        if match:
            area_type = match.group(1).lower()
            area_size = int(match.group(2))
    
    return range_type, range_value, area_type, area_size


def extract_power_type(type_raw):
    """
    Extract power usage type: At-Will, Encounter, Daily
    """
    if not type_raw:
        return None
    
    t = type_raw.lower()
    if 'at-will' in t or 'atwill' in t:
        return 'At-Will'
    elif 'enc' in t:
        return 'Encounter'
    elif 'daily' in t:
        return 'Daily'
    return None


def parse_level(level_raw):
    """Parse level to integer, handling ranges and special values."""
    if not level_raw:
        return None
    
    if isinstance(level_raw, int):
        return level_raw
    
    if isinstance(level_raw, list):
        # Range format like ["5+", 5, 30]
        if len(level_raw) >= 2:
            return level_raw[1] if isinstance(level_raw[1], int) else None
        return None
    
    # String parsing
    s = str(level_raw).strip()
    match = re.match(r'(\d+)', s)
    if match:
        return int(match.group(1))
    
    return None


# =============================================================================
# Database Schema Creation
# =============================================================================

def create_schema(conn):
    """Create all database tables."""
    cursor = conn.cursor()
    
    # -------------------------------------------------------------------------
    # Core tables for each category
    # -------------------------------------------------------------------------
    
    # Powers table (the big one with all enhancements)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS powers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            class_name TEXT,
            level INTEGER,
            level_raw TEXT,
            type TEXT,
            type_raw TEXT,
            action TEXT,
            keywords_raw TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT,
            
            -- Enhanced parsed fields
            power_usage TEXT,           -- At-Will, Encounter, Daily
            defense_targeted TEXT,      -- AC, Fortitude, Reflex, Will
            range_type TEXT,            -- Melee, Ranged, Close, Area
            range_value INTEGER,
            area_type TEXT,             -- burst, blast, wall
            area_size INTEGER
        )
    ''')
    
    # Feats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feats (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT,
            prerequisite TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Monsters table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monsters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER,
            level_raw TEXT,
            combat_role TEXT,
            group_role TEXT,
            size TEXT,
            creature_type TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            type TEXT,
            level INTEGER,
            level_raw TEXT,
            cost TEXT,
            rarity TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Classes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT,
            power_source TEXT,
            key_abilities TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Races table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS races (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            origin TEXT,
            description TEXT,
            size TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Paragon Paths table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paragon_paths (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            prerequisite TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Epic Destinies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS epic_destinies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            prerequisite TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Themes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS themes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            prerequisite TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Rituals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rituals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER,
            level_raw TEXT,
            component_cost TEXT,
            price TEXT,
            key_skill TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Backgrounds table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backgrounds (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            campaign TEXT,
            skills TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Traps table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traps (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            level INTEGER,
            level_raw TEXT,
            role TEXT,
            xp TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Diseases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS diseases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER,
            level_raw TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Poisons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS poisons (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER,
            level_raw TEXT,
            cost TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Deities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            alignment TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Companions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Glossary table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS glossary (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            type TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Armor table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS armor (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            armor_bonus TEXT,
            min_enhancement_bonus TEXT,
            armor_check TEXT,
            speed TEXT,
            price TEXT,
            weight TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Weapons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weapons (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            weapon_category TEXT,
            hands_required TEXT,
            proficiency_bonus TEXT,
            damage TEXT,
            range TEXT,
            price TEXT,
            weight TEXT,
            weapon_group TEXT,
            properties TEXT,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # Implements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS implements (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_book TEXT,
            html_body TEXT,
            search_text TEXT
        )
    ''')
    
    # -------------------------------------------------------------------------
    # Tag tables (many-to-many)
    # -------------------------------------------------------------------------
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS power_keywords (
            power_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            PRIMARY KEY (power_id, keyword),
            FOREIGN KEY (power_id) REFERENCES powers(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS power_damage_types (
            power_id TEXT NOT NULL,
            damage_type TEXT NOT NULL,
            PRIMARY KEY (power_id, damage_type),
            FOREIGN KEY (power_id) REFERENCES powers(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS power_conditions (
            power_id TEXT NOT NULL,
            condition TEXT NOT NULL,
            PRIMARY KEY (power_id, condition),
            FOREIGN KEY (power_id) REFERENCES powers(id)
        )
    ''')
    
    # -------------------------------------------------------------------------
    # Global name index table
    # -------------------------------------------------------------------------
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS name_index (
            name_lower TEXT NOT NULL,
            entry_id TEXT NOT NULL,
            PRIMARY KEY (name_lower, entry_id)
        )
    ''')
    
    # -------------------------------------------------------------------------
    # Audit / Parse log
    # -------------------------------------------------------------------------
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS _parse_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id TEXT NOT NULL,
            field TEXT NOT NULL,
            value TEXT,
            source TEXT,
            confidence TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS _meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS _categories (
            name TEXT PRIMARY KEY,
            entry_count INTEGER,
            table_name TEXT
        )
    ''')
    
    conn.commit()


def create_fts_indexes(conn):
    """Create FTS5 full-text search virtual tables."""
    cursor = conn.cursor()
    
    # Powers FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS powers_fts USING fts5(
            id,
            name,
            class_name,
            keywords_raw,
            search_text,
            html_body,
            content='powers',
            content_rowid='rowid'
        )
    ''')
    
    # Populate powers FTS
    cursor.execute('''
        INSERT INTO powers_fts(powers_fts) VALUES('rebuild')
    ''')
    
    # Feats FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS feats_fts USING fts5(
            id,
            name,
            tier,
            prerequisite,
            search_text,
            content='feats',
            content_rowid='rowid'
        )
    ''')
    cursor.execute("INSERT INTO feats_fts(feats_fts) VALUES('rebuild')")
    
    # Monsters FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS monsters_fts USING fts5(
            id,
            name,
            combat_role,
            creature_type,
            search_text,
            content='monsters',
            content_rowid='rowid'
        )
    ''')
    cursor.execute("INSERT INTO monsters_fts(monsters_fts) VALUES('rebuild')")
    
    # Items FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            id,
            name,
            category,
            type,
            search_text,
            content='items',
            content_rowid='rowid'
        )
    ''')
    cursor.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
    
    # Classes FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS classes_fts USING fts5(
            id,
            name,
            role,
            power_source,
            search_text,
            content='classes',
            content_rowid='rowid'
        )
    ''')
    cursor.execute("INSERT INTO classes_fts(classes_fts) VALUES('rebuild')")
    
    # Races FTS
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS races_fts USING fts5(
            id,
            name,
            origin,
            search_text,
            content='races',
            content_rowid='rowid'
        )
    ''')
    cursor.execute("INSERT INTO races_fts(races_fts) VALUES('rebuild')")
    
    # Generic FTS for other categories
    for table in ['paragon_paths', 'epic_destinies', 'themes', 'rituals', 
                  'backgrounds', 'traps', 'diseases', 'poisons', 'deities',
                  'companions', 'glossary', 'armor', 'weapons', 'implements']:
        cursor.execute(f'''
            CREATE VIRTUAL TABLE IF NOT EXISTS {table}_fts USING fts5(
                id,
                name,
                search_text,
                content='{table}',
                content_rowid='rowid'
            )
        ''')
        cursor.execute(f"INSERT INTO {table}_fts({table}_fts) VALUES('rebuild')")
    
    conn.commit()


def create_indexes(conn):
    """Create standard indexes for fast queries."""
    cursor = conn.cursor()
    
    # Power indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_powers_class ON powers(class_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_powers_level ON powers(level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_powers_usage ON powers(power_usage)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_powers_defense ON powers(defense_targeted)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_powers_range ON powers(range_type)")
    
    # Feat indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feats_tier ON feats(tier)")
    
    # Monster indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_level ON monsters(level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_role ON monsters(combat_role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_type ON monsters(creature_type)")
    
    # Item indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_level ON items(level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_rarity ON items(rarity)")
    
    # Tag table indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_power_keywords_keyword ON power_keywords(keyword)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_power_damage_types_type ON power_damage_types(damage_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_power_conditions_cond ON power_conditions(condition)")
    
    conn.commit()


# =============================================================================
# Data Loading
# =============================================================================

def load_category_data(category):
    """
    Load all data for a category.
    Returns (columns, rows, html_bodies, search_texts)
    """
    category_path = DATA_PATH / category
    
    # Load listing
    listing_file = category_path / "_listing.js"
    columns, rows = [], []
    if listing_file.exists():
        content = listing_file.read_text(encoding='utf-8')
        columns, rows = parse_listing(content)
    
    # Load HTML bodies from data files
    html_bodies = {}
    for i in range(20):
        data_file = category_path / f"data{i}.js"
        if data_file.exists():
            content = data_file.read_text(encoding='utf-8')
            bodies = parse_batch_data(content)
            html_bodies.update(bodies)
    
    # Load search index
    search_texts = {}
    index_file = category_path / "_index.js"
    if index_file.exists():
        content = index_file.read_text(encoding='utf-8')
        search_texts = parse_index(content)
    
    return columns, rows, html_bodies, search_texts


def insert_powers(conn, columns, rows, html_bodies, search_texts):
    """Insert power data with enhanced parsing."""
    cursor = conn.cursor()
    
    # Map column names to indices
    col_map = {col: idx for idx, col in enumerate(columns)}
    
    for row in rows:
        try:
            entry_id = normalize_value(row[col_map.get('ID', 0)])
            name = normalize_value(row[col_map.get('Name', 1)] if len(row) > col_map.get('Name', 1) else '')
            class_name = normalize_value(row[col_map.get('ClassName', 2)] if len(row) > col_map.get('ClassName', 2) else '')
            level_raw = row[col_map.get('Level', 3)] if len(row) > col_map.get('Level', 3) else ''
            type_raw = normalize_value(row[col_map.get('Type', 4)] if len(row) > col_map.get('Type', 4) else '')
            action = normalize_value(row[col_map.get('Action', 5)] if len(row) > col_map.get('Action', 5) else '')
            keywords_raw = normalize_value(row[col_map.get('Keywords', 6)] if len(row) > col_map.get('Keywords', 6) else '')
            source_book = normalize_value(row[col_map.get('SourceBook', 7)] if len(row) > col_map.get('SourceBook', 7) else '')
            
            html_body = html_bodies.get(entry_id, '')
            search_text = search_texts.get(entry_id, '')
            
            # Parse enhanced fields
            level = parse_level(level_raw)
            power_usage = extract_power_type(type_raw)
            defense, defense_conf = extract_defense_targeted(html_body, search_text)
            range_type, range_value, area_type, area_size = extract_range_info(action, html_body)
            
            # Insert main record
            cursor.execute('''
                INSERT OR REPLACE INTO powers 
                (id, name, class_name, level, level_raw, type, type_raw, action, 
                 keywords_raw, source_book, html_body, search_text,
                 power_usage, defense_targeted, range_type, range_value, area_type, area_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (entry_id, name, class_name, level, str(level_raw), type_raw, type_raw, action,
                  keywords_raw, source_book, html_body, search_text,
                  power_usage, defense, range_type, range_value, area_type, area_size))
            
            # Insert keywords
            if keywords_raw:
                keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
                for kw in keywords:
                    cursor.execute('''
                        INSERT OR IGNORE INTO power_keywords (power_id, keyword)
                        VALUES (?, ?)
                    ''', (entry_id, kw))
            
            # Extract and insert damage types
            damage_types, dt_sources = extract_damage_types(keywords_raw, html_body, search_text)
            for dt in damage_types:
                cursor.execute('''
                    INSERT OR IGNORE INTO power_damage_types (power_id, damage_type)
                    VALUES (?, ?)
                ''', (entry_id, dt))
            
            # Log damage type extractions
            for source, value, confidence in dt_sources:
                cursor.execute('''
                    INSERT INTO _parse_log (entry_id, field, value, source, confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entry_id, 'damage_type', value, source, confidence))
            
            # Extract and insert conditions
            conditions, cond_sources = extract_conditions(html_body, search_text)
            for cond in conditions:
                cursor.execute('''
                    INSERT OR IGNORE INTO power_conditions (power_id, condition)
                    VALUES (?, ?)
                ''', (entry_id, cond))
            
            # Log condition extractions
            for source, value, confidence in cond_sources:
                cursor.execute('''
                    INSERT INTO _parse_log (entry_id, field, value, source, confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entry_id, 'condition', value, source, confidence))
            
            # Log defense extraction if found
            if defense:
                cursor.execute('''
                    INSERT INTO _parse_log (entry_id, field, value, source, confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entry_id, 'defense_targeted', defense, 'regex', defense_conf))
                
        except Exception as e:
            print(f"Error inserting power {row}: {e}")
    
    conn.commit()


def insert_generic(conn, table_name, columns, rows, html_bodies, search_texts, col_mapping):
    """
    Generic insert for simpler categories.
    col_mapping maps table columns to listing column names.
    """
    cursor = conn.cursor()
    col_map = {col: idx for idx, col in enumerate(columns)}
    
    for row in rows:
        try:
            values = {}
            for table_col, listing_col in col_mapping.items():
                idx = col_map.get(listing_col)
                if idx is not None and idx < len(row):
                    # Normalize list values to their display string
                    values[table_col] = normalize_value(row[idx])
                else:
                    values[table_col] = None
            
            entry_id = values.get('id', '')
            values['html_body'] = html_bodies.get(entry_id, '')
            values['search_text'] = search_texts.get(entry_id, '')
            
            # Handle level parsing for tables that have it
            if 'level_raw' in col_mapping:
                values['level'] = parse_level(values.get('level_raw'))
            
            # Build INSERT statement
            cols = list(values.keys())
            placeholders = ', '.join(['?' for _ in cols])
            col_names = ', '.join(cols)
            
            cursor.execute(f'''
                INSERT OR REPLACE INTO {table_name} ({col_names})
                VALUES ({placeholders})
            ''', [values[c] for c in cols])
            
        except Exception as e:
            print(f"Error inserting into {table_name}: {e}")
    
    conn.commit()


# =============================================================================
# Main Build Process
# =============================================================================

def build_database():
    """Main function to build the SQLite database."""
    print(f"Building {OUTPUT_DB}...")
    print("=" * 60)
    
    # Remove existing database
    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)
        print(f"Removed existing {OUTPUT_DB}")
    
    # Connect and create schema
    conn = sqlite3.connect(OUTPUT_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    print("Creating schema...")
    create_schema(conn)
    
    # Load catalog
    catalog_file = DATA_PATH / "catalog.js"
    if catalog_file.exists():
        catalog = parse_catalog(catalog_file.read_text(encoding='utf-8'))
        print(f"Catalog: {len(catalog)} categories")
    else:
        catalog = {}
        print("Warning: catalog.js not found")
    
    # Process each category
    category_table_map = {
        'power': 'powers',
        'feat': 'feats',
        'monster': 'monsters',
        'item': 'items',
        'class': 'classes',
        'race': 'races',
        'paragonpath': 'paragon_paths',
        'epicdestiny': 'epic_destinies',
        'theme': 'themes',
        'ritual': 'rituals',
        'background': 'backgrounds',
        'trap': 'traps',
        'disease': 'diseases',
        'poison': 'poisons',
        'deity': 'deities',
        'companion': 'companions',
        'glossary': 'glossary',
        'armor': 'armor',
        'weapon': 'weapons',
        'implement': 'implements',
    }
    
    # Column mappings for generic insert
    generic_mappings = {
        'feats': {
            'id': 'ID', 'name': 'Name', 'tier': 'Tier', 
            'prerequisite': 'Prerequisite', 'source_book': 'SourceBook'
        },
        'monsters': {
            'id': 'ID', 'name': 'Name', 'level_raw': 'Level', 'combat_role': 'CombatRole',
            'group_role': 'GroupRole', 'size': 'Size', 'creature_type': 'CreatureType',
            'source_book': 'SourceBook'
        },
        'items': {
            'id': 'ID', 'name': 'Name', 'category': 'Category', 'type': 'Type',
            'level_raw': 'Level', 'cost': 'Cost', 'rarity': 'Rarity', 'source_book': 'SourceBook'
        },
        'classes': {
            'id': 'ID', 'name': 'Name', 'role': 'RoleName', 'power_source': 'PowerSourceText',
            'key_abilities': 'KeyAbilities', 'source_book': 'SourceBook'
        },
        'races': {
            'id': 'ID', 'name': 'Name', 'origin': 'Origin', 'description': 'DescriptionAttribute',
            'size': 'Size', 'source_book': 'SourceBook'
        },
        'paragon_paths': {
            'id': 'ID', 'name': 'Name', 'prerequisite': 'Prerequisite', 'source_book': 'SourceBook'
        },
        'epic_destinies': {
            'id': 'ID', 'name': 'Name', 'prerequisite': 'Prerequisite', 'source_book': 'SourceBook'
        },
        'themes': {
            'id': 'ID', 'name': 'Name', 'prerequisite': 'Prerequisite', 'source_book': 'SourceBook'
        },
        'rituals': {
            'id': 'ID', 'name': 'Name', 'level_raw': 'Level', 'component_cost': 'ComponentCost',
            'price': 'Price', 'key_skill': 'KeySkillDescription', 'source_book': 'SourceBook'
        },
        'backgrounds': {
            'id': 'ID', 'name': 'Name', 'type': 'Type', 'campaign': 'Campaign',
            'skills': 'Skills', 'source_book': 'SourceBook'
        },
        'traps': {
            'id': 'ID', 'name': 'Name', 'type': 'Type', 'level_raw': 'Level',
            'role': 'Role', 'xp': 'XP', 'source_book': 'SourceBook'
        },
        'diseases': {
            'id': 'ID', 'name': 'Name', 'level_raw': 'Level', 'source_book': 'SourceBook'
        },
        'poisons': {
            'id': 'ID', 'name': 'Name', 'level_raw': 'Level', 'cost': 'Cost', 'source_book': 'SourceBook'
        },
        'deities': {
            'id': 'ID', 'name': 'Name', 'alignment': 'Alignment', 'source_book': 'SourceBook'
        },
        'companions': {
            'id': 'ID', 'name': 'Name', 'type': 'Type', 'source_book': 'SourceBook'
        },
        'glossary': {
            'id': 'ID', 'name': 'Name', 'category': 'Category', 'type': 'Type', 'source_book': 'SourceBook'
        },
        'armor': {
            'id': 'ID', 'name': 'Name', 'type': 'Type', 'armor_bonus': 'ArmorBonus',
            'min_enhancement_bonus': 'MinEnhancementBonus', 'armor_check': 'Check',
            'speed': 'Speed', 'price': 'Price', 'weight': 'Weight', 'source_book': 'SourceBook'
        },
        'weapons': {
            'id': 'ID', 'name': 'Name', 'weapon_category': 'WeaponCategory',
            'hands_required': 'HandsRequired', 'proficiency_bonus': 'ProficiencyBonus',
            'damage': 'Damage', 'range': 'Range', 'price': 'Price', 'weight': 'Weight',
            'weapon_group': 'Group', 'properties': 'Properties', 'source_book': 'SourceBook'
        },
        'implements': {
            'id': 'ID', 'name': 'Name', 'source_book': 'SourceBook'
        },
    }
    
    total_entries = 0
    
    for category, table_name in category_table_map.items():
        category_path = DATA_PATH / category
        if not category_path.exists():
            print(f"  Skipping {category} (not found)")
            continue
        
        print(f"  Processing {category}...", end=' ')
        columns, rows, html_bodies, search_texts = load_category_data(category)
        
        if not rows:
            print("no data")
            continue
        
        # Special handling for powers (with enhancements)
        if category == 'power':
            insert_powers(conn, columns, rows, html_bodies, search_texts)
        else:
            mapping = generic_mappings.get(table_name, {})
            if mapping:
                insert_generic(conn, table_name, columns, rows, html_bodies, search_texts, mapping)
        
        # Record category metadata
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO _categories (name, entry_count, table_name)
            VALUES (?, ?, ?)
        ''', (category, len(rows), table_name))
        
        print(f"{len(rows)} entries")
        total_entries += len(rows)
    
    # Load global name index
    print("  Processing global name index...", end=' ')
    name_index_file = DATA_PATH / "index.js"
    if name_index_file.exists():
        name_index = parse_name_index(name_index_file.read_text(encoding='utf-8'))
        cursor = conn.cursor()
        insert_count = 0
        for name_lower, entry_id in name_index.items():
            # Handle cases where entry_id might be a list of IDs
            if isinstance(entry_id, list):
                for eid in entry_id:
                    cursor.execute('''
                        INSERT OR IGNORE INTO name_index (name_lower, entry_id)
                        VALUES (?, ?)
                    ''', (name_lower, str(eid)))
                    insert_count += 1
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO name_index (name_lower, entry_id)
                    VALUES (?, ?)
                ''', (name_lower, str(entry_id)))
                insert_count += 1
        conn.commit()
        print(f"{len(name_index)} names ({insert_count} entries)")
    else:
        print("not found")
    
    # Create FTS indexes
    print("Creating FTS5 indexes...")
    create_fts_indexes(conn)
    
    # Create standard indexes
    print("Creating indexes...")
    create_indexes(conn)
    
    # Record metadata
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
                   ('build_date', datetime.now().isoformat()))
    cursor.execute("INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
                   ('total_entries', str(total_entries)))
    cursor.execute("INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
                   ('version', '1.0'))
    conn.commit()
    
    # Optimize
    print("Optimizing database...")
    conn.execute("VACUUM")
    conn.execute("ANALYZE")
    
    conn.close()
    
    # Report
    db_size = os.path.getsize(OUTPUT_DB) / (1024 * 1024)
    print("=" * 60)
    print(f"Done! Created {OUTPUT_DB}")
    print(f"  Total entries: {total_entries:,}")
    print(f"  Database size: {db_size:.1f} MB")
    print()
    print("Example queries:")
    print("  sqlite3 4e_compendium.db \"SELECT name, class_name, level FROM powers WHERE defense_targeted='Will' LIMIT 5\"")
    print("  sqlite3 4e_compendium.db \"SELECT * FROM powers_fts WHERE powers_fts MATCH 'fire damage' LIMIT 5\"")
    print("  sqlite3 4e_compendium.db \"SELECT p.name FROM powers p JOIN power_conditions c ON p.id=c.power_id WHERE c.condition='stunned'\"")


if __name__ == '__main__':
    build_database()
