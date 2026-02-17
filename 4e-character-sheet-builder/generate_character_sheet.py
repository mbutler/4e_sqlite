#!/usr/bin/env python3
"""
Generate a detailed character sheet from a D&D 4e Character Builder export.

Reads a character.txt file, looks up all referenced entries in the compendium
database, and produces a beautifully formatted Markdown file with full details.

Usage:
    python3 generate_character_sheet.py character.txt
    python3 generate_character_sheet.py character.txt -o output.md
"""

import sqlite3
import re
import sys
import argparse
from pathlib import Path
from html.parser import HTMLParser
from textwrap import wrap, indent

# =============================================================================
# Configuration
# =============================================================================

# Use compendium DB from parent project folder (shared with 4e_xml_parser)
DB_PATH = str(Path(__file__).resolve().parent.parent / "4e_compendium.db")
LINE_WIDTH = 80
INDENT = "  "

# =============================================================================
# HTML to Markdown Conversion
# =============================================================================

class HTMLToMarkdownConverter(HTMLParser):
    """
    Convert HTML to nicely formatted Markdown.
    Preserves structure, handles headers, lists, bold text, etc.
    """
    
    def __init__(self):
        super().__init__()
        self.output = []
        self.current_line = ""
        self.in_bold = False
        self.in_italic = False
        self.in_header = False
        self.header_level = 0
        self.list_depth = 0
        self.in_blockquote = False
        self.skip_content = False
        self.tag_stack = []
        self.is_power_header = False
        
    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)
        css_class = attrs_dict.get('class', '')
        
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self._flush_line()
            self.output.append("")  # Blank line before header
            self.in_header = True
            self.header_level = int(tag[1])
            # Check if this is a power/item header (has special class)
            self.is_power_header = any(x in css_class for x in ['power', 'player', 'monster', 'magicitem', 'mihead'])
            # Add markdown header prefix
            self.current_line = "### "
            
        elif tag == 'b' or tag == 'strong':
            self.current_line += "**"
            self.in_bold = True
            
        elif tag == 'i' or tag == 'em':
            self.current_line += "*"
            self.in_italic = True
            
        elif tag == 'br':
            self._flush_line()
            
        elif tag == 'p':
            self._flush_line()
            if 'flavor' in css_class:
                self.current_line = "> *"
                self.in_italic = True
            elif 'publishedIn' in css_class:
                self.output.append("")
                self.current_line = "*"
                self.in_italic = True
            elif 'powerstat' in css_class:
                self.current_line = "> "
                
        elif tag in ('ul', 'ol'):
            self._flush_line()
            self.list_depth += 1
            
        elif tag == 'li':
            self._flush_line()
            self.current_line = "  " * (self.list_depth - 1) + "- "
            
        elif tag == 'blockquote':
            self._flush_line()
            self.in_blockquote = True
            
        elif tag == 'span':
            if 'level' in css_class:
                # This is the level/subtype span in a header
                self.current_line += " — *"
                self.in_italic = True
                
    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            
        if tag in ('h1', 'h2', 'h3', 'h4'):
            if self.in_italic:
                self.current_line += "*"
                self.in_italic = False
            self._flush_line()
            self.in_header = False
            self.header_level = 0
            self.is_power_header = False
            
        elif tag == 'b' or tag == 'strong':
            self.current_line += "**"
            self.in_bold = False
            
        elif tag == 'i' or tag == 'em':
            self.current_line += "*"
            self.in_italic = False
            
        elif tag == 'p':
            if self.in_italic:
                self.current_line += "*"
                self.in_italic = False
            self._flush_line()
            
        elif tag in ('ul', 'ol'):
            self.list_depth = max(0, self.list_depth - 1)
            self._flush_line()
            
        elif tag == 'blockquote':
            self._flush_line()
            self.in_blockquote = False
            
        elif tag == 'span':
            if self.in_italic and self.in_header:
                self.current_line += "*"
                self.in_italic = False
            
    def handle_data(self, data):
        if self.skip_content:
            return
            
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', data)
        self.current_line += text
            
    def handle_entityref(self, name):
        entities = {
            'nbsp': ' ',
            'amp': '&',
            'lt': '<',
            'gt': '>',
            'quot': '"',
            'apos': "'",
            'mdash': '—',
            'ndash': '–',
            'bull': '•',
            'middot': '·',
        }
        self.current_line += entities.get(name, f'&{name};')
        
    def handle_charref(self, name):
        try:
            if name.startswith('x'):
                char = chr(int(name[1:], 16))
            else:
                char = chr(int(name))
            self.current_line += char
        except:
            self.current_line += f'&#{name};'
            
    def _flush_line(self):
        line = self.current_line.strip()
        if line:
            if self.in_blockquote and not line.startswith('>'):
                line = "> " + line
            self.output.append(line)
        self.current_line = ""
        
    def get_markdown(self):
        self._flush_line()
        # Clean up multiple blank lines and fix common issues
        result = []
        prev_blank = False
        for line in self.output:
            # Fix stray markers
            line = re.sub(r'\*\*\*+', '**', line)  # Too many asterisks
            line = re.sub(r'\*\s*$', '', line)     # Trailing single asterisk
            line = re.sub(r'^\*\s*$', '', line)    # Line with just asterisk
            
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            result.append(line)
            prev_blank = is_blank
        return '\n'.join(result)


def html_to_markdown(html):
    """Convert HTML to formatted Markdown."""
    if not html:
        return ""
    
    # Pre-process: convert common HTML entities and special chars
    html = html.replace('\u2726', '✦')  # Keep the star
    html = html.replace('\u2014', '—')  # Em dash
    html = html.replace('\u2019', "'")  # '
    html = html.replace('\u201c', '"')  # "
    html = html.replace('\u201d', '"')  # "
    
    converter = HTMLToMarkdownConverter()
    try:
        converter.feed(html)
        md = converter.get_markdown()
        
        # Post-process cleanup
        lines = md.split('\n')
        cleaned = []
        for line in lines:
            # Fix unbalanced italics - ensure * pairs are matched
            asterisk_count = line.count('*') - line.count('**') * 2
            if asterisk_count % 2 == 1:
                # Odd number of single asterisks, try to fix
                if line.rstrip().endswith('*'):
                    pass  # Already ends with asterisk
                elif '*' in line and not line.rstrip().endswith('*'):
                    line = line.rstrip() + '*'
            
            # Clean up "> **text" at start becoming "> *text*" for flavor
            if line.startswith('> **') and not '**:' in line:
                # This might be flavor text that should be italic
                pass
                
            cleaned.append(line)
        
        return '\n'.join(cleaned)
    except Exception as e:
        # Fallback: strip tags
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


# =============================================================================
# Character File Parsing
# =============================================================================

def parse_character_file(filepath):
    """
    Parse a character builder export file.
    Returns a dict with all extracted information.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    char = {
        'raw_content': content,
        'name': '',
        'level': 0,
        'race': '',
        'class': '',
        'paragon_path': '',
        'epic_destiny': '',
        'build': '',
        'background': '',
        'abilities': {},
        'defenses': {},
        'hp': {},
        'skills_trained': [],
        'skills_untrained': [],
        'feats': [],
        'powers': [],
        'items': [],
        'rituals': [],
    }
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Skip header/footer lines
        if line.startswith('======'):
            continue
            
        # Header line: "Name, level N"
        if re.match(r'.+, level \d+', line):
            match = re.match(r'(.+), level (\d+)', line)
            if match:
                char['name'] = match.group(1)
                char['level'] = int(match.group(2))
            continue
            
        # Race, Class, Paragon, Epic line
        if not current_section and char['name'] and not char['race']:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                char['race'] = parts[0]
                char['class'] = parts[1]
                if len(parts) >= 3:
                    char['paragon_path'] = parts[2]
                if len(parts) >= 4:
                    char['epic_destiny'] = parts[3]
            continue
            
        # Build line
        if line.startswith('Build:'):
            char['build'] = line.replace('Build:', '').strip()
            continue
            
        # Background line
        if line.startswith('Background:'):
            bg = line.replace('Background:', '').strip()
            # Extract background name (before any parenthetical)
            match = re.match(r'([^(]+)', bg)
            if match:
                char['background'] = match.group(1).strip()
            continue
            
        # Section headers
        if line in ('FINAL ABILITY SCORES', 'STARTING ABILITY SCORES'):
            current_section = 'abilities'
            continue
        elif line == 'TRAINED SKILLS':
            current_section = 'skills_trained'
            continue
        elif line == 'UNTRAINED SKILLS':
            current_section = 'skills_untrained'
            continue
        elif line == 'FEATS':
            current_section = 'feats'
            continue
        elif line == 'POWERS':
            current_section = 'powers'
            continue
        elif line == 'ITEMS':
            current_section = 'items'
            continue
        elif line == 'RITUALS':
            current_section = 'rituals'
            continue
            
        # AC/Fort/Ref/Will line
        if line.startswith('AC:'):
            match = re.search(r'AC:\s*(\d+)\s+Fort:\s*(\d+)\s+Reflex:\s*(\d+)\s+Will:\s*(\d+)', line)
            if match:
                char['defenses'] = {
                    'AC': int(match.group(1)),
                    'Fort': int(match.group(2)),
                    'Reflex': int(match.group(3)),
                    'Will': int(match.group(4)),
                }
            continue
            
        # HP line
        if line.startswith('HP:'):
            match = re.search(r'HP:\s*(\d+)\s+Surges:\s*(\d+)\s+Surge Value:\s*(\d+)', line)
            if match:
                char['hp'] = {
                    'HP': int(match.group(1)),
                    'Surges': int(match.group(2)),
                    'Surge Value': int(match.group(3)),
                }
            continue
            
        # Skip empty lines
        if not line:
            continue
            
        # Process section content
        if current_section == 'feats':
            # Extract feat name from lines like "Level 1: Feat Name" or "Cleric: Feat Name"
            match = re.match(r'(?:Level \d+|Cleric|Feat User Choice):\s*(.+)', line)
            if match:
                char['feats'].append(match.group(1).strip())
            elif ':' not in line:
                char['feats'].append(line.strip())
                
        elif current_section == 'powers':
            # Extract power name from various formats
            # "Cleric at-will 1: Power Name (retrained to X at Level Y)"
            # "Channel Divinity: Power Name"
            match = re.match(r'[^:]+:\s*(.+?)(?:\s*\((?:retrained|replaces)[^)]*\))*$', line)
            if match:
                power_name = match.group(1).strip()
                # Remove any trailing (replaces X) or (retrained...)
                power_name = re.sub(r'\s*\((?:retrained|replaces)[^)]*\)\s*', '', power_name)
                char['powers'].append(power_name.strip())
                
        elif current_section == 'items':
            # Items are comma-separated
            items = [i.strip() for i in line.split(',')]
            char['items'].extend(items)
            
        elif current_section == 'rituals':
            # Rituals are comma-separated
            rituals = [r.strip() for r in line.split(',')]
            char['rituals'].extend(rituals)
            
        elif current_section == 'skills_trained':
            # Skills are comma-separated with bonuses
            skills = [s.strip() for s in line.split(',')]
            char['skills_trained'].extend(skills)
            
        elif current_section == 'skills_untrained':
            skills = [s.strip() for s in line.split(',')]
            char['skills_untrained'].extend(skills)
    
    return char


# =============================================================================
# Database Lookups
# =============================================================================

def connect_db(db_path=DB_PATH):
    """Connect to the compendium database."""
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Run build_compendium_db.py first to create the database.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def lookup_entry(conn, name, tables=None):
    """
    Look up an entry by name across multiple tables.
    Returns (table_name, row) or (None, None) if not found.
    """
    if tables is None:
        tables = [
            'powers', 'feats', 'items', 'rituals', 'backgrounds',
            'classes', 'races', 'paragon_paths', 'epic_destinies',
            'themes', 'armor', 'weapons', 'implements', 'glossary'
        ]
    
    # Clean up the name for searching
    search_name = name.strip()
    
    # Remove common suffixes like "+5", "(paragon tier)", etc.
    clean_name = re.sub(r'\s*\+\d+\s*$', '', search_name)
    clean_name = re.sub(r'\s*\([^)]*tier\)\s*$', '', clean_name, flags=re.IGNORECASE)
    clean_name = clean_name.strip()
    
    for table in tables:
        # Try exact match first
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE name = ? COLLATE NOCASE",
            (clean_name,)
        )
        row = cursor.fetchone()
        if row:
            return table, row
            
        # Try LIKE match
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE name LIKE ? COLLATE NOCASE",
            (f"{clean_name}%",)
        )
        row = cursor.fetchone()
        if row:
            return table, row
            
        # Try with original name
        if clean_name != search_name:
            cursor = conn.execute(
                f"SELECT * FROM {table} WHERE name LIKE ? COLLATE NOCASE",
                (f"{search_name}%",)
            )
            row = cursor.fetchone()
            if row:
                return table, row
    
    return None, None


def lookup_by_name_index(conn, name):
    """Look up using the global name index."""
    clean_name = name.lower().strip()
    # Remove common suffixes
    clean_name = re.sub(r'\s*\+\d+\s*$', '', clean_name)
    clean_name = re.sub(r'\s*\([^)]*tier\)\s*$', '', clean_name)
    clean_name = clean_name.strip()
    
    cursor = conn.execute(
        "SELECT entry_id FROM name_index WHERE name_lower = ?",
        (clean_name,)
    )
    row = cursor.fetchone()
    if row:
        entry_id = row['entry_id']
        # Determine table from ID prefix
        match = re.match(r'([a-z]+)', entry_id)
        if match:
            prefix = match.group(1)
            table_map = {
                'power': 'powers',
                'feat': 'feats',
                'item': 'items',
                'ritual': 'rituals',
                'background': 'backgrounds',
                'class': 'classes',
                'race': 'races',
                'paragonpath': 'paragon_paths',
                'epicdestiny': 'epic_destinies',
                'theme': 'themes',
                'armor': 'armor',
                'weapon': 'weapons',
                'implement': 'implements',
                'glossary': 'glossary',
                'monster': 'monsters',
            }
            table = table_map.get(prefix)
            if table:
                cursor = conn.execute(
                    f"SELECT * FROM {table} WHERE id = ?",
                    (entry_id,)
                )
                row = cursor.fetchone()
                if row:
                    return table, row
    
    return None, None


# =============================================================================
# Output Formatting (Markdown)
# =============================================================================

def format_section_header(title):
    """Format a major section header in Markdown."""
    return f"\n---\n\n## {title}\n"


def format_entry(name, table, row, found=True):
    """Format a single entry for Markdown output."""
    output = []
    
    if not found:
        output.append(f"\n### ⚠️ {name}")
        output.append("\n*Not found in database*\n")
        return '\n'.join(output)
    
    # Get the HTML body and convert to markdown
    html_body = row['html_body'] if 'html_body' in row.keys() else ''
    
    if html_body:
        markdown = html_to_markdown(html_body)
        output.append(f"\n{markdown}")
    else:
        # Fallback: just show the name and any available fields
        output.append(f"\n### {row['name']}")
        output.append("")
        for key in row.keys():
            if key not in ('id', 'html_body', 'search_text') and row[key]:
                output.append(f"- **{key}:** {row[key]}")
    
    return '\n'.join(output)


def generate_character_sheet(char, conn):
    """Generate the full character sheet in Markdown."""
    output = []
    
    # Title
    output.append(f"# {char['name']}")
    output.append("")
    subtitle_parts = [f"**Level {char['level']}**", f"**{char['race']}**", f"**{char['class']}**"]
    output.append(" | ".join(subtitle_parts))
    
    if char['paragon_path'] or char['epic_destiny']:
        path_parts = []
        if char['paragon_path']:
            path_parts.append(char['paragon_path'])
        if char['epic_destiny']:
            path_parts.append(char['epic_destiny'])
        output.append(f"\n*{' • '.join(path_parts)}*")
    
    # Quick Stats in a nice table
    output.append(format_section_header("⚔️ Combat Statistics"))
    
    if char['defenses']:
        output.append("| AC | Fort | Reflex | Will |")
        output.append("|:--:|:----:|:------:|:----:|")
        output.append(f"| {char['defenses'].get('AC', '-')} | {char['defenses'].get('Fort', '-')} | {char['defenses'].get('Reflex', '-')} | {char['defenses'].get('Will', '-')} |")
        output.append("")
    
    if char['hp']:
        output.append(f"**HP:** {char['hp'].get('HP', '-')} · **Surges:** {char['hp'].get('Surges', '-')}/day · **Surge Value:** {char['hp'].get('Surge Value', '-')}")
        output.append("")
    
    if char['skills_trained']:
        output.append(f"**Trained Skills:** {', '.join(char['skills_trained'])}")
    
    # Race
    if char['race']:
        output.append(format_section_header("🧬 Race"))
        table, row = lookup_entry(conn, char['race'], ['races'])
        if row:
            output.append(format_entry(char['race'], table, row))
        else:
            output.append(f"*{char['race']} — Not found in database*")
    
    # Class
    if char['class']:
        output.append(format_section_header("⚜️ Class"))
        table, row = lookup_entry(conn, char['class'], ['classes'])
        if not row:
            # Try variations like "Cleric (Templar)" or "Cleric (Warpriest)"
            table, row = lookup_entry(conn, f"{char['class']} (Templar)", ['classes'])
        if not row:
            table, row = lookup_entry(conn, f"{char['class']} (Warpriest)", ['classes'])
        if row:
            output.append(format_entry(char['class'], table, row))
        else:
            output.append(f"*{char['class']} — Not found in database*")
    
    # Background
    if char['background']:
        output.append(format_section_header("📜 Background"))
        table, row = lookup_entry(conn, char['background'], ['backgrounds'])
        if not row:
            table, row = lookup_by_name_index(conn, char['background'])
        if row:
            output.append(format_entry(char['background'], table, row))
        else:
            output.append(f"*{char['background']} — Not found in database*")
    
    # Paragon Path
    if char['paragon_path']:
        output.append(format_section_header("🛡️ Paragon Path"))
        table, row = lookup_entry(conn, char['paragon_path'], ['paragon_paths'])
        if row:
            output.append(format_entry(char['paragon_path'], table, row))
        else:
            output.append(f"*{char['paragon_path']} — Not found in database*")
    
    # Epic Destiny
    if char['epic_destiny']:
        output.append(format_section_header("👑 Epic Destiny"))
        table, row = lookup_entry(conn, char['epic_destiny'], ['epic_destinies'])
        if row:
            output.append(format_entry(char['epic_destiny'], table, row))
        else:
            output.append(f"*{char['epic_destiny']} — Not found in database*")
    
    # Feats
    if char['feats']:
        output.append(format_section_header("🎯 Feats"))
        for feat_name in char['feats']:
            table, row = lookup_entry(conn, feat_name, ['feats'])
            if not row:
                table, row = lookup_by_name_index(conn, feat_name)
            output.append(format_entry(feat_name, table, row, found=row is not None))
    
    # Powers
    if char['powers']:
        output.append(format_section_header("✨ Powers"))
        for power_name in char['powers']:
            table, row = lookup_entry(conn, power_name, ['powers'])
            if not row:
                table, row = lookup_by_name_index(conn, power_name)
            output.append(format_entry(power_name, table, row, found=row is not None))
    
    # Items
    if char['items']:
        output.append(format_section_header("🎒 Items"))
        for item_name in char['items']:
            if not item_name:
                continue
            table, row = lookup_entry(conn, item_name, ['items', 'armor', 'weapons', 'implements'])
            if not row:
                table, row = lookup_by_name_index(conn, item_name)
            output.append(format_entry(item_name, table, row, found=row is not None))
    
    # Rituals
    if char['rituals']:
        output.append(format_section_header("🔮 Rituals"))
        for ritual_name in char['rituals']:
            if not ritual_name:
                continue
            table, row = lookup_entry(conn, ritual_name, ['rituals'])
            if not row:
                table, row = lookup_by_name_index(conn, ritual_name)
            output.append(format_entry(ritual_name, table, row, found=row is not None))
    
    # Footer
    output.append("\n---\n")
    output.append("*Generated from 4e Compendium Database*")
    
    return '\n'.join(output)


# =============================================================================
# Cheat Sheet Generation - Extract Triggers, Conditions, Reminders
# =============================================================================

def extract_triggers_and_conditions(html_body, search_text):
    """
    Extract trigger phrases, conditions, and special mechanics from power/feat text.
    Returns a dict of categorized findings with improved accuracy.
    """
    text = search_text if search_text else ''
    if not text and html_body:
        text = re.sub(r'<[^>]+>', ' ', html_body)
    text_lower = text.lower()
    
    findings = {
        'trigger': None,
        'action_type': None,  # 'immediate reaction', 'immediate interrupt', 'free action', etc.
        'on_hit_conditions': [],  # Conditions inflicted on hit
        'on_hit_effects': [],     # Other effects on hit (push, pull, etc.)
        'on_miss': None,          # Miss effect (if interesting)
        'on_crit': None,          # Critical hit effect
        'when_bloodied': None,    # Bloodied triggers
        'healing_synergy': None,  # Healing word / surge synergies
        'sustain': None,
        'save_bonus': None,       # Save bonuses you grant
        'start_of_turn': None,    # Start of turn effects
        'adjacency': None,
        'is_defensive': False,    # Flag for "helps YOU" vs "hurts ENEMY"
    }
    
    # Determine action type
    if 'immediate reaction' in text_lower:
        findings['action_type'] = 'Immediate Reaction'
    elif 'immediate interrupt' in text_lower:
        findings['action_type'] = 'Immediate Interrupt'
    elif re.search(r'free action.*trigger', text_lower) or re.search(r'trigger.*free action', text_lower):
        findings['action_type'] = 'Free Action (Triggered)'
    elif 'trigger:' in text_lower or 'trigger :' in text_lower:
        # Has a trigger but check if free action
        if 'free action' in text_lower:
            findings['action_type'] = 'Free Action (Triggered)'
    
    # Extract trigger text (clean it up)
    trigger_match = re.search(r'trigger\s*:\s*([^.]+(?:attack|hit|miss|damage|drops|bloodied|adjacent|enters|leaves)[^.]*)', text_lower)
    if trigger_match:
        trigger_text = trigger_match.group(1).strip()
        # Clean up - remove "effect:" if it got captured
        trigger_text = re.sub(r'\s*effect\s*:.*', '', trigger_text)
        findings['trigger'] = trigger_text
    
    # Parse Hit: section for conditions on TARGET
    # Need to capture multiple sentences until we hit "Miss:" or "Effect:" or "Special:"
    hit_match = re.search(r'hit\s*:\s*(.*?)(?=\s*(?:miss\s*:|effect\s*:|special\s*:|level \d|$))', text_lower, re.DOTALL)
    if hit_match:
        hit_text = hit_match.group(1)
        
        # Extract conditions inflicted on target
        conditions = ['dazed', 'stunned', 'prone', 'immobilized', 'slowed', 'weakened', 
                      'blinded', 'dominated', 'marked', 'restrained', 'grabbed']
        for cond in conditions:
            # Look for "target is <cond>" or "is <cond>" or "and <cond>" patterns in hit text
            # Handle compound: "is weakened and dazed" - each condition may follow "is", "are", or "and"
            if re.search(rf'(?:target |targets |the target )?(?:is |are |and ){cond}', hit_text):
                # Check for save ends
                if 'save ends' in hit_text:
                    findings['on_hit_conditions'].append(f"{cond} (save ends)")
                elif 'end of your next turn' in hit_text:
                    findings['on_hit_conditions'].append(f"{cond} (EOYNT)")
                else:
                    findings['on_hit_conditions'].append(cond)
        
        # Check for push/pull/slide
        movement_match = re.search(r'(push|pull|slide)[^.]*(\d+)[^.]*squares?', hit_text)
        if movement_match:
            findings['on_hit_effects'].append(f"{movement_match.group(1)} {movement_match.group(2)}")
    
    # Also check Effect: section for conditions (for powers like Greater Augment of War)
    effect_match = re.search(r'effect\s*:\s*([^.]+(?:\.[^.]*){0,3})', text_lower)
    if effect_match:
        effect_text = effect_match.group(1)
        conditions = ['dazed', 'stunned', 'prone', 'immobilized', 'slowed', 'weakened', 
                      'blinded', 'dominated', 'marked', 'restrained', 'grabbed']
        for cond in conditions:
            if re.search(rf'(?:enemy |enemies |target |targets )?(?:is |are ){cond}', effect_text):
                if cond not in [c.split(' (')[0] for c in findings['on_hit_conditions']]:
                    findings['on_hit_conditions'].append(f"{cond} (via effect)")
    
    # Parse Miss: section (only if NOT just "half damage")
    miss_match = re.search(r'miss\s*:\s*([^.]+\.)', text_lower)
    if miss_match:
        miss_text = miss_match.group(1).strip()
        if miss_text != 'half damage.' and 'half damage' not in miss_text[:20]:
            # Check for conditions on miss
            for cond in ['slowed', 'dazed', 'weakened']:
                if cond in miss_text:
                    findings['on_miss'] = f"{cond} on miss"
                    break
    
    # Critical hit effects - clean extraction
    crit_match = re.search(r'critical\s*:\s*\+?([^.]+?)(?:\s+(?:requirement|property|power)|\.|$)', text_lower)
    if crit_match:
        crit_text = crit_match.group(1).strip()
        findings['on_crit'] = crit_text
    
    # Check for "when you crit" in feat text
    crit_feat_match = re.search(r'when you (?:score a )?critical hit,?\s*([^.]+)', text_lower)
    if crit_feat_match:
        findings['on_crit'] = crit_feat_match.group(1).strip()
    
    # Detect defensive effects (helps YOU vs hurts ENEMY)
    # If text mentions "if you are dazed" or "when you are hit", it's defensive
    if re.search(r'if you are (dazed|stunned|bloodied|hit)', text_lower):
        findings['is_defensive'] = True
    if re.search(r'when you are (hit|bloodied|damaged)', text_lower):
        findings['is_defensive'] = True
    
    # Healing synergies - look for the Benefit text in feats
    # Pattern: "when you use...healing word...you/target regains/gains..."
    healing_patterns = [
        r'when you use[^.]*healing word[^.]*,\s*([^.]+regain[^.]+)',
        r'when you use[^.]*healing word[^.]*,\s*([^.]+additional[^.]+)',
        r'healing word[^.]*the target[^.]*regains?\s+([^.]+additional[^.]+)',
        r'benefit\s*:\s*when you use[^.]*healing word[^.]*,\s*([^.]+)',
    ]
    for pattern in healing_patterns:
        match = re.search(pattern, text_lower)
        if match:
            synergy = match.group(1).strip()
            if len(synergy) > 10:  # Sanity check
                findings['healing_synergy'] = synergy
                break
    
    # If HTML-based, try to extract from Benefit section
    if not findings['healing_synergy'] and html_body:
        benefit_match = re.search(r'<b>Benefit</b>:\s*([^<]+healing word[^<]+)', html_body, re.IGNORECASE)
        if benefit_match:
            benefit_text = benefit_match.group(1).strip()
            # Remove the "When you use your healing word, " prefix
            benefit_text = re.sub(r'^when you use (?:your )?healing word,?\s*', '', benefit_text, flags=re.IGNORECASE)
            if len(benefit_text) > 10:
                findings['healing_synergy'] = benefit_text
    
    # Healing surge synergies  
    surge_match = re.search(r'when[^.]*(?:spend|use)[^.]*healing surge[^.]*,\s*([^.]{10,})', text_lower)
    if surge_match and not findings['healing_synergy']:
        findings['healing_synergy'] = surge_match.group(1).strip()
    
    # Sustain
    sustain_match = re.search(r'sustain\s+(minor|move|standard)', text_lower)
    if sustain_match:
        findings['sustain'] = sustain_match.group(1).capitalize()
    
    # Save bonuses (for allies or self)
    save_match = re.search(r'(\+\d+|bonus)[^.]*(?:to )?saving throws?', text_lower)
    if save_match:
        findings['save_bonus'] = True
    
    # Start of turn effects
    if 'start of your turn' in text_lower:
        start_match = re.search(r'(?:at the )?start of your turn,?\s*([^.]+)', text_lower)
        if start_match:
            findings['start_of_turn'] = start_match.group(1).strip()
    
    # Adjacency effects
    if 'adjacent' in text_lower:
        # Look for auras or adjacency-based effects
        adj_match = re.search(r'(?:while|when|enemies?)[^.]*adjacent[^.]*(?:take|gain|suffer|bonus)[^.]*', text_lower)
        if adj_match:
            findings['adjacency'] = adj_match.group(0).strip()
    
    return findings


def generate_cheat_sheet(char, conn):
    """Generate a conditional combat cheat sheet."""
    output = []
    
    # Collect all findings from powers, feats, items
    all_entries = []
    
    # Process feats
    for feat_name in char['feats']:
        table, row = lookup_entry(conn, feat_name, ['feats'])
        if not row:
            table, row = lookup_by_name_index(conn, feat_name)
        if row:
            html = row['html_body'] if 'html_body' in row.keys() else ''
            search = row['search_text'] if 'search_text' in row.keys() else ''
            findings = extract_triggers_and_conditions(html, search)
            findings['name'] = row['name']
            findings['entry_type'] = 'Feat'
            findings['source'] = row
            all_entries.append(findings)
    
    # Process powers
    for power_name in char['powers']:
        table, row = lookup_entry(conn, power_name, ['powers'])
        if not row:
            table, row = lookup_by_name_index(conn, power_name)
        if row:
            html = row['html_body'] if 'html_body' in row.keys() else ''
            search = row['search_text'] if 'search_text' in row.keys() else ''
            findings = extract_triggers_and_conditions(html, search)
            findings['name'] = row['name']
            findings['entry_type'] = 'Power'
            findings['source'] = row
            all_entries.append(findings)
    
    # Process items
    for item_name in char['items']:
        if not item_name:
            continue
        table, row = lookup_entry(conn, item_name, ['items', 'armor', 'weapons', 'implements'])
        if not row:
            table, row = lookup_by_name_index(conn, item_name)
        if row:
            html = row['html_body'] if 'html_body' in row.keys() else ''
            search = row['search_text'] if 'search_text' in row.keys() else ''
            findings = extract_triggers_and_conditions(html, search)
            findings['name'] = row['name']
            findings['entry_type'] = 'Item'
            findings['source'] = row
            all_entries.append(findings)
    
    # Title
    output.append(f"# {char['name']} — Combat Cheat Sheet")
    output.append("")
    output.append(f"*Level {char['level']} {char['race']} {char['class']}*")
    output.append("")
    output.append("> **State-driven reference.** Only triggers, reactions, and conditional effects.")
    output.append("")
    
    # Quick Stats Reference
    output.append("---")
    output.append("")
    output.append("## 📊 Quick Stats")
    output.append("")
    if char['defenses']:
        output.append(f"| AC | Fort | Ref | Will |")
        output.append(f"|:--:|:----:|:---:|:----:|")
        output.append(f"| {char['defenses'].get('AC', '-')} | {char['defenses'].get('Fort', '-')} | {char['defenses'].get('Reflex', '-')} | {char['defenses'].get('Will', '-')} |")
        output.append("")
    if char['hp']:
        bloodied = char['hp'].get('HP', 0) // 2
        output.append(f"**HP** {char['hp'].get('HP', '-')} · **Bloodied** {bloodied} · **Surge** {char['hp'].get('Surge Value', '-')} × {char['hp'].get('Surges', '-')}")
    output.append("")
    
    # START OF TURN
    output.append("---")
    output.append("")
    output.append("## ⏰ Start of Your Turn")
    output.append("")
    output.append("- [ ] **Ongoing damage** — take it now")
    output.append("- [ ] **Regeneration** — if bloodied, regain HP")
    
    # Sustains
    for entry in all_entries:
        if entry.get('sustain'):
            output.append(f"- [ ] **{entry['name']}** — Sustain {entry['sustain']} to maintain")
    
    # Start of turn effects (skip if we'll handle it specially below)
    handled_start_of_turn = set()
    for entry in all_entries:
        if entry.get('start_of_turn'):
            # Skip if this is a dazed/stunned save feat (handled specially)
            if entry['entry_type'] == 'Feat':
                search = entry['source']['search_text'] if entry['source'] and 'search_text' in entry['source'].keys() else ''
                html = entry['source']['html_body'] if entry['source'] and 'html_body' in entry['source'].keys() else ''
                text = (search or html or '').lower()
                if 'dazed or stunned' in text and 'saving throw' in text:
                    handled_start_of_turn.add(entry['name'])
                    continue
            output.append(f"- [ ] **{entry['name']}** — {entry['start_of_turn']}")
    
    # Check for Superior Will or similar (defensive dazed/stunned saves)
    for entry in all_entries:
        if entry['entry_type'] == 'Feat' and entry.get('is_defensive'):
            search = entry['source']['search_text'] if entry['source'] and 'search_text' in entry['source'].keys() else ''
            html = entry['source']['html_body'] if entry['source'] and 'html_body' in entry['source'].keys() else ''
            text = (search or html or '').lower()
            if 'dazed or stunned' in text and 'saving throw' in text:
                output.append(f"- [ ] **{entry['name']}** — save vs dazed/stunned at start of turn")
    output.append("")
    
    # IMMEDIATE REACTIONS (true immediates only)
    immediate_reactions = [e for e in all_entries 
                          if e.get('action_type') in ['Immediate Reaction', 'Immediate Interrupt']
                          and e.get('trigger')]
    if immediate_reactions:
        output.append("---")
        output.append("")
        output.append("## ⚡ Immediate Reactions/Interrupts")
        output.append("")
        output.append("*Use on others' turns. One immediate per round.*")
        output.append("")
        for entry in immediate_reactions:
            action = entry['action_type']
            output.append(f"### {entry['name']} *({action})*")
            output.append(f"> **Trigger:** {entry['trigger'].capitalize()}")
            output.append("")
    
    # FREE ACTIONS WITH TRIGGERS (separate from immediates)
    free_triggered = [e for e in all_entries 
                      if e.get('action_type') == 'Free Action (Triggered)'
                      and e.get('trigger')]
    if free_triggered:
        output.append("---")
        output.append("")
        output.append("## 🆓 Free Actions (Triggered)")
        output.append("")
        output.append("*No limit per round, but usually 1/encounter or 1/day.*")
        output.append("")
        for entry in free_triggered:
            output.append(f"### {entry['name']}")
            output.append(f"> **Trigger:** {entry['trigger'].capitalize()}")
            output.append("")
    
    # WHEN YOU HIT - Only offensive effects, exclude defensive feats
    hit_entries = [e for e in all_entries 
                   if (e.get('on_hit_conditions') or e.get('on_hit_effects'))
                   and not e.get('is_defensive')]
    if hit_entries:
        output.append("---")
        output.append("")
        output.append("## 🎯 When You Hit")
        output.append("")
        for entry in hit_entries:
            effects = []
            if entry.get('on_hit_conditions'):
                effects.extend(entry['on_hit_conditions'])
            if entry.get('on_hit_effects'):
                effects.extend(entry['on_hit_effects'])
            if effects:
                output.append(f"- **{entry['name']}** → {', '.join(effects)}")
        output.append("")
    
    # ON MISS (interesting miss effects)
    miss_entries = [e for e in all_entries if e.get('on_miss')]
    if miss_entries:
        output.append("---")
        output.append("")
        output.append("## ❌ On Miss")
        output.append("")
        for entry in miss_entries:
            output.append(f"- **{entry['name']}:** {entry['on_miss']}")
        output.append("")
    
    # ON CRIT
    crit_entries = [e for e in all_entries if e.get('on_crit')]
    if crit_entries:
        output.append("---")
        output.append("")
        output.append("## 💥 On Critical Hit")
        output.append("")
        for entry in crit_entries:
            crit_text = entry['on_crit']
            # Clean up the crit text
            if entry['entry_type'] == 'Feat' and 'healing word' in crit_text:
                output.append(f"- **{entry['name']}:** gain extra healing word use this encounter")
            elif '+' in crit_text and 'damage' in crit_text:
                output.append(f"- **{entry['name']}:** {crit_text}")
            else:
                output.append(f"- **{entry['name']}:** {crit_text}")
        output.append("")
    
    # HEALING SYNERGIES
    healing_entries = [e for e in all_entries if e.get('healing_synergy')]
    if healing_entries:
        output.append("---")
        output.append("")
        output.append("## 💚 Healing Word Synergies")
        output.append("")
        for entry in healing_entries:
            output.append(f"- **{entry['name']}:** {entry['healing_synergy']}")
        output.append("")
    
    # CONDITIONS YOU CAN INFLICT (summary)
    all_conditions = {}
    for entry in all_entries:
        if entry.get('is_defensive'):
            continue  # Skip defensive entries
        for cond in entry.get('on_hit_conditions', []):
            # Strip duration info for grouping
            base_cond = cond.split(' (')[0]
            if base_cond not in all_conditions:
                all_conditions[base_cond] = []
            all_conditions[base_cond].append(entry['name'])
    
    if all_conditions:
        output.append("---")
        output.append("")
        output.append("## 🎭 Conditions You Can Inflict")
        output.append("")
        for cond in sorted(all_conditions):
            sources = all_conditions[cond][:3]
            output.append(f"- **{cond.capitalize()}:** {', '.join(sources)}")
        output.append("")
    
    # SUSTAINS (reminder section)
    sustain_entries = [e for e in all_entries if e.get('sustain')]
    if sustain_entries:
        output.append("---")
        output.append("")
        output.append("## 🔄 Active Sustains")
        output.append("")
        output.append("*Cannot sustain on the turn you create the effect.*")
        output.append("")
        for entry in sustain_entries:
            output.append(f"- **{entry['name']}:** Sustain {entry['sustain']}")
        output.append("")
    
    # END OF TURN
    output.append("---")
    output.append("")
    output.append("## ⏰ End of Your Turn")
    output.append("")
    output.append("- [ ] **Saving throws** — roll for each (save ends) effect")
    output.append("- [ ] **Marks expire** — unless refreshed")
    output.append("- [ ] **\"Until end of next turn\"** — effects on enemies expire")
    output.append("")
    
    # ADJACENCY
    adj_entries = [e for e in all_entries if e.get('adjacency')]
    if adj_entries:
        output.append("---")
        output.append("")
        output.append("## 📍 Adjacency & Positioning")
        output.append("")
        for entry in adj_entries:
            output.append(f"- **{entry['name']}:** {entry['adjacency']}")
        output.append("")
    
    # Footer
    output.append("---")
    output.append("")
    output.append("*Generated from 4e Compendium Database*")
    
    return '\n'.join(output)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate character sheet and combat cheat sheet from a D&D 4e Character Builder export.'
    )
    parser.add_argument('character_file', help='Path to the character.txt file')
    parser.add_argument('-o', '--output', help='Output file for character sheet (default: <name>_sheet.md)')
    parser.add_argument('--db', default=DB_PATH, help=f'Database path (default: {DB_PATH})')
    parser.add_argument('--no-cheatsheet', action='store_true', help='Skip generating the cheat sheet')
    
    args = parser.parse_args()
    
    # Parse character file
    print(f"Reading {args.character_file}...")
    char = parse_character_file(args.character_file)
    print(f"  Character: {char['name']}, Level {char['level']} {char['race']} {char['class']}")
    print(f"  Feats: {len(char['feats'])}, Powers: {len(char['powers'])}, Items: {len(char['items'])}")
    
    # Connect to database
    print(f"Connecting to {args.db}...")
    conn = connect_db(args.db)
    
    # Create output filename base
    safe_name = re.sub(r'[^\w\s-]', '', char['name']).strip().replace(' ', '_')
    
    # Generate character sheet
    print("Generating character sheet...")
    sheet = generate_character_sheet(char, conn)
    
    if args.output:
        sheet_file = args.output
    else:
        sheet_file = f"{safe_name}_sheet.md"
    
    with open(sheet_file, 'w', encoding='utf-8') as f:
        f.write(sheet)
    print(f"  ✓ Character sheet: {sheet_file}")
    
    # Generate cheat sheet
    if not args.no_cheatsheet:
        print("Generating combat cheat sheet...")
        cheatsheet = generate_cheat_sheet(char, conn)
        cheatsheet_file = f"{safe_name}_cheatsheet.md"
        
        with open(cheatsheet_file, 'w', encoding='utf-8') as f:
            f.write(cheatsheet)
        print(f"  ✓ Combat cheat sheet: {cheatsheet_file}")
    
    print("Done!")
    conn.close()


if __name__ == '__main__':
    main()
