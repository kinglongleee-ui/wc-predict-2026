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
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "runs"

# Make scripts/ importable so _enrich_with_top3 can lazy-load elo_poisson
# regardless of the caller's working directory.
import sys as _sys
if str(SCRIPT_DIR) not in _sys.path:
    _sys.path.insert(0, str(SCRIPT_DIR))
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
    """Extract match rows from a group's markdown table. Supports R3, R4, R5 styles."""
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

    # R5 style: | MD | Match | A% | D% | B% | MLS |  (numeric MD col, plain numbers w/o %)
    # Skip header rows where col1 is "MD" or "---"
    for row in re.finditer(
        r"\|\s*(\d+)\s*\|\s*([^|]+?)\s+vs\s+([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        md, team_a, team_b, a_pct, draw_pct, b_pct, score_raw = row.groups()
        matches.append({
            "stage": f"Group {group_letter}",
            "matchday": int(md),
            "team_a": team_a.strip(),
            "team_b": team_b.strip(),
            "team_a_win": parse_pct(a_pct + "%"),
            "draw": parse_pct(draw_pct + "%"),
            "team_b_win": parse_pct(b_pct + "%"),
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


def _parse_md1_narrative(section_text: str, teams: list) -> list:
    """Extract MD1 (already-played) matches from R5 narrative line.

    R5 example narrative formats:
      "*MD1 already played: Mexico 2-0 South Africa; South Korea 2-1 Czech Republic*"
      "*MD1: Canada 1-1 Bosnia*"
      "*MD1: Scotland 1-0 Morocco; Brazil played Haiti 6/12 (projected 3-0 win)*"
      "*MD1: Australia 2-0 win; USA–Paraguay and Turkey fixtures pending*"  (incomplete)
      "*MD1: Germany 7-1 Ivory Coast*"

    Returns list of dicts with team_a / team_b / most_likely_score / matchday=1.
    Skips narrative entries that name only one team (e.g. "Australia 2-0 win")
    because we can't pair them. Caller backfills the rest from real data.
    """
    # Pull the first *MD1 ...* narrative line from this section
    narr = re.search(r"\*MD1[^:]*:\s*([^*]+?)\*", section_text)
    if not narr:
        return []
    body = narr.group(1)

    md1 = []
    for piece in re.split(r"\s*;\s*", body):
        m = re.match(
            r"\s*([A-Za-z .'’\-]+?)\s+(\d+)\s*[-–]\s*(\d+)\s+([A-Za-z .'’\-]+?)\s*(?:\(.*\))?\s*$",
            piece,
        )
        if not m:
            continue
        a_raw, a_score, b_score, b_raw = m.groups()
        a = _match_team(a_raw.strip(), teams)
        b = _match_team(b_raw.strip(), teams)
        if not a or not b:
            continue
        md1.append({
            "stage": None,  # filled by caller
            "matchday": 1,
            "team_a": a,
            "team_b": b,
            "team_a_win": 1.0 if int(a_score) > int(b_score) else (0.0 if int(a_score) < int(b_score) else 0.0),
            "draw": 1.0 if int(a_score) == int(b_score) else 0.0,
            "team_b_win": 1.0 if int(b_score) > int(a_score) else 0.0,
            "most_likely_score": {
                "raw": f"{a_score}-{b_score}",
                "home": int(a_score),
                "away": int(b_score),
                "aet": False,
                "pens": False,
            },
            "is_played": True,
        })
    return md1


def _match_team(raw: str, candidates: list) -> Optional[str]:
    """Fuzzy match `raw` (e.g. 'USA', 'South Africa', 'Bosnia') against the
    canonical teams list. Returns the canonical team name or None."""
    if not raw:
        return None
    raw_l = raw.lower()
    for c in candidates:
        if c.lower() == raw_l:
            return c
    for c in candidates:
        if raw_l in c.lower() or c.lower() in raw_l:
            return c
    for c in candidates:
        if c.lower().startswith(raw_l) or raw_l.startswith(c.lower()):
            return c
    return None


def _load_real_md1_for_backfill() -> dict:
    """Load data/real/wc_2026_results.json and bucket MD1 matches by group.

    MD1 is determined by date sort: the earliest matchday in each group is MD1.
    We do not have explicit matchday info from ESPN, so we approximate by
    selecting the first 2 matches per group (4-team group has 2 MD1 matches).
    For groups where MiroFish already filled MD1, the backfill is a no-op
    (de-dupe key on team pair).
    """
    real_path = ROOT / "data" / "real" / "wc_2026_results.json"
    if not real_path.exists():
        return {}
    try:
        data = json.loads(real_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    by_group = {}
    for m in data.get("matches", []):
        g = m.get("group")
        if not g:
            continue
        by_group.setdefault(g, []).append(m)
    # Sort each group by date (asc) so MD1 are the first 2 entries
    md1_only = {}
    for g, ms in by_group.items():
        sorted_ms = sorted(ms, key=lambda x: x.get("date", ""))
        # MD1 has 2 matches (4-team group). For groups with more matches
        # already played, just return the first 2 — backfill is conservative.
        md1_only[g] = sorted_ms[:2]
    return md1_only


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

    # Match R5: **Final standings:** 1) Mexico 7pts 2) South Korea 6pts 3) Czech Republic 3pts 4) South Africa 0pts. ...
    r5_match = re.search(r"\*\*Final\s+standings:\*\*\s*([^\n]+)", section_text)
    if r5_match:
        text = r5_match.group(1).strip()
        # split on " N) " or "(GD +/-)" patterns; 关键是用数字编号 split
        # 提取 entries via: "1) Mexico 7pts 2) South Korea 6pts ..."
        entries = re.findall(r"\d+\)\s*([^\d]+?)\s+(\d+)\s*pts?", text)
        if entries:
            standings = []
            for team, pts in entries:
                standings.append({
                    "team": team.strip(),
                    "points": int(pts),
                    "note": None,
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
    section_match = re.search(r"##\s*(?:\d+\.\s*)?(?:8|Eight)\s+Best\s+(?:Third|3rd)[-\s]Place", md_text)
    if not section_match:
        return []
    start = section_match.end()
    next_section = re.search(r"\n##\s", md_text[start:])
    end = start + next_section.start() if next_section else len(md_text)
    section_text = md_text[start:end]

    rows = []

    # R5 markdown table: | Rank | Team | Group | Pts | GD | Pool |
    for row in re.finditer(
        r"\|\s*(\d+)\s*\|\s*([^*|]+?)\s*\|\s*([A-L])\s*\|\s*(\d+)\s*\|\s*([+\-]?\d+)\s*\|\s*([^|]+?)\s*\|",
        section_text,
    ):
        rank, team, group, pts, gd, pool = row.groups()
        rows.append({
            "rank": int(rank),
            "team": team.strip(),
            "group": group.strip(),
            "points": int(pts),
            "goal_difference": int(gd),
            "reason": f"R5 pool={pool.strip()}",
        })

    # R5 corrected list (sometimes replaces first table): 1. Iran (G, 5pts, +3GD)
    if not rows:
        for row in re.finditer(
            r"(\d+)\.\s*\*\*([^*]+?)\*\*\s*\(([A-L]),\s*(\d+)pts?,\s*([+\-]?\d+)GD\)",
            section_text,
        ):
            rank, team, group, pts, gd = row.groups()
            rows.append({
                "rank": int(rank),
                "team": team.strip(),
                "group": group.strip(),
                "points": int(pts),
                "goal_difference": int(gd),
                "reason": "R5 corrected list",
            })

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

    if risks:
        return risks

    # R5 numbered: 1. **MD2 Croatia vs Ghana (Group L)** — 48/26/26. Ghana's pace ...
    # Use a single combined regex so rationale matches the SAME entry as the team.
    for row in re.finditer(
        r"(\d+)\.\s*\*\*([^*\n]+?)\*\*\s*[—\-–]\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\.?\s*([^\n]+)",
        section_text,
    ):
        rank, match, _a, _d, _b, rationale = row.groups()
        nums = [int(_a), int(_d), int(_b)]
        risks.append({
            "rank": int(rank),
            "match": match.strip(),
            "stage": "—",
            "upset_probability": (100 - max(nums)) / 100.0,
            "rationale": rationale.strip(),
        })

    return risks


def _strip_group_pos(raw: str) -> str:
    """[Legacy] Strip 'Mexico (1A)' (R3) or 'Mexico (A1)' (R4) → 'Mexico'. Tolerant of leading **bold** markers."""
    name, _g, _s = _parse_team_with_seed(raw)
    return name


def _parse_team_with_seed(raw: str):
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


def _extract_winner_from_score(score: str, team_a: str, team_b: str) -> Optional[str]:
    """If R5 score annotates the winner in parens (e.g. '1-2 (France)' or
    '1-1 (Argentina pens)'), match against team_a/team_b and return 'a'/'b'.

    Returns None when no annotation or team name doesn't match.
    """
    m = re.search(r"\(([^)]+)\)\s*$", score)
    if not m:
        return None
    inner = m.group(1)
    # Strip "pens" / "pen" / "wins" suffixes that signal how (not who)
    cleaned = re.sub(r"\b(pens?|wins?|on pens|aet)\b", "", inner, flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    if cleaned == team_a:
        return "a"
    if cleaned == team_b:
        return "b"
    # Partial match (e.g. "France wins" → "France")
    if team_a in cleaned or cleaned in team_a:
        return "a"
    if team_b in cleaned or cleaned in team_b:
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
        # R5 style: | # | 1st A (Mexico) vs 2nd B (Canada) | 44 | 28 | 28 | 1-0 | 22 | 10 |
        # Best-3rd slot: | # | 1st E (Germany) vs 3rd (Scotland) | ... (group letter optional)
        r5_rows = list(re.finditer(
            r"\|\s*(?:\w+\s*\|)?\s*(\d+)(?:st|nd|rd|th)\s+(?:([A-L])\s+)?\(([^)]+)\)\s+vs\s+(\d+)(?:st|nd|rd|th)\s+(?:([A-L])\s+)?\(([^)]+)\)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
            section_text,
        ))
        for row in r5_rows:
            seed_a, group_a, team_a, seed_b, group_b, team_b, a_pct, d_pct, b_pct, score, aet_pct, pen_pct = row.groups()
            if a_pct == "0" and d_pct == "0" and b_pct == "0":
                continue
            team_a_s, team_b_s = team_a.strip(), team_b.strip()
            score_clean = score.strip()
            winner_hint = _extract_winner_from_score(score_clean, team_a_s, team_b_s)
            matches.append({
                "bracket_idx": len(matches),  # sequential index for R5
                "team_a": team_a_s,
                "group_a": group_a.strip() if group_a else None,
                "seed_a": int(seed_a),
                "team_b": team_b_s,
                "group_b": group_b.strip() if group_b else None,
                "seed_b": int(seed_b),
                "team_a_win": parse_pct(a_pct + "%"),
                "draw": parse_pct(d_pct + "%"),
                "team_b_win": parse_pct(b_pct + "%"),
                "score": score_clean,
                "aet_pct": parse_pct(aet_pct + "%"),
                "pen_pct": parse_pct(pen_pct + "%"),
                "winner": winner_hint or _winner_from_pct(a_pct + "%", b_pct + "%", d_pct + "%"),
            })

        if matches:
            return matches

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
        # R5 style: | R16-1 | TeamA vs TeamB | 64 | 22 | 14 | 2-1 | 14 | 6 | (plain numbers, no %)
        r4_rows = list(re.finditer(
            r"\|\s*(?:R\d+-\d+|QF\d+|SF\d+|Match)\s*\|\s*\**([^|*]+?)\**\s+vs\s+\**([^|*]+?)\**(?:\s*\([^)]+\))?\s*\|\s*(\d+%?)\s*\|\s*(\d+%?)\s*\|\s*(\d+%?)\s*\|\s*([^|]+?)\s*\|\s*(\d+%?)\s*\|\s*(\d+%?)\s*\|",
            section_text,
        ))
        for row in r4_rows:
            team_a, team_b, a_pct, d_pct, b_pct, score, aet_pct, pen_pct = row.groups()
            team_a_clean, group_a, seed_a = _parse_team_with_seed(team_a)
            team_b_clean, group_b, seed_b = _parse_team_with_seed(team_b)
            # normalize to "N%" for parse_pct
            def _norm_pct(s: str) -> str:
                s = s.strip()
                return s if s.endswith("%") else s + "%"
            a_n, d_n, b_n, ae_n, pe_n = _norm_pct(a_pct), _norm_pct(d_pct), _norm_pct(b_pct), _norm_pct(aet_pct), _norm_pct(pen_pct)
            # R5 score may carry winner hint in parentheses, e.g. "1-1 (Argentina pens)"
            # or "1-2 (France)". Use that to override a_pct/b_pct when the
            # probabilities are tied or draw is highest (AET/pen decided).
            score_clean = score.strip()
            winner_hint = _extract_winner_from_score(score_clean, team_a_clean, team_b_clean)
            matches.append({
                "team_a": team_a_clean,
                "group_a": group_a,
                "seed_a": seed_a,
                "team_b": team_b_clean,
                "group_b": group_b,
                "seed_b": seed_b,
                "team_a_win": parse_pct(a_n),
                "draw": parse_pct(d_n),
                "team_b_win": parse_pct(b_n),
                "score": score_clean,
                "aet_pct": parse_pct(ae_n),
                "pen_pct": parse_pct(pe_n),
                "winner": winner_hint or _winner_from_pct(a_n, b_n, d_n),
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


# ---------------------------------------------------------------------------
# 134 兜底: 按 FIFA 真实 Match 73-88 规则生成 R32 配对
# 不信 MiroFish 的配对 (历史 R3/R4 都跑错过), 用 standings + best_thirds 强制按
# 官方规则算。来源: Wikipedia "2026 FIFA World Cup knockout stage"。
# ---------------------------------------------------------------------------
# (match_num, slot1_kind, slot1_arg, slot2_kind, slot2_arg)
# kind ∈ {"winner", "runner_up", "best3"}; best3 的 arg 是 allowed group letters tuple
REAL_R32_RULES = [
    (73, "runner_up", "A", "runner_up", "B"),
    (74, "winner",    "E", "best3", ("A","B","C","D","F")),
    (75, "winner",    "F", "runner_up", "C"),
    (76, "winner",    "C", "runner_up", "F"),
    (77, "winner",    "I", "best3", ("C","D","F","G","H")),
    (78, "runner_up", "E", "runner_up", "I"),
    (79, "winner",    "A", "best3", ("C","E","F","H","I")),
    (80, "winner",    "L", "best3", ("E","H","I","J","K")),
    (81, "winner",    "D", "best3", ("B","E","F","I","J")),
    (82, "winner",    "G", "best3", ("A","E","H","I","J")),
    (83, "runner_up", "K", "runner_up", "L"),
    (84, "winner",    "H", "runner_up", "J"),
    (85, "winner",    "B", "best3", ("E","F","G","I","J")),
    (86, "winner",    "J", "runner_up", "H"),
    (87, "winner",    "K", "best3", ("D","E","I","J","L")),
    (88, "runner_up", "D", "runner_up", "G"),
]


def _resolve_r32_slot(groups: dict, best_thirds: list, kind: str, arg, used: set) -> dict:
    """Resolve one R32 slot to {team, group, seed}.

    - kind="winner":    arg = group letter, take standings[0]
    - kind="runner_up": arg = group letter, take standings[1]
    - kind="best3":     arg = tuple of allowed group letters, greedy pick
                        best_thirds sorted by rank asc, skip used, must be in allowed set
    """
    if kind == "winner":
        st = groups.get(arg, {}).get("standings", [])
        if not st:
            return {"team": f"{arg}组头名(待定)", "group": arg, "seed": 1}
        return {"team": st[0]["team"], "group": arg, "seed": 1}
    if kind == "runner_up":
        st = groups.get(arg, {}).get("standings", [])
        if len(st) < 2:
            return {"team": f"{arg}组次名(待定)", "group": arg, "seed": 2}
        return {"team": st[1]["team"], "group": arg, "seed": 2}
    if kind == "best3":
        for bt in sorted(best_thirds, key=lambda x: x.get("rank", 99)):
            key = (bt["team"], bt["group"])
            if key in used:
                continue
            if bt["group"] not in arg:
                continue
            used.add(key)
            return {"team": bt["team"], "group": bt["group"], "seed": 3}
        return {"team": "best3(待定)", "group": None, "seed": 3}
    raise ValueError(f"unknown r32 slot kind: {kind}")


def build_real_r32(groups: dict, best_thirds: list) -> list:
    """按 FIFA 真实 Match 73-88 规则生成 16 场 R32 (覆盖 MiroFish 错配)。

    Returns list of 16 BracketMatch dicts 按 Match 73→88 升序。
    概率字段重置为中性 (0.5/0.0/0.5, winner=null, score="待定"), 不沿用 MiroFish 错配的概率。
    """
    used_best3 = set()
    out = []
    for idx, (_, k1, a1, k2, a2) in enumerate(REAL_R32_RULES):
        s1 = _resolve_r32_slot(groups, best_thirds, k1, a1, used_best3)
        s2 = _resolve_r32_slot(groups, best_thirds, k2, a2, used_best3)
        out.append({
            "bracket_idx": idx,
            "team_a": s1["team"], "group_a": s1["group"], "seed_a": s1["seed"],
            "team_b": s2["team"], "group_b": s2["group"], "seed_b": s2["seed"],
            "team_a_win": 0.5, "draw": 0.0, "team_b_win": 0.5,
            "score": "待定", "aet_pct": None, "pen_pct": None, "winner": None,
        })
    return out


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

    # R5 style: | Outcome Tier | Probability | Score |
    #   | 90-minute decision | **52%** | France 2–1 Argentina |
    if not tiers:
        # Match rows like "| <label> | **<pct>%** | <score> |"
        for i, trow in enumerate(re.finditer(
            r"\|\s*([^|*]+?)\s*\|\s*\*\*(\d+)%\*\*\s*\|\s*([^|\n]+?)\s*\|",
            section_text,
        ), start=1):
            label_raw, pct, score_raw = trow.groups()
            label_raw = label_raw.strip()
            if label_raw.lower() in {"outcome tier", "tier", "score", "probability"}:
                continue  # header row
            label_zh_map = {
                "90-minute decision": "90 min",
                "after extra time": "AET",
                "penalties": "Penalties",
                "90 minutes (regulation)": "90 min",
                "after extra time (aet)": "AET",
            }
            label_zh = label_zh_map.get(label_raw.lower(), label_raw)
            tiers.append({
                "tier": i,
                "label": label_zh,
                "content": score_raw.strip(),
                "probability": int(pct) / 100,
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


def load_elo_baseline() -> dict:
    """Read data/elo/wc_2026_baseline.json (Elo-Poisson top-3 scores).

    Returns {} if the file is missing (e.g., first run before elo_poisson.py
    has been executed). Format:
      {meta, matches: [{key, stage, team_a, team_b, top_3: [{home, away, prob}, ...], ...}]}
    """
    fp = ROOT / "data" / "elo" / "wc_2026_baseline.json"
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _enrich_with_top3(matches, baseline):
    """For each match, attach top_3_scores from the Elo-Poisson baseline.

    Two-step resolution:
      1. Lookup in pre-computed baseline (data/elo/wc_2026_baseline.json) by
         (stage, sorted team pair). Works when the run being parsed uses the
         SAME name style as the run that built the baseline.
      2. On miss, compute on the fly via elo_poisson.predict_one — handles the
         R4 (3-letter codes) vs R3 (full names) mismatch automatically, since
         the Elo JSON has both spellings.
    Returns (matches, n_enriched).
    """
    if not matches:
        return matches, 0
    by_key = {}
    if baseline and baseline.get("matches"):
        for bm in baseline["matches"]:
            s = (bm.get("stage") or "").strip()
            a = (bm.get("team_a") or "").strip().lower()
            b = (bm.get("team_b") or "").strip().lower()
            if not a or not b:
                continue
            k = (s.lower(), tuple(sorted([a, b])))
            if bm.get("top_3") and k not in by_key:
                by_key[k] = bm["top_3"]
    n = 0
    elo_helper = None  # lazy import
    elo_ratings = None
    for m in matches:
        s = (m.get("stage") or "").strip()
        a = (m.get("team_a") or "").strip()
        b = (m.get("team_b") or "").strip()
        if not a or not b:
            continue
        k = (s.lower(), tuple(sorted([a.lower(), b.lower()])))
        top3 = by_key.get(k)
        if not top3:
            if elo_helper is None:
                try:
                    import elo_poisson  # type: ignore
                    elo_helper = elo_poisson
                    elo_ratings = elo_helper.load_elo_ratings()
                except (ImportError, OSError):
                    elo_helper = False
            if elo_helper and elo_helper is not False:
                pred = elo_helper.predict_one(a, b, elo_ratings)
                top3 = pred.get("top_3")
        if top3:
            m["top_3_scores"] = top3
            n += 1
    return matches, n


def parse_run(run_id: str, run_dir: Path) -> dict:
    report_md = (run_dir / "report" / "report.md").read_text(encoding="utf-8")
    verdict = json.loads((run_dir / "report" / "verdict.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "report" / "summary.json").read_text(encoding="utf-8"))

    # All 12 groups
    groups = {}
    real_md1 = _load_real_md1_for_backfill()  # {group: [{team_a, team_b, score_a, score_b, date}]}
    for letter in "ABCDEFGHIJKL":
        teams = _find_group_teams(report_md, letter)
        matches = parse_group_table(report_md, letter)
        # R5: MD1 matches are described in narrative line above the table.
        # Try to extract them and prepend; mark is_played=True so the UI
        # can color them as "已比赛" without conflicting with future predictions.
        start, end = _find_group_section(report_md, letter)
        if start != -1:
            section_text = report_md[start:end]
            md1 = _parse_md1_narrative(section_text, teams)
            for m in md1:
                m["stage"] = f"Group {letter}"
                # Avoid duplicates (in case the table also lists MD1)
                if not any(
                    ex["team_a"] == m["team_a"] and ex["team_b"] == m["team_b"]
                    and ex["matchday"] == 1
                    for ex in matches
                ):
                    matches.append(m)
            # For F-L, MiroFish listed MD1 in the table as predictions, but
            # often with WRONG matchups (e.g. MiroFish said Netherlands-Sweden
            # MD1 but the actual FIFA MD1 was Netherlands-Japan). To avoid
            # bogus "future MD1" rows polluting the data, drop MiroFish's MD1
            # entries that don't correspond to a real played match, then
            # append the real MD1 entries. For A-E, narrative backfill above
            # already added real MD1 entries; we dedupe by team pair.
            real_pairs = set()
            for rm in real_md1.get(letter, []):
                team_a = _match_team(rm["team_a"], teams)
                team_b = _match_team(rm["team_b"], teams)
                if not team_a or not team_b:
                    continue
                real_pairs.add(frozenset({team_a, team_b}))
                sa, sb = rm["score_a"], rm["score_b"]
                replaced = False
                for ex in matches:
                    if ex["matchday"] == 1 and (
                        {ex["team_a"], ex["team_b"]} == {team_a, team_b}
                    ):
                        ex["most_likely_score"] = {
                            "raw": f"{sa}-{sb}",
                            "home": sa,
                            "away": sb,
                            "aet": False,
                            "pens": False,
                        }
                        ex["team_a_win"] = 1.0 if sa > sb else (0.0 if sa < sb else 0.0)
                        ex["draw"] = 1.0 if sa == sb else 0.0
                        ex["team_b_win"] = 1.0 if sb > sa else 0.0
                        ex["is_played"] = True
                        ex["played_date"] = rm.get("date")
                        replaced = True
                        break
                if replaced:
                    continue
                matches.append({
                    "stage": f"Group {letter}",
                    "matchday": 1,
                    "team_a": team_a,
                    "team_b": team_b,
                    "team_a_win": 1.0 if sa > sb else (0.0 if sa < sb else 0.0),
                    "draw": 1.0 if sa == sb else 0.0,
                    "team_b_win": 1.0 if sb > sa else 0.0,
                    "most_likely_score": {
                        "raw": f"{sa}-{sb}",
                        "home": sa,
                        "away": sb,
                        "aet": False,
                        "pens": False,
                    },
                    "is_played": True,
                    "played_date": rm.get("date"),
                })
            # Drop ALL MD1 entries whose pairing is NOT in real data
            # (these are bogus predictions/narrative with wrong matchups).
            # Real MD1 is authoritative; only real entries survive.
            matches = [
                m for m in matches
                if not (m["matchday"] == 1
                        and frozenset({m["team_a"], m["team_b"]}) not in real_pairs)
            ]
        groups[letter] = {
            "letter": letter,
            "teams": teams,
            "matches": matches,
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

    best_thirds = parse_best_thirds(report_md)
    # Dedupe best_thirds: 如果既匹配 first table 又匹配 corrected list, 只保留 corrected (8 个)
    if len(best_thirds) > 8:
        # 保留每组 (rank, team, group) 唯一的 8 个; rank 1-8 优先
        seen = set()
        deduped = []
        # 先按 rank 排序, 取前 8 个 unique
        for bt in sorted(best_thirds, key=lambda x: x.get("rank", 99)):
            key = (bt["team"], bt["group"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(bt)
            if len(deduped) >= 8:
                break
        best_thirds = deduped

    bracket = parse_bracket(report_md)
    # 134 兜底: 用 FIFA 真实 Match 73-88 规则覆盖 MiroFish 错配的 R32
    # 只在 MiroFish 解析出 R32 但配对看起来错位时触发。R5 现在 R32 表格清晰,
    # 解析出的 team_a_win/draw/team_b_win 概率应该用 MiroFish 的, 不用中性 0.5。
    # 判断标准: MiroFish R32 第一个 entry 概率是否全 0 (134 兜底标志)
    needs_override = False
    if bracket["r32"] and len(groups) == 12:
        first = bracket["r32"][0]
        if (first.get("team_a_win") in (None, 0.0)
            and first.get("draw") in (None, 0.0)
            and first.get("team_b_win") in (None, 0.0)):
            needs_override = True
        # 或 MiroFish 报告含明显错位信号 (e.g. M73 不应该是 runner-up A vs runner-up B)
        m73 = next((m for m in bracket["r32"] if m.get("bracket_idx") == 0), None)
        if m73:
            a_team, a_group, a_seed = m73.get("team_a"), m73.get("group_a"), m73.get("seed_a")
            b_team, b_group, b_seed = m73.get("team_b"), m73.get("group_b"), m73.get("seed_b")
            # FIFA M73 = Runner-up A vs Runner-up B (a_seed=2,b_seed=2,a_group=A,b_group=B)
            if not (a_seed == 2 and b_seed == 2 and a_group == "A" and b_group == "B"):
                needs_override = True
    if needs_override:
        bracket["r32"] = build_real_r32(groups, best_thirds)

    # A+B 提分: 注入 Elo-Poisson top_3_scores 到所有 match
    # (MiroFish 未来输出新 top_3 字段会覆盖; 现在都是 fallback 兜底)
    baseline = load_elo_baseline()
    n_top3 = 0
    for letter, g in groups.items():
        g["matches"], n = _enrich_with_top3(g["matches"], baseline)
        n_top3 += n
    for stage in ["r32", "r16", "qf", "sf"]:
        if bracket.get(stage):
            bracket[stage], n = _enrich_with_top3(bracket[stage], baseline)
            n_top3 += n
    if n_top3 > 0:
        print(f"  [A+B] enriched {n_top3} matches with top_3_scores from Elo-Poisson baseline")

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
        "best_thirds": best_thirds,
        "bracket": bracket,
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