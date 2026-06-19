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
from typing import Optional

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
    """Return (start, end) of a group's section, or (-1, -1).
    Supports both R3 ('### Group D (USA, ...)') and R4 ('### Group D: USA, ...').
    """
    pattern = rf"###\s*Group\s+{group_letter}\s*(?:\(([^)]+)\)|:\s*([^\n]+))"
    section_match = re.search(pattern, md_text)
    if not section_match:
        return -1, -1
    start = section_match.end()
    next_section = re.search(r"\n###\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    return start, end


def _find_group_teams(md_text: str, group_letter: str) -> list:
    """Return the list of teams for a group, regardless of R3/R4 heading style.
    Returns [] when the group isn't present.
    """
    pattern = rf"###\s*Group\s+{group_letter}\s*(?:\(([^)]+)\)|:\s*([^\n]+))"
    m = re.search(pattern, md_text)
    if not m:
        return []
    raw = (m.group(1) or m.group(2) or "").strip()
    return [t.strip() for t in raw.split(",") if t.strip()]


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
    R3: 'Final: MEX 7 / KOR 5 / CZE 3 / RSA 0' (slash-delimited)
    R3: 'Predicted Final Standings: 1. Mexico (7pts) | 2. South Korea (5pts) | ...'
    R4: '**Standings: MEX 7, KOR 6, CZE 1, RSA 0**' (comma-delimited, optional trailing note)
    """
    start, end = _find_group_section(md_text, group_letter)
    if start == -1:
        return []
    section_text = md_text[start:end]

    # Match R3 alt: **Predicted Final Standings:** 1. Mexico (7pts) | 2. South Korea (5pts) | ...
    r4_match = re.search(r"\*\*Predicted Final Standings:\*\*\s*([^\n]+)", section_text)
    if r4_match:
        text = r4_match.group(1).strip()
        standings = []
        for raw_entry in text.split("|"):
            entry = raw_entry.strip()
            if not entry:
                continue
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

    # Match R4: **Standings: MEX 7, KOR 6, CZE 1, RSA 0** (optionally followed by ** (... note))
    r4_standings = re.search(r"\*\*Standings:\s*([^*]+?)\*\*", section_text)
    if r4_standings:
        text = r4_standings.group(1).strip().rstrip(".")
        # Extract trailing parenthetical note (e.g. "(AUS ahead on GD)")
        note_m = re.search(r"\s*\(([^)]+)\)\s*$", text)
        trailing_note = note_m.group(1).strip() if note_m else None
        if note_m:
            text = text[: note_m.start()].strip().rstrip(",")
        standings = []
        for raw_entry in text.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            m = re.match(r"(.+?)\s+(\d+)$", entry)
            if not m:
                continue
            team, pts = m.groups()
            standings.append({
                "team": team.strip(),
                "points": int(pts),
                "note": trailing_note,
            })
        return standings

    # Match R3: **Final: ...** or **Final standings: ...** (slash-delimited)
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
    """Parse '## N. 8 Best 3rd-Place Teams'. Supports:
    R3 table: | 1 | **France** | I | 4 | 0 | reason |
    R3 numbered: 1. **France** (Group I, 4pts, GD 0) — reason
    R4 simplified: 1. **Cape Verde (H)** — 3 pts, +1 GD (reason)
    """
    section_match = re.search(r"##\s*(?:\d+\.\s*)?8\s+Best\s+(?:Third|3rd)[-\s]Place", md_text)
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

    # R3 numbered list: 1. **France** (Group I, 4pts, GD 0) — reason
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

    if rows:
        return rows

    # R4 simplified: 1. **Cape Verde (H)** — 3 pts, +1 GD (upset specialist)
    for row in re.finditer(
        r"(\d+)\.\s*\*\*([^*\n]+?)\s*\(([A-L])\)\*\*\s*[—\-–]\s*(\d+)\s*pts,\s*([+\-]?\d+)\s*GD(?:\s*\(([^)]+)\))?",
        section_text,
    ):
        rank, team, group, pts, gd, reason = row.groups()
        rows.append({
            "rank": int(rank),
            "team": team.strip(),
            "group": group.strip(),
            "points": int(pts),
            "goal_difference": int(gd),
            "reason": reason.strip() if reason else None,
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
    """Parse '## N. Top 5 Upset-Risk Matches'. Supports:
    R3: | 1 | **Mexico vs France** | R32 | 38% | rationale |  (5 cols)
    R4 alt: | 1 | **Senegal (2I) vs Croatia (2L) — 55% upset risk:** "..."   (numbered list)
    R4: | Rank | Match | Context | Upset Prob |  (4 cols, no rationale, pct in **bold**)
    """
    section_match = re.search(r"##\s*(?:\d+\.\s*)?Top\s+5\s+Upset-Risk", md_text)
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

    # R4 4-col table: | 1 | **Cape Verde vs Spain (R32)** | context text | **22%** |
    for row in re.finditer(
        r"\|\s*(\d+)\s*\|\s*\*\*([^|*]+?)\*\*\s*\|\s*([^|]+?)\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|",
        section_text,
    ):
        rank, match, context, upset_pct = row.groups()
        risks.append({
            "rank": int(rank),
            "match": match.strip(),
            "stage": "—",
            "upset_probability": parse_pct(upset_pct + "%"),
            "rationale": context.strip(),
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
            "stage": "—",
            "upset_probability": parse_pct(pct + "%"),
            "rationale": rationale.strip().rstrip("\"").rstrip("”").rstrip("'"),
        })

    return risks


def _strip_group_pos(raw: str) -> str:
    """[Legacy] Strip 'Mexico (1A)' (R3) or 'Mexico (A1)' (R4) → 'Mexico'. Tolerant of leading **bold** markers."""
    name, _g, _s = _parse_team_with_seed(raw)
    return name


def _parse_team_with_seed(raw: str) -> tuple[str, Optional[str], Optional[int]]:
    """Parse 'Mexico (1A)' / 'Mexico (A1)' / '**Mexico (1A)**' → ('Mexico', 'A', 1).

    Returns (team_name, group_letter, seed_rank).
    Tolerates leading/trailing ** bold markers and various formats:
      R3: Mexico (1A)         → ('Mexico', 'A', 1)
      R4: Mexico (A1)         → ('Mexico', 'A', 1)
      R4: Mexico (1A-2)       → ('Mexico', 'A', 1)
      No suffix              → (raw, None, None)
    """
    s = raw.strip().strip("*").strip()
    # 捕获队名 + 字母 (A-L)
    m = re.match(r"([^(]+?)\s*\((?:\d+)?([A-L])(?:\d+)?(?:-\w+)?\)", s)
    if not m:
        return (s, None, None)
    name = m.group(1).strip()
    group = m.group(2)
    # 种子: 优先取括号里数字 (R3 = 1A 数字在前; R4 = A1 数字在后)
    inside = s[s.index("("):s.index(")")]
    nums = re.findall(r"\d+", inside)
    seed = int(nums[0]) if nums else None
    return (name, group, seed)


def _winner_from_pct(a: str, b: str, d: str) -> Optional[str]:
    """Pick winner from '48%' / '26%' / '26%' strings.
    Returns 'a', 'b', or None when draw is highest (match goes to AET/pen).
    """
    a_val = parse_pct(a)
    b_val = parse_pct(b)
    d_val = parse_pct(d)
    if a_val > b_val and a_val > d_val:
        return "a"
    if b_val > a_val and b_val > d_val:
        return "b"
    return None


def _parse_bracket_table(md_text: str, section_start: int, with_index: bool) -> list:
    """Parse a knockout bracket table starting at section_start (after the heading).

    with_index=True  → R32 format:
        R3: | # | Matchup | A% | D% | B% | Score |
        R4: | # | Team A | Team B | A% | Draw | B% | Score | AET | Pen |
    with_index=False → R16/QF/SF format:
        R3: | Matchup | A% | D% | B% | Score | AET% | Pen% |
        R4: | Match | Matchup | A% | Draw | B% | Score | AET | Pen |
    """
    next_section = re.search(r"\n##\s", md_text[section_start:])
    section_end = section_start + next_section.start() if next_section else len(md_text)
    section_text = md_text[section_start:section_end]

    matches = []

    if with_index:
        # R4 style: | # | **Team A (X1)** | Team B (Y3) | A% | Draw | B% | Score | AET | Pen |
        # Tolerates **70%** bolded percentages and skips n/a rows.
        r4_rows = list(re.finditer(
            r"\|\s*(\d+)\s*\|\s*\*\*([^*]+?)\*\*\s*\|\s*([^|]+?)\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|\s*([^|]+?)\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|\s*\*?\*?(\d+)%\*?\*?\s*\|",
            section_text,
        ))
        for row in r4_rows:
            idx, team_a_raw, team_b_raw, a_pct, d_pct, b_pct, score, aet_pct, pen_pct = row.groups()
            # Skip rows where all percentages are zero (likely n/a row)
            if a_pct == "0" and d_pct == "0" and b_pct == "0":
                continue
            team_a, group_a, seed_a = _parse_team_with_seed(team_a_raw)
            team_b, group_b, seed_b = _parse_team_with_seed(team_b_raw)
            matches.append({
                "bracket_idx": int(idx) - 1,
                "team_a": team_a,
                "group_a": group_a,
                "seed_a": seed_a,
                "team_b": team_b,
                "group_b": group_b,
                "seed_b": seed_b,
                "team_a_win": parse_pct(a_pct + "%"),
                "draw": parse_pct(d_pct + "%"),
                "team_b_win": parse_pct(b_pct + "%"),
                "score": score.strip(),
                "aet_pct": parse_pct(aet_pct + "%"),
                "pen_pct": parse_pct(pen_pct + "%"),
                "winner": _winner_from_pct(a_pct + "%", b_pct + "%", d_pct + "%"),
            })

        if matches:
            return matches

        # R3 style: | # | Matchup | A% | D% | B% | Score |
        for row in re.finditer(
            r"\|\s*(\d+)\s*\|\s*([^|]+?)\s+vs\s+([^|]+?)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|",
            section_text,
        ):
            idx, team_a_raw, team_b_raw, a_pct, d_pct, b_pct, score = row.groups()
            team_a, group_a, seed_a = _parse_team_with_seed(team_a_raw)
            team_b, group_b, seed_b = _parse_team_with_seed(team_b_raw)
            matches.append({
                "bracket_idx": int(idx) - 1,  # 0-based for tree indexing
                "team_a": team_a,
                "group_a": group_a,
                "seed_a": seed_a,
                "team_b": team_b,
                "group_b": group_b,
                "seed_b": seed_b,
                "team_a_win": parse_pct(a_pct),
                "draw": parse_pct(d_pct),
                "team_b_win": parse_pct(b_pct),
                "score": score.strip(),
                "aet_pct": None,
                "pen_pct": None,
                "winner": _winner_from_pct(a_pct, b_pct, d_pct),
            })
    else:
        # R4 style: | Match | Matchup | A% | Draw | B% | Score | AET | Pen |
        r4_rows = list(re.finditer(
            r"\|\s*(?:R\d+-\d+|QF\d+|SF\d+|Match)\s*\|\s*\*\*?([^|*]+?)\*\*?\s+vs\s+\*\*?([^|*]+?)\*\*?(?:\s*\([^)]+\))?\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|",
            section_text,
        ))
        for row in r4_rows:
            team_a, team_b, a_pct, d_pct, b_pct, score, aet_pct, pen_pct = row.groups()
            team_a_clean, group_a, seed_a = _parse_team_with_seed(team_a)
            team_b_clean, group_b, seed_b = _parse_team_with_seed(team_b)
            matches.append({
                "team_a": team_a_clean,
                "group_a": group_a,
                "seed_a": seed_a,
                "team_b": team_b_clean,
                "group_b": group_b,
                "seed_b": seed_b,
                "team_a_win": parse_pct(a_pct),
                "draw": parse_pct(d_pct),
                "team_b_win": parse_pct(b_pct),
                "score": score.strip(),
                "aet_pct": parse_pct(aet_pct),
                "pen_pct": parse_pct(pen_pct),
                "winner": _winner_from_pct(a_pct, b_pct, d_pct),
            })
        for i, m in enumerate(matches):
            m["bracket_idx"] = i

        if matches:
            return matches

        # R3 style: | Matchup | A% | D% | B% | Score | AET% | Pen% |
        for row in re.finditer(
            r"\|\s*([^|]+?)\s+vs\s+([^|]+?)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|\s*([^|]+?)\s*\|\s*(\d+%)\s*\|\s*(\d+%)\s*\|",
            section_text,
        ):
            team_a, team_b, a_pct, d_pct, b_pct, score, aet_pct, pen_pct = row.groups()
            team_a_clean, group_a, seed_a = _parse_team_with_seed(team_a)
            team_b_clean, group_b, seed_b = _parse_team_with_seed(team_b)
            matches.append({
                "team_a": team_a_clean,
                "group_a": group_a,
                "seed_a": seed_a,
                "team_b": team_b_clean,
                "group_b": group_b,
                "seed_b": seed_b,
                "team_a_win": parse_pct(a_pct),
                "draw": parse_pct(d_pct),
                "team_b_win": parse_pct(b_pct),
                "score": score.strip(),
                "aet_pct": parse_pct(aet_pct),
                "pen_pct": parse_pct(pen_pct),
                "winner": _winner_from_pct(a_pct, b_pct, d_pct),
            })
        for i, m in enumerate(matches):
            m["bracket_idx"] = i

    return matches


def _parse_third_place(md_text: str, sf_start: int) -> Optional[dict]:
    """Parse '**3rd-place playoff:** Germany 1-2 England (AET, ...)' from SF section."""
    next_section = re.search(r"\n##\s", md_text[sf_start:])
    section_end = sf_start + next_section.start() if next_section else len(md_text)
    section_text = md_text[sf_start:section_end]

    m = re.search(r"\*\*3rd-place\s+playoff:\*\*\s*([^\n]+)", section_text)
    if not m:
        return None

    text = m.group(1).strip()
    # Format: "Germany 1-2 England (AET, 88' winner by Bellingham)"
    score_match = re.match(r"(.+?)\s+(\d+[-:]\d+)\s+(.+?)(?:\s*\(.*\))?$", text)
    if score_match:
        team_a, score, team_b = score_match.groups()
        return {
            "team_a": team_a.strip(),
            "team_b": team_b.strip(),
            "score": score.strip(),
            "raw": text,
            "aet": "AET" in text.upper(),
        }
    return {"raw": text}


def parse_bracket(md_text: str) -> dict:
    """Extract the full knockout bracket (R32, R16, QF, SF, 3rd-place) from report.md.

    The Final itself is parsed separately by parse_final() and stored under
    `final` at the top level, so the bracket dict does NOT include it.
    Index pairing is left to the frontend (R16[i] parents = R32[2i], R32[2i+1]).

    Heading patterns:
      R3: '## 3. Round of 32 — 16 Matchups'
      R4: '## Round of 32 (12 Matchups)'
    Both are matched.
    """
    result = {"r32": [], "r16": [], "qf": [], "sf": [], "third_place": None}

    # R32: ## 3. Round of 32 / ## Round of 32 (...)
    r32_head = re.search(r"##\s*(?:\d+\.\s*)?Round\s+of\s+32[^\n]*", md_text)
    if r32_head:
        result["r32"] = _parse_bracket_table(md_text, r32_head.end(), with_index=True)

    # R16: ## 4. Round of 16 / ## Round of 16 (...)
    r16_head = re.search(r"##\s*(?:\d+\.\s*)?Round\s+of\s+16[^\n]*", md_text)
    if r16_head:
        result["r16"] = _parse_bracket_table(md_text, r16_head.end(), with_index=False)
        # Tag bracket_idx so frontend can pair parents
        for i, m in enumerate(result["r16"]):
            m["bracket_idx"] = i

    # QF: ## 5. Quarterfinals / ## Quarterfinals (...)
    qf_head = re.search(r"##\s*(?:\d+\.\s*)?Quarterfinals?[^\n]*", md_text)
    if qf_head:
        result["qf"] = _parse_bracket_table(md_text, qf_head.end(), with_index=False)
        for i, m in enumerate(result["qf"]):
            m["bracket_idx"] = i

    # SF: ## 6. Semifinals / ## Semifinals (...)
    sf_head = re.search(r"##\s*(?:\d+\.\s*)?Semifinals?[^\n]*", md_text)
    if sf_head:
        result["sf"] = _parse_bracket_table(md_text, sf_head.end(), with_index=False)
        for i, m in enumerate(result["sf"]):
            m["bracket_idx"] = i
        result["third_place"] = _parse_third_place(md_text, sf_head.end())

    return result


def parse_final(md_text: str, verdict: Optional[dict] = None) -> dict:
    """Parse '## N. Final — TeamA vs TeamB'. Supports R3 (Tier lines) and R4 (3-Tier Breakdown table).

    R3 final section uses '**Tier X — label:**' lines.
    R4 final section uses '### 3-Tier Probability Breakdown' table with 3 rows (90 min / AET / Pen).
    Champion falls back to verdict.prediction when no Champion Outlook section is found.
    """
    # Find ANY ## N. Final heading (also match plain '## Final' with no number)
    section_match = re.search(r"##\s*(?:\d+\.\s*)?Final(?:\s*[—\-:]\s*([^*\n]+))?", md_text)
    if not section_match:
        return {}
    final_matchup = section_match.group(1).strip() if section_match.group(1) else None
    # Strip trailing annotation like "(per section requirement)" or venue
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

    # R4 style: 3-Tier Probability Breakdown table
    #   | Tier | Probability | Most Likely Outcome |
    #   | **90 minutes (regulation)** | 1-1 draw — **22%** | ... |
    if not tiers:
        breakdown = re.search(r"###\s*3-Tier\s+Probability\s+Breakdown", section_text)
        if breakdown:
            breakdown_text = section_text[breakdown.end():]
            tier_rows = list(re.finditer(
                r"\|\s*\*\*([^*]+?)\*\*\s*\|\s*([^*\n]+?)\s*\|\s*([^\n|]+?)\s*\|",
                breakdown_text,
            ))
            tier_labels = {
                "90 minutes (regulation)": ("90 min", "常规 90 分钟内分出胜负"),
                "After Extra Time (AET)": ("AET", "进入加时赛 (120 分钟)"),
                "Penalties": ("Penalties", "进入点球大战"),
            }
            for i, trow in enumerate(tier_rows, start=1):
                raw_label, mid, _outcome = trow.groups()
                pct_m = re.search(r"(\d+)%", mid)
                pct = int(pct_m.group(1)) / 100 if pct_m else None
                label_key = raw_label.strip()
                label_zh, content_zh = tier_labels.get(label_key, (raw_label.strip(), raw_label.strip()))
                tiers.append({
                    "tier": i,
                    "label": label_zh,
                    "content": content_zh,
                    "probability": pct,
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
        m = re.search(r"1\.\s*\*\*([^*]+)\*\*\s*[—\-]\s*(\d+)%", champ_text)
        if m:
            champion = m.group(1).strip()
            confidence = parse_pct(m.group(2) + "%")

    # Fallback: look for **Final aggregated: X champion probability ~N%** (R4 style)
    if not champion:
        agg = re.search(r"\*\*Final\s+aggregated:\s*([^*]+?)\*\*", md_text)
        if agg:
            text = agg.group(1)
            m = re.search(r"([A-Za-z][A-Za-z\s]+?)\s+champion\s+probability\s+~?(\d+)%", text)
            if m:
                champion = m.group(1).strip()
                confidence = parse_pct(m.group(2) + "%")

    # Fallback: anywhere for **Champion pick:
    if not champion:
        champion_match = re.search(r"\*\*Champion pick:\s*([^*\n]+)", md_text)
        if champion_match:
            champion = champion_match.group(1).strip()
            conf_match = re.search(r"confidence\s+(\d+%)", champion_match.group(0))
            if conf_match:
                confidence = parse_pct(conf_match.group(1))

    # Final fallback: parse verdict.json's prediction sentence (e.g. "France are crowned ... 17% confidence")
    if not champion and verdict and verdict.get("prediction"):
        vp = verdict["prediction"]
        m = re.search(r"([A-Z][a-zA-Z\s]+?)\s+are\s+crowned\s+.*?(\d+)%\s+confidence", vp)
        if m:
            champion = m.group(1).strip()
            confidence = parse_pct(m.group(2) + "%")

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
        teams = _find_group_teams(report_md, letter)
        groups[letter] = {
            "letter": letter,
            "teams": teams,
            "matches": parse_group_table(report_md, letter),
            "standings": parse_standings(report_md, letter),
        }

    final = parse_final(report_md, verdict=verdict)
    # If final.confidence not detected from report, use verdict.confidence
    if not final.get("confidence"):
        final["confidence"] = verdict.get("confidence")
    # If final.champion not detected from report, use first capitalized team from verdict.prediction
    if not final.get("champion") and verdict.get("prediction"):
        import re as _re
        m = _re.search(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b", verdict["prediction"])
        if m:
            final["champion"] = m.group(1).strip()

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
        "bracket": parse_bracket(report_md),
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