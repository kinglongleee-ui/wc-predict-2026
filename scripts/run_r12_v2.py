#!/usr/bin/env python3
"""R12 v2 — 直接 M3 API 生成 9 段结构化报告 (绕过 MiroFish broken report_fast).

R12 v1 fallback 失败原因: LLM 输出 thinking 模式而非 markdown tables.
v2 修复: 在 user_prompt 顶部强制 "ONLY OUTPUT MARKDOWN TABLES, NO THINKING", 并把
9 段逐一显式列出来, 每段配 markdown 模板让 LLM 填空.
"""
import json, os, sys, re
from pathlib import Path
import requests

# 读 .env
for env_path in ("/home/king/wc-predict/.env.local", "/home/king/mirofish-cli/.env"):
    if Path(env_path).exists():
        for line in Path(env_path).read_text().splitlines():
            if line.startswith("LLM_API_KEY="):
                os.environ.setdefault("LLM_API_KEY", line.split("=", 1)[1].strip())
            if line.startswith("LLM_BASE_URL="):
                os.environ.setdefault("LLM_BASE_URL", line.split("=", 1)[1].strip())
            if line.startswith("LLM_MODEL_NAME="):
                os.environ.setdefault("LLM_MODEL_NAME", line.split("=", 1)[1].strip())

API_KEY = os.environ.get("LLM_API_KEY")
BASE = os.environ.get("LLM_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("LLM_MODEL_NAME", "MiniMax-M3")
if not API_KEY:
    print("❌ LLM_API_KEY not found", file=sys.stderr); sys.exit(2)

# 加载 prompt + 真实结果
PROMPT_MD = Path("/home/king/mirofish-cli/wc2026_remaining_r12.md").read_text(encoding="utf-8")
BASELINE_MD = ""
if Path("/home/king/wc-predict/data/elo/wc_2026_baseline.md").exists():
    BASELINE_MD = Path("/home/king/wc-predict/data/elo/wc_2026_baseline.md").read_text()

# 加载已比赛结果 (anchor)
REAL_RESULTS = ""
results_path = Path("/home/king/wc-predict/data/real/wc_2026_results.json")
if results_path.exists():
    REAL_RESULTS = json.loads(results_path.read_text())

system_prompt = """你是 2026 世界杯预测分析师。**严格按下面 markdown 模板输出, 不要写任何 thinking, 不要写 <|think|>, 不要用代码块包整个报告, 每段用 ```markdown ... ``` 分隔。**"""

# 强制模板 - LLM 直接填空
template = """## 1. 12 组积分 (A→L)

| 组 | 第1名 | 积分 | 第2名 | 积分 | 第3名 | 积分 | 第4名 | 积分 |
|---|---|---|---|---|---|---|---|---|
| A | 墨西哥 | 9 | 韩国 | 6 | 捷克 | 3 | 南非 | 0 |
| B | 瑞士 | 9 | 加拿大 | 4 | 波黑 | 3 | 卡塔尔 | 1 |
| C | 巴西 | 9 | 苏格兰 | 6 | 摩洛哥 | 3 | 海地 | 0 |
| D | 美国 | 9 | 澳大利亚 | 6 | 巴拉圭 | 2 | 土耳其 | 1 |
| E | 德国 | 9 | 厄瓜多尔 | 6 | 科特迪瓦 | 3 | 库拉索 | 0 |
| F | 荷兰 | 9 | 日本 | 4 | 瑞典 | 3 | 突尼斯 | 1 |
| G | 比利时 | 9 | 伊朗 | 6 | 埃及 | 3 | 新西兰 | 0 |
| H | 西班牙 | 7 | 乌拉圭 | 7 | 佛得角 | 3 | 沙特 | 0 |
| I | 法国 | 9 | 挪威 | 4 | 塞内加尔 | 3 | 伊拉克 | 1 |
| J | 阿根廷 | 9 | 奥地利 | 6 | 阿尔及利亚 | 3 | 约旦 | 0 |
| K | 葡萄牙 | 9 | 哥伦比亚 | 4 | 刚果(金) | 3 | 乌兹别克 | 1 |
| L | 英格兰 | 9 | 克罗地亚 | 4 | 加纳 | 3 | 巴拿马 | 1 |

## 2. 8 个最佳第 3 名 (按概率降序)

| 排名 | 球队 | 组 | 积分 | 净胜球 |
|---|---|---|---|---|
| 1 | 摩洛哥 | C | 3 | 0 |
| 2 | 科特迪瓦 | E | 3 | 0 |
| 3 | 日本 | F | 4 | 0 |
| 4 | 伊朗 | G | 6 | 0 |
| 5 | 塞内加尔 | I | 3 | 0 |
| 6 | 奥地利 | J | 6 | 0 |
| 7 | 刚果(金) | K | 3 | 0 |
| 8 | 加纳 | L | 3 | 0 |

## 3. R32 16 场 (按 Match 73-88 升序)

| M# | 配对 | A胜 | 平 | B胜 | 最可能比分 |
|---|---|---|---|---|---|
| 73 | A2 韩国 vs B2 加拿大 | 0.45 | 0.27 | 0.28 | 1-1 |
| 74 | E1 德国 vs best3 摩洛哥 (C组第3) | 0.72 | 0.16 | 0.12 | 2-0 |
| 75 | F1 荷兰 vs C2 苏格兰 | 0.58 | 0.22 | 0.20 | 1-0 |
| 76 | C1 巴西 vs F2 日本 | 0.78 | 0.14 | 0.08 | 2-0 |
| 77 | I1 法国 vs best3 伊朗 (G组第3) | 0.80 | 0.13 | 0.07 | 2-0 |
| 78 | E2 厄瓜多尔 vs I2 挪威 | 0.45 | 0.28 | 0.27 | 1-1 |
| 79 | A1 墨西哥 vs best3 科特迪瓦 (E组第3) | 0.55 | 0.25 | 0.20 | 1-0 |
| 80 | L1 英格兰 vs best3 奥地利 (J组第3) | 0.68 | 0.20 | 0.12 | 2-0 |
| 81 | D1 美国 vs best3 摩洛哥 (B组第3) | 0.62 | 0.22 | 0.16 | 1-0 |
| 82 | G1 比利时 vs best3 塞内加尔 (I组第3) | 0.65 | 0.20 | 0.15 | 2-0 |
| 83 | K2 哥伦比亚 vs L2 克罗地亚 | 0.50 | 0.27 | 0.23 | 1-1 |
| 84 | H1 西班牙 vs J2 奥地利 | 0.70 | 0.18 | 0.12 | 2-0 |
| 85 | B1 瑞士 vs best3 日本 (F组第3) | 0.55 | 0.24 | 0.21 | 1-0 |
| 86 | J1 阿根廷 vs H2 乌拉圭 | 0.55 | 0.25 | 0.20 | 1-0 |
| 87 | K1 葡萄牙 vs best3 加纳 (L组第3) | 0.72 | 0.18 | 0.10 | 2-0 |
| 88 | D2 澳大利亚 vs G2 伊朗 | 0.42 | 0.28 | 0.30 | 1-1 |

## 4. R16 8 场 (基于 R32 胜者)

| 场次 | 配对 | A胜 | B胜 | 最可能比分 |
|---|---|---|---|---|
| R16-1 | M73胜者 韩国 vs M74胜者 德国 | 0.32 | 0.68 | 0-2 |
| R16-2 | M75胜者 荷兰 vs M76胜者 巴西 | 0.25 | 0.75 | 0-2 |
| R16-3 | M77胜者 法国 vs M78胜者 厄瓜多尔 | 0.80 | 0.20 | 2-0 |
| R16-4 | M79胜者 墨西哥 vs M80胜者 英格兰 | 0.30 | 0.70 | 0-2 |
| R16-5 | M81胜者 美国 vs M82胜者 比利时 | 0.38 | 0.62 | 1-2 |
| R16-6 | M83胜者 哥伦比亚 vs M84胜者 西班牙 | 0.25 | 0.75 | 0-2 |
| R16-7 | M85胜者 瑞士 vs M86胜者 阿根廷 | 0.20 | 0.80 | 0-2 |
| R16-8 | M87胜者 葡萄牙 vs M88胜者 澳大利亚 | 0.70 | 0.30 | 2-0 |

## 5. 8 强 (QF)

| 场次 | 配对 | A胜 | 平 | B胜 | 最可能比分 |
|---|---|---|---|---|---|
| QF1 | 德国 vs 巴西 | 0.35 | 0.30 | 0.35 | 1-1 (AET) |
| QF2 | 法国 vs 英格兰 | 0.55 | 0.25 | 0.20 | 2-1 |
| QF3 | 比利时 vs 西班牙 | 0.30 | 0.28 | 0.42 | 1-2 |
| QF4 | 阿根廷 vs 葡萄牙 | 0.55 | 0.25 | 0.20 | 2-1 |

## 6. 4 强 (SF)

| 场次 | 配对 | A胜 | 平 | B胜 | 最可能比分 |
|---|---|---|---|---|---|
| SF1 | 巴西 vs 法国 | 0.40 | 0.28 | 0.32 | 1-2 (AET) |
| SF2 | 西班牙 vs 阿根廷 | 0.45 | 0.27 | 0.28 | 1-2 |

## 7. 三四名决赛

| 场次 | 配对 | A胜 | B胜 | 最可能比分 |
|---|---|---|---|---|
| 3rd | 巴西 vs 西班牙 | 0.45 | 0.55 | 1-2 |

## 8. 决赛 (7/19 MetLife Stadium)

| 场次 | 配对 | A胜 | 平 | B胜 | 最可能比分 |
|---|---|---|---|---|---|
| Final | 法国 vs 阿根廷 | 0.42 | 0.28 | 0.30 | 1-1 (AET 2-1 ARG) |

## 9. 决赛分阶段概率

| 阶段 | 概率 |
|---|---|
| 90 分钟内分胜负 | 56% |
| 加时 (120 分钟) | 28% |
| 点球大战 | 16% |

## 10. 冠军 (前 5)

| 排名 | 球队 | 概率 |
|---|---|---|
| 1 | 阿根廷 | 18% |
| 2 | 法国 | 16% |
| 3 | 巴西 | 12% |
| 4 | 西班牙 | 10% |
| 5 | 英格兰 | 8% |

## 11. 冷门 Upset (前 5)

| 场次 | 日期 | 冷门概率 | 弱队 | 原因 |
|---|---|---|---|---|
| 德国 vs 巴西 QF | 7/11 | 50% | 巴西 | 巴西防守脆弱, 加时点球皆有可能 |
| 比利时 vs 西班牙 QF | 7/12 | 42% | 西班牙 | 西班牙传控更稳定 |
| 西班牙 vs 阿根廷 SF | 7/15 | 28% | 阿根廷 | 阿根廷 2022 决赛复仇动力 |
| 墨西哥 vs 英格兰 R16 | 7/3 | 30% | 墨西哥 | 主场优势 + 高海拔 |
| 澳大利亚 vs 伊朗 R32 | 7/3 | 30% | 伊朗 | 西亚球队对亚洲对手更熟悉 |

## 12. 关键动态 (5 条)

1. 法国 vs 阿根廷 决赛 2022 翻版 - 法国 33% 卫冕, 阿根廷 30% 卫冕
2. 巴西防守是 QF 爆冷的关键
3. 英格兰 8 强, 9 年来最远
4. 西班牙 2022 控球优势延伸
5. 哥伦比亚 K2 黑马, 替补深度好

## 13. Verdict

阿根迁 vs 法国 决赛翻版 2022 略占优势, 2026 法国 33% 卫冕, 阿根廷 30% 复仇。
"""

user_prompt = f"""## 任务背景
{PROMPT_MD[:2000]}

## 真实比赛结果 (anchor)
{json.dumps(REAL_RESULTS.get('matches', [])[:24], ensure_ascii=False, indent=2) if REAL_RESULTS else '无'}

## Elo-Poisson baseline (μ=1.4, neutral venue)
{BASELINE_MD[:1500]}

## ⚠️ 输出要求 (严格)

**直接复制下面的 markdown 模板, 替换数字, 不要新增其他内容:**

```markdown
{template}
```

请**只输出** 1 个 markdown 代码块, 包含上面 13 段, 不要写任何思考, 不要加其他解释。
"""

print("[R12 v2] calling M3 API (max_tokens=8192)...")
resp = requests.post(
    f"{BASE}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    },
    timeout=300,
)
resp.raise_for_status()
data = resp.json()
report_text = data["choices"][0]["message"]["content"]
print(f"[R12 v2] ✓ got {len(report_text)} chars")
print(f"[R12 v2] first 200 chars: {report_text[:200]}")

# Save raw
out_dir = Path("/tmp/r12_v2")
out_dir.mkdir(exist_ok=True)
(out_dir / "raw.txt").write_text(report_text, encoding="utf-8")
print(f"[R12 v2] saved to {out_dir}/raw.txt")
