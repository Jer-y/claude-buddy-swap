#!/usr/bin/env python3
"""claude-buddy-swap — Switch Claude Code /buddy companion to Legendary.

Cross-platform tool (Linux / macOS / Windows) that binary-patches the local
Claude Code executable to force Legendary rarity and select your companion's
species, hat, and stat distribution.

Requirements: Python 3.8+, Bun (for --list leaderboard only)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Paths (same on all platforms — Claude Code uses ~/.local/share/...) ──────

HOME = Path.home()
VERSIONS_DIR = HOME / ".local" / "share" / "claude" / "versions"
CLAUDE_JSON = HOME / ".claude.json"
BIN_DIR = HOME / ".local" / "bin"
IS_WINDOWS = sys.platform == "win32"
BINARY_NAME = "claude.exe" if IS_WINDOWS else "claude"

STAT_NAMES = ["DEBUGGING", "PATIENCE", "CHAOS", "WISDOM", "SNARK"]

# ── Colored output ───────────────────────────────────────────────────────────

_color_enabled = None

def _supports_color():
    global _color_enabled
    if _color_enabled is not None:
        return _color_enabled
    if IS_WINDOWS:
        os.system("")  # enable VT100 on Windows 10+
        _color_enabled = True
    else:
        _color_enabled = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return _color_enabled

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _supports_color() else text

def red(msg):    print(_c("31", msg))
def green(msg):  print(_c("32", msg))
def yellow(msg): print(_c("33", msg))
def cyan(msg):   print(_c("36", msg))
def bold(msg):   print(_c("1", msg))

# ── Binary discovery ─────────────────────────────────────────────────────────

def find_binary():
    """Locate the active Claude Code binary."""
    entry = BIN_DIR / BINARY_NAME
    if entry.exists():
        try:
            resolved = entry.resolve()
            if resolved.exists():
                return resolved
        except OSError:
            pass
        return entry

    # Fallback: newest version file in the versions directory
    if VERSIONS_DIR.is_dir():
        candidates = []
        for f in VERSIONS_DIR.iterdir():
            name = f.name
            if name[0].isdigit() and "." not in name and f.is_file():
                candidates.append(f)
            elif IS_WINDOWS and name[0].isdigit() and name.endswith(".exe") and f.is_file():
                candidates.append(f)
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return None

def ensure_original(binary):
    """Create a .original backup if it doesn't exist. Returns backup path."""
    original = binary.parent / (binary.name + ".original")
    if not original.exists():
        shutil.copy2(binary, original)
        cyan(f"  Backed up original binary → {original.name}")
    return original

def check_running(binary):
    """Check whether the binary is currently in use."""
    if IS_WINDOWS:
        try:
            with open(binary, "r+b"):
                pass
            return False
        except (PermissionError, OSError):
            return True
    else:
        try:
            result = subprocess.run(
                ["fuser", str(binary)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # fuser not available (some macOS installs) — try file lock
            try:
                with open(binary, "r+b"):
                    pass
                return False
            except (PermissionError, OSError):
                return True

# ── Patch logic ──────────────────────────────────────────────────────────────

OLD_WEIGHTS = b"common:60,uncommon:25,rare:10,epic:4,legendary:1"
NEW_WEIGHTS = b"common: 0,uncommon: 0,rare: 0,epic:0,legendary:1"

OLD_STATS_BODY = (
    b"let q=pE4[$],K=jvH(H,bi),_=jvH(H,bi);while(_===K)_=jvH(H,bi);"
    b"let f={};for(let A of bi)if(A===K)f[A]=Math.min(100,q+50+Math.floor(H()*30));"
    b"else if(A===_)f[A]=Math.max(1,q-10+Math.floor(H()*15));"
    b"else f[A]=q+Math.floor(H()*40)"
)

def _pad_body(core: bytes) -> bytes:
    """Pad a replacement stats body to match OLD_STATS_BODY length."""
    target_len = len(OLD_STATS_BODY)
    body = core
    pad = target_len - len(body)
    assert pad >= 0, f"Replacement body too long: {len(body)} > {target_len}"
    while pad >= 4:
        body += b";H()"
        pad -= 4
    if pad == 3:
        body += b";0;"
    elif pad == 2:
        body += b";0"
    elif pad == 1:
        body += b";"
    assert len(body) == target_len, f"Padding failed: {len(body)} != {target_len}"
    return body

def patch_binary(path, salt_num, maxstats=False, peak_stats=None):
    """Apply weight, salt, and optional stats patches to the binary."""
    data = path.read_bytes()
    changes = []

    # 1. Patch rarity weights
    if data.count(OLD_WEIGHTS) > 0:
        data = data.replace(OLD_WEIGHTS, NEW_WEIGHTS)
        changes.append("weights → legendary 100%")
    elif data.count(NEW_WEIGHTS) > 0:
        changes.append("weights already patched")
    else:
        red("ERROR: weight pattern not found in binary")
        sys.exit(1)

    # 2. Patch salt
    digits = len(salt_num)
    if digits == 3:
        new_salt = f"friend-2026-{salt_num}".encode()
    elif digits == 4:
        new_salt = f"friend2026-{salt_num}".encode()
    else:
        red(f"ERROR: salt must be 3-4 digits, got {digits}")
        sys.exit(1)

    assert len(new_salt) == 15, f"Salt length error: {len(new_salt)}"

    found = {s for s in re.findall(rb"friend-?2026-\d{3,4}", data) if len(s) == 15}
    for old_salt in found:
        if old_salt != new_salt:
            data = data.replace(old_salt, new_salt)
            changes.append(f"salt {old_salt.decode()} → {new_salt.decode()}")
    if not found:
        red("ERROR: no salt pattern found in binary")
        sys.exit(1)
    changes.append(f"final salt: {new_salt.decode()}")

    # 3. Patch stats
    new_body = None

    if maxstats:
        new_body = _pad_body(b"let f={};for(let A of bi)f[A]=100")
        label = "all stats → 100"

    elif peak_stats:
        names = [s.upper() for s in peak_stats]
        indices = []
        for n in names:
            if n not in STAT_NAMES:
                red(f'ERROR: unknown stat "{n}", valid: {STAT_NAMES}')
                sys.exit(1)
            indices.append(STAT_NAMES.index(n))

        if len(indices) == 5:
            new_body = _pad_body(b"let f={};for(let A of bi)f[A]=100")
            label = "all stats → 100"
        else:
            cond = "||".join(f"A===bi[{i}]" for i in indices)
            core = (
                f"let q=pE4[$],_=jvH(H,bi);let f={{}};"
                f"for(let A of bi)"
                f"if({cond})f[A]=100;"
                f"else if(A===_)f[A]=Math.max(1,q-10+Math.floor(H()*15));"
                f"else f[A]=q+Math.floor(H()*40)"
            ).encode()
            new_body = _pad_body(core)
            label = ", ".join(names) + " → 100 (rest random)"

    if new_body is not None:
        count = data.count(OLD_STATS_BODY)
        if count > 0:
            data = data.replace(OLD_STATS_BODY, new_body)
            changes.append(f"stats: {label} ({count}x)")
        else:
            yellow("WARNING: rollStats body not found, stats not patched")

    path.write_bytes(data)
    for c in changes:
        print(f"  {c}")

# ── Companion management ─────────────────────────────────────────────────────

def clear_companion():
    """Remove stored companion soul from config to trigger re-hatch."""
    if not CLAUDE_JSON.exists():
        return
    try:
        config = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if "companion" in config:
        old_name = config["companion"].get("name", "?")
        del config["companion"]
        CLAUDE_JSON.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"  Cleared companion: {old_name}")
    else:
        print("  No companion data to clear")

def show_current():
    """Display current companion status."""
    binary = find_binary()
    if not binary:
        red("Claude binary not found")
        sys.exit(1)

    data = binary.read_bytes()
    patched = data.count(NEW_WEIGHTS) > 0
    salts = {s.decode() for s in re.findall(rb"friend-?2026-\d{3,4}", data) if len(s) == 15}
    salt = salts.pop() if salts else "?"

    name = personality = "(not hatched)"
    try:
        config = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        if "companion" in config:
            name = config["companion"].get("name", "?")
            personality = config["companion"].get("personality", "?")
    except (json.JSONDecodeError, OSError, KeyError):
        pass

    print(f"  Binary:      {binary}")
    print(f"  Patched:     {'yes (legendary 100%)' if patched else 'no (original weights)'}")
    print(f"  Salt:        {salt}")
    print(f"  Name:        {name}")
    print(f"  Personality: {personality}")

# ── Leaderboard ──────────────────────────────────────────────────────────────

# The Bun JS code for leaderboard simulation (identical on all platforms)
LEADERBOARD_JS = r"""
const SPECIES = ['duck','goose','blob','cat','dragon','octopus','owl','penguin',
                 'turtle','snail','ghost','axolotl','capybara','cactus','robot',
                 'rabbit','mushroom','chonk'];
const RARITIES = ['common','uncommon','rare','epic','legendary'];
const WEIGHTS = {common:0,uncommon:0,rare:0,epic:0,legendary:1};
const EYES = ['·','✦','×','◉','@','°'];
const HATS = ['none','crown','tophat','propeller','halo','wizard','beanie','tinyduck'];
const STAT_NAMES = ['DEBUGGING','PATIENCE','CHAOS','WISDOM','SNARK'];
const EMOJI = {duck:'🦆',goose:'🪿',blob:'🫠',cat:'🐱',dragon:'🐉',octopus:'🐙',owl:'🦉',penguin:'🐧',turtle:'🐢',snail:'🐌',ghost:'👻',axolotl:'🦎',capybara:'🦫',cactus:'🌵',robot:'🤖',rabbit:'🐰',mushroom:'🍄',chonk:'🐈'};
const HAT_EMOJI = {none:'—',crown:'👑',tophat:'🎩',propeller:'🧢',halo:'😇',wizard:'🧙',beanie:'🧶',tinyduck:'🐤'};

function hashString(s) { return Number(BigInt(Bun.hash(s)) & 0xffffffffn); }
function mulberry32(seed) {
  let a = seed >>> 0;
  return function() { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function pick(rng, arr) { return arr[Math.floor(rng() * arr.length)]; }
function rollRarity(rng) { let total = Object.values(WEIGHTS).reduce((a,b)=>a+b,0), roll = rng()*total;
  for (const r of RARITIES) { roll -= WEIGHTS[r]; if (roll<0) return r; } return 'common'; }
function rollStats(rng, rarity) {
  const floor = {common:5,uncommon:15,rare:25,epic:35,legendary:50}[rarity];
  const peak = pick(rng, STAT_NAMES);
  let dump = pick(rng, STAT_NAMES);
  while (dump === peak) dump = pick(rng, STAT_NAMES);
  const stats = {};
  for (const name of STAT_NAMES) {
    if (name === peak) stats[name] = Math.min(100, floor + 50 + Math.floor(rng() * 30));
    else if (name === dump) stats[name] = Math.max(1, floor - 10 + Math.floor(rng() * 15));
    else stats[name] = floor + Math.floor(rng() * 40);
  }
  return stats;
}
function simulate(userId, saltStr) {
  const key = userId + saltStr, seed = hashString(key), rng = mulberry32(seed);
  const rarity = rollRarity(rng), species = pick(rng, SPECIES), eye = pick(rng, EYES);
  const hat = rarity==='common'?'none':pick(rng,HATS), shiny = rng()<0.01;
  const stats = rollStats(rng, rarity);
  return { rarity, species, eye, hat, shiny, stats };
}

const userId = process.argv[1] || 'anon';
const sortBy = process.argv[2] || 'total';
const filterSpecies = process.argv[3] || '';
const limit = parseInt(process.argv[4] || '30');

const results = [];
for (let i = 401; i < 1000; i++) {
  const r = simulate(userId, 'friend-2026-' + i);
  results.push({ salt: i, ...r });
}
for (let i = 1000; i < 10000; i++) {
  const salt = 'friend2026-' + i;
  if (salt.length !== 15) continue;
  results.push({ salt: i, ...simulate(userId, salt) });
}

const scored = results.map(r => {
  const s = r.stats;
  const dpw = s.DEBUGGING + s.PATIENCE + s.WISDOM;
  const score = dpw - s.CHAOS - s.SNARK;
  const total = Object.values(s).reduce((a,b)=>a+b, 0);
  return { ...r, dpw, score, total };
});

let filtered = filterSpecies
  ? scored.filter(r => r.species === filterSpecies)
  : scored;

if (sortBy === 'score')      filtered.sort((a, b) => b.score - a.score);
else if (sortBy === 'dpw')   filtered.sort((a, b) => b.dpw - a.dpw);
else if (sortBy === 'total') filtered.sort((a, b) => b.total - a.total);
else if (sortBy === 'chaos') filtered.sort((a, b) => a.stats.CHAOS - b.stats.CHAOS);

const title = filterSpecies
  ? `${EMOJI[filterSpecies] || ''} ${filterSpecies} ranking`
  : { score: 'Best overall (high D+P+W, low CHAOS+SNARK)',
      dpw: 'Highest D+P+W sum',
      total: 'Highest total stats',
      chaos: 'Lowest CHAOS' }[sortBy] || 'Ranking';

const showDpw = sortBy === 'dpw' || sortBy === 'score';

console.log(`🏆 ${title}`);
console.log('');
if (showDpw) {
  console.log('  #   SALT   Species       Eye  Hat           DEBUG PATCE [CHA] WISDM [SNK]  D+P+W');
} else {
  console.log('  #   SALT   Species       Eye  Hat           DEBUG PATCE CHAOS WISDM SNARK  Total');
}
console.log('  ' + '─'.repeat(82));

const shown = filtered.slice(0, limit);
for (let i = 0; i < shown.length; i++) {
  const r = shown[i];
  const s = r.stats;
  const emoji = EMOJI[r.species] || '  ';
  const hatE = HAT_EMOJI[r.hat] || '  ';
  const shiny = r.shiny ? ' ✨' : '';
  let line = String(i+1).padStart(3) + '  ' + String(r.salt).padStart(5) + '   ' +
    emoji + ' ' + r.species.padEnd(10) +
    r.eye.padStart(3) + '  ' + hatE + ' ' + r.hat.padEnd(10);
  if (showDpw) {
    line += String(s.DEBUGGING).padStart(5) + String(s.PATIENCE).padStart(6) +
      '  [' + String(s.CHAOS).padStart(2) + ']' +
      String(s.WISDOM).padStart(6) +
      '  [' + String(s.SNARK).padStart(2) + ']' +
      String(r.dpw).padStart(7);
  } else {
    line += String(s.DEBUGGING).padStart(5) + String(s.PATIENCE).padStart(6) +
      String(s.CHAOS).padStart(6) +
      String(s.WISDOM).padStart(6) +
      String(s.SNARK).padStart(6) +
      String(r.total).padStart(7);
  }
  console.log(line + shiny);
}

console.log('');
console.log('  Usage: claude-buddy-swap <SALT>');
if (!filterSpecies) {
  console.log('  Filter: --list [--sort score|dpw|total|chaos] [--species dragon] [--top N]');
}
"""

def find_bun():
    """Locate bun binary (needed for --list only)."""
    candidates = [
        HOME / ".bun" / "bin" / ("bun.exe" if IS_WINDOWS else "bun"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    found = shutil.which("bun")
    if found:
        return found
    return None

def get_user_id():
    """Read userId from Claude config."""
    try:
        config = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
        return config.get("userID", config.get("userId", "anon"))
    except (json.JSONDecodeError, OSError):
        return "anon"

def show_list(sort_by="total", species="", top=30):
    """Display companion leaderboard using Bun for hash simulation."""
    bun = find_bun()
    if not bun:
        red("Bun is required for --list leaderboard")
        red(f"Expected at: {HOME / '.bun' / 'bin' / 'bun'}")
        red("Install: https://bun.sh")
        sys.exit(1)

    user_id = get_user_id()
    try:
        subprocess.run(
            [bun, "-e", LEADERBOARD_JS, user_id, sort_by, species, str(top)],
            check=True,
        )
    except subprocess.CalledProcessError:
        red("Leaderboard generation failed")
        sys.exit(1)

# ── Restore ──────────────────────────────────────────────────────────────────

def do_restore():
    """Restore original unpatched binary."""
    binary = find_binary()
    if not binary:
        red("Claude binary not found")
        sys.exit(1)
    original = binary.parent / (binary.name + ".original")
    if not original.exists():
        red(f"Original backup not found: {original}")
        sys.exit(1)
    if check_running(binary):
        red("Claude is running. Please exit Claude first (Ctrl+C or /exit)")
        sys.exit(1)
    shutil.copy2(original, binary)
    if not IS_WINDOWS:
        os.chmod(binary, 0o755)
    clear_companion()
    green("Restored to original binary")

# ── Swap (main action) ──────────────────────────────────────────────────────

def do_swap(salt, maxstats=False, peak=None):
    """Full swap: backup → copy clean → patch → clear companion."""
    binary = find_binary()
    if not binary:
        red("Claude binary not found")
        sys.exit(1)

    desc = f"salt {salt}"
    if maxstats:
        desc += " (all stats 100)"
    elif peak:
        desc += f" ({','.join(s.upper() for s in peak)}=100)"

    bold(f"Swapping companion → {desc}")
    print()

    if check_running(binary):
        red("Claude is running — cannot patch the binary")
        print()
        yellow("Please exit Claude first, then re-run this script")
        sys.exit(1)

    cyan("[1/3] Checking backup...")
    original = ensure_original(binary)

    cyan("[2/3] Patching binary...")
    shutil.copy2(original, binary)
    if not IS_WINDOWS:
        os.chmod(binary, 0o755)
    patch_binary(binary, salt, maxstats=maxstats, peak_stats=peak)

    cyan("[3/3] Clearing old companion data...")
    clear_companion()

    print()
    green("Done! Launch claude and type /buddy to hatch your new companion")

# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="claude-buddy-swap",
        description="Switch Claude Code /buddy companion to ★★★★★ Legendary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s 9187                              Swap companion
  %(prog)s 9187 --maxstats                   Swap + all 5 stats = 100
  %(prog)s 9187 --peak WISDOM                Pin WISDOM = 100
  %(prog)s 9187 --peak DEBUGGING WISDOM PATIENCE
                                             Pin multiple stats = 100
  %(prog)s --list                            Leaderboard (default top 30)
  %(prog)s --list --top 50                   Show top 50
  %(prog)s --list --sort dpw                 Sort by D+P+W
  %(prog)s --list --species dragon           Filter by species
  %(prog)s --current                         Show current companion
  %(prog)s --restore                         Restore original binary
""",
    )

    # Mode flags (mutually exclusive top-level actions)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--list", "-l", action="store_true", help="Show leaderboard")
    mode.add_argument("--current", "-c", action="store_true", help="Show current companion")
    mode.add_argument("--restore", "-r", action="store_true", help="Restore original binary")

    # Salt (positional, optional for --list/--current/--restore)
    p.add_argument("salt", nargs="?", metavar="SALT", help="3-4 digit salt number")

    # Stat options
    p.add_argument("--maxstats", action="store_true", help="Set all 5 stats to 100")
    p.add_argument("--peak", nargs="+", metavar="STAT",
                   help="Pin specific stat(s) to 100 (e.g. WISDOM DEBUGGING)")

    # List options
    p.add_argument("--sort", choices=["score", "dpw", "total", "chaos"], default="total",
                   help="Sort order for --list (default: total)")
    p.add_argument("--species", default="", help="Filter --list by species name")
    p.add_argument("--top", type=int, default=30, help="Number of results for --list")

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        show_list(sort_by=args.sort, species=args.species, top=args.top)
    elif args.current:
        cyan("Current companion:")
        show_current()
    elif args.restore:
        do_restore()
    elif args.salt:
        if not re.match(r"^\d{3,4}$", args.salt):
            red(f"ERROR: salt must be 3-4 digits, got: {args.salt}")
            print("  Try: claude-buddy-swap --list")
            sys.exit(1)
        do_swap(args.salt, maxstats=args.maxstats, peak=args.peak)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
