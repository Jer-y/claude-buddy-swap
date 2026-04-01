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
# 克隆仓库
git clone https://github.com/Jer-y/claude-buddy-swap.git
cd claude-buddy-swap
```

### 依赖

- **Python 3.8+**
- **Claude Code** — 安装在 `~/.local/share/claude/versions/` 的二进制文件
- **Bun** (可选) — 仅 `--list` 排行榜需要（用于 `Bun.hash` Wyhash 模拟）

## 快速开始

```bash
# 查看帮助
python3 claude-buddy-swap.py -h

# 1. 先浏览排行榜，挑一个喜欢的 salt
python3 claude-buddy-swap.py --list

# 2. 退出 Claude Code（必须！运行中的二进制无法覆写）

# 3. 执行切换
python3 claude-buddy-swap.py 9187
```

完成后启动 Claude Code，输入 `/buddy` 即可孵化新宠物。

## 用法

### 切换宠物

```bash
# 基础：选择物种（属性随机）
python3 claude-buddy-swap.py 9187

# 指定一个或多个属性为 100（其余随机）
python3 claude-buddy-swap.py 9187 --peak WISDOM
python3 claude-buddy-swap.py 9187 --peak DEBUGGING WISDOM PATIENCE

# 五维全部 100
python3 claude-buddy-swap.py 9187 --maxstats
```

`--peak` 支持的属性名：`DEBUGGING`、`PATIENCE`、`CHAOS`、`WISDOM`、`SNARK`，空格分隔可写多个。

脚本自动完成全部流程：备份原始二进制 → 从干净备份复制 → patch 权重和 salt → 清除旧宠物灵魂。

### 浏览排行榜

```bash
# 默认按五维总属性排序（前 30 名）
python3 claude-buddy-swap.py --list

# 显示前 50 名
python3 claude-buddy-swap.py --list --top 50

# 按 D+P+W 排序（CHAOS 和 SNARK 标记为次要）
python3 claude-buddy-swap.py --list --sort dpw

# 按综合评分排序（D+P+W 高, CHAOS+SNARK 低）
python3 claude-buddy-swap.py --list --sort score

# 按 CHAOS 从低到高
python3 claude-buddy-swap.py --list --sort chaos

# 只看特定物种
python3 claude-buddy-swap.py --list --species dragon
python3 claude-buddy-swap.py --list --species robot --top 10
```

### 其他命令

```bash
# 查看当前宠物状态
python3 claude-buddy-swap.py --current

# 恢复原始未修改版本
python3 claude-buddy-swap.py --restore

# 查看完整帮助
python3 claude-buddy-swap.py -h
```

> **提示：** 也可以把脚本加到 PATH 里直接调用：
> ```bash
> # Linux / macOS
> cp claude-buddy-swap.py ~/.local/bin/claude-buddy-swap
> chmod +x ~/.local/bin/claude-buddy-swap
> # 之后直接用：
> claude-buddy-swap --list
> ```
>
> **Windows (PowerShell):**
> ```powershell
> python claude-buddy-swap.py --list
> ```

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
