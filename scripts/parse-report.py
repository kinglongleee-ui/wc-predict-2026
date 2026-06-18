#!/usr/bin/env python3
"""
parse-report.py — Parse MiroFish run output (verdict.json + report.md)
into a single structured JSON consumable by the Next.js frontend.

Usage:
  python parse-report.py <run_id> <run_dir>

Output:
  data/runs/<run_id>.json
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
    # Try primary score (first N-M)
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", s)
    if m:
        result["home"] = int(m.group(1))
        result["away"] = int(m.group(2))
    return result


def parse_group_table(md_text: str, group_letter: str) -> list:
    """Extract match rows from a group's markdown table."""
    # Find section for this group
    pattern = rf"###\s*Group\s+{group_letter}\s*\(([^)]+)\)"
    section_match = re.search(pattern, md_text)
    if not section_match:
        return []
    teams_str = section_match.group(1)
    teams = [t.strip() for t in teams_str.split(",")]

    # Find the table after this header
    start = section_match.end()
    # next ### or end of file
    next_section = re.search(r"\n###\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    # Parse table rows: | **TEAM_A vs TEAM_B (MDx)** | A win% | Draw% | B win% | Score |
    matches = []
    for row in re.finditer(
        r"\|\s*\*\*([^*]+?)\s*vs\s+([^*]+?)\s*\(MD(\d+)(?:,\s*prior)?\)\*\*\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        team_a_full, team_b_full, md, a_pct, draw_pct, b_pct, score_raw = row.groups()
        team_a = team_a_full.strip()
        team_b = team_b_full.strip()
        # Some team names have aliases like "Mexico (1A)" in later rounds — keep the alias for context
        matches.append({
            "stage": f"Group {group_letter}",
            "matchday": int(md),
            "team_a": team_a,
            "team_b": team_b,
            "team_a_win": parse_pct(a_pct),
            "draw": parse_pct(draw_pct),
            "team_b_win": parse_pct(b_pct),
            "most_likely_score": parse_score(score_raw),
        })
    return matches


def parse_standings(md_text: str, group_letter: str) -> list:
    """Extract 'Final: X 7 / Y 4 / Z 3 / W 0' or 'Final standings: ...' from a group section."""
    pattern = rf"###\s*Group\s+{group_letter}\s*\(([^)]+)\)"
    section_match = re.search(pattern, md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n###\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    # Match either "**Final: ...**" or "**Final standings: ...**"
    final_match = re.search(r"\*\*Final(?:\s+standings)?:\s*([^*]+?)\*\*", section_text)
    if not final_match:
        return []
    final_text = final_match.group(1).strip().rstrip(".")
    # Split on " / " then parse each entry "TEAM PTS (note)"
    standings = []
    for raw_entry in final_text.split("/"):
        entry = raw_entry.strip()
        if not entry:
            continue
        # Match "TEAM_NAME PTS" or "TEAM_NAME PTS (note)"
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
    section_match = re.search(r"##\s*3\.\s*8\s+Best\s+Third-Place", md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    rows = []
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
    section_match = re.search(r"##\s*9\.\s*Top\s+5\s+Upset-Risk\s+Matches", md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    risks = []
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
    return risks


def parse_final(md_text: str) -> dict:
    section_match = re.search(r"##\s*8\.\s*Final", md_text)
    if not section_match:
        return {}
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    # Extract final matchup from header line "## 8. Final — France vs Spain"
    header_match = re.search(r"##\s*8\.\s*Final\s*[—\-:]\s*([^*\n]+)", md_text)
    final_matchup = header_match.group(1).strip() if header_match else None

    # Extract tier breakdowns
    tiers = []
    for tier in re.finditer(
        r"\*\*Tier\s+(\d+)\s*[—\-]\s*([^:*]+):\*\*\s*([^\n]+)",
        section_text,
    ):
        tier_num, label, content = tier.groups()
        # Extract percentage
        pct_match = re.search(r"\(?(\d+%)\s+probability\)?", content)
        tiers.append({
            "tier": int(tier_num),
            "label": label.strip(),
            "content": content.strip(),
            "probability": parse_pct(pct_match.group(1)) if pct_match else None,
        })

    # Combined probability
    combined = re.search(r"Combined[^:]*:\s*([^\n]+)", section_text)
    champion = re.search(r"\*\*Champion pick:\s*([^*\n]+)", md_text)
    confidence = re.search(r"confidence\s+(\d+%)", champion.group(0)) if champion else None

    return {
        "matchup": final_matchup,
        "tiers": tiers,
        "combined_text": combined.group(1).strip() if combined else None,
        "champion": champion.group(1).strip() if champion else None,
        "confidence": parse_pct(confidence.group(1)) if confidence else None,
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
        "final": parse_final(report_md),
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
    print(f"  Groups: {sum(len(g['matches']) for g in data['groups'].values())} matches")
    print(f"  Best thirds: {len(data['best_thirds'])}")
    print(f"  Upset risks: {len(data['upset_risks'])}")
    print(f"  Final: {data['final'].get('matchup', 'N/A')}")
    print(f"  Champion: {data['final'].get('champion', 'N/A')}")


if __name__ == "__main__":
    main()
