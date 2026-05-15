#!/usr/bin/env python3
"""
pokered ROM enhancement:
1. Merge RED+BLUE exclusives in wild encounters → 151 Pokémon
2. Add missing starters, trade evos, Mew to wild
3. Scale all wild levels +20%
4. Scale trainer levels +20%

WARNING: each wild grass/water block is strictly 21 bytes (rate + 10 slots).
All modifications MUST preserve exactly 10 entries per block.
"""

import re
import math
import os

MAX_LEVEL = 100
SCALE_PCT = 1.20
WILD_DIR = '/Users/jp/Projects/pokered/data/wild/maps'
TRAINER_FILE = '/Users/jp/Projects/pokered/data/trainers/parties.asm'

def scale(n):
    return min(math.ceil(n * SCALE_PCT), MAX_LEVEL)

def parse_db(line):
    m = re.match(r'^\s*db\s+(\d+),\s*([A-Z_]+)', line)
    if m:
        return (int(m.group(1)), m.group(2))
    return None

# ─── 1. Merge version conditionals ────────────────────────────────────

def merge_file(fpath):
    """Merge RED+BLUE entries in one file. Returns True if modified."""
    with open(fpath) as f:
        lines = f.readlines()
    
    if not any('IF DEF' in l for l in lines):
        return False
    
    gs = None  # grass start index
    ge = None  # grass end index
    ws = None  # water start index
    we = None  # water end index
    
    for i, l in enumerate(lines):
        if 'def_grass_wildmons' in l:
            gs = i
        if 'end_grass_wildmons' in l and gs is not None and i > gs:
            ge = i
        if 'def_water_wildmons' in l and ge is not None:
            ws = i
        if 'end_water_wildmons' in l and ws is not None and i > ws:
            we = i
            break
    
    def merge_block(start, end, block_name):
        """Merge IF DEF blocks within a range. Returns new lines or None."""
        if start is None or end is None:
            return None
        
        entries = {'common': [], 'red': [], 'blue': []}
        state = 'common'
        
        for i in range(start + 1, end):
            l = lines[i]
            if 'IF DEF(_RED)' in l:
                state = 'red'; continue
            if 'IF DEF(_BLUE)' in l:
                state = 'blue'; continue
            if 'ENDC' in l:
                state = 'common'; continue
            pd = parse_db(l)
            if pd:
                entries[state].append(pd)
        
        # Only merge if there were conditionals
        if not entries['red'] and not entries['blue']:
            return None
        
        m = re.match(r'^(\s*)', lines[start])
        indent = m.group(1) if m else '\t'
        
        # Check the encounter rate: def_grass_wildmons X or def_water_wildmons X
        rate_match = re.search(r'\d+', lines[start])
        rate = int(rate_match.group()) if rate_match else 10
        
        # Number of entries: if rate > 0, exactly 10; if rate == 0, exactly 0
        if rate == 0:
            new_lines = []  # no entries
        else:
            target_count = 10
            
            # Merge: common + red + blue unique
            merged = list(entries['common'])
            merged.extend(entries['red'])
            
            seen = set(sp for _, sp in merged)
            for lvl, sp in entries['blue']:
                if sp not in seen and len(merged) < target_count:
                    merged.append((lvl, sp))
                    seen.add(sp)
            
            # If still has room, try harder to add blue species
            for lvl, sp in entries['blue']:
                if sp in seen:
                    continue
                if len(merged) >= target_count:
                    # Replace a duplicate common species
                    for j in range(len(merged)):
                        _, js = merged[j]
                        cnt = sum(1 for _, s in merged if s == js)
                        if cnt >= 2:
                            merged[j] = (lvl, sp)
                            seen.add(sp)
                            break
                else:
                    merged.append((lvl, sp))
                    seen.add(sp)
            
            # Ensure exactly 10 entries (trim if needed)
            merged = merged[:target_count]
            
            new_lines = []
            for lvl, sp in merged:
                new_lines.append(f'{indent}db {lvl:3d}, {sp}\n')
        
        # Rebuild this block
        result = list(lines[:start + 1])
        result.extend(new_lines)
        result.append(lines[end])
        result.extend(lines[end + 1:])
        return result
    
    # Merge grass block
    result = merge_block(gs, ge, 'grass')
    if result is not None:
        lines = result
        # Recalculate water indices after grass change
        ws = None
        we = None
        for i, l in enumerate(lines):
            if 'def_water_wildmons' in l and ('end_grass_wildmons' in lines[i-1] if i > 0 else True):
                ws = i
            if 'end_water_wildmons' in l and ws is not None and i > ws:
                we = i
                break
    
    # Merge water block
    result = merge_block(ws, we, 'water')
    if result is not None:
        lines = result
    
    with open(fpath, 'w') as f:
        f.writelines(lines)
    return True


def merge_version_files():
    count = 0
    for fname in sorted(os.listdir(WILD_DIR)):
        if not fname.endswith('.asm'):
            continue
        fpath = os.path.join(WILD_DIR, fname)
        if merge_file(fpath):
            count += 1
            print(f"  Merged: {fname}")
    print(f"  ({count} files modified)")


# ─── 2. Add missing Pokémon (replacing, never exceeding 10) ────────

ADDITIONS_GRASS = {
    'ViridianForest.asm': [(5, 'BULBASAUR')],
    'Route2.asm': [(5, 'BULBASAUR')],
    'Route24.asm': [(10, 'SQUIRTLE')],
    'Route25.asm': [(10, 'SQUIRTLE')],
    'PowerPlant.asm': [(30, 'JOLTEON')],
    'PokemonMansion1F.asm': [(36, 'FLAREON')],
    'PokemonMansionB1F.asm': [(38, 'FLAREON')],
    'PokemonTower7F.asm': [(30, 'GENGAR')],
    'VictoryRoad3F.asm': [(45, 'MACHAMP'), (45, 'GOLEM')],
    'VictoryRoad1F.asm': [(45, 'HITMONLEE'), (45, 'GOLEM')],
    'VictoryRoad2F.asm': [(42, 'HITMONLEE')],
    'CeruleanCave1F.asm': [(55, 'ALAKAZAM'), (58, 'MACHAMP')],
    'CeruleanCave2F.asm': [(56, 'ALAKAZAM')],
    'CeruleanCaveB1F.asm': [(70, 'MEW')],
    'SafariZoneCenter.asm': [(28, 'HITMONCHAN'), (30, 'KABUTO')],
    'SafariZoneWest.asm': [(28, 'HITMONCHAN'), (30, 'OMANYTE')],
    'SafariZoneEast.asm': [(27, 'HITMONLEE'), (30, 'OMANYTE')],
    'SafariZoneNorth.asm': [(30, 'KABUTO')],
}

ADDITIONS_WATER = {
    'SeaRoutes.asm': [(20, 'HORSEA'), (25, 'SEEL'), (30, 'STARYU'), (35, 'SHELLDER')],
}

def add_to_block(lines, block_name, additions, start_idx, end_idx):
    """Add Pokemon to a block, replacing duplicates, keeping exactly 10 entries."""
    m = re.match(r'^(\s*)', lines[start_idx])
    indent = m.group(1) if m else '\t'
    
    # Parse existing entries
    entries = []
    for i in range(start_idx + 1, end_idx):
        pd = parse_db(lines[i])
        if pd:
            entries.append(pd)
    
    current_sp = set(sp for _, sp in entries)
    if not additions:
        return False
    
    added = 0
    for lvl, sp in additions:
        if sp in current_sp:
            continue
        
        # Try to replace the most duplicated common species
        candidates = [(j, s) for j, (_, s) in enumerate(entries) if s != sp]
        candidates.sort(key=lambda x: -sum(1 for _, s in entries if s == x[1]))
        
        for j, old_sp in candidates:
            cnt = sum(1 for _, s in entries if s == old_sp)
            if cnt >= 2:
                entries[j] = (lvl, sp)
                current_sp.add(sp)
                added += 1
                break
        else:
            # Use last entry as fallback
            entries[-1] = (lvl, sp)
            current_sp.add(sp)
            added += 1
    
    # Ensure exactly 10 (trim or pad as needed)
    target = min(len(entries), 10)
    entries = entries[:10]
    
    # Rebuild lines
    new_block = []
    for lvl, sp in entries:
        new_block.append(f'{indent}db {lvl:3d}, {sp}\n')
    
    # Replace old lines
    lines[start_idx + 1:end_idx] = new_block
    return added > 0


def add_pokemon():
    """Add missing Pokemon replacements to wild files."""
    for fname, additions in ADDITIONS_GRASS.items():
        fpath = os.path.join(WILD_DIR, fname)
        with open(fpath) as f:
            lines = f.readlines()
        
        gs = ge = None
        for i, l in enumerate(lines):
            if 'def_grass_wildmons' in l:
                gs = i
            if 'end_grass_wildmons' in l and gs is not None and i > gs:
                ge = i
                break
        
        if gs is None or ge is None:
            continue
        
        if add_to_block(lines, 'grass', additions, gs, ge):
            with open(fpath, 'w') as f:
                f.writelines(lines)
            print(f"  Added to {fname}: {additions}")
    
    for fname, additions in ADDITIONS_WATER.items():
        fpath = os.path.join(WILD_DIR, fname)
        with open(fpath) as f:
            lines = f.readlines()
        
        ws = we = None
        for i, l in enumerate(lines):
            if 'def_water_wildmons' in l:
                ws = i
            if 'end_water_wildmons' in l and ws is not None and i > ws:
                we = i
                break
        
        if ws is None or we is None:
            print(f"  WARNING: {fname} has no water block")
            continue
        
        if add_to_block(lines, 'water', additions, ws, we):
            with open(fpath, 'w') as f:
                f.writelines(lines)
            print(f"  Added to {fname}: {additions}")


# ─── 3. Scale wild levels +20% ──────────────────────────────────────

def scale_wild_levels():
    for fname in sorted(os.listdir(WILD_DIR)):
        if not fname.endswith('.asm'):
            continue
        fpath = os.path.join(WILD_DIR, fname)
        with open(fpath) as f:
            lines = f.readlines()
        
        changed = 0
        for i, l in enumerate(lines):
            m = re.match(r'^(\s*db\s+)(\d+)(,.*)', l)
            if m:
                new_lvl = scale(int(m.group(2)))
                lines[i] = f'{m.group(1)}{new_lvl:3d}{m.group(3)}\n'
                changed += 1
        
        if changed > 0:
            with open(fpath, 'w') as f:
                f.writelines(lines)
            print(f"  Scaled {changed} entries in {fname}")


# ─── 4. Scale rod levels ───────────────────────────────────────────

def scale_rod_levels():
    for fname in ['good_rod.asm', 'super_rod.asm']:
        fpath = f'/Users/jp/Projects/pokered/data/wild/{fname}'
        with open(fpath) as f:
            lines = f.readlines()
        
        changed = 0
        for i, l in enumerate(lines):
            m = re.match(r'^(\s*db\s+)(\d+)(,.*)', l)
            if m:
                new_lvl = scale(int(m.group(2)))
                lines[i] = f'{m.group(1)}{new_lvl:3d}{m.group(3)}\n'
                changed += 1
        
        if changed > 0:
            with open(fpath, 'w') as f:
                f.writelines(lines)
            print(f"  Scaled {changed} entries in {fname}")


# ─── 5. Scale trainer levels +20% ──────────────────────────────────

def scale_trainer_levels():
    with open(TRAINER_FILE) as f:
        lines = f.readlines()
    
    changed = 0
    for i, l in enumerate(lines):
        indent_len = len(l) - len(l.lstrip())
        indent = l[:indent_len]
        stripped = l[indent_len:]
        if not stripped.startswith('db '):
            continue
        
        rest = stripped[3:].strip()
        comment = ''
        if ';' in rest:
            idx = rest.index(';')
            comment = rest[idx:]
            rest = rest[:idx].strip()
        
        tokens = [t.strip() for t in rest.split(',')]
        if not tokens:
            continue
        
        first = tokens[0]
        
        if first == '$FF':
            new_tokens = ['$FF']
            for j in range(1, len(tokens)):
                if j % 2 == 1 and tokens[j].isdigit():
                    new_tokens.append(str(scale(int(tokens[j]))))
                else:
                    new_tokens.append(tokens[j])
            new_content = ', '.join(new_tokens)
        elif first.isdigit() and not first.startswith('0'):
            new_level = scale(int(first))
            new_content = str(new_level)
            if len(tokens) > 1:
                new_content += ', ' + ', '.join(tokens[1:])
        else:
            continue
        
        lines[i] = f'{indent}db {new_content}'
        if comment:
            lines[i] += f' {comment}'
        lines[i] += '\n'
        changed += 1
    
    with open(TRAINER_FILE, 'w') as f:
        f.writelines(lines)
    print(f"  Scaled {changed} trainer lines")


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("pokered 151 + Level Up")
    print("=" * 60)
    
    print("\n1. Merging RED+BLUE exclusives...")
    merge_version_files()
    
    print("\n2. Adding missing Pokémon...")
    add_pokemon()
    
    print("\n3. Scaling wild levels +20%...")
    scale_wild_levels()
    
    print("\n4. Scaling rod levels +20%...")
    scale_rod_levels()
    
    print("\n5. Scaling trainer levels +20%...")
    scale_trainer_levels()
    
    print("\n✅ Done! Run 'make red' to build the ROM.")
