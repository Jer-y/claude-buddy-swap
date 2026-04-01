# claude-buddy-swap

Switch your Claude Code `/buddy` companion to ★★★★★ Legendary with full control over species, hat, and stat distribution.

> **[中文版](README.md)**

---

## What is this

Claude Code launched a `/buddy` companion system on April 1, 2026 — a gacha-style system that deterministically generates a pet from your user ID. The rarity probabilities are:

| Rarity | Probability |
|--------|------------|
| Common | 60% |
| Uncommon | 25% |
| Rare | 10% |
| Epic | 4% |
| **Legendary** | **1%** |

This tool binary-patches the local Claude Code executable to modify the rarity weight table and PRNG seed, allowing you to:

- **Force Legendary rarity** (100%)
- **Choose your species combo** — swap the salt value to "re-roll"
- **Browse full leaderboards** — sort/filter by total stats, D+P+W, CHAOS, etc.

## How it works

```
Companion generation pipeline:

userId + SALT("friend-2026-401")
    → Bun.hash (Wyhash)
    → Mulberry32 PRNG seed
    → rollRarity()  ← weight table patch point
    → rollSpecies()
    → rollEye() → rollHat() → rollShiny()
    → rollStats(peak, dump, normals)
```

The script performs two equal-length byte replacements (binary-safe, no file size change):

**1. Rarity weights** (48 bytes)
```
original: common:60,uncommon:25,rare:10,epic:4,legendary:1
patched:  common: 0,uncommon: 0,rare: 0,epic:0,legendary:1
```

**2. PRNG Salt** (15 bytes)
```
friend-2026-401  →  friend-2026-XXX  (3-digit salt)
friend-2026-401  →  friend2026-XXXX  (4-digit salt, one hyphen removed to keep length)
```

The companion's "bones" (species, rarity, stats) are regenerated from `hash(userId + salt)` on every launch — never stored in config. Only the "soul" (name, personality) is persisted in `~/.claude.json`. After changing the salt, the old soul must be cleared to trigger a re-hatch.

## Installation

```bash
# Clone the repo
git clone https://github.com/Jer-y/claude-buddy-swap.git
cd claude-buddy-swap
```

### Requirements

- **Python 3.8+**
- **Claude Code** — binary installed at `~/.local/share/claude/versions/`
- **Bun** (optional) — only needed for `--list` leaderboard (uses `Bun.hash` for Wyhash simulation)

## Quick start

```bash
# Show help
python3 claude-buddy-swap.py -h

# 1. Browse the leaderboard and pick a salt
python3 claude-buddy-swap.py --list

# 2. Exit Claude Code (required — the binary can't be overwritten while running)

# 3. Swap
python3 claude-buddy-swap.py 9187
```

Then launch Claude Code and type `/buddy` to hatch your new companion.

## Usage

### Swap companion

```bash
# Basic: choose species (stats are random)
python3 claude-buddy-swap.py 9187

# Pin one or more stats to 100 (rest stay random)
python3 claude-buddy-swap.py 9187 --peak WISDOM
python3 claude-buddy-swap.py 9187 --peak DEBUGGING WISDOM PATIENCE

# All 5 stats = 100
python3 claude-buddy-swap.py 9187 --maxstats
```

`--peak` accepts: `DEBUGGING`, `PATIENCE`, `CHAOS`, `WISDOM`, `SNARK` — space-separated, any combination.

The script automatically handles the full flow: back up original binary → copy from clean backup → patch weights + salt → clear old companion soul.

### Browse leaderboard

```bash
# Default: sort by total stats (top 30)
python3 claude-buddy-swap.py --list

# Show top 50
python3 claude-buddy-swap.py --list --top 50

# Sort by D+P+W (CHAOS and SNARK shown as secondary)
python3 claude-buddy-swap.py --list --sort dpw

# Sort by composite score (high D+P+W, low CHAOS+SNARK)
python3 claude-buddy-swap.py --list --sort score

# Sort by CHAOS ascending
python3 claude-buddy-swap.py --list --sort chaos

# Filter by species
python3 claude-buddy-swap.py --list --species dragon
python3 claude-buddy-swap.py --list --species robot --top 10
```

### Other commands

```bash
# Show current companion status
python3 claude-buddy-swap.py --current

# Restore original unpatched binary
python3 claude-buddy-swap.py --restore

# Show full help
python3 claude-buddy-swap.py -h
```

> **Tip:** You can add the script to your PATH for convenience:
> ```bash
> # Linux / macOS
> cp claude-buddy-swap.py ~/.local/bin/claude-buddy-swap
> chmod +x ~/.local/bin/claude-buddy-swap
> # Then just use:
> claude-buddy-swap --list
> ```
>
> **Windows (PowerShell):**
> ```powershell
> python claude-buddy-swap.py --list
> ```

## Stats

Each Legendary companion has 5 stats: 1 peak stat (always 100), 1 dump stat (40-54), and 3 normal stats (50-89):

| Stat | Description | Effect on companion |
|------|-------------|-------------------|
| **DEBUGGING** | Debugging skill | High → more likely to spot bugs |
| **PATIENCE** | Patience | High → calmer, more tolerant |
| **CHAOS** | Chaos level | High → more random, unpredictable reactions |
| **WISDOM** | Wisdom | High → deeper, more insightful comments |
| **SNARK** | Snarkiness | High → more likely to roast your code |

Stats are sent to Anthropic's `buddy_react` API, where the server-side AI uses them to flavor the companion's speech bubble quips. This is a soft influence, not hard-coded behavior.

## Species (18 total)

| | | | |
|---|---|---|---|
| 🦆 duck | 🪿 goose | 🫠 blob | 🐱 cat |
| 🐉 dragon | 🐙 octopus | 🦉 owl | 🐧 penguin |
| 🐢 turtle | 🐌 snail | 👻 ghost | 🦎 axolotl |
| 🦫 capybara | 🌵 cactus | 🤖 robot | 🐰 rabbit |
| 🍄 mushroom | 🐈 chonk | | |

## Hats

Legendary companions always get a hat (Common gets none):

| Hat | ASCII |
|-----|-------|
| 👑 crown | `\^^^/` |
| 🎩 tophat | `[___]` |
| 🧢 propeller | `-+-` |
| 😇 halo | `(   )` |
| 🧙 wizard | `/^\` |
| 🧶 beanie | `(___)` |
| 🐤 tinyduck | `,>` |

## Notes

- **Updates:** `claude --update` downloads a fresh binary, wiping the patch. Re-run `claude-buddy-swap <SALT>` after each update.
- **Client-side only:** All companion data is local. The server does not validate rarity — no ban risk.
- **Deterministic:** The same userId + salt always produces the same companion. The `--list` leaderboard is personalized to your userId.
- **Salt length:** Must stay at 15 bytes. 3-digit salts use `friend-2026-XXX`, 4-digit salts use `friend2026-XXXX` (one hyphen removed).

## License

MIT
