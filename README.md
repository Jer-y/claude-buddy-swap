# claude-buddy-swap

一键切换 Claude Code `/buddy` 宠物为 ★★★★★ Legendary，并自由选择物种、帽子和属性分配。

> **[English Version](README_EN.md)**

---

## 这是什么

Claude Code 在 2026 年 4 月 1 日上线了 `/buddy` 宠物系统 —— 一个基于用户 ID 确定性抽卡的 gacha 机制。每个用户绑定唯一的宠物，稀有度概率如下：

| 稀有度 | 概率 |
|--------|------|
| Common | 60% |
| Uncommon | 25% |
| Rare | 10% |
| Epic | 4% |
| **Legendary** | **1%** |

本工具通过 binary patch 修改本地 Claude Code 二进制文件中的权重表和 PRNG seed，让你：

- **强制 Legendary 稀有度** (100%)
- **自由选择物种组合** — 通过更换 salt 值来"重新抽卡"
- **浏览完整排行榜** — 按总属性、D+P+W、CHAOS 等维度排序筛选

## 原理

```
宠物生成流程:

userId + SALT("friend-2026-401")
    → Bun.hash (Wyhash)
    → Mulberry32 PRNG seed
    → rollRarity()  ← 权重表 patch 点
    → rollSpecies()
    → rollEye() → rollHat() → rollShiny()
    → rollStats(peak, dump, normals)
```

脚本做了两处等长字节替换（不改变文件大小）：

**1. 权重表** (48 bytes)
```
原始: common:60,uncommon:25,rare:10,epic:4,legendary:1
修改: common: 0,uncommon: 0,rare: 0,epic:0,legendary:1
```

**2. PRNG Salt** (15 bytes)
```
friend-2026-401  →  friend-2026-XXX  (3位数 salt)
friend-2026-401  →  friend2026-XXXX  (4位数 salt, 去掉一个连字符保持等长)
```

宠物的"骨架"（物种、稀有度、属性）每次启动都从 `hash(userId + salt)` 重新计算，不存储在配置文件中。只有"灵魂"（名字、性格描述）存储在 `~/.claude.json` 中。因此更换 salt 后需要同时清除旧灵魂数据让系统重新孵化。

## 安装

```bash
cp claude-buddy-swap ~/.local/bin/
chmod +x ~/.local/bin/claude-buddy-swap
```

### 依赖

- **Claude Code** — Linux，Bun 编译的二进制文件，位于 `~/.local/share/claude/versions/`
- **Bun** (`~/.bun/bin/bun`) — 用于 `--list` 排行榜计算（需要 `Bun.hash` 精确模拟 Wyhash）
- **Python 3** — 用于二进制 patch 和配置文件操作
- **fuser** (procps) — 用于检测 Claude 是否在运行

## 用法

> **重要：** 必须先退出 Claude Code 再运行本脚本（二进制在运行时无法被覆写）。

### 切换宠物

```bash
# 基础：只选物种（属性随机）
claude-buddy-swap 9187

# 指定某个属性为 100（其余随机）
claude-buddy-swap 9187 --peak WISDOM

# 五维全部 100
claude-buddy-swap 9187 --maxstats
```

`--peak` 支持的属性名：`DEBUGGING`、`PATIENCE`、`CHAOS`、`WISDOM`、`SNARK`

脚本会自动完成：备份原始二进制 → 从干净备份复制 → patch 权重和 salt → 清除旧宠物灵魂。

启动 Claude Code 后输入 `/buddy` 即可孵化新宠物。

### 浏览排行榜

```bash
# 默认按五维总属性排序
claude-buddy-swap --list

# 显示前 50 名
claude-buddy-swap --list --top 50

# 按 D+P+W 排序（CHAOS 和 SNARK 标记为次要）
claude-buddy-swap --list --sort dpw

# 按综合评分排序（D+P+W 高, CHAOS+SNARK 低）
claude-buddy-swap --list --sort score

# 按 CHAOS 从低到高
claude-buddy-swap --list --sort chaos

# 只看特定物种
claude-buddy-swap --list --species dragon
claude-buddy-swap --list --species robot --top 10
```

### 查看当前状态

```bash
claude-buddy-swap --current
```

### 恢复原始版本

```bash
claude-buddy-swap --restore
```

## 五维属性

每只 Legendary 宠物有 5 个属性。其中 1 个为 peak stat（固定 100），1 个为 dump stat（40-54），其余 3 个为普通值（50-89）：

| 属性 | 含义 | 对宠物行为的影响 |
|------|------|----------------|
| **DEBUGGING** | 调试能力 | 高 → 更关注代码问题 |
| **PATIENCE** | 耐心 | 高 → 更温和淡定 |
| **CHAOS** | 混乱程度 | 高 → 反应更随机跳脱 |
| **WISDOM** | 智慧 | 高 → 评论更有深度 |
| **SNARK** | 毒舌 | 高 → 更容易嘲讽你的代码 |

属性值通过 `buddy_react` API 发送到 Anthropic 服务端，服务端 AI 根据这些值生成对应风格的气泡台词。这是 soft influence，不是硬编码规则。

## 物种 (18 种)

| | | | |
|---|---|---|---|
| 🦆 duck | 🪿 goose | 🫠 blob | 🐱 cat |
| 🐉 dragon | 🐙 octopus | 🦉 owl | 🐧 penguin |
| 🐢 turtle | 🐌 snail | 👻 ghost | 🦎 axolotl |
| 🦫 capybara | 🌵 cactus | 🤖 robot | 🐰 rabbit |
| 🍄 mushroom | 🐈 chonk | | |

## 帽子

Legendary 必定有帽子（Common 没有）：

| 帽子 | ASCII |
|------|-------|
| 👑 crown | `\^^^/` |
| 🎩 tophat | `[___]` |
| 🧢 propeller | `-+-` |
| 😇 halo | `(   )` |
| 🧙 wizard | `/^\` |
| 🧶 beanie | `(___)` |
| 🐤 tinyduck | `,>` |

## 注意事项

- **版本更新：** `claude --update` 会下载全新二进制，patch 会丢失。更新后需重新运行 `claude-buddy-swap <SALT>`。
- **纯客户端：** 宠物数据完全在本地，服务端不校验稀有度，无封号风险。
- **确定性：** 相同的 userId + salt 永远生成相同的宠物。`--list` 的结果是你的专属排行榜（绑定你的 userId）。
- **Salt 长度：** 必须保持 15 字节。3 位数用 `friend-2026-XXX`，4 位数用 `friend2026-XXXX`（去掉一个连字符）。

## License

MIT
