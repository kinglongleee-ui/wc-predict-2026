#!/usr/bin/env python3
"""
parse-report.py — Parse MiroFish run output (verdict.json + report.md)
into a single structured JSON consumable by the Next.js frontend.

Usage:
  python parse-report.py <run_id> <run_dir>

Output:
  data/runs/<run_id>.json

Compatible with both R3-style and R4-style report.md output:
  - R3: | **Mexico vs South Korea (MD2)** | 48% | 26% | 26% | 1-1 |
       Final standings: MEX 7 / KOR 5 / CZE 3 / RSA 0
  - R4: | MD2: Mexico vs South Korea | 44% | 28% | 28% | 1-1 |
       Predicted Final Standings: 1. Mexico (7pts) | 2. South Korea (5pts) | 3. Czech Republic (3pts) | 4. South Africa (1pt)
  - R4 final: ## 7. Final — uses sub-sections (90-Minute / AET / Penalties)
              vs R3 ## 8. Final with **Tier X — label:** lines
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def parse_pct(s: str) -> float:
    """Parse '68%' → 0.68"""
    s = s.strip().rstrip("%").strip()
    try:
        return float(s) / 100
    except ValueError:
        return 0.0


def parse_score(s: str) -> dict:
    """Parse '3-0' or '2-1 (AET)' or '1-1 → 2-1 (AET)' → {home, away, aet, pens}"""
    s = s.strip()
    result = {
        "raw": s,
        "home": None,
        "away": None,
        "aet": "AET" in s.upper() or "→" in s,
        "pens": "pen" in s.lower(),
    }
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", s)
    if m:
        result["home"] = int(m.group(1))
        result["away"] = int(m.group(2))
    return result


def _find_group_section(md_text: str, group_letter: str) -> tuple:
    """Return (start, end) of a group's section, or (-1, -1)."""
    pattern = rf"###\s*Group\s+{group_letter}\s*\(([^)]+)\)"
    section_match = re.search(pattern, md_text)
    if not section_match:
        return -1, -1
    start = section_match.end()
    next_section = re.search(r"\n###\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    return start, end


def parse_group_table(md_text: str, group_letter: str) -> list:
    """Extract match rows from a group's markdown table. Supports both R3 and R4 styles."""
    start, end = _find_group_section(md_text, group_letter)
    if start == -1:
        return []
    section_text = md_text[start:end]

    matches = []

    # R3 style: | **TEAM_A vs TEAM_B (MDx)** | A% | D% | B% | Score |
    for row in re.finditer(
        r"\|\s*\*\*([^*]+?)\s*vs\s+([^*]+?)\s*\(MD(\d+)(?:,\s*prior)?\)\*\*\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        team_a_full, team_b_full, md, a_pct, draw_pct, b_pct, score_raw = row.groups()
        matches.append({
            "stage": f"Group {group_letter}",
            "matchday": int(md),
            "team_a": team_a_full.strip(),
            "team_b": team_b_full.strip(),
            "team_a_win": parse_pct(a_pct),
            "draw": parse_pct(draw_pct),
            "team_b_win": parse_pct(b_pct),
            "most_likely_score": parse_score(score_raw),
        })

    if matches:
        return matches

    # R4 style: | MD2: Mexico vs South Korea | 44% | 28% | 28% | 1-1 |
    for row in re.finditer(
        r"\|\s*MD(\d+):\s*([^|]+?)\s+vs\s+([^|]+?)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        md, team_a, team_b, a_pct, draw_pct, b_pct, score_raw = row.groups()
        matches.append({
            "stage": f"Group {group_letter}",
            "matchday": int(md),
            "team_a": team_a.strip(),
            "team_b": team_b.strip(),
            "team_a_win": parse_pct(a_pct),
            "draw": parse_pct(draw_pct),
            "team_b_win": parse_pct(b_pct),
            "most_likely_score": parse_score(score_raw),
        })

    return matches


def parse_standings(md_text: str, group_letter: str) -> list:
    """Extract final standings. Supports:
    R3: 'Final: MEX 7 / KOR 5 / CZE 3 / RSA 0'
        'Final standings: ...'
    R4: 'Predicted Final Standings: 1. Mexico (7pts) | 2. South Korea (5pts) | 3. Czech Republic (3pts) | 4. South Africa (1pt)'
    """
    start, end = _find_group_section(md_text, group_letter)
    if start == -1:
        return []
    section_text = md_text[start:end]

    # Match R4: **Predicted Final Standings:** 1. Mexico (7pts) | 2. South Korea (5pts) | ...
    r4_match = re.search(r"\*\*Predicted Final Standings:\*\*\s*([^\n]+)", section_text)
    if r4_match:
        text = r4_match.group(1).strip()
        standings = []
        for raw_entry in text.split("|"):
            entry = raw_entry.strip()
            if not entry:
                continue
            # Match "1. Mexico (7pts)" or "1. Mexico 7pts" — capture rank, team, pts
            m = re.match(r"(\d+)\.\s*([^\(]+?)\s*\(?\s*(\d+)\s*pts?\s*\)?", entry)
            if not m:
                continue
            rank, team, pts = m.groups()
            standings.append({
                "rank": int(rank),
                "team": team.strip(),
                "points": int(pts),
                "note": None,
            })
        return standings

    # Match R3: **Final: ...** or **Final standings: ...**
    final_match = re.search(r"\*\*Final(?:\s+standings)?:\s*([^*]+?)\*\*", section_text)
    if not final_match:
        return []
    final_text = final_match.group(1).strip().rstrip(".")
    standings = []
    for raw_entry in final_text.split("/"):
        entry = raw_entry.strip()
        if not entry:
            continue
        m = re.match(r"(.+?)\s+(\d+)(?:\s*\(([^)]+)\))?", entry)
        if not m:
            continue
        team, pts, note = m.groups()
        standings.append({
            "team": team.strip(),
            "points": int(pts),
            "note": note.strip() if note else None,
        })
    return standings


def parse_best_thirds(md_text: str) -> list:
    """Parse '## N. 8 Best 3rd-Place Teams'. Supports R3 table and R4 numbered list."""
    section_match = re.search(r"##\s*\d+\.\s*8\s+Best\s+(?:Third|3rd)[-\s]Place", md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    rows = []

    # R3 table style: | 1 | **France** | I | 4 | 0 | reason |
    for row in re.finditer(
        r"\|\s*(\d+)\s*\|\s*(\S+(?:\s+\S+)*?)\s*\|\s*(\S+)\s*\|\s*(\d+)\s*\|\s*([+\-]?\d+)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        rank, team, group, pts, gd, reason = row.groups()
        rows.append({
            "rank": int(rank),
            "team": team.strip(),
            "group": group.strip(),
            "points": int(pts),
            "goal_difference": int(gd),
            "reason": reason.strip(),
        })

    if rows:
        return rows

    # R4 numbered list: 1. **France** (Group I, 4pts, GD 0) — reason
    for row in re.finditer(
        r"(\d+)\.\s*\*\*([^*]+?)\*\*\s*\(Group\s+([A-L]),\s*(\d+)pts,\s*GD\s*([+\-]?\d+)\)\s*[—\-–]\s*([^\n]+)",
        section_text,
    ):
        rank, team, group, pts, gd, reason = row.groups()
        rows.append({
            "rank": int(rank),
            "team": team.strip(),
            "group": group.strip(),
            "points": int(pts),
            "goal_difference": int(gd),
            "reason": reason.strip(),
        })

    return rows


def parse_knockout_table(md_text: str, section_pattern: str) -> list:
    section_match = re.search(section_pattern, md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    rows = []
    for row in re.finditer(
        r"\|\s*\*\*?([^|*]+?)\s+vs\s+([^|*]+?)\*\*?\s*\|([^|]+)\|",
        section_text,
    ):
        team_a, team_b, rest = row.groups()
        cells = [c.strip() for c in rest.split("|")]
        rows.append({"team_a": team_a.strip(), "team_b": team_b.strip(), "cells": cells})
    return rows


def parse_upset_risks(md_text: str) -> list:
    """Parse '## N. Top 5 Upset-Risk Matches'. Supports R3 table and R4 numbered list."""
    section_match = re.search(r"##\s*\d+\.\s*Top\s+5\s+Upset-Risk", md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    risks = []

    # R3 table: | 1 | **Mexico vs France** | R32 | 38% | rationale |
    for row in re.finditer(
        r"\|\s*(\d+)\s*\|\s*\*\*([^|*]+?)\*\*\s*\|\s*([^|]+?)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        rank, match, stage, upset_pct, rationale = row.groups()
        risks.append({
            "rank": int(rank),
            "match": match.strip(),
            "stage": stage.strip(),
            "upset_probability": parse_pct(upset_pct),
            "rationale": rationale.strip(),
        })

    if risks:
        return risks

    # R4 numbered: 1. **Senegal (2I) vs Croatia (2L) — 55% upset risk:** "..."
    for row in re.finditer(
        r"(\d+)\.\s*\*\*([^—\-]+?)\s*[—\-–]\s*(\d+)%\s+upset\s+risk:\*\*\s*[“\"']?([^\"”\n]+)",
        section_text,
    ):
        rank, match, pct, rationale = row.groups()
        risks.append({
            "rank": int(rank),
            "match": match.strip(),
            "stage": "—",  # R4 doesn't label stage explicitly
            "upset_probability": parse_pct(pct + "%"),
            "rationale": rationale.strip().rstrip("\"").rstrip("”").rstrip("'"),
        })

    return risks


def parse_final(md_text: str) -> dict:
    """Parse '## N. Final — TeamA vs TeamB'. Supports R3 (Tier lines) and R4 (sub-sections)."""
    # Find ANY ## N. Final heading
    section_match = re.search(r"##\s*\d+\.\s*Final(?:\s*[—\-:]\s*([^*\n]+))?", md_text)
    if not section_match:
        return {}
    final_matchup = section_match.group(1).strip() if section_match.group(1) else None
    # Strip trailing annotation like "(per section requirement)"
    if final_matchup:
        final_matchup = re.sub(r"\s*\(per[^)]+\)\s*$", "", final_matchup).strip()
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    tiers = []

    # R3 style: **Tier X — label:** content (XX% probability)
    for tier in re.finditer(
        r"\*\*Tier\s+(\d+)\s*[—\-]\s*([^:*]+):\*\*\s*([^\n]+)",
        section_text,
    ):
        tier_num, label, content = tier.groups()
        pct_match = re.search(r"\(?(\d+%)\s+probability\)?", content)
        tiers.append({
            "tier": int(tier_num),
            "label": label.strip(),
            "content": content.strip(),
            "probability": parse_pct(pct_match.group(1)) if pct_match else None,
        })

    # R4 style: sub-sections (90-Minute Breakdown / Extra Time (AET) / Penalties)
    if not tiers:
        # Extract AET probability: **AET probability: 26%**
        aet_pct = re.search(r"\*\*AET\s+probability:\s*(\d+)%\*\*", section_text)
        # Extract Penalties probability
        pen_pct = re.search(r"\*\*Penalties\s+probability:\s*(\d+)%\*\*", section_text)
        # Extract 90min: each row in the table
        ninety = re.search(r"### 90-Minute Breakdown", section_text)

        if ninety:
            tiers.append({
                "tier": 1,
                "label": "90 min",
                "content": "常规 90 分钟内分出胜负",
                "probability": (100 - (int(aet_pct.group(1)) if aet_pct else 0) - (int(pen_pct.group(1)) if pen_pct else 0)) / 100,
            })
        if aet_pct:
            tiers.append({
                "tier": 2,
                "label": "AET",
                "content": "进入加时赛 (120 分钟)",
                "probability": int(aet_pct.group(1)) / 100,
            })
        if pen_pct:
            tiers.append({
                "tier": 3,
                "label": "Penalties",
                "content": "进入点球大战",
                "probability": int(pen_pct.group(1)) / 100,
            })

    # Combined probability / aggregated outcome
    combined_match = re.search(r"(?:Combined[^:]*:|Final\s+Aggregated\s+Outcome:?)\s*([^\n]+)", section_text)
    combined_text = combined_match.group(1).strip() if combined_match else None

    # Champion pick — try multiple locations
    champion = None
    confidence = None
    # Look in ## Champion Outlook section
    champ_section = re.search(r"##\s*\d+\.\s*Champion\s+Outlook[^\n]*\n([\s\S]+?)(?=\n##\s|\Z)", md_text)
    if champ_section:
        champ_text = champ_section.group(1)
        # Look for "1. **Argentina** — 22%" line → champion is the highest
        m = re.search(r"1\.\s*\*\*([^*]+)\*\*\s*[—\-]\s*(\d+)%", champ_text)
        if m:
            champion = m.group(1).strip()
            confidence = parse_pct(m.group(2) + "%")

    # Fallback: look anywhere in doc for **Champion pick:**
    if not champion:
        champion_match = re.search(r"\*\*Champion pick:\s*([^*\n]+)", md_text)
        if champion_match:
            champion = champion_match.group(1).strip()
            conf_match = re.search(r"confidence\s+(\d+%)", champion_match.group(0))
            if conf_match:
                confidence = parse_pct(conf_match.group(1))

    # Verdict confidence fallback
    if not confidence:
        verdict_conf = re.search(r"\*\*(?:Champion|冠军).*?(\d+)%", md_text)
        if verdict_conf:
            confidence = parse_pct(verdict_conf.group(1) + "%")

    return {
        "matchup": final_matchup,
        "tiers": tiers,
        "combined_text": combined_text,
        "champion": champion,
        "confidence": confidence,
    }


def parse_run(run_id: str, run_dir: Path) -> dict:
    report_md = (run_dir / "report" / "report.md").read_text(encoding="utf-8")
    verdict = json.loads((run_dir / "report" / "verdict.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "report" / "summary.json").read_text(encoding="utf-8"))

    # All 12 groups
    groups = {}
    for letter in "ABCDEFGHIJKL":
        teams_match = re.search(rf"###\s*Group\s+{letter}\s*\(([^)]+)\)", report_md)
        teams = [t.strip() for t in teams_match.group(1).split(",")] if teams_match else []
        groups[letter] = {
            "letter": letter,
            "teams": teams,
            "matches": parse_group_table(report_md, letter),
            "standings": parse_standings(report_md, letter),
        }

    final = parse_final(report_md)
    # If final.confidence not detected from report, use verdict.confidence
    if not final.get("confidence"):
        final["confidence"] = verdict.get("confidence")

    return {
        "run_id": run_id,
        "created_at": summary.get("created_at", datetime.now().isoformat()),
        "verdict": {
            "prediction": verdict["prediction"],
            "confidence": verdict["confidence"],
            "key_dynamics": verdict["key_dynamics"],
            "signals": verdict["signals"],
        },
        "summary": {
            "rounds": summary.get("rounds"),
            "node_count": summary.get("node_count"),
            "edge_count": summary.get("edge_count"),
            "total_actions": summary.get("total_actions"),
            "top_agents": summary.get("top_agents", []),
        },
        "groups": groups,
        "best_thirds": parse_best_thirds(report_md),
        "final": final,
        "upset_risks": parse_upset_risks(report_md),
        "report_markdown": report_md,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: parse-report.py <run_id> <run_dir>", file=sys.stderr)
        sys.exit(1)
    run_id = sys.argv[1]
    run_dir = Path(sys.argv[2])
    if not run_dir.exists():
        print(f"Error: {run_dir} not found", file=sys.stderr)
        sys.exit(1)

    data = parse_run(run_id, run_dir)
    out_path = DATA_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Parsed {run_id} → {out_path}")
    print(f"  Groups: {sum(len(g['matches']) for g in data['groups'].values())} matches, "
          f"{sum(len(g['standings']) for g in data['groups'].values())} standings entries")
    print(f"  Best thirds: {len(data['best_thirds'])}")
    print(f"  Upset risks: {len(data['upset_risks'])}")
    print(f"  Final: {data['final'].get('matchup', 'N/A')}")
    print(f"  Champion: {data['final'].get('champion', 'N/A')} ({data['final'].get('confidence', 'N/A')})")


if __name__ == "__main__":
    main()