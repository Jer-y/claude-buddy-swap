# claude-buddy-swap

一键切换 Claude Code `/buddy` 宠物为 ★★★★★ Legendary，并自由选择物种、帽子和属性分配。

Switch your Claude Code `/buddy` companion to ★★★★★ Legendary with full control over species, hat, and stat distribution.

---

## 这是什么 / What is this

Claude Code 在 2026 年 4 月 1 日上线了 `/buddy` 宠物系统 —— 一个基于用户 ID 确定性抽卡的 gacha 机制。每个用户绑定唯一的宠物，稀有度概率如下：

Claude Code launched a `/buddy` companion system on April 1, 2026 — a gacha-style system that deterministically generates a pet from your user ID. The rarity probabilities are:

| Rarity | Probability |
|--------|------------|
| Common | 60% |
| Uncommon | 25% |
| Rare | 10% |
| Epic | 4% |
| **Legendary** | **1%** |

本工具通过 binary patch 修改本地 Claude Code 二进制文件中的权重表和 PRNG seed，让你：

This tool binary-patches the local Claude Code executable to modify the rarity weight table and PRNG seed, allowing you to:

- **强制 Legendary 稀有度** (100%)
- **自由选择物种组合** — 通过更换 salt 值来"重新抽卡"
- **浏览完整排行榜** — 按总属性、D+P+W、CHAOS 等维度排序筛选

## 原理 / How it works

```
宠物生成流程 / Companion generation pipeline:

userId + SALT("friend-2026-401")
    → Bun.hash (Wyhash)
    → Mulberry32 PRNG seed
    → rollRarity()  ← 权重表 patch 点
    → rollSpecies()
    → rollEye() → rollHat() → rollShiny()
    → rollStats(peak, dump, normals)
```

脚本做了两处等长字节替换 (binary-safe, 不改变文件大小)：

The script performs two equal-length byte replacements (binary-safe, no file size change):

**1. 权重表 / Rarity weights** (48 bytes)
```
common:60,uncommon:25,rare:10,epic:4,legendary:1
common: 0,uncommon: 0,rare: 0,epic:0,legendary:1
```

**2. PRNG Salt** (15 bytes)
```
friend-2026-401  →  friend-2026-XXX  (3-digit)
friend-2026-401  →  friend2026-XXXX  (4-digit, 去掉一个连字符)
```

宠物的"骨架"(物种、稀有度、属性) 每次启动都从 `hash(userId + salt)` 重新计算，不存储在配置文件中。只有"灵魂"(名字、性格描述) 存储在 `~/.claude.json` 中。因此更换 salt 后需要同时清除旧灵魂数据让系统重新孵化。

The companion's "bones" (species, rarity, stats) are regenerated from `hash(userId + salt)` on every launch — never stored in config. Only the "soul" (name, personality) is persisted in `~/.claude.json`. After changing the salt, the old soul must be cleared to trigger a re-hatch.

## 安装 / Installation

```bash
# 复制到 PATH 中 / Copy to your PATH
cp claude-buddy-swap ~/.local/bin/
chmod +x ~/.local/bin/claude-buddy-swap
```

### 依赖 / Requirements

- **Claude Code** (Linux, Bun-compiled binary at `~/.local/share/claude/versions/`)
- **Bun** (`~/.bun/bin/bun`) — 用于 `--list` 排行榜计算（需要 `Bun.hash` 来精确模拟 Wyhash）
- **Python 3** — 用于二进制 patch 和配置文件操作
- **fuser** (procps) — 用于检测 Claude 是否在运行

## 用法 / Usage

> **重要 / Important:** 必须先退出 Claude Code 再运行本脚本（二进制在运行时无法被覆写）。
>
> You must exit Claude Code before running this script (the binary cannot be overwritten while running).

### 切换宠物 / Switch companion

```bash
claude-buddy-swap 9187
```

脚本会自动完成：备份原始二进制 → 从干净备份复制 → patch 权重 + salt → 清除旧宠物灵魂。

The script automatically: backs up the original binary → copies from clean backup → patches weights + salt → clears old companion soul.

启动 Claude Code 后输入 `/buddy` 即可孵化新宠物。

After launching Claude Code, type `/buddy` to hatch your new companion.

### 浏览排行榜 / Browse rankings

```bash
# 默认按五维总属性排序 / Default: sort by total stats
claude-buddy-swap --list

# 前 50 名 / Top 50
claude-buddy-swap --list --top 50

# 按 D+P+W 排序 (CHAOS 和 SNARK 标记为次要)
# Sort by D+P+W (CHAOS and SNARK shown as secondary)
claude-buddy-swap --list --sort dpw

# 按综合评分排序 (D+P+W 高, CHAOS+SNARK 低)
# Sort by composite score (high D+P+W, low CHAOS+SNARK)
claude-buddy-swap --list --sort score

# 按 CHAOS 从低到高 / Sort by CHAOS ascending
claude-buddy-swap --list --sort chaos

# 只看某个物种 / Filter by species
claude-buddy-swap --list --species dragon
claude-buddy-swap --list --species robot --top 10
```

### 查看当前状态 / Check current status

```bash
claude-buddy-swap --current
```

### 恢复原始版本 / Restore original

```bash
claude-buddy-swap --restore
```

## 五维属性 / Stats

每只 Legendary 宠物有 5 个属性，其中 1 个为 peak stat (固定 100)，1 个为 dump stat (40-54)，其余 3 个为普通值 (50-89)：

Each Legendary companion has 5 stats: 1 peak stat (always 100), 1 dump stat (40-54), and 3 normal stats (50-89):

| Stat | Description (CN) | Description (EN) | Effect on companion |
|------|------------------|-------------------|-------------------|
| **DEBUGGING** | 调试能力 | Debugging skill | 高 → 更关注代码问题 / High → more likely to spot bugs |
| **PATIENCE** | 耐心 | Patience | 高 → 更温和淡定 / High → calmer, more tolerant |
| **CHAOS** | 混乱程度 | Chaos level | 高 → 反应更随机跳脱 / High → more random, unpredictable |
| **WISDOM** | 智慧 | Wisdom | 高 → 评论更有深度 / High → deeper, more insightful comments |
| **SNARK** | 毒舌 | Snarkiness | 高 → 更容易嘲讽你的代码 / High → more likely to roast your code |

属性值通过 `buddy_react` API 发送到 Anthropic 服务端，服务端 AI 根据这些值生成对应风格的气泡台词。这是 soft influence，不是硬编码规则。

Stats are sent to Anthropic's `buddy_react` API, where the server-side AI uses them to flavor the companion's speech bubble quips. This is a soft influence, not hard-coded behavior.

## 物种列表 / Species

共 18 种，每种有 3 帧 ASCII 动画：

18 species total, each with 3-frame ASCII animations:

| | | | |
|---|---|---|---|
| 🦆 duck | 🪿 goose | 🫠 blob | 🐱 cat |
| 🐉 dragon | 🐙 octopus | 🦉 owl | 🐧 penguin |
| 🐢 turtle | 🐌 snail | 👻 ghost | 🦎 axolotl |
| 🦫 capybara | 🌵 cactus | 🤖 robot | 🐰 rabbit |
| 🍄 mushroom | 🐈 chonk | | |

## 帽子 / Hats

非 Common 稀有度可以戴帽子 (Legendary 必定有帽子)：

Non-Common rarities can wear hats (Legendary always gets one):

| Hat | Display |
|-----|---------|
| 👑 crown | `\^^^/` |
| 🎩 tophat | `[___]` |
| 🧢 propeller | `-+-` |
| 😇 halo | `(   )` |
| 🧙 wizard | `/^\` |
| 🧶 beanie | `(___)` |
| 🐤 tinyduck | `,>` |

## 注意事项 / Notes

- **版本更新 / Updates:** `claude --update` 会下载全新二进制，patch 会丢失。更新后需重新运行 `claude-buddy-swap <SALT>`。
- **纯客户端 / Client-side only:** 宠物数据完全在本地，服务端不校验稀有度，无封号风险。
- **确定性 / Deterministic:** 相同的 userId + salt 永远生成相同的宠物。`--list` 的结果是你的专属排行榜（绑定你的 userId）。
- **Salt 长度 / Salt length:** 必须保持 15 字节。3 位数用 `friend-2026-XXX`，4 位数用 `friend2026-XXXX`（去掉一个连字符）。

## License

MIT
