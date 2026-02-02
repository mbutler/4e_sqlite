<?php
/**
 * D&D 4e Compendium Search Interface
 * Swiss-style design with sophisticated filtering
 */

$DB_PATH = __DIR__ . '/4e_compendium.db';

// Initialize database connection
function getDB() {
    global $DB_PATH;
    static $db = null;
    if ($db === null) {
        if (!file_exists($DB_PATH)) {
            throw new Exception("Database file not found: $DB_PATH");
        }
        $db = new SQLite3($DB_PATH, SQLITE3_OPEN_READONLY);
        $db->busyTimeout(5000);
    }
    return $db;
}

// Get distinct values for a column
function getDistinctValues($table, $column, $where = null) {
    $db = getDB();
    $sql = "SELECT DISTINCT $column FROM $table WHERE $column IS NOT NULL AND $column != ''";
    if ($where) $sql .= " AND $where";
    $sql .= " ORDER BY $column";
    $result = $db->query($sql);
    $values = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $values[] = $row[$column];
    }
    return $values;
}

// Get tag values from junction tables
function getTagValues($table, $column) {
    $db = getDB();
    $sql = "SELECT DISTINCT $column FROM $table ORDER BY $column";
    $result = $db->query($sql);
    $values = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $values[] = $row[$column];
    }
    return $values;
}

// Category configurations
$CATEGORIES = [
    'powers' => [
        'label' => 'Powers',
        'count' => 9416,
        'columns' => ['name', 'class_name', 'level', 'power_usage', 'action', 'keywords_raw', 'source_book'],
        'display_columns' => ['Name', 'Class', 'Lvl', 'Usage', 'Action', 'Keywords', 'Source'],
        'sortable' => ['name', 'class_name', 'level', 'power_usage'],
        'filters' => ['class_name', 'level', 'power_usage', 'defense_targeted', 'range_type', 'area_type', 'damage_types', 'conditions', 'keywords']
    ],
    'monsters' => [
        'label' => 'Monsters',
        'count' => 5326,
        'columns' => ['name', 'level', 'combat_role', 'group_role', 'size', 'creature_type', 'source_book'],
        'display_columns' => ['Name', 'Lvl', 'Role', 'Group', 'Size', 'Type', 'Source'],
        'sortable' => ['name', 'level', 'combat_role', 'group_role'],
        'filters' => ['level', 'combat_role', 'group_role', 'size', 'creature_type']
    ],
    'feats' => [
        'label' => 'Feats',
        'count' => 3283,
        'columns' => ['name', 'tier', 'prerequisite', 'source_book'],
        'display_columns' => ['Name', 'Tier', 'Prerequisite', 'Source'],
        'sortable' => ['name', 'tier'],
        'filters' => ['tier']
    ],
    'items' => [
        'label' => 'Items',
        'count' => 1964,
        'columns' => ['name', 'category', 'type', 'level', 'cost', 'rarity', 'source_book'],
        'display_columns' => ['Name', 'Category', 'Type', 'Lvl', 'Cost', 'Rarity', 'Source'],
        'sortable' => ['name', 'level', 'category', 'rarity'],
        'filters' => ['category', 'type', 'level', 'rarity']
    ],
    'classes' => [
        'label' => 'Classes',
        'count' => 77,
        'columns' => ['name', 'role', 'power_source', 'key_abilities', 'source_book'],
        'display_columns' => ['Name', 'Role', 'Power Source', 'Key Abilities', 'Source'],
        'sortable' => ['name', 'role', 'power_source'],
        'filters' => ['role', 'power_source']
    ],
    'races' => [
        'label' => 'Races',
        'count' => 55,
        'columns' => ['name', 'size', 'origin', 'source_book'],
        'display_columns' => ['Name', 'Size', 'Origin', 'Source'],
        'sortable' => ['name', 'size'],
        'filters' => ['size', 'origin']
    ],
    'paragon_paths' => [
        'label' => 'Paragon Paths',
        'count' => 577,
        'columns' => ['name', 'prerequisite', 'source_book'],
        'display_columns' => ['Name', 'Prerequisite', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'epic_destinies' => [
        'label' => 'Epic Destinies',
        'count' => 115,
        'columns' => ['name', 'prerequisite', 'source_book'],
        'display_columns' => ['Name', 'Prerequisite', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'themes' => [
        'label' => 'Themes',
        'count' => 116,
        'columns' => ['name', 'prerequisite', 'source_book'],
        'display_columns' => ['Name', 'Prerequisite', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'rituals' => [
        'label' => 'Rituals',
        'count' => 360,
        'columns' => ['name', 'level', 'key_skill', 'component_cost', 'source_book'],
        'display_columns' => ['Name', 'Lvl', 'Key Skill', 'Cost', 'Source'],
        'sortable' => ['name', 'level'],
        'filters' => ['level', 'key_skill']
    ],
    'backgrounds' => [
        'label' => 'Backgrounds',
        'count' => 808,
        'columns' => ['name', 'type', 'campaign', 'source_book'],
        'display_columns' => ['Name', 'Type', 'Campaign', 'Source'],
        'sortable' => ['name', 'type'],
        'filters' => ['type', 'campaign']
    ],
    'armor' => [
        'label' => 'Armor',
        'count' => 493,
        'columns' => ['name', 'type', 'armor_bonus', 'speed', 'source_book'],
        'display_columns' => ['Name', 'Type', 'AC', 'Speed', 'Source'],
        'sortable' => ['name', 'type'],
        'filters' => ['type']
    ],
    'weapons' => [
        'label' => 'Weapons',
        'count' => 631,
        'columns' => ['name', 'weapon_category', 'weapon_group', 'hands_required', 'damage', 'source_book'],
        'display_columns' => ['Name', 'Category', 'Group', 'Hands', 'Damage', 'Source'],
        'sortable' => ['name', 'weapon_category', 'weapon_group'],
        'filters' => ['weapon_category', 'weapon_group', 'hands_required']
    ],
    'implements' => [
        'label' => 'Implements',
        'count' => 647,
        'columns' => ['name', 'type', 'source_book'],
        'display_columns' => ['Name', 'Type', 'Source'],
        'sortable' => ['name', 'type'],
        'filters' => ['type']
    ],
    'traps' => [
        'label' => 'Traps',
        'count' => 776,
        'columns' => ['name', 'level', 'type', 'role', 'xp', 'source_book'],
        'display_columns' => ['Name', 'Lvl', 'Type', 'Role', 'XP', 'Source'],
        'sortable' => ['name', 'level', 'type', 'role'],
        'filters' => ['level', 'type', 'role']
    ],
    'companions' => [
        'label' => 'Companions',
        'count' => 193,
        'columns' => ['name', 'type', 'size', 'creature_type', 'source_book'],
        'display_columns' => ['Name', 'Type', 'Size', 'Creature Type', 'Source'],
        'sortable' => ['name', 'type', 'size'],
        'filters' => ['type', 'size']
    ],
    'deities' => [
        'label' => 'Deities',
        'count' => 134,
        'columns' => ['name', 'source_book'],
        'display_columns' => ['Name', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'diseases' => [
        'label' => 'Diseases',
        'count' => 69,
        'columns' => ['name', 'source_book'],
        'display_columns' => ['Name', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'poisons' => [
        'label' => 'Poisons',
        'count' => 38,
        'columns' => ['name', 'source_book'],
        'display_columns' => ['Name', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ],
    'glossary' => [
        'label' => 'Glossary',
        'count' => 467,
        'columns' => ['name', 'source_book'],
        'display_columns' => ['Name', 'Source'],
        'sortable' => ['name'],
        'filters' => []
    ]
];

// Handle AJAX requests
if (isset($_GET['ajax'])) {
    header('Content-Type: application/json');
    
    $action = $_GET['ajax'];
    
    if ($action === 'filters') {
        // Return filter options for a category
        $category = $_GET['category'] ?? 'powers';
        $config = $CATEGORIES[$category] ?? $CATEGORIES['powers'];
        $filters = [];
        
        $db = getDB();
        
        foreach ($config['filters'] as $filter) {
            if ($filter === 'damage_types') {
                $filters['damage_types'] = getTagValues('power_damage_types', 'damage_type');
            } elseif ($filter === 'conditions') {
                $filters['conditions'] = getTagValues('power_conditions', 'condition');
            } elseif ($filter === 'keywords') {
                $filters['keywords'] = getTagValues('power_keywords', 'keyword');
            } elseif ($filter === 'level') {
                // Get min/max level
                $result = $db->querySingle("SELECT MIN(level) as min, MAX(level) as max FROM $category WHERE level IS NOT NULL", true);
                $filters['level'] = ['min' => $result['min'] ?? 1, 'max' => $result['max'] ?? 30];
            } else {
                $filters[$filter] = getDistinctValues($category, $filter);
            }
        }
        
        echo json_encode($filters);
        exit;
    }
    
    if ($action === 'search') {
        $category = $_GET['category'] ?? 'powers';
        $config = $CATEGORIES[$category] ?? $CATEGORIES['powers'];
        $db = getDB();
        
        // Build query
        $columns = implode(', ', array_merge(['id'], $config['columns']));
        $sql = "SELECT $columns FROM $category";
        $where = [];
        $params = [];
        $joins = [];
        
        // Full-text search
        if (!empty($_GET['q'])) {
            $ftsTable = $category . '_fts';
            // Escape special FTS5 characters and wrap in quotes for phrase search
            $ftsQuery = str_replace('"', '""', $_GET['q']);
            $where[] = "id IN (SELECT id FROM $ftsTable WHERE $ftsTable MATCH :fts)";
            $params[':fts'] = '"' . $ftsQuery . '"';
        }
        
        // Level range filter
        if (isset($_GET['level_min']) && $_GET['level_min'] !== '') {
            $where[] = "level >= :level_min";
            $params[':level_min'] = (int)$_GET['level_min'];
        }
        if (isset($_GET['level_max']) && $_GET['level_max'] !== '') {
            $where[] = "level <= :level_max";
            $params[':level_max'] = (int)$_GET['level_max'];
        }
        
        // Standard column filters - only apply if column exists in this category
        $filterColumns = [
            'powers' => ['class_name', 'power_usage', 'defense_targeted', 'range_type', 'area_type'],
            'monsters' => ['combat_role', 'group_role', 'size', 'creature_type'],
            'feats' => ['tier'],
            'items' => ['category', 'type', 'rarity'],
            'classes' => ['role', 'power_source'],
            'races' => ['size', 'origin'],
            'rituals' => ['key_skill'],
            'backgrounds' => ['type', 'campaign'],
            'armor' => ['type'],
            'weapons' => ['weapon_category', 'weapon_group', 'hands_required'],
            'traps' => ['type', 'role'],
            'companions' => ['type', 'size'],
            'implements' => ['type']
        ];
        
        $validFilters = $filterColumns[$category] ?? [];
        
        foreach ($validFilters as $col) {
            if (!empty($_GET[$col])) {
                // Skip if this is the 'category' column and value equals the table name (collision with table selector)
                if ($col === 'category' && $_GET[$col] === $category) {
                    continue;
                }
                $values = is_array($_GET[$col]) ? $_GET[$col] : [$_GET[$col]];
                $placeholders = [];
                foreach ($values as $i => $v) {
                    $key = ":{$col}_{$i}";
                    $placeholders[] = $key;
                    $params[$key] = $v;
                }
                $where[] = "$col IN (" . implode(',', $placeholders) . ")";
            }
        }
        
        // Tag filters (damage types, conditions, keywords)
        if (!empty($_GET['damage_types']) && $category === 'powers') {
            $dmgTypes = is_array($_GET['damage_types']) ? $_GET['damage_types'] : [$_GET['damage_types']];
            foreach ($dmgTypes as $i => $dt) {
                $where[] = "id IN (SELECT power_id FROM power_damage_types WHERE damage_type = :dmg_$i)";
                $params[":dmg_$i"] = $dt;
            }
        }
        
        if (!empty($_GET['conditions']) && $category === 'powers') {
            $conds = is_array($_GET['conditions']) ? $_GET['conditions'] : [$_GET['conditions']];
            foreach ($conds as $i => $c) {
                $where[] = "id IN (SELECT power_id FROM power_conditions WHERE condition = :cond_$i)";
                $params[":cond_$i"] = $c;
            }
        }
        
        if (!empty($_GET['keywords']) && $category === 'powers') {
            $kws = is_array($_GET['keywords']) ? $_GET['keywords'] : [$_GET['keywords']];
            foreach ($kws as $i => $k) {
                $where[] = "id IN (SELECT power_id FROM power_keywords WHERE keyword = :kw_$i)";
                $params[":kw_$i"] = $k;
            }
        }
        
        // Prerequisite text search
        if (!empty($_GET['prereq'])) {
            $where[] = "prerequisite LIKE :prereq";
            $params[':prereq'] = '%' . $_GET['prereq'] . '%';
        }
        
        if (!empty($where)) {
            $sql .= " WHERE " . implode(" AND ", $where);
        }
        
        // Sorting
        $sortCol = $_GET['sort'] ?? 'name';
        $sortDir = ($_GET['dir'] ?? 'asc') === 'desc' ? 'DESC' : 'ASC';
        if (in_array($sortCol, $config['sortable'])) {
            $sql .= " ORDER BY $sortCol $sortDir";
        } else {
            $sql .= " ORDER BY name ASC";
        }
        
        // Pagination
        $limit = min((int)($_GET['limit'] ?? 50), 200);
        $offset = (int)($_GET['offset'] ?? 0);
        $sql .= " LIMIT $limit OFFSET $offset";
        
        // Execute query
        $stmt = $db->prepare($sql);
        if ($stmt === false) {
            echo json_encode(['error' => 'Query error: ' . $db->lastErrorMsg(), 'sql' => $sql]);
            exit;
        }
        foreach ($params as $key => $value) {
            $stmt->bindValue($key, $value);
        }
        
        $result = $stmt->execute();
        $rows = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $rows[] = $row;
        }
        
        // Get total count
        $countSql = "SELECT COUNT(*) FROM $category";
        if (!empty($where)) {
            $countSql .= " WHERE " . implode(" AND ", $where);
        }
        $countStmt = $db->prepare($countSql);
        if ($countStmt === false) {
            echo json_encode(['error' => 'Count query error: ' . $db->lastErrorMsg()]);
            exit;
        }
        foreach ($params as $key => $value) {
            $countStmt->bindValue($key, $value);
        }
        $total = $countStmt->execute()->fetchArray()[0];
        
        echo json_encode([
            'results' => $rows,
            'total' => $total,
            'offset' => $offset,
            'limit' => $limit
        ]);
        exit;
    }
    
    if ($action === 'entry') {
        $category = $_GET['category'] ?? 'powers';
        $id = $_GET['id'] ?? '';
        
        $db = getDB();
        $stmt = $db->prepare("SELECT * FROM $category WHERE id = :id");
        $stmt->bindValue(':id', $id);
        $result = $stmt->execute();
        $entry = $result->fetchArray(SQLITE3_ASSOC);
        
        echo json_encode($entry);
        exit;
    }
    
    exit;
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>4e Compendium</title>
    <style>
        :root {
            --bg: #fafafa;
            --bg-panel: #ffffff;
            --border: #e0e0e0;
            --text: #1a1a1a;
            --text-muted: #666666;
            --text-light: #999999;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --row-hover: #f5f5f5;
            --row-alt: #fafafa;
            
            /* Power usage colors */
            --at-will: #619869;
            --encounter: #961334;
            --daily: #4a4a4a;
            
            /* Stat block colors */
            --stat-header: #1a472a;
            --stat-subheader: #c9a335;
            --monster-header: #7a200d;
            --item-header: #1e3a5f;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            color: var(--text);
            background: var(--bg);
        }
        
        /* Layout */
        .app {
            display: grid;
            grid-template-columns: 240px 1fr 400px;
            grid-template-rows: auto 1fr;
            height: 100vh;
            overflow: hidden;
        }
        
        .app.detail-closed {
            grid-template-columns: 240px 1fr 0;
        }
        
        /* Header */
        header {
            grid-column: 1 / -1;
            display: flex;
            flex-direction: column;
            gap: 0;
            padding: 0;
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border);
        }
        
        .header-top {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 10px 16px;
        }
        
        .header-categories {
            border-top: 1px solid var(--border);
            padding: 6px 16px;
            background: var(--bg);
        }
        
        .logo {
            font-size: 14px;
            font-weight: 600;
            letter-spacing: -0.02em;
            color: var(--text);
        }
        
        .logo span {
            color: var(--text-muted);
            font-weight: 400;
        }
        
        /* Search bar */
        .search-container {
            flex: 1;
            max-width: 480px;
        }
        
        .search-input {
            width: 100%;
            padding: 6px 10px;
            font-size: 13px;
            border: 1px solid var(--border);
            border-radius: 3px;
            background: var(--bg);
            outline: none;
            transition: border-color 0.15s;
        }
        
        .search-input:focus {
            border-color: var(--accent);
        }
        
        .search-input::placeholder {
            color: var(--text-light);
        }
        
        .search-hint {
            font-size: 11px;
            color: var(--text-light);
            margin-top: 2px;
        }
        
        /* Category tabs */
        .categories {
            display: flex;
            gap: 4px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
            padding: 2px;
        }
        
        .categories::-webkit-scrollbar {
            display: none;
        }
        
        .category-btn {
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 500;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 3px;
            cursor: pointer;
            color: var(--text-muted);
            transition: all 0.15s;
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .category-btn:hover {
            border-color: var(--accent);
            color: var(--text);
        }
        
        .category-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        
        /* Sidebar filters */
        .sidebar {
            background: var(--bg-panel);
            border-right: 1px solid var(--border);
            overflow-y: auto;
            overflow-x: hidden;
            padding: 0;
            display: flex;
            flex-direction: column;
        }
        
        .sidebar-header {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg);
            position: sticky;
            top: 0;
            z-index: 1;
        }
        
        .sidebar-title {
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }
        
        .clear-filters {
            font-size: 10px;
            color: var(--accent);
            background: none;
            border: none;
            cursor: pointer;
            padding: 2px 0;
        }
        
        .clear-filters:hover {
            text-decoration: underline;
        }
        
        /* Active filters display */
        .active-filters {
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
            display: none;
        }
        
        .active-filters.has-filters {
            display: block;
        }
        
        .filter-chip {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 6px 2px 8px;
            margin: 2px;
            font-size: 10px;
            background: var(--accent);
            color: white;
            border-radius: 10px;
            cursor: default;
        }
        
        .filter-chip-remove {
            cursor: pointer;
            opacity: 0.7;
            font-size: 12px;
            line-height: 1;
        }
        
        .filter-chip-remove:hover {
            opacity: 1;
        }
        
        .filters-list {
            flex: 1;
            overflow-y: auto;
        }
        
        /* Filter sections - accordion style */
        .filter-section {
            border-bottom: 1px solid var(--border);
        }
        
        .filter-section:last-child {
            border-bottom: none;
        }
        
        .filter-toggle {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            padding: 8px 12px;
            font-size: 11px;
            font-weight: 500;
            color: var(--text);
            background: none;
            border: none;
            cursor: pointer;
            text-align: left;
        }
        
        .filter-toggle:hover {
            background: var(--row-hover);
        }
        
        .filter-toggle-icon {
            font-size: 10px;
            color: var(--text-muted);
            transition: transform 0.15s;
        }
        
        .filter-section.open .filter-toggle-icon {
            transform: rotate(180deg);
        }
        
        .filter-content {
            display: none;
            padding: 0 12px 10px 12px;
        }
        
        .filter-section.open .filter-content {
            display: block;
        }
        
        /* Simple filter rows */
        .filter-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            border-bottom: 1px solid var(--border);
            overflow: hidden;
        }
        
        .filter-row:last-child {
            border-bottom: none;
        }
        
        .filter-label {
            font-size: 11px;
            font-weight: 500;
            color: var(--text-muted);
            min-width: 70px;
            flex-shrink: 0;
        }
        
        /* Filter inputs */
        .filter-select {
            flex: 1;
            min-width: 0;
            max-width: 100%;
            padding: 5px 8px;
            font-size: 11px;
            border: 1px solid var(--border);
            border-radius: 3px;
            text-overflow: ellipsis;
            background: var(--bg);
            cursor: pointer;
        }
        
        .filter-select:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        /* Compact checkbox grid */
        .filter-checks {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        
        .filter-check {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            font-size: 10px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 3px;
            cursor: pointer;
            transition: all 0.1s;
        }
        
        .filter-check:hover {
            border-color: var(--accent);
        }
        
        .filter-check.selected {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        
        .filter-check input {
            display: none;
        }
        
        /* Range inputs */
        .range-inputs {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        
        .range-input {
            width: 50px;
            padding: 4px 6px;
            font-size: 11px;
            border: 1px solid var(--border);
            border-radius: 3px;
            text-align: center;
        }
        
        .range-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .range-sep {
            color: var(--text-light);
            font-size: 10px;
        }
        
        /* Text filter input */
        .filter-text {
            width: 100%;
            padding: 5px 8px;
            font-size: 11px;
            border: 1px solid var(--border);
            border-radius: 3px;
        }
        
        .filter-text:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        /* Results panel */
        .results {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: var(--bg-panel);
        }
        
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
            background: var(--bg);
        }
        
        .results-count {
            font-size: 11px;
            color: var(--text-muted);
        }
        
        .results-count strong {
            color: var(--text);
        }
        
        /* Results table */
        .results-table-container {
            flex: 1;
            overflow: auto;
        }
        
        .results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        
        .results-table th {
            position: sticky;
            top: 0;
            padding: 8px 10px;
            text-align: left;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: var(--text-muted);
            background: var(--bg);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        
        .results-table th:hover {
            color: var(--text);
        }
        
        .results-table th.sorted {
            color: var(--accent);
        }
        
        .results-table th .sort-arrow {
            margin-left: 4px;
            opacity: 0.5;
        }
        
        .results-table th.sorted .sort-arrow {
            opacity: 1;
        }
        
        .results-table td {
            padding: 6px 10px;
            border-bottom: 1px solid var(--border);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .results-table tr {
            cursor: pointer;
            transition: background 0.1s;
        }
        
        .results-table tr:hover {
            background: var(--row-hover);
        }
        
        .results-table tr.selected {
            background: #e8f0fe;
        }
        
        .results-table tr:nth-child(even) {
            background: var(--row-alt);
        }
        
        .results-table tr:nth-child(even):hover {
            background: var(--row-hover);
        }
        
        /* Usage badges */
        .usage-badge {
            display: inline-block;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: 500;
            border-radius: 2px;
            color: white;
        }
        
        .usage-badge.at-will { background: var(--at-will); }
        .usage-badge.encounter { background: var(--encounter); }
        .usage-badge.daily { background: var(--daily); }
        
        /* Pagination */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            padding: 10px;
            border-top: 1px solid var(--border);
            background: var(--bg);
        }
        
        .page-btn {
            padding: 4px 10px;
            font-size: 11px;
            border: 1px solid var(--border);
            border-radius: 3px;
            background: var(--bg-panel);
            cursor: pointer;
            transition: all 0.15s;
        }
        
        .page-btn:hover:not(:disabled) {
            border-color: var(--accent);
            color: var(--accent);
        }
        
        .page-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .page-info {
            font-size: 11px;
            color: var(--text-muted);
        }
        
        /* Detail panel */
        .detail {
            background: var(--bg-panel);
            border-left: 1px solid var(--border);
            overflow: hidden;
        }
        
        .detail.closed {
            display: none;
        }
        
        .detail-content {
            height: 100%;
            overflow-y: auto;
            padding: 16px;
        }
        
        /* Stat block styling */
        .stat-block {
            font-family: "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif;
            font-size: 13px;
            line-height: 1.4;
        }
        
        .stat-block h1 {
            font-size: 18px;
            font-weight: normal;
            margin: 0 0 2px 0;
            color: var(--stat-header);
        }
        
        .stat-block .flavor {
            font-style: italic;
            color: var(--text-muted);
            margin-bottom: 10px;
            font-size: 12px;
        }
        
        /* Original HTML header styles - Magic Items */
        .stat-block h1.mihead {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: var(--item-header);
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        .stat-block h1.mihead span.milevel {
            font-size: 11px;
            opacity: 0.9;
            margin-left: 12px;
            white-space: nowrap;
        }
        
        /* Poison headers */
        .stat-block h1.poison {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #4a2a4a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        .stat-block h1.poison span.milevel {
            font-size: 11px;
            opacity: 0.9;
            margin-left: 12px;
            white-space: nowrap;
        }
        
        /* Disease headers */
        .stat-block h1.disease {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #3a4a2a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Trap headers */
        .stat-block h1.trap {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #5a3a2a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* DM/Terrain headers */
        .stat-block h1.dm {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #3a3a4a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Familiar headers */
        .stat-block h1.familiar {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            background: #2a4a5a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        .stat-block h1.familiar span.level {
            font-size: 11px;
            opacity: 0.9;
            margin-left: 12px;
            white-space: nowrap;
        }
        
        /* Monster headers */
        .stat-block h1.monster {
            background: var(--monster-header);
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 15px;
            font-weight: normal;
        }
        
        /* Thhead class (used by various categories) */
        .stat-block h1.thHead,
        .stat-block h1.pointed {
            background: #4a4a4a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Player info headers */
        .stat-block h1.player {
            background: var(--stat-header);
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Subheaders */
        .stat-block h2.mihead {
            font-size: 12px;
            font-weight: 600;
            color: var(--text);
            margin: 12px 0 4px 0;
            padding: 0;
        }
        
        /* Magic item stats */
        .stat-block p.mistat {
            margin: 4px 0;
            font-size: 12px;
        }
        
        .stat-block p.mistat.indent {
            margin-left: 12px;
        }
        
        .stat-block p.miflavor {
            font-style: italic;
            color: var(--text-muted);
            margin: 0 0 10px 0;
            font-size: 12px;
        }
        
        /* Magic item tables */
        .stat-block table.magicitem {
            width: 100%;
            font-size: 11px;
            margin: 8px 0;
            border-collapse: collapse;
        }
        
        .stat-block table.magicitem td {
            padding: 2px 6px;
        }
        
        .stat-block table.magicitem td.mic1 { font-weight: 500; }
        .stat-block table.magicitem td.mic2 { color: var(--text-muted); }
        .stat-block table.magicitem td.mic3 { }
        .stat-block table.magicitem td.mic4 { width: 20px; }
        
        /* Monster headers */
        .stat-block h1.monster {
            background: var(--monster-header);
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 15px;
            font-weight: normal;
            line-height: 1.3;
        }
        
        .stat-block h1.monster span.type {
            display: block;
            font-size: 11px;
            opacity: 0.9;
            margin-top: 2px;
        }
        
        /* Monster body table */
        .stat-block table.bodytable {
            width: 100%;
            font-size: 12px;
            margin-bottom: 12px;
            border-collapse: collapse;
        }
        
        .stat-block table.bodytable td {
            padding: 2px 0;
            vertical-align: top;
        }
        
        .stat-block table.bodytable td.rightalign {
            text-align: right;
        }
        
        /* Section headers (h2) */
        .stat-block h2 {
            font-size: 12px;
            font-weight: 600;
            color: var(--text);
            margin: 14px 0 6px 0;
            padding-bottom: 2px;
            border-bottom: 1px solid var(--border);
        }
        
        /* Flavor text for actions */
        .stat-block p.flavor {
            margin: 6px 0;
            font-size: 12px;
        }
        
        .stat-block p.flavor.alt {
            background: var(--row-alt);
            padding: 4px 6px;
            margin: 4px -6px;
            border-radius: 2px;
        }
        
        .stat-block p.flavorIndent {
            margin: 2px 0 2px 16px;
            font-size: 12px;
        }
        
        /* Trait/Feature headers */
        .stat-block h3 {
            font-size: 11px;
            font-weight: 600;
            margin: 10px 0 4px 0;
        }
        
        /* Class/Race headers */
        .stat-block h1.pointed,
        .stat-block h1.thHead {
            background: #4a4a4a;
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        .stat-block h1.pointed span,
        .stat-block h1.thHead span {
            display: block;
            font-size: 11px;
            opacity: 0.9;
            margin-top: 2px;
        }
        
        /* Player/PC headers */
        .stat-block h1.player {
            background: var(--stat-header);
            color: white;
            padding: 8px 12px;
            margin: -16px -16px 12px -16px;
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Fullwidth paragraphs */
        .stat-block p.pointed,
        .stat-block p.pointed1 {
            margin: 6px 0;
            font-size: 12px;
        }
        
        /* Detail sections */
        .stat-block .pointed,
        .stat-block .pointed1 {
            font-size: 12px;
        }
        
        /* Lists */
        .stat-block ul, .stat-block ol {
            margin: 6px 0 6px 20px;
            font-size: 12px;
        }
        
        .stat-block li {
            margin: 2px 0;
        }
        
        /* Power headers - default inline style */
        .stat-block h1.atwillpower,
        .stat-block h1.encounterpower,
        .stat-block h1.dailypower {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 6px 10px;
            margin: 14px 0 10px 0;
            font-size: 13px;
            color: white;
            border-radius: 2px;
        }
        
        .stat-block h1.atwillpower { background: var(--at-will); }
        .stat-block h1.encounterpower { background: var(--encounter); }
        .stat-block h1.dailypower { background: var(--daily); }
        
        /* Standalone power view - edge to edge header */
        .stat-block.power > h1.atwillpower:first-child,
        .stat-block.power > h1.encounterpower:first-child,
        .stat-block.power > h1.dailypower:first-child {
            margin: -16px -16px 12px -16px;
            padding: 8px 12px;
            border-radius: 0;
            font-size: 14px;
        }
        
        .stat-block h1 span.level {
            font-size: 11px;
            font-weight: normal;
            opacity: 0.9;
            text-align: right;
            margin-left: 12px;
            white-space: nowrap;
        }
        
        /* Power stat lines */
        .stat-block p.powerstat {
            margin: 4px 0;
            font-size: 12px;
        }
        
        .stat-block p.flavor {
            font-style: italic;
            color: var(--text-muted);
            margin: 6px 0;
        }
        
        .stat-block p.flavor b {
            font-style: normal;
            color: var(--text);
        }
        
        .stat-block p.publishedIn {
            font-size: 10px;
            color: var(--text-light);
            margin-top: 12px;
            font-style: italic;
        }
        
        
        /* Stat block body content */
        .stat-block b {
            font-weight: 600;
        }
        
        .stat-block p {
            margin: 6px 0;
        }
        
        .stat-block table {
            width: 100%;
            border-collapse: collapse;
            margin: 8px 0;
            font-size: 12px;
        }
        
        .stat-block td, .stat-block th {
            padding: 3px 6px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        .stat-block hr {
            border: none;
            border-top: 1px solid var(--border);
            margin: 10px 0;
        }
        
        .stat-block .published {
            font-size: 10px;
            color: var(--text-light);
            margin-top: 12px;
            font-style: italic;
        }
        
        /* Loading state */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
            color: var(--text-muted);
            font-size: 12px;
        }
        
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Empty state */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            color: var(--text-muted);
            text-align: center;
        }
        
        .empty-state h3 {
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 6px;
            color: var(--text);
        }
        
        .empty-state p {
            font-size: 12px;
        }
        
        /* Mobile close button - hidden on desktop */
        .detail-close-mobile {
            display: none;
            position: sticky;
            top: 0;
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border);
            padding: 10px 12px;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            z-index: 10;
        }
        
        .detail-close-mobile:hover {
            background: var(--bg);
        }
        
        .detail-close-mobile::before {
            content: "←";
            font-size: 16px;
        }
        
        /* Mobile responsive */
        @media (max-width: 1024px) {
            .app,
            .app.detail-closed {
                grid-template-columns: 200px 1fr;
            }
            
            .detail {
                position: fixed;
                right: 0;
                top: 0;
                bottom: 0;
                width: 360px;
                z-index: 200;
                box-shadow: -4px 0 20px rgba(0,0,0,0.15);
            }
            
            .detail.closed {
                display: none;
            }
            
            .header-top {
                gap: 10px;
            }
            
            .header-categories {
                padding: 6px 12px;
            }
        }
        
        @media (max-width: 768px) {
            .app,
            .app.detail-closed {
                grid-template-columns: 1fr;
                grid-template-rows: auto 1fr;
            }
            
            header {
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .sidebar {
                display: none;
            }
            
            .results {
                grid-column: 1;
                width: 100%;
                max-width: 100vw;
                overflow-y: auto;
            }
            
            .header-top {
                padding: 8px 12px;
                flex-direction: column;
                gap: 8px;
            }
            
            .logo {
                font-size: 13px;
                align-self: flex-start;
            }
            
            .search-container {
                width: 100%;
                max-width: none;
            }
            
            .header-categories {
                padding: 8px 12px;
            }
            
            .categories {
                flex-wrap: wrap;
                overflow-x: visible;
            }
            
            .category-btn {
                padding: 6px 10px;
                font-size: 11px;
            }
            
            .detail {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                width: 100%;
                z-index: 300;
            }
            
            .detail-close-mobile {
                display: flex;
            }
            
            /* Show only first 2 columns on mobile */
            .results-table th:nth-child(n+3),
            .results-table td:nth-child(n+3) {
                display: none;
            }
            
            .results-table th,
            .results-table td {
                padding: 8px;
                font-size: 12px;
            }
            
            .results-table td {
                max-width: none;
            }
        }
    </style>
</head>
<body>
    <div class="app detail-closed" id="app">
        <header>
            <div class="header-top">
                <div class="logo">4e Compendium <span>Search</span></div>
                
                <div class="search-container">
                    <input type="text" class="search-input" id="searchInput" 
                           placeholder="Search... (e.g., fire AND damage, teleport*, &quot;ongoing fire&quot;)">
                </div>
            </div>
            
            <div class="header-categories">
                <div class="categories" id="categoryTabs">
                    <button class="category-btn active" data-category="powers">Powers</button>
                    <button class="category-btn" data-category="monsters">Monsters</button>
                <button class="category-btn" data-category="feats">Feats</button>
                <button class="category-btn" data-category="items">Items</button>
                <button class="category-btn" data-category="classes">Classes</button>
                <button class="category-btn" data-category="races">Races</button>
                <button class="category-btn" data-category="paragon_paths">Paragon</button>
                <button class="category-btn" data-category="epic_destinies">Epic</button>
                <button class="category-btn" data-category="themes">Themes</button>
                <button class="category-btn" data-category="rituals">Rituals</button>
                <button class="category-btn" data-category="backgrounds">Backgrounds</button>
                <button class="category-btn" data-category="armor">Armor</button>
                <button class="category-btn" data-category="weapons">Weapons</button>
                <button class="category-btn" data-category="implements">Implements</button>
                <button class="category-btn" data-category="traps">Traps</button>
                <button class="category-btn" data-category="companions">Companions</button>
                <button class="category-btn" data-category="deities">Deities</button>
                <button class="category-btn" data-category="diseases">Diseases</button>
                <button class="category-btn" data-category="poisons">Poisons</button>
                    <button class="category-btn" data-category="glossary">Glossary</button>
                </div>
            </div>
        </header>
        
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <span class="sidebar-title">Filters</span>
                <button class="clear-filters" id="clearFilters">Clear</button>
            </div>
            <div class="active-filters" id="activeFilters"></div>
            <div class="filters-list" id="filterContainer">
                <div class="loading"><div class="spinner"></div>Loading...</div>
            </div>
        </aside>
        
        <main class="results">
            <div class="results-header">
                <span class="results-count" id="resultsCount">Loading...</span>
            </div>
            
            <div class="results-table-container" id="resultsContainer">
                <div class="loading"><div class="spinner"></div>Loading results...</div>
            </div>
            
            <div class="pagination" id="pagination">
                <button class="page-btn" id="prevPage" disabled>&larr; Prev</button>
                <span class="page-info" id="pageInfo">Page 1</span>
                <button class="page-btn" id="nextPage">Next &rarr;</button>
            </div>
        </main>
        
        <aside class="detail closed" id="detailPanel">
            <div class="detail-close-mobile" id="detailCloseMobile">Back to results</div>
            <div class="detail-content" id="detailContent"></div>
        </aside>
    </div>
    
    <script>
    (function() {
        // State
        const state = {
            category: 'powers',
            filters: {},
            filterValues: {},
            query: '',
            sort: 'name',
            sortDir: 'asc',
            offset: 0,
            limit: 50,
            total: 0,
            selectedId: null
        };
        
        // Category metadata
        const CATEGORIES = <?php echo json_encode($CATEGORIES); ?>;
        
        // DOM elements
        const dom = {
            app: document.getElementById('app'),
            searchInput: document.getElementById('searchInput'),
            categoryTabs: document.getElementById('categoryTabs'),
            filterContainer: document.getElementById('filterContainer'),
            activeFilters: document.getElementById('activeFilters'),
            resultsContainer: document.getElementById('resultsContainer'),
            resultsCount: document.getElementById('resultsCount'),
            pagination: document.getElementById('pagination'),
            pageInfo: document.getElementById('pageInfo'),
            prevPage: document.getElementById('prevPage'),
            nextPage: document.getElementById('nextPage'),
            detailPanel: document.getElementById('detailPanel'),
            detailContent: document.getElementById('detailContent'),
            detailCloseMobile: document.getElementById('detailCloseMobile'),
            clearFilters: document.getElementById('clearFilters')
        };
        
        // Debounce utility
        function debounce(fn, delay) {
            let timer;
            return function(...args) {
                clearTimeout(timer);
                timer = setTimeout(() => fn.apply(this, args), delay);
            };
        }
        
        // API calls
        async function api(action, params = {}) {
            const url = new URL(window.location.href);
            url.searchParams.set('ajax', action);
            for (const [key, value] of Object.entries(params)) {
                if (Array.isArray(value)) {
                    value.forEach(v => url.searchParams.append(key + '[]', v));
                } else if (value !== '' && value !== null && value !== undefined) {
                    url.searchParams.set(key, value);
                }
            }
            const response = await fetch(url);
            return response.json();
        }
        
        // Load filters for current category
        async function loadFilters() {
            dom.filterContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Loading filters...</div>';
            
            const filters = await api('filters', { category: state.category });
            state.filterValues = filters;
            state.filters = {};
            
            renderFilters(filters);
        }
        
        // Render filter controls
        function renderFilters(filters) {
            const config = CATEGORIES[state.category];
            let html = '';
            
            // Full-text search box (always shown)
            html += `
                <div class="filter-row">
                    <label class="filter-label">Search</label>
                    <input type="text" class="filter-text" id="ftsSearch" 
                           placeholder="Search text..." 
                           value="${escapeHtml(state.filters.q || '')}"
                           style="flex:1;">
                </div>
            `;
            
            const filterLabels = {
                level: 'Level',
                class_name: 'Class',
                power_usage: 'Usage',
                defense_targeted: 'Defense',
                range_type: 'Range',
                area_type: 'Area Type',
                combat_role: 'Combat Role',
                group_role: 'Group Role',
                size: 'Size',
                creature_type: 'Creature Type',
                tier: 'Tier',
                category: 'Category',
                type: 'Type',
                rarity: 'Rarity',
                role: 'Role',
                power_source: 'Power Source',
                origin: 'Origin',
                damage_types: 'Damage Type',
                conditions: 'Condition',
                keywords: 'Keyword',
                prereq: 'Prerequisite',
                key_skill: 'Key Skill',
                campaign: 'Campaign',
                weapon_category: 'Category',
                weapon_group: 'Group',
                hands_required: 'Hands'
            };
            
            // Level range filter
            if (filters.level) {
                html += `
                    <div class="filter-row">
                        <label class="filter-label">Level</label>
                        <div class="range-inputs">
                            <input type="number" class="range-input" id="levelMin" 
                                   min="${filters.level.min}" max="${filters.level.max}" 
                                   placeholder="${filters.level.min}">
                            <span class="range-sep">–</span>
                            <input type="number" class="range-input" id="levelMax" 
                                   min="${filters.level.min}" max="${filters.level.max}" 
                                   placeholder="${filters.level.max}">
                        </div>
                    </div>
                `;
            }
            
            // Dropdown filters as collapsible selects
            const dropdownFilters = ['class_name', 'power_usage', 'defense_targeted', 'range_type', 
                                    'area_type', 'combat_role', 'group_role', 'size', 'creature_type',
                                    'tier', 'category', 'type', 'rarity', 'role', 'power_source', 'origin',
                                    'weapon_category', 'weapon_group', 'hands_required', 'key_skill', 'campaign'];
            
            for (const filter of dropdownFilters) {
                if (filters[filter] && filters[filter].length > 0) {
                    html += `
                        <div class="filter-row">
                            <label class="filter-label">${filterLabels[filter] || filter}</label>
                            <select class="filter-select" data-filter="${filter}">
                                <option value="">Any</option>
                                ${filters[filter].map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('')}
                            </select>
                        </div>
                    `;
                }
            }
            
            // Multi-select chip filters (keep collapsible since they can have many options)
            const checkFilters = ['damage_types', 'conditions', 'keywords'];
            
            for (const filter of checkFilters) {
                if (filters[filter] && filters[filter].length > 0) {
                    html += `
                        <div class="filter-section" data-section="${filter}">
                            <button class="filter-toggle">
                                ${filterLabels[filter]} <span class="filter-toggle-icon">▶</span>
                            </button>
                            <div class="filter-content">
                                <div class="filter-checks" data-filter="${filter}">
                                    ${filters[filter].map(v => `
                                        <label class="filter-check" data-value="${escapeHtml(v)}">
                                            <input type="checkbox" value="${escapeHtml(v)}">
                                            ${escapeHtml(v)}
                                        </label>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    `;
                }
            }
            
            // Prerequisite text search for relevant categories
            if (['feats', 'paragon_paths', 'epic_destinies', 'themes'].includes(state.category)) {
                html += `
                    <div class="filter-row">
                        <label class="filter-label">Prereq</label>
                        <input type="text" class="filter-text" id="prereqFilter" placeholder="e.g., Rogue, Str 15" style="flex:1;">
                    </div>
                `;
            }
            
            if (html === '') {
                html = '<div class="empty-state" style="padding: 20px;"><p>No filters for this category</p></div>';
            }
            
            dom.filterContainer.innerHTML = html;
            attachFilterListeners();
        }
        
        // Attach event listeners to filter controls
        function attachFilterListeners() {
            // Accordion toggles
            document.querySelectorAll('.filter-toggle').forEach(toggle => {
                toggle.addEventListener('click', () => {
                    toggle.closest('.filter-section').classList.toggle('open');
                });
            });
            
            // Full-text search
            const ftsSearch = document.getElementById('ftsSearch');
            if (ftsSearch) {
                ftsSearch.addEventListener('input', debounce(() => {
                    state.filters.q = ftsSearch.value;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                }, 300));
            }
            
            // Level range
            const levelMin = document.getElementById('levelMin');
            const levelMax = document.getElementById('levelMax');
            if (levelMin) {
                levelMin.addEventListener('input', debounce(() => {
                    state.filters.level_min = levelMin.value;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                }, 300));
            }
            if (levelMax) {
                levelMax.addEventListener('input', debounce(() => {
                    state.filters.level_max = levelMax.value;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                }, 300));
            }
            
            // Dropdown selects
            document.querySelectorAll('.filter-select').forEach(select => {
                select.addEventListener('change', () => {
                    state.filters[select.dataset.filter] = select.value;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                });
            });
            
            // Chip-style checkbox filters
            document.querySelectorAll('.filter-check').forEach(label => {
                label.addEventListener('click', (e) => {
                    e.preventDefault();
                    const checkbox = label.querySelector('input');
                    checkbox.checked = !checkbox.checked;
                    label.classList.toggle('selected', checkbox.checked);
                    
                    const container = label.closest('.filter-checks');
                    const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
                    state.filters[container.dataset.filter] = checked;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                });
            });
            
            // Prerequisite filter
            const prereqFilter = document.getElementById('prereqFilter');
            if (prereqFilter) {
                prereqFilter.addEventListener('input', debounce(() => {
                    state.filters.prereq = prereqFilter.value;
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                }, 300));
            }
        }
        
        // Update active filters display
        function updateActiveFilters() {
            const container = document.getElementById('activeFilters');
            const chips = [];
            
            const labels = {
                q: 'Search: ',
                level_min: 'Level ≥',
                level_max: 'Level ≤',
                class_name: '',
                power_usage: '',
                defense_targeted: 'vs ',
                range_type: '',
                area_type: '',
                combat_role: '',
                group_role: '',
                size: '',
                creature_type: '',
                tier: '',
                category: '',
                type: '',
                rarity: '',
                role: '',
                power_source: '',
                origin: '',
                prereq: 'Prereq: ',
                weapon_category: '',
                weapon_group: '',
                hands_required: '',
                key_skill: '',
                campaign: ''
            };
            
            for (const [key, value] of Object.entries(state.filters)) {
                if (!value || (Array.isArray(value) && value.length === 0)) continue;
                
                if (Array.isArray(value)) {
                    value.forEach(v => {
                        chips.push({ key, value: v, label: v });
                    });
                } else {
                    const prefix = labels[key] !== undefined ? labels[key] : '';
                    chips.push({ key, value, label: prefix + value });
                }
            }
            
            if (chips.length === 0) {
                container.classList.remove('has-filters');
                container.innerHTML = '';
                return;
            }
            
            container.classList.add('has-filters');
            container.innerHTML = chips.map(c => `
                <span class="filter-chip" data-key="${c.key}" data-value="${escapeHtml(c.value)}">
                    ${escapeHtml(c.label)}
                    <span class="filter-chip-remove">×</span>
                </span>
            `).join('');
            
            // Chip remove handlers
            container.querySelectorAll('.filter-chip-remove').forEach(btn => {
                btn.addEventListener('click', () => {
                    const chip = btn.closest('.filter-chip');
                    const key = chip.dataset.key;
                    const value = chip.dataset.value;
                    
                    if (Array.isArray(state.filters[key])) {
                        state.filters[key] = state.filters[key].filter(v => v !== value);
                        // Update checkbox UI
                        const checkbox = document.querySelector(`.filter-check[data-value="${value}"] input`);
                        if (checkbox) {
                            checkbox.checked = false;
                            checkbox.closest('.filter-check').classList.remove('selected');
                        }
                    } else {
                        state.filters[key] = '';
                        // Update select/input UI
                        const select = document.querySelector(`[data-filter="${key}"]`);
                        if (select) select.value = '';
                        const input = document.getElementById(key === 'level_min' ? 'levelMin' : key === 'level_max' ? 'levelMax' : 'prereqFilter');
                        if (input) input.value = '';
                    }
                    
                    state.offset = 0;
                    search();
                    updateActiveFilters();
                });
            });
        }
        
        // Perform search
        async function search() {
            dom.resultsContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Searching...</div>';
            
            const params = {
                category: state.category,
                q: state.query,
                sort: state.sort,
                dir: state.sortDir,
                offset: state.offset,
                limit: state.limit,
                ...state.filters
            };
            
            const data = await api('search', params);
            state.total = data.total;
            
            renderResults(data);
            updatePagination();
        }
        
        // Render results table
        function renderResults(data) {
            const config = CATEGORIES[state.category];
            
            if (data.results.length === 0) {
                dom.resultsContainer.innerHTML = `
                    <div class="empty-state">
                        <h3>No results found</h3>
                        <p>Try adjusting your filters or search terms</p>
                    </div>
                `;
                dom.resultsCount.innerHTML = '<strong>0</strong> results';
                return;
            }
            
            dom.resultsCount.innerHTML = `<strong>${data.total.toLocaleString()}</strong> results`;
            
            let html = '<table class="results-table"><thead><tr>';
            
            // Headers
            config.columns.forEach((col, i) => {
                const isSortable = config.sortable.includes(col);
                const isSorted = state.sort === col;
                const sortClass = isSorted ? 'sorted' : '';
                const arrow = isSorted ? (state.sortDir === 'asc' ? '↑' : '↓') : '↕';
                
                if (isSortable) {
                    html += `<th class="${sortClass}" data-sort="${col}">
                        ${config.display_columns[i]}
                        <span class="sort-arrow">${arrow}</span>
                    </th>`;
                } else {
                    html += `<th>${config.display_columns[i]}</th>`;
                }
            });
            
            html += '</tr></thead><tbody>';
            
            // Rows
            for (const row of data.results) {
                const selectedClass = row.id === state.selectedId ? 'selected' : '';
                html += `<tr data-id="${row.id}" class="${selectedClass}">`;
                
                for (const col of config.columns) {
                    let value = row[col] ?? '';
                    
                    // Special formatting
                    if (col === 'power_usage' && value) {
                        const usageClass = value.toLowerCase().replace('-', '');
                        value = `<span class="usage-badge ${usageClass}">${value}</span>`;
                    } else {
                        value = escapeHtml(String(value));
                    }
                    
                    html += `<td title="${escapeHtml(String(row[col] ?? ''))}">${value}</td>`;
                }
                
                html += '</tr>';
            }
            
            html += '</tbody></table>';
            dom.resultsContainer.innerHTML = html;
            
            // Attach row click handlers
            dom.resultsContainer.querySelectorAll('tr[data-id]').forEach(row => {
                row.addEventListener('click', () => loadEntry(row.dataset.id));
            });
            
            // Attach sort handlers
            dom.resultsContainer.querySelectorAll('th[data-sort]').forEach(th => {
                th.addEventListener('click', () => {
                    const col = th.dataset.sort;
                    if (state.sort === col) {
                        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
                    } else {
                        state.sort = col;
                        state.sortDir = 'asc';
                    }
                    state.offset = 0;
                    search();
                });
            });
        }
        
        // Update pagination controls
        function updatePagination() {
            const totalPages = Math.ceil(state.total / state.limit);
            const currentPage = Math.floor(state.offset / state.limit) + 1;
            
            dom.pageInfo.textContent = `Page ${currentPage} of ${totalPages || 1}`;
            dom.prevPage.disabled = state.offset === 0;
            dom.nextPage.disabled = state.offset + state.limit >= state.total;
        }
        
        // Load entry details
        async function loadEntry(id) {
            state.selectedId = id;
            
            // Update selection in table
            dom.resultsContainer.querySelectorAll('tr[data-id]').forEach(row => {
                row.classList.toggle('selected', row.dataset.id === id);
            });
            
            // Show detail panel
            dom.detailPanel.classList.remove('closed');
            dom.app.classList.remove('detail-closed');
            dom.detailContent.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
            
            const entry = await api('entry', { category: state.category, id: id });
            renderEntry(entry);
        }
        
        // Render entry stat block
        function renderEntry(entry) {
            if (!entry) {
                dom.detailContent.innerHTML = '<div class="empty-state"><p>Entry not found</p></div>';
                return;
            }
            
            
            // All categories: just render the HTML body with appropriate wrapper class
            // The original HTML already contains styled headers
            const categoryClass = state.category === 'powers' ? 'power' : 
                                  state.category === 'monsters' ? 'monster' :
                                  state.category === 'items' ? 'item' : '';
            
            const html = `
                <div class="stat-block ${categoryClass}">
                    ${entry.html_body || '<p class="empty-state">No content available</p>'}
                </div>
            `;
            
            dom.detailContent.innerHTML = html;
        }
        
        // Close detail panel
        function closeDetail() {
            dom.detailPanel.classList.add('closed');
            dom.app.classList.add('detail-closed');
            state.selectedId = null;
            
            dom.resultsContainer.querySelectorAll('tr.selected').forEach(row => {
                row.classList.remove('selected');
            });
        }
        
        // Switch category
        function switchCategory(category) {
            state.category = category;
            state.filters = {};
            state.offset = 0;
            state.sort = 'name';
            state.sortDir = 'asc';
            state.selectedId = null;
            
            // Update active tab
            document.querySelectorAll('.category-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.category === category);
            });
            
            // Clear active filter chips display
            updateActiveFilters();
            
            closeDetail();
            loadFilters();
            search();
        }
        
        // Clear all filters
        function clearFilters() {
            state.filters = {};
            state.query = '';
            state.offset = 0;
            dom.searchInput.value = '';
            
            // Clear active filters display
            dom.activeFilters.classList.remove('has-filters');
            dom.activeFilters.innerHTML = '';
            
            loadFilters();
            search();
        }
        
        // Escape HTML
        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }
        
        // Event listeners
        dom.searchInput.addEventListener('input', debounce(() => {
            state.query = dom.searchInput.value;
            state.offset = 0;
            search();
        }, 300));
        
        // Category tab clicks
        dom.categoryTabs.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-category]');
            if (btn && btn.dataset.category) {
                switchCategory(btn.dataset.category);
            }
        });
        
        dom.prevPage.addEventListener('click', () => {
            if (state.offset > 0) {
                state.offset = Math.max(0, state.offset - state.limit);
                search();
            }
        });
        
        dom.nextPage.addEventListener('click', () => {
            if (state.offset + state.limit < state.total) {
                state.offset += state.limit;
                search();
            }
        });
        
        dom.clearFilters.addEventListener('click', clearFilters);
        dom.detailCloseMobile.addEventListener('click', closeDetail);
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !dom.detailPanel.classList.contains('closed')) {
                closeDetail();
            }
            
            // Focus search on / key
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
                e.preventDefault();
                dom.searchInput.focus();
            }
        });
        
        // Initialize
        loadFilters();
        search();
    })();
    </script>
</body>
</html>
