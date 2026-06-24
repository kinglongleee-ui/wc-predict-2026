#!/usr/bin/env python3
"""Patch R8c JSON with narrative-extracted SF, Final tiers, upset_risks (parse-report regex gaps).

R8 report.md 已经有完整 SF/Final/UpseRisk 段, 但 parse-report.py regex 不识别.
直接从 R8 report.md 重读 narrative + 注入 R8 JSON.
"""
import json
from pathlib import Path

R8_JSON = Path("/home/king/wc-predict/data/runs/run_d1f74f4afe69.json")
R8_MD = Path("/home/king/mirofish-cli/uploads/runs/run_d1f74f4afe69/report/report.md")

with R8_JSON.open(encoding="utf-8") as f:
    data = json.load(f)
md = R8_MD.read_text(encoding="utf-8")

# ---------- 1. SF (Semifinals) — R8 段: | **SF1** | Brazil vs France | **France 2-1 (AET)** |
sf_section_match = None
import re
# Find Semifinals section
sf_head = re.search(r"##\s*(?:\d+\.\s*)?Semifinals?[^\n]*", md)
if sf_head:
    sf_section = md[sf_head.end():]
    sf_next = re.search(r"\n##\s", sf_section)
    sf_text = sf_section[:sf_next.start() if sf_next else len(sf_section)]
    sf_matches = []
    for line in sf_text.split("\n"):
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5 or not cells[1]:
            continue
        m = re.match(r"\*\*(SF\d+)\*\*", cells[1])
        if not m:
            continue
        if " vs " not in cells[2]:
            continue
        ta, tb = cells[2].split(" vs ", 1)
        ta = re.sub(r"\s*\(.*?\)\s*", "", ta).strip()
        tb = re.sub(r"\s*\(.*?\)\s*", "", tb).strip()
        score = cells[3].strip().strip("*").strip()
        # parse winner
        winner = "a"
        sm = re.search(r"(\d+)\s*[-:]\s*(\d+)", score)
        if sm:
            h, a_ = int(sm.group(1)), int(sm.group(2))
            if h == a_:
                winner = None  # AET/Pen decided
            else:
                winner = "a" if h > a_ else "b"
        sf_matches.append({
            "bracket_idx": len(sf_matches),
            "team_a": ta, "team_b": tb,
            "group_a": None, "seed_a": None,
            "group_b": None, "seed_b": None,
            "team_a_win": 0.5, "draw": 0.0, "team_b_win": 0.5,
            "score": score, "aet_pct": None, "pen_pct": None,
            "winner": winner,
        })
    if sf_matches:
        data["bracket"]["sf"] = sf_matches
        print(f"  [sf] injected {len(sf_matches)} SF entries")

# ---------- 2. Final 4-tier outcomes (R8 narrative 4 rows)
# R8: | Argentina win in 90 minutes (e.g., 2-1) | **28%** |
# R8: | France win in 90 minutes (e.g., 2-1) | **22%** |
# R8: | **AET** (Argentina or France) | **30%** |
# R8: | **Penalties** | **20%** |
final_section_match = re.search(r"##\s*(?:\d+\.\s*)?Final[^\n]*", md)
if final_section_match:
    final_section = md[final_section_match.end():]
    # Find first tier-related paragraph (3-tier outcome probabilities)
    tier_match = re.search(r"\*\*3-tier[^\n]*:\*\*\s*([\s\S]+?)(?=\n\n|\n\*\*)", final_section)
    if tier_match:
        tier_text = tier_match.group(1)
        rows = re.findall(r"\|\s*([^|]+?)\s*\|\s*\*\*(\d+)%\*\*\s*\|", tier_text)
        if rows:
            tier_labels = {
                "argentina": ("90 min (阿根廷胜)", "阿根廷 90 分钟内取胜"),
                "france": ("90 min (法国胜)", "法国 90 分钟内取胜"),
                "aet": ("AET", "进入加时赛 (120 分钟)"),
                "penalty": ("Penalties", "进入点球大战"),
            }
            new_tiers = []
            for i, (label, pct) in enumerate(rows, start=1):
                label_l = label.lower()
                zh_label, zh_content = label, label
                for k, (z, c) in tier_labels.items():
                    if k in label_l:
                        zh_label, zh_content = z, c
                        break
                new_tiers.append({
                    "tier": i, "label": zh_label, "content": zh_content,
                    "probability": int(pct) / 100,
                })
            if new_tiers:
                data["final"]["tiers"] = new_tiers
                print(f"  [final.tiers] injected {len(new_tiers)} tier rows")

# ---------- 3. Upset-Risks (R8 numbered: "1. **R32 — Norway (G1) vs Ecuador (best 3rd)** (M82): ... **Upset probability: 15% Ecuador win.**")
upset_section_match = re.search(r"##\s*(?:\d+\.\s*)?Top\s+5\s+Upset[-\s]Risk[^\n]*", md)
if upset_section_match:
    upset_section = md[upset_section_match.end():]
    upset_next = re.search(r"\n##\s", upset_section)
    upset_text = upset_section[:upset_next.start() if upset_next else len(upset_section)]
    risks = []
    for line in upset_text.split("\n"):
        # R8 format: "1. **match label** (M82): rationale **Upset probability: N% Team win.**"
        # OR:        "3. **Group A MD3 — ...** (group decider): rationale **Upset probability: N%**"
        # OR:        "5. **Group B — Switzerland vs Bosnia**: rationale **Upset probability: N%**"
        m = re.match(
            r"(\d+)\.\s*\*\*(.+?)\*\*\s*(?:\([^)]+\))?:\s*(.+?)\*\*Upset probability:\s*(\d+)%([^*\n]+?)\*\*\.?\s*$",
            line,
        )
        if not m:
            continue
        rank, match, rationale, pct, who = m.groups()
        # Extract stage from match label
        stage_match = re.match(r"^(R\d+|QF\d+|SF\d+|Group [A-L])", match.strip())
        stage = stage_match.group(1) if stage_match else "—"
        risks.append({
            "rank": int(rank),
            "match": match.strip(),
            "stage": stage,
            "upset_probability": int(pct) / 100,
            "rationale": rationale.strip().rstrip("."),
        })
    if risks:
        data["upset_risks"] = risks
        print(f"  [upset_risks] injected {len(risks)} entries")

# ---------- 4. third_place playoff (R8 没写, 留 None)
# R8 report.md 没有 3rd-place playoff 段

# Save back
with R8_JSON.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"✓ Patched {R8_JSON}")
print(f"   bracket.sf: {len(data['bracket']['sf'])}")
print(f"   final.tiers: {len(data['final'].get('tiers', []))}")
print(f"   upset_risks: {len(data['upset_risks'])}")