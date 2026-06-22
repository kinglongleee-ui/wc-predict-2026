#!/usr/bin/env python3
"""R7 partial + R6 fallback 合并脚本。

策略:
- groups[letter].matches ← R6 (覆盖 R7 损坏的 "Mexico · South Korea · ..." 4 队 list)
- groups[letter].standings ← R7 (8 组完整 + H-L 用 [] 兜底)
- groups[letter].teams ← R7 (12 组 letter + teams 全有)
- best_thirds ← R6 (R7=空)
- bracket ← R6 (R7=空)
- final ← R7 (Argentina 0.62) + matchup 改为 "Argentina vs France"
- upset_risks ← R6 (R7=空)
- summary ← R7 (有数据)
- verdict ← R7 (英文保留, 因为 translate API 401)
- report_markdown ← R7 (5091, 截断) + R6 拼接 (R32 配对 + Champion + Upsets)
- run_id ← run_3e9d8be4115d (R7 不变)
- created_at ← R7 created_at
- 加 fallback_source 字段标记
"""
import json
from pathlib import Path

R7_PATH = Path("/home/king/wc-predict/data/runs/run_3e9d8be4115d.json")
R6_PATH = Path("/home/king/wc-predict/data/runs/run_ea1419a0e22f.json")
OUT_PATH = R7_PATH

with R7_PATH.open(encoding="utf-8") as f:
    r7 = json.load(f)
with R6_PATH.open(encoding="utf-8") as f:
    r6 = json.load(f)

# Sanity check
assert r7["run_id"] == "run_3e9d8be4115d", f"R7 id mismatch: {r7['run_id']}"
assert r6["run_id"] == "run_ea1419a0e22f", f"R6 id mismatch: {r6['run_id']}"

# 1. groups: 合并 R7 letter/teams/standings + R6 matches
for letter in "ABCDEFGHIJKL":
    r7_g = r7["groups"][letter]
    r6_g = r6["groups"].get(letter, {})

    # teams: R7 有 (12 组 letter/teams), 但 matches 损坏 → 用 R6 matches
    if r6_g.get("matches"):
        r7_g["matches"] = r6_g["matches"]

    # standings: R7 (8 组有, H-L 用 [])
    if not r7_g.get("standings"):
        r7_g["standings"] = r6_g.get("standings", [])

    # letter 保留 R7
    r7_g["letter"] = letter

# 2. best_thirds ← R6
r7["best_thirds"] = r6["best_thirds"]

# 3. bracket ← R6
r7["bracket"] = r6["bracket"]

# 4. final ← R7 (Argentina 0.62) + matchup 配对
r7_final = r7.get("final", {})
r7_final["matchup"] = "Argentina vs France (MetLife, 7/19)"  # 与 verdict.prediction 一致
r7_final["champion"] = r7_final.get("champion") or "Argentina"
r7_final["confidence"] = r7_final.get("confidence") or 0.62
r7_final["combined_text"] = (
    f"阿根廷以 {int(r7_final['confidence']*100)}% 概率赢得 2026 国际足联世界杯冠军, "
    f"决赛在 MetLife 球场 2-1 战胜法国 (经加时)。R7 LLM 模拟 (Elo-Poisson baseline μ=1.4 + DraftKings 1X2 priors) 锚定。\n\n"
    f"原 R7 verdict: {r7.get('verdict', {}).get('prediction', '')}"
)
r7_final["tiers"] = r7_final.get("tiers", [])
r7["final"] = r7_final

# 5. upset_risks ← R6 (R7 空)
if not r7.get("upset_risks"):
    r7["upset_risks"] = r6.get("upset_risks", [])

# 6. summary ← R7 (保留)

# 7. verdict 保留 R7 (英文)

# 8. report_markdown ← R7 完整 + R6 补 R32 段
r7_md = r7["report_markdown"]
# 在 R7 md 末尾加一个 "R32+ 配对采用 R6 fallback" 段
note = """

---

## ⚠️ R7 报告说明 (LLM 输出截断)

R7 MiroFish LLM 模拟因 `max_tokens` 默认值限制, 报告输出截断在 Group H MD2 处 (5091 字符)。
本轮采用**混合策略**:

- **小组赛 (12 组 standings + matches)**: 优先采用 R7 输出 (R7 matches 损坏 fallback 至 R6)
- **淘汰赛 R32/R16/QF/SF/Final**: 采用 R6 fallback 数据 (R7 未输出)
- **冠军预测**: R7 verdict (`Argentina 2-1 France AET, 62% confidence`)

R8 将于明天 cron 9 AM 重跑 (修复后),届时 LLM 完整输出将覆盖本轮 partial 状态。

---

## 🔁 R6 fallback 补充段 (R32 配对 + 冠军预测)

"""
# 取 R6 md 的 R32 → Champion 段 (从 "Round of 32" 开始到 "Top 5 Upset Risks" 之前)
r6_md = r6["report_markdown"]
# 找 R32 段起点
start = r6_md.find("## Round of 32")
end = r6_md.find("## Top 5 Upset Risks")
if start > 0 and end > start:
    r6_fallback_section = r6_md[start:end].rstrip()
else:
    # 兜底: 取后 4000 字符
    r6_fallback_section = r6_md[-4000:]

r7["report_markdown"] = r7_md + note + r6_fallback_section

# 9. 加 metadata
r7["fallback_source"] = {
    "reason": "R7 MiroFish LLM output truncated at Group H MD2 (max_tokens limit)",
    "r7_partial_fields": ["groups.standings (8/12 complete)", "verdict", "final.champion", "summary", "report_markdown (partial)"],
    "r6_fallback_fields": ["groups.matches (R7 corrupted with 4-team lists)", "best_thirds", "bracket", "upset_risks"],
    "r7_kept_fields": ["groups.letter", "groups.teams", "groups.standings (where available)", "verdict", "final.champion=Argentina confidence=0.62", "summary"],
    "round": "R7 + R6 fallback",
    "date": "2026-06-22",
}

# 写回
with OUT_PATH.open("w", encoding="utf-8") as f:
    json.dump(r7, f, ensure_ascii=False, indent=2)

print(f"✅ Patched {OUT_PATH}")
print(f"   run_id: {r7['run_id']}")
print(f"   groups: {len(r7['groups'])} (each matches/standings updated)")
print(f"   best_thirds: {len(r7['best_thirds'])}")
print(f"   bracket.r32: {len(r7['bracket']['r32'])}")
print(f"   final.champion: {r7['final']['champion']} ({r7['final']['confidence']})")
print(f"   upset_risks: {len(r7['upset_risks'])}")
print(f"   report_markdown: {len(r7['report_markdown'])} chars")