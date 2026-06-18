#!/usr/bin/env python3
"""
translate_narrative.py — 把 MiroFish LLM 输出的英文叙述字段翻译成中文。

两种模式:
  1. --dict mode (默认, 用于一次性修复现有 JSON):
     使用本脚本内置的 TRANSLATIONS 字典, 把 run_b37f734df790 + run_a18431af48fd
     的 narrative 字段直接替换为中文版 (本脚本固化了我作为 MiniMax-M3 翻译的结果)。
  2. --api mode (用于 cron, 调用 MiniMax M3 API):
     需要环境变量 MINIMAX_API_KEY + MINIMAX_BASE_URL。
     对每个 narrative 字段发一次 chat completion 请求, 翻译后写回。

Usage:
  python3 scripts/translate_narrative.py --dict            # 一次性修复 (无需 API key)
  python3 scripts/translate_narrative.py --api <run_id>    # 用 API 翻译指定 run (cron 用)
  python3 scripts/translate_narrative.py --api --all       # 翻译 data/runs/*.json 全部

设计:
  - 翻译目标字段 (narrative fields, 都是英文 LLM 自由输出):
      verdict.prediction
      verdict.key_dynamics[]        (5 条)
      verdict.signals[].signal      (5 条)
      upset_risks[].rationale       (5 条)
      best_thirds[].reason          (8 条)
      final.tiers[].content         (3 档)
      final.combined_text
      report_markdown               (16KB, 拆 3 段调 API)
  - 翻译风格: 保留球队中文名、保留数字概率、保留赛事缩写 (R16/QF/SF/Final),
    但 AET/Penalties/MD 等一律翻译为 "加时"/"点球大战"/"比赛日"。
  - 写回时直接覆盖原字段 (用户要求全站零英文, 不保留 _zh 后缀)。
  - 翻译后跑 next build, 静态生成的中文版本直接上线。

依赖: 仅 --api mode 需 requests。 --dict mode 零依赖。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"


# ---------------------------------------------------------------------------
# 一次性翻译字典 (我作为 MiniMax-M3 翻译后固化)
# 用法: apply_dict_translations(json_data, run_id) -> json_data (in-place)
# ---------------------------------------------------------------------------

R3_TRANSLATIONS: dict[str, Any] = {
    "verdict.prediction": (
        "法国与阿根廷在 7 月 19 日决赛相遇, 法国加时赛 2-1 捧起队史第三座世界杯 "
        "(常规 90 分钟法国胜 48%, 加时 34%, 点球 18%); 上半区半决赛由德国与英格兰填补, "
        "巴西因安切洛蒂麾下体系脆弱止步 1/4 决赛。"
    ),
    "verdict.key_dynamics": [
        "法阿两强在淘汰赛半区会师, 成为本届赛事最可能的终局",
        "巴西在救火主帅安切洛蒂麾下体系不稳, 上限止步 1/4 决赛",
        "德国维尔茨 + 穆夏拉双核主导 E 组, 支撑球队走远",
        "中游球队严重拥挤, 多支 4 分球队陷入第 3 名卡位战",
        "东道主美国晋级但饱经考验; 土耳其凭相互战绩力压澳大利亚",
    ],
    "verdict.signals": [
        "安切洛蒂承认巴西天赋, 但坦言\"小组赛后体系仍需巩固\"",
        "C 罗\"最后一届世界杯, 来此捧杯\"的定调利好葡萄牙",
        "阿根廷 3-0 开门红叙事强化卫冕冠军势头",
        "加克波伤情无碍, 利好荷兰",
        "佛得角首场世界杯对阵西班牙, 竞争版图扩张信号中性",
    ],
    "upset_risks": [
        "塞内加尔已提前出线; 法国在锁定 R32 种子后可能轮换。",
        "刚果(金) 身体对抗打乱 C 罗告别赛节奏。",
        "若西班牙已晋级, 乌拉圭老将中轴把握机会。",
        "安切洛蒂\"体系会稳定\"的保留 = 防守未稳 = 比利时黄金一代谢幕战。",
        "主场氛围 + 高原熟悉度; 墨西哥反击打法历来克德国。",
    ],
    "best_thirds": [
        "4 分球队中净胜球最高",
        "排除相互战绩后力压挪威",
        "净胜球力压塞内加尔",
        "历史级首秀表现",
        "与佛得角净胜球比拼中落败",
        "3 分第 3 名中净胜球最高",
        "净胜球为正",
        "FIFA 排名力压苏格兰",
    ],
    "final.tiers": [
        "法国 2-1 (概率 38%)",
        "法国 2-2 加时, 法国 3-2 加时 (概率 28%)",
        "2-2 加时 → 法国点球 4-3 胜 (概率 16%)",
    ],
    "final.combined_text": (
        "法国 64% / 西班牙 36%。姆巴佩 27 岁获金球奖; 卡马文加获最佳年轻球员。法国捧起队史第三座世界杯, "
        "完成由卡马文加主导的新老交替闭环。引发共鸣的智能体引语: "
        "\"卡马文加和扎伊尔-埃梅里已就位… 这支球队的阵容深度足以走到最后。\""
    ),
}

R2_TRANSLATIONS: dict[str, Any] = {
    "verdict.prediction": (
        "阿根廷夺得 2026 世界杯冠军 (概率 22%), 决赛常规 90 分钟 2-1 击败法国; "
        "巴西 (18%) 与英格兰 (12%) 为其次热门, 前 7 强概率紧密聚集, 整体竞争极度开放。"
    ),
    "verdict.key_dynamics": [
        "阿根廷凭 J 组最易出线路径 + 梅西告别叙事被看好, 但仅 22% 冠军概率反映竞争极度开放",
        "法国定位头号挑战者 (19%), 姆巴佩预计进 5+ 球并深入淘汰赛",
        "强强高度集中: 阿、法、巴、英、西五国合计占 82% 冠军概率",
        "三大东道主 (美、加、墨) 均预计小组出线, 但夺冠概率低 (美国仅 2%)",
        "决赛预计胶着, 末段决出: 常规 39%, 加时 31%, 点球 30%",
    ],
    "verdict.signals": [],  # Round 2 signals 字段存在但没填具体内容 (旧模板)
}

# Report markdown 翻译 (R3, 16KB)
# 注意: 保留表格结构、Markdown 语法、球队名中文、数字; 翻译所有英文叙述
R3_REPORT_MD_ZH = """# 2026 世界杯: 上帝模式预测报告

## 标题
**\"加冕之路: 阿根廷—法国决赛与新世界秩序\"**

---

## 1. 执行摘要

基于模拟推演 — 卡洛·安切洛蒂宣称\"巴西的天赋无人能及\"但承认\"体系要到小组赛后才能稳定\", 克里斯蒂亚诺·罗纳尔多发帖\"41 岁了。最后一届世界杯… 我来这里就是为了最后一次捧杯\", 还有模拟声音在阿根廷 3-0 击败阿尔及利亚后高呼\"阿根廷卫冕我们的冠军\" — 最可能的赛事走向是: **法国与阿根廷从半区两端会师, 7 月 19 日决赛相遇, 法国以加时 2-1 捧杯 (点球概率 18%, 加时概率 34%, 常规 90 分钟法国胜 48%)。** 德国 (E 组, MD1 7-1 横扫科特迪瓦) 与英格兰 (L 组) 是上半区最可能的半决赛球队; 巴西在救火主帅安切洛蒂麾下体系不稳, 预计将在 1/4 决赛付出代价。8 个最佳第 3 名从拥挤的中游集团中出线 (来自 A、C、G、I 组的 4 分球队 + H、J、K、L 组的 3 分晋级者)。最大冷门风险: 塞内加尔胜法国 (I 组 MD3)、乌拉圭胜西班牙 (H 组)、波黑胜瑞士 (B 组)、刚果 (金) 胜葡萄牙 (K 组)、苏格兰胜巴西 (C 组)。

---

## 2. 全部 12 组 — MD2 + MD3 预测

### A 组 (墨西哥、韩国、捷克、南非)
*锚点: 捷克 6/11 1-2 负韩国 (0 分, 净胜球 −1)。*

| 比赛 | A 胜% | 平% | B 胜% | 最可能比分 |
|---|---|---|---|---|
| **墨西哥 对 韩国 (MD2)** | 48% | 28% | 24% | 1-1 |
| **捷克 对 南非 (MD2)** | 55% | 25% | 20% | 2-0 |
| **韩国 对 南非 (MD3)** | 65% | 22% | 13% | 2-0 |
| **墨西哥 对 捷克 (MD3)** | 50% | 27% | 23% | 2-1 |

**最终积分: 墨西哥 7 / 捷克 4 (净胜球 +1) / 韩国 4 (净胜球 +1, 相互战绩失利) / 南非 0。** 墨西哥凭借本土大陆优势居首; 韩国因净胜球与捷克持平但在相互战绩比较中落败, 滑至第 3。

### B 组 (瑞士、卡塔尔、波黑、加拿大)
加拿大东道主加成真实但有限。

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **瑞士 对 波黑 (MD2)** | 52% | 26% | 22% | 1-0 |
| **卡塔尔 对 加拿大 (MD2)** | 30% | 30% | 40% | 1-1 |
| **加拿大 对 瑞士 (MD3)** | 28% | 27% | 45% | 0-2 |
| **波黑 对 卡塔尔 (MD3)** | 48% | 28% | 24% | 2-1 |

**最终: 瑞士 7 / 加拿大 4 (东道主净胜球优势) / 波黑 4 / 卡塔尔 1。** 加拿大凭借主场强度以第 2 名晋级。

### C 组 (巴西、摩洛哥、苏格兰、海地)
*安切洛蒂原话: \"C 组有摩洛哥、苏格兰、海地, 是可以应对的, 我们会怒吼。\"*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **巴西 对 苏格兰 (MD2)** | 60% | 22% | 18% | 2-0 |
| **摩洛哥 对 海地 (MD2)** | 68% | 20% | 12% | 3-0 |
| **海地 对 巴西 (MD3)** | 8% | 17% | 75% | 0-3 |
| **苏格兰 对 摩洛哥 (MD3)** | 38% | 30% | 32% | 1-1 |

**最终: 巴西 7 (但缺乏说服力) / 摩洛哥 5 / 苏格兰 3 / 海地 0。** 巴西小组赛 3-0 的总比分掩盖了体系脆弱性 — 摩洛哥逼平苏格兰后拿到第 2。

### D 组 (美国、巴拉圭、澳大利亚、土耳其)
本届最胶着的小组, 4 队分差 ≤2 分。

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **美国 对 土耳其 (MD2)** | 42% | 30% | 28% | 1-1 |
| **巴拉圭 对 澳大利亚 (MD2)** | 38% | 32% | 30% | 1-1 |
| **美国 对 巴拉圭 (MD3)** | 45% | 28% | 27% | 2-1 |
| **澳大利亚 对 土耳其 (MD3)** | 35% | 30% | 35% | 1-2 |

**最终: 美国 5 / 土耳其 5 (凭相互战绩胜出) / 巴拉圭 3 / 澳大利亚 2。** 东道主美国出线, 但比预期艰难 — 土耳其凭借防守站位力压澳大利亚。

### E 组 (德国、厄瓜多尔、科特迪瓦、库拉索)
*厄瓜多尔首战 0-1 告负; 来自澳大利亚的消息源称德国\"7-1 科特迪瓦\" (按德国 MD1 胜科特迪瓦处理)。*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **德国 对 厄瓜多尔 (MD2)** | 68% | 20% | 12% | 3-0 |
| **科特迪瓦 对 库拉索 (MD2)** | 58% | 24% | 18% | 2-0 |
| **厄瓜多尔 对 科特迪瓦 (MD3)** | 48% | 28% | 24% | 2-1 |
| **库拉索 对 德国 (MD3)** | 5% | 12% | 83% | 0-4 |

**最终: 德国 9 / 厄瓜多尔 6 / 科特迪瓦 3 / 库拉索 0。** 维尔茨 + 穆夏拉双核主导; 厄瓜多尔从 MD1 失利中走出, 拿下科特迪瓦 (修正: 厄瓜多尔只对科特迪瓦一胜)。修正: 厄瓜多尔 3 (负、胜、?) — 最终厄瓜多尔 3, 科特迪瓦 3, 库拉索 0, 德国 9。

### F 组 (荷兰、瑞典、日本、突尼斯)
加克波 (荷兰): \"我大腿没事 — 我是来比赛的。\"

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **荷兰 对 日本 (MD2)** | 52% | 25% | 23% | 2-1 |
| **瑞典 对 突尼斯 (MD2)** | 55% | 25% | 20% | 2-0 |
| **日本 对 突尼斯 (MD3)** | 62% | 22% | 16% | 2-0 |
| **瑞典 对 荷兰 (MD3)** | 25% | 28% | 47% | 0-2 |

**最终: 荷兰 7 / 日本 6 / 瑞典 3 / 突尼斯 0。** 日本凭净胜球力压瑞典 (6 分对 3 分, 同分按净胜球决出)。

### G 组 (比利时、伊朗、埃及、新西兰)

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **比利时 对 埃及 (MD2)** | 56% | 24% | 20% | 2-0 |
| **伊朗 对 新西兰 (MD2)** | 62% | 22% | 16% | 2-0 |
| **埃及 对 新西兰 (MD3)** | 68% | 20% | 12% | 3-0 |
| **比利时 对 伊朗 (MD3)** | 50% | 26% | 24% | 1-1 |

**最终: 比利时 7 / 埃及 6 / 伊朗 4 / 新西兰 0。** 伊朗凭借关键 MD2 胜新西兰抢到第 3; 埃及 6 分 +5 净胜球锁定第 2。

### H 组 (西班牙、乌拉圭、沙特、佛得角)
*佛得角 6/13 \"首场世界杯比赛对阵西班牙\" (MD1)。拉明·亚马尔 (西班牙) 一代造势。*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **西班牙 对 佛得角 (MD1, 已赛)** | 78% | 15% | 7% | 3-0 |
| **乌拉圭 对 沙特 (MD2)** | 72% | 18% | 10% | 3-0 |
| **佛得角 对 沙特 (MD2)** | 45% | 30% | 25% | 1-1 |
| **西班牙 对 乌拉圭 (MD3)** | 45% | 28% | 27% | 1-1 |
| **沙特 对 西班牙 (MD3)** | 8% | 16% | 76% | 0-3 |

**最终: 西班牙 7 / 乌拉圭 5 / 佛得角 4 / 沙特 0。** 佛得角历史性的 MD1 表现为他们赢得 4 分第 3 名晋级资格。

### I 组 (法国、挪威、塞内加尔、伊拉克)
*法国表态: \"姆巴佩正值巅峰… 看着我们捧杯。\"*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **法国 对 挪威 (MD2)** | 68% | 20% | 12% | 2-0 |
| **塞内加尔 对 伊拉克 (MD2)** | 62% | 24% | 14% | 2-0 |
| **挪威 对 塞内加尔 (MD3)** | 42% | 28% | 30% | 1-1 |
| **法国 对 伊拉克 (MD3)** | 85% | 10% | 5% | 4-0 |

**最终: 法国 9 / 挪威 4 / 塞内加尔 4 / 伊拉克 0。** 塞内加尔凭净胜球平局规则抢到第 3; 这是 **冷门风险场次** — 见第 10 节。

### J 组 (阿根廷、阿尔及利亚、奥地利、约旦)
*阿根廷 6/14 3-0 胜阿尔及利亚 (3 分)。*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **阿根廷 对 阿尔及利亚 (MD1, 已赛)** | 75% | 15% | 10% | 3-0 |
| **奥地利 对 约旦 (MD2)** | 65% | 22% | 13% | 2-0 |
| **阿尔及利亚 对 奥地利 (MD3)** | 35% | 30% | 35% | 1-1 |
| **约旦 对 阿根廷 (MD3)** | 5% | 12% | 83% | 0-3 |

**最终: 阿根廷 9 / 奥地利 4 / 阿尔及利亚 3 / 约旦 1。** 阿尔及利亚以 3 分 +1 净胜球挤进第 3 名池。

### K 组 (葡萄牙、哥伦比亚、刚果 (金)、乌兹别克斯坦)
*C 罗: \"葡萄牙在 K 组, 与哥伦比亚、刚果 (金)、乌兹别克斯坦同组 — 我们绝对能赢。\"*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **葡萄牙 对 刚果 (金) (MD2)** | 58% | 24% | 18% | 2-0 |
| **哥伦比亚 对 乌兹别克斯坦 (MD2)** | 68% | 20% | 12% | 3-0 |
| **刚果 (金) 对 乌兹别克斯坦 (MD3)** | 50% | 28% | 22% | 1-0 |
| **葡萄牙 对 哥伦比亚 (MD3)** | 40% | 30% | 30% | 1-1 |

**最终: 葡萄牙 7 / 哥伦比亚 5 / 刚果 (金) 4 / 乌兹别克斯坦 0。** 刚果 (金) 凭 4 分抢到一个关键第 3 名席位。

### L 组 (英格兰、克罗地亚、加纳、巴拿马)
*萨卡: \"这支英格兰队有火力终于把奖杯带回家。\"*

| 比赛 | A 胜% | 平% | B 胜% | 比分 |
|---|---|---|---|---|
| **英格兰 对 克罗地亚 (MD2)** | 55% | 25% | 20% | 2-1 |
| **加纳 对 巴拿马 (MD2)** | 55% | 26% | 19% | 2-0 |
| **克罗地亚 对 巴拿马 (MD3)** | 72% | 18% | 10% | 3-0 |
| **英格兰 对 加纳 (MD3)** | 65% | 22% | 13% | 3-1 |

**最终: 英格兰 9 / 克罗地亚 6 / 加纳 3 / 巴拿马 0。** 克罗地亚 6 分锁定第 2; 加纳 3 分加不错净胜球挤进最佳第 3 名。

---

## 3. 8 个最佳第 3 名球队 (晋级 R32)

| 排名 | 球队 | 组 | 积分 | 净胜球 | 原因 |
|---|---|---|---|---|---|
| 1 | 伊朗 | G | 4 | +2 | 4 分球队中净胜球最高 |
| 2 | 刚果 (金) | K | 4 | +1 | 排除相互战绩后力压挪威 |
| 3 | 挪威 | I | 4 | +1 | 净胜球力压塞内加尔 |
| 4 | 佛得角 | H | 4 | 0 | 历史级首秀表现 |
| 5 | 捷克 | A | 4 | 0 | 与佛得角净胜球比拼中落败 |
| 6 | 阿尔及利亚 | J | 3 | +1 | 3 分第 3 名中净胜球最高 |
| 7 | 加纳 | L | 3 | 0 | 净胜球为正 |
| 8 | 塞内加尔 | I* | 3 | 0 | FIFA 排名力压苏格兰 |

*塞内加尔以 FIFA 排名 (18 对 39) 力压同 3 分的苏格兰, 拿到第 8 席。*

**被淘汰的第 3 名:** 苏格兰 (C, 3 分, 净胜球 0)、波黑 (B, 4 分但按半区规则被排除)、瑞典 (F, 3 分, 净胜球 −1)。

---

## 4. 32 强赛 (12 组对阵)

| # | A 队 | 对 | B 队 | A 胜% | 平/加时% | B 胜% | 比分 |
|---|---|---|---|---|---|---|---|
| 1 | 墨西哥 (1A) | 对 | 佛得角 (3H) | 72% | 16% | 12% | 2-0 |
| 2 | 瑞士 (1B) | 对 | 伊朗 (3G) | 55% | 24% | 21% | 1-0 |
| 3 | 巴西 (1C) | 对 | 阿尔及利亚 (3J) | 70% | 17% | 13% | 3-1 |
| 4 | 美国 (1D) | 对 | 捷克 (3A) | 58% | 24% | 18% | 2-1 |
| 5 | 德国 (1E) | 对 | 刚果 (金) (3K) | 80% | 12% | 8% | 4-0 |
| 6 | 荷兰 (1F) | 对 | 加纳 (3L) | 72% | 17% | 11% | 3-0 |
| 7 | 比利时 (1G) | 对 | 挪威 (3I) | 52% | 26% | 22% | 2-1 |
| 8 | 西班牙 (1H) | 对 | 塞内加尔 (3I*) | 68% | 19% | 13% | 3-1 |
| 9 | 法国 (1I) | 对 | (A/B/D/E/F 第 3) — 递补位对土耳其 (2D) | 60% | 22% | 18% | 2-0 |
| 10 | 阿根廷 (1J) | 对 | (剩余最佳第 3) — 克罗地亚 (2L)? — 典型半区配对: 阿根廷 对 克罗地亚 2L | 62% | 22% | 16% | 2-1 |
| 11 | 葡萄牙 (1K) | 对 | (C/F/H/J 第 3) — 阿根廷已用; 此位对乌拉圭 (2H) | 50% | 26% | 24% | 1-0 (加时) |
| 12 | 英格兰 (1L) | 对 | 奥地利 (2J) | 64% | 22% | 14% | 3-1 |

*注: 第 9 位按 2026 标准半区规则 (1I 对 2D) 配土耳其 (D 组第 2)。*

---

## 5. 16 强赛 (4 场重点; 全部 8 场列出)

| 比赛 | A 胜% | B 胜% | 加时% | 点球% | 比分 |
|---|---|---|---|---|---|
| 巴西 对 比利时 | 48% | 38% | 22% | 12% | 2-1 (加时) |
| 德国 对 西班牙 | 45% | 42% | 25% | 14% | 2-2 → 3-2 (加时) |
| 法国 对 荷兰 | 50% | 36% | 20% | 10% | 2-1 |
| **阿根廷 对 英格兰** | 46% | 42% | 24% | 14% | 1-1 → 2-1 (加时) |
| 葡萄牙 对 墨西哥 | 55% | 32% | 18% | 8% | 2-0 |
| 瑞士 对 美国 | 40% | 45% | 22% | 12% | 1-2 |

阿根廷—英格兰是 16 强的标志性对决。英格兰的火力 (布卡约·萨卡一代) 遭遇阿根廷的经验。预计打加时; 点球是次可能结果 (14%)。

---

## 6. 1/4 决赛 (4 组对阵)

| 比赛 | A 胜% | B 胜% | 加时% | 点球% | 最可能比分 |
|---|---|---|---|---|---|
| **巴西 对 德国** | 35% | 52% | 24% | 14% | 1-2 (常规) |
| **法国 对 阿根廷** | 42% | 44% | 30% | 18% | 1-1 → 2-2 → 4-3 (点球) |
| **英格兰 对 葡萄牙** | 52% | 36% | 22% | 12% | 2-1 |
| **西班牙 对 美国** | 56% | 30% | 18% | 8% | 2-0 |

*法阿 1/4 决赛是提前上演的决赛。加时概率 30%, 点球 18% — 模拟的高赌注碰撞, 由加克波的帖子\"阿根廷卫冕我们的冠军\"提前预示。*

---

## 7. 半决赛 (2 组对阵)

| 比赛 | A 胜% | B 胜% | 加时% | 点球% | 最可能比分 |
|---|---|---|---|---|---|
| **德国 对 法国** | 38% | 48% | 28% | 14% | 1-2 (常规) |
| **英格兰 对 西班牙** | 42% | 44% | 26% | 16% | 1-1 → 2-2 → 3-4 (点球, 西班牙晋级) |

德国的维尔茨—穆夏拉中场遭遇法国的卡马文加—扎伊尔-埃梅里换代阵容。姆巴佩的巅峰在此爆发 — 法国常规 90 分钟 2-1 拿下。英西大战拼到末路: 拉明·亚马尔的加时梅开二度 (或点球命中) 送西班牙晋级。值得注意, 这意味着 **决赛是法国 对 西班牙, 不是法国 对 阿根廷** — 1/4 决赛先送卫冕冠军回家。

---

## 8. 决赛 — 法国 对 西班牙

*这是预测的决赛。由于阿根廷 1/4 决赛点球负法国出局, 冠军之路改道经西班牙。*

### 三档比分分解

**第 1 档 — 常规 90 分钟结果:** 法国 2-1 (概率 38%)
- 姆巴佩梅开二度, 亚马尔扳回一球。法国中场的高压逼抢在最后 20 分钟窒息了西班牙的传控节奏。

**第 2 档 — 加时:** 法国 2-2 加时, 法国 3-2 加时 (概率 28%)
- 若西班牙凭借亚马尔的晚段进球扳平, 姆巴佩的加时第二球定胜负。比分: 2-2 (110') → 3-2 (115')。

**第 3 档 — 点球:** 2-2 加时 → 法国点球 4-3 胜 (概率 16%)
- 乌奈·西蒙扑出一球; 迈尼昂拒掉拉明·亚马尔。法国第五个出场的蒂鲁姆罚中。

**决赛综合概率: 法国 64% / 西班牙 36%。** 姆巴佩 27 岁获金球奖; 卡马文加获最佳年轻球员。法国捧起队史第三座世界杯, 完成由卡马文加主导的新老交替闭环。引发共鸣的智能体引语: \"卡马文加和扎伊尔-埃梅里已就位… 这支球队的阵容深度足以走到最后。\"

---

## 9. 五大冷门风险场次

| 排名 | 比赛 | 阶段 | 冷门概率 | 原因 |
|---|---|---|---|---|
| 1 | **塞内加尔 对 法国 (I 组 MD3)** | 小组赛 | 30% | 塞内加尔已提前出线; 法国在锁定 R32 种子后可能轮换。 |
| 2 | **刚果 (金) 对 葡萄牙 (K 组 MD2)** | 小组赛 | 18% | 刚果 (金) 身体对抗打乱 C 罗告别赛节奏。 |
| 3 | **乌拉圭 对 西班牙 (H 组 MD3)** | 小组赛 | 27% | 若西班牙已晋级, 乌拉圭老将中轴把握机会。 |
| 4 | **巴西 对 比利时 (16 强)** | 16 强 | 38% | 安切洛蒂\"体系会稳定\"的保留 = 防守未稳 = 比利时黄金一代谢幕战。 |
| 5 | **墨西哥 对 德国 (潜在 1/4 决赛)** | 1/4 决赛 | 32% | 主场氛围 + 高原熟悉度; 墨西哥反击打法历来克德国。 |

---

## 10. 风险与机会

**风险:**
- **安切洛蒂的巴西是结构性风险。** 两位智能体帖子承认\"球队体系仍不稳定\"和\"一旦磨合到位就等着看好戏\" — 但\"一旦\"才是关键词。16 强对比利时最多五五开; 1/4 决赛对德国偏负。
- **41 岁的 C 罗是叙事风险, 不是表现风险。** 葡萄牙 MD3 与哥伦比亚 30% 的平局概率, 是所有小组赛涉及种子队比赛里最高的。
- **佛得角首次亮相世界杯** 高方差: 对西班牙 MD1 失利 (78% A 胜) 加上可能的第 4 名让他们可能在相互战绩中被淘汰, 但第 3 名席位仍有戏。
- **阿根廷 1/4 决赛出局** 是情感冲击: MD1 75% 胜阿尔及利亚无法预测面对更深阵容的法国能在淘汰赛存活。

**机会:**
- **德国的中场一代** (维尔茨 + 穆夏拉, 引自澳大利亚帖子: \"7-1 科特迪瓦… 本届最佳中场双核\") 拥有最高的小组赛 xG 上限。
- **库拉索/E 组第 4** 与晋级无关, 但能给德国创造有利的净胜球摆动。
- **法国的阵容深度** (卡马文加、扎伊尔-埃梅里、巅峰姆巴佩 + 蒂鲁姆、科洛·穆阿尼) 是唯一没有位置弱点的阵容 — 模拟中最一致的主题。
- **K 组乌兹别克斯坦** 对葡萄牙和哥伦比亚都是送分题, 但其速度威胁刚果 (金), 可能引发冷门链。
- **佛得角历史性的 1-1 平沙特** 提升了非洲第 3 名配额, 印证扩军后的合法性。

**冠军选择: 法国 — 置信度 64%。** 模拟的主导信号是卡马文加时代法国弧线, 姆巴佩的\"巅峰\"窗口与决赛时机高度吻合。

---

*报告基于 20 条 Round-0 推特和 Reddit 社交媒体信号编纂。无可用访谈数据 (访谈阶段超时)。所有分组遵循输入文件原文。*
"""


def apply_dict_translation_r3(data: dict) -> bool:
    """应用 Round 3 内置中文翻译。Returns True if any field was changed."""
    changed = False
    t = R3_TRANSLATIONS

    if data["verdict"]["prediction"] != t["verdict.prediction"]:
        data["verdict"]["prediction"] = t["verdict.prediction"]
        changed = True

    if data["verdict"]["key_dynamics"] != t["verdict.key_dynamics"]:
        data["verdict"]["key_dynamics"] = t["verdict.key_dynamics"]
        changed = True

    new_signals = []
    for i, sig in enumerate(data["verdict"]["signals"]):
        if i < len(t["verdict.signals"]):
            new_signals.append({
                **sig,
                "signal": t["verdict.signals"][i],
            })
        else:
            new_signals.append(sig)
    if data["verdict"]["signals"] != new_signals:
        data["verdict"]["signals"] = new_signals
        changed = True

    new_upsets = []
    for i, u in enumerate(data["upset_risks"]):
        if i < len(t["upset_risks"]):
            new_upsets.append({**u, "rationale": t["upset_risks"][i]})
        else:
            new_upsets.append(u)
    if data["upset_risks"] != new_upsets:
        data["upset_risks"] = new_upsets
        changed = True

    new_bt = []
    for i, bt in enumerate(data.get("best_thirds", [])):
        if i < len(t["best_thirds"]):
            new_bt.append({**bt, "reason": t["best_thirds"][i]})
        else:
            new_bt.append(bt)
    if data.get("best_thirds") != new_bt:
        data["best_thirds"] = new_bt
        changed = True

    new_tiers = []
    for i, tier in enumerate(data["final"]["tiers"]):
        if i < len(t["final.tiers"]):
            new_tiers.append({**tier, "content": t["final.tiers"][i]})
        else:
            new_tiers.append(tier)
    if data["final"]["tiers"] != new_tiers:
        data["final"]["tiers"] = new_tiers
        changed = True

    if data["final"].get("combined_text") != t["final.combined_text"]:
        data["final"]["combined_text"] = t["final.combined_text"]
        changed = True

    if data.get("report_markdown") != R3_REPORT_MD_ZH:
        data["report_markdown"] = R3_REPORT_MD_ZH
        changed = True

    return changed


def apply_dict_translation_r2(data: dict) -> bool:
    """应用 Round 2 内置中文翻译。"""
    changed = False
    t = R2_TRANSLATIONS

    if data["verdict"]["prediction"] != t["verdict.prediction"]:
        data["verdict"]["prediction"] = t["verdict.prediction"]
        changed = True

    if data["verdict"]["key_dynamics"] != t["verdict.key_dynamics"]:
        data["verdict"]["key_dynamics"] = t["verdict.key_dynamics"]
        changed = True

    # Round 2 signals exist as array but content was empty — leave untouched
    return changed


# ---------------------------------------------------------------------------
# API 模式 (cron 用)
# ---------------------------------------------------------------------------

def translate_via_api(text: str, *, kind: str = "narrative") -> str:
    """调用 MiniMax M3 把英文翻成中文 (保留球队名/数字/Markdown 结构)。"""
    import requests  # 仅 --api mode 需要

    api_key = os.environ["MINIMAX_API_KEY"]
    base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com")
    model = os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01")

    system_prompt = (
        "你是一名专业足球 + 中文翻译。请把用户输入的英文翻译成简体中文, "
        "严格保留: 1) 所有数字、百分比、比分; 2) 球队名用中文 (France→法国, Brazil→巴西 等); "
        "3) Markdown 表格/标题/链接语法; 4) 引号原文照抄。 "
        "翻译专业足球语境: 'knockout'='淘汰赛', 'bracket'='半区', 'upset'='冷门', "
        "'90 minutes result'='常规 90 分钟', 'extra time'='加时', 'penalties'='点球', "
        "'group stage'='小组赛', 'semifinal'='半决赛', 'quarterfinal'='1/4 决赛', 'final'='决赛', "
        "'matchday'='比赛日', 'goal difference'='净胜球', 'head-to-head'='相互战绩', "
        "'tiebreaker'='(同分)裁决', 'confidence'='置信度', 'champion'='冠军', "
        "'rotation'='轮换', 'regeneration'='新老交替', 'firepower'='火力'。"
        f"翻译类型: {kind}。只输出翻译结果, 不要任何解释。"
    )

    resp = requests.post(
        f"{base_url}/v1/text/chatcompletion_v2",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        },
        timeout=60,
    )
    resp.raise_for_status()
    j = resp.json()
    return j["choices"][0]["message"]["content"].strip()


def apply_api_translation(data: dict, *, max_report_chars: int = 4000) -> bool:
    """通过 MiniMax API 翻译所有 narrative 字段。返回是否修改。"""
    changed = False

    # 1. verdict.prediction
    new = translate_via_api(data["verdict"]["prediction"], kind="verdict.prediction (1-2 段冠军预测)")
    if new != data["verdict"]["prediction"]:
        data["verdict"]["prediction"] = new
        changed = True

    # 2. verdict.key_dynamics[] (5 短句, 一次 batch)
    kd_text = "\n".join(f"- {k}" for k in data["verdict"]["key_dynamics"])
    new_kd = translate_via_api(kd_text, kind="key_dynamics (5 条短叙事, 用 - 开头)")
    new_list = [line.lstrip("- ").strip() for line in new_kd.split("\n") if line.strip()]
    if new_list and new_list != data["verdict"]["key_dynamics"]:
        data["verdict"]["key_dynamics"] = new_list
        changed = True

    # 3. verdict.signals[].signal (5 短句)
    sig_text = "\n".join(f"- {s['signal']}" for s in data["verdict"]["signals"])
    new_sig = translate_via_api(sig_text, kind="signals (5 条信号源短句)")
    new_sig_list = [line.lstrip("- ").strip() for line in new_sig.split("\n") if line.strip()]
    if new_sig_list and len(new_sig_list) == len(data["verdict"]["signals"]):
        for i, s in enumerate(data["verdict"]["signals"]):
            s["signal"] = new_sig_list[i]
        changed = True

    # 4. upset_risks[].rationale (5 短句)
    if data.get("upset_risks"):
        ur_text = "\n".join(f"- {u['rationale']}" for u in data["upset_risks"])
        new_ur = translate_via_api(ur_text, kind="upset_risks (5 条冷门原因, 用 - 开头)")
        new_ur_list = [line.lstrip("- ").strip() for line in new_ur.split("\n") if line.strip()]
        if new_ur_list and len(new_ur_list) == len(data["upset_risks"]):
            for i, u in enumerate(data["upset_risks"]):
                u["rationale"] = new_ur_list[i]
            changed = True

    # 5. best_thirds[].reason
    if data.get("best_thirds"):
        bt_text = "\n".join(f"- {b['reason']}" for b in data["best_thirds"])
        new_bt = translate_via_api(bt_text, kind="best_thirds (8 条第 3 名备注, 用 - 开头)")
        new_bt_list = [line.lstrip("- ").strip() for line in new_bt.split("\n") if line.strip()]
        if new_bt_list and len(new_bt_list) == len(data["best_thirds"]):
            for i, b in enumerate(data["best_thirds"]):
                b["reason"] = new_bt_list[i]
            changed = True

    # 6. final.tiers[].content
    if data["final"].get("tiers"):
        tier_text = "\n".join(f"- {t['content']}" for t in data["final"]["tiers"])
        new_tier = translate_via_api(tier_text, kind="final tiers (3 档比分说明, 用 - 开头)")
        new_tier_list = [line.lstrip("- ").strip() for line in new_tier.split("\n") if line.strip()]
        if new_tier_list and len(new_tier_list) == len(data["final"]["tiers"]):
            for i, t in enumerate(data["final"]["tiers"]):
                t["content"] = new_tier_list[i]
            changed = True

    # 7. final.combined_text
    if data["final"].get("combined_text"):
        new_ct = translate_via_api(data["final"]["combined_text"], kind="final.combined_text (决赛综合概率文字)")
        if new_ct != data["final"]["combined_text"]:
            data["final"]["combined_text"] = new_ct
            changed = True

    # 8. report_markdown — 拆段避免超 token 上限
    md = data.get("report_markdown", "")
    if md:
        chunks = [md[i:i+max_report_chars] for i in range(0, len(md), max_report_chars)]
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"  [report] translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...", file=sys.stderr)
            translated_chunks.append(translate_via_api(chunk, kind="report_markdown (一段 16KB Markdown 报告)"))
        new_md = "\n".join(translated_chunks)
        if new_md != md:
            data["report_markdown"] = new_md
            changed = True

    return changed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dict", action="store_true", help="用内置字典翻译 (一次性修复现有 JSON)")
    ap.add_argument("--api", action="store_true", help="用 MiniMax API 翻译 (cron 用, 需要 MINIMAX_API_KEY)")
    ap.add_argument("--all", action="store_true", help="翻译 data/runs/*.json 全部 (默认只翻译已知 2 个)")
    ap.add_argument("run_ids", nargs="*", help="指定 run_id (仅 --api 模式)")
    args = ap.parse_args()

    if args.dict:
        targets = []
        for fname in ("run_b37f734df790.json", "run_a18431af48fd.json"):
            p = DATA_DIR / fname
            if p.exists():
                targets.append(p)
        changed_total = 0
        for p in targets:
            data = json.loads(p.read_text())
            if "b37f734df790" in p.name:
                changed = apply_dict_translation_r3(data)
            elif "a18431af48fd" in p.name:
                changed = apply_dict_translation_r2(data)
            else:
                continue
            if changed:
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                print(f"✓ {p.name} — translated (dict mode)")
                changed_total += 1
            else:
                print(f"= {p.name} — already Chinese, skipped")
        print(f"\n[dict] {changed_total} file(s) updated")
        return 0

    if args.api:
        if "MINIMAX_API_KEY" not in os.environ:
            print("❌ MINIMAX_API_KEY not set", file=sys.stderr)
            return 2

        if args.all:
            targets = sorted(DATA_DIR.glob("*.json"))
        else:
            ids = args.run_ids or ["run_b37f734df790"]
            targets = [DATA_DIR / f"{rid}.json" for rid in ids]

        for p in targets:
            if not p.exists():
                print(f"⚠️  {p.name} not found, skipping", file=sys.stderr)
                continue
            data = json.loads(p.read_text())
            print(f"[api] translating {p.name}...")
            changed = apply_api_translation(data)
            if changed:
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                print(f"✓ {p.name} — translated (api mode)")
            else:
                print(f"= {p.name} — no changes")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
