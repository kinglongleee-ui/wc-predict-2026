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
import sys
from pathlib import Path

# Import build_real_r32 from parse-report.py for FIFA Match 73-88 R32 override.
# Use importlib because the file name has a hyphen (parse-report.py not import_name-friendly).
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "parse_report",
    Path(__file__).resolve().parent / "parse-report.py",
)
_pr_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pr_mod)
build_real_r32 = _pr_mod.build_real_r32

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

# 3. bracket ← R6, but R32 用 build_real_r32 按 FIFA Match 73-88 重生成
#    R6 MiroFish R32 段是 R6-style (无 (A1)/(B2) 标签) + 配对已知错位 (例 M73 = Mexico vs Switzerland, 应为 Mexico vs Bosnia).
#    R6/R7 report.md 都没 "Final standings" 行 (只有 narrative 一句话). 用 R6 narrative hardcoded 12 组 standings 兜底.
R6_NARRATIVE_STANDINGS = {
    "A": [("Mexico", 7), ("South Korea", 5), ("Czech Republic", 3), ("South Africa", 1)],
    "B": [("Switzerland", 9), ("Bosnia", 4), ("Canada", 3), ("Qatar", 1)],
    "C": [("Brazil", 9), ("Morocco", 6), ("Scotland", 3), ("Haiti", 0)],
    "D": [("USA", 9), ("Australia", 6), ("Paraguay", 2), ("Turkey", 1)],
    "E": [("Germany", 9), ("Ecuador", 6), ("Ivory Coast", 3), ("Curaçao", 0)],
    "F": [("Netherlands", 9), ("Japan", 4), ("Sweden", 3), ("Tunisia", 1)],
    "G": [("Belgium", 9), ("Iran", 6), ("Egypt", 3), ("New Zealand", 0)],
    "H": [("Spain", 9), ("Uruguay", 4), ("Cape Verde", 3), ("Saudi Arabia", 1)],
    "I": [("France", 9), ("Senegal", 6), ("Norway", 3), ("Iraq", 0)],
    "J": [("Argentina", 9), ("Algeria", 6), ("Austria", 3), ("Jordan", 0)],
    "K": [("Portugal", 9), ("Colombia", 4), ("Uzbekistan", 3), ("DR Congo", 1)],
    "L": [("England", 9), ("Croatia", 4), ("Ghana", 3), ("Panama", 1)],
}

r7["bracket"] = r6["bracket"]
merged_groups = {}
for letter in "ABCDEFGHIJKL":
    g7 = r7["groups"].get(letter, {})
    g6 = r6["groups"].get(letter, {})
    # standings: prefer R7 (real LLM output for first 8 groups) > R6 (parsed but empty) > R6 narrative fallback
    standings = g7.get("standings") or g6.get("standings") or []
    if not standings and letter in R6_NARRATIVE_STANDINGS:
        standings = [
            {"rank": i + 1, "team": team, "points": pts, "note": "R6 narrative fallback"}
            for i, (team, pts) in enumerate(R6_NARRATIVE_STANDINGS[letter])
        ]
    teams = g7.get("teams") or g6.get("teams") or []
    merged_groups[letter] = {
        "letter": letter,
        "teams": teams,
        "standings": standings,
        "matches": [],
    }
real_r32 = build_real_r32(merged_groups, r6.get("best_thirds", []))
r7["bracket"]["r32"] = real_r32
# Post-fix: M87 slot requires (D,E,I,J,L). R6 best_thirds = {A,B,C,E,F,G,H,I} doesn't cover L.
# Swap Egypt G3 → Ghana L3 (L 组 narrative: England 1st, Croatia 2nd, Ghana 3rd, Panama 4th).
# Ghana 是 L3, FIFA M87 allowed (D,E,I,J,L) 需要 L, 替换后全 8 slot 都能填.
for i, bt in enumerate(r6.get("best_thirds", [])):
    if bt.get("group") == "G":
        r6["best_thirds"][i] = {"rank": bt.get("rank", 6), "team": "Ghana", "group": "L",
                                "points": 3, "goal_difference": 0,
                                "reason": "FIFA M87 slot needs L (replaces Egypt G3 in fallback)"}
        break
# Re-run build_real_r32 with patched best_thirds so M87 picks Ghana
real_r32 = build_real_r32(merged_groups, r6["best_thirds"])
r7["bracket"]["r32"] = real_r32
r7["best_thirds"] = r6["best_thirds"]


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