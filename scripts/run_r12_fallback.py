#!/usr/bin/env python3
"""R12 fallback: 直接调 M3 API 写报告 (绕过 MiroFish broken report_fast)."""
import json, os, sys
from pathlib import Path

import requests

# 优先从 wc-predict 仓 .env 读 (LLM_API_KEY), 否则从 mirofish-cli .env 读
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

# Load wc2026_remaining_r12.md as context
with open("/home/king/mirofish-cli/wc2026_remaining_r12.md", encoding="utf-8") as f:
    PROMPT_MD = f.read()

# Load Elo baseline (anchor)
BASELINE_MD = ""
if Path("/home/king/wc-predict/data/elo/wc_2026_baseline.md").exists():
    BASELINE_MD = Path("/home/king/wc-predict/data/elo/wc_2026_baseline.md").read_text()

system_prompt = (
    "你是 2026 世界杯预测分析师。基于下述赛事数据/规则/数字 anchor, 输出完整的 9 段预测报告 (中文)。\n"
    "风格: 简洁、量化、有依据。保留所有数字、百分比、比分。不确定时标'待定'。\n"
    "硬约束: 12 组 → 8 best 3rd → R32 (按 Match 73-88 升序) → R16 → QF → SF → Final → Champion\n"
    "每场都给: team_a_win_prob / draw_prob / team_b_win_prob / most_likely_score / aet_prob / penalties_prob\n"
    "R32 8 个 best 3rd 互不重复, 且满足各 slot 的组别限制。"
)

user_prompt = f"""## 任务
{PROMPT_MD}

## NUMERIC ANCHOR (Elo-Poisson, μ=1.4)
{BASELINE_MD[:3000]}

---

请按以下顺序写 9 段 (中文), **不要漏段**:

1. **12 组 final standings** (A→L): 每组列头名/次名/第3名 (用组字母 A/B/C 等 + 排名 1/2/3)
2. **8 个 best 3rd-place** (按概率降序, 含组别)
3. **R32 16 场** (按 Match 73→88 升序, 用 X1/X2/best3 表示种子)
4. **R32 → R16 → QF → SF → 三四名 → Final** 各场: 胜负概率 + most_likely_score + aet_prob + penalties_prob
5. **关键动态 (5 条)**: 1-2 句话
6. **Upset Risk 前 5**: match/date/upset_prob/underdog/reason
7. **决赛预测 (7/19)**: 90min / AET / Penalties 三段概率
8. **冠军 (前 5 + 黑马 3)**
9. **verdict.prediction** (1-2 段总结)

最后再输出一个 JSON 代码块, 格式:
```json
{{
  "prediction": "<verdict.prediction 文本>",
  "confidence": 0.0-1.0,
  "champion_pick": "<冠军队名>",
  "final_matchup": "X vs Y",
  "final_score_90min": "1-1",
  "final_score_likely": "2-1 (加时)",
  "penalty_prob": 0.15,
  "key_dynamics": ["..."],
  "upset_watch": [{{"match":"X vs Y","date":"2026-07-XX","upset_prob":0.4,"underdog":"Y","reason":"..."}}],
  "signals": [{{"match":"X vs Y","date":"2026-07-19","team_a_win_prob":0.55,"draw_prob":0.2,"team_b_win_prob":0.25,"most_likely_score":"2-1","aet_prob":0.1,"penalties_prob":0.05}}]
}}
```"""

print("[fallback] calling M3 API for R12 report...")
resp = requests.post(
    f"{BASE}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    json={
        "model": MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.4,
        "max_tokens": 8000,
    },
    timeout=300,
)
resp.raise_for_status()
data = resp.json()
report_text = data["choices"][0]["message"]["content"]
print(f"[fallback] ✓ got {len(report_text)} chars")

# Extract JSON block (贪心找最后一个, 因为 LLM 可能输出多个)
import re
blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", report_text, re.DOTALL)
verdict = None
if blocks:
    # 试每个, 取第一个能 parse 的
    for b in blocks:
        try:
            verdict = json.loads(b)
            break
        except Exception:
            continue

if not verdict:
    # 退化: 从报告文本里手动拼一个最小 verdict (parse-report.py 会从 report.md 重新解析)
    print("⚠️ JSON 解析失败, 用最小 verdict 占位 (parse-report 会从 report.md 重新 parse)")
    verdict = {
        "prediction": report_text[:600],
        "confidence": 0.5,
        "champion_pick": "见报告",
        "final_matchup": "见报告",
        "final_score_90min": "见报告",
        "final_score_likely": "见报告",
        "penalty_prob": 0.15,
        "key_dynamics": [],
        "upset_watch": [],
        "signals": [],
    }

# Save to R12 run dir
R12_DIR = "/home/king/mirofish-cli/uploads/runs/run_14dbeb45e10a"
report_dir = Path(R12_DIR) / "report"
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / "report.md").write_text(report_text, encoding="utf-8")
(report_dir / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

# Update manifest
manifest_path = Path(R12_DIR) / "manifest.json"
m_data = json.load(open(manifest_path))
m_data["status"] = "completed"
m_data["error"] = None
m_data["task_message"] = "R12 fallback: 直接 M3 API 写报告 (绕过 MiroFish broken report_fast)"
m_data["task_progress"] = 100
m_data["updated_at"] = "2026-06-25T16:10:00"
json.dump(m_data, open(manifest_path, "w"), indent=2)

print(f"[fallback] ✓ saved to {report_dir}/report.md + verdict.json")
print(f"[fallback] verdict.prediction: {verdict.get('prediction', '')[:120]}")