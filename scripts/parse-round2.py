#!/usr/bin/env python3
"""
parse-round2.py — Lightweight parser for Round 2 MiroFish report (run_a18431af48fd).
Round 2 uses inline-list format (different from Round 3's table format).
This parser extracts only the high-level verdict + a subset of matches for multi-round comparison.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def parse_pct(s: str) -> float:
    s = s.strip().rstrip("%").strip()
    try:
        return float(s) / 100
    except ValueError:
        return 0.0


def parse_round2(run_id: str, run_dir: Path) -> dict:
    report_md = (run_dir / "report" / "report.md").read_text(encoding="utf-8")
    verdict = json.loads((run_dir / "report" / "verdict.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "report" / "summary.json").read_text(encoding="utf-8"))

    # Champion probabilities (from Section 1 quote)
    champ_table = {}
    champ_match = re.search(
        r"CHAMPION CONFIDENCE LEVELS:\s*([^\"]+?)\.",
        report_md,
    )
    if champ_match:
        text = champ_match.group(1)
        for entry in re.finditer(r"(\S+)\s+(\d+)%", text):
            team, pct = entry.groups()
            champ_table[team.strip()] = int(pct) / 100

    # Group A, B, C, ... matches (inline-list format)
    groups = {}
    for letter in "ABCDEFGHIJKL":
        # Match the group section
        m = re.search(rf"###\s*Group\s+{letter}\s*—\s*([^(]+)", report_md)
        if not m:
            continue
        teams = [t.strip() for t in m.group(1).split(",")]
        # Find the section end
        start = m.end()
        next_section = re.search(r"\n###\s", report_md[start:])
        end = start + next_section.start() if next_section else len(report_md)
        section_text = report_md[start:end]

        # Parse MD2/MD3 lines
        matches = []
        for line_match in re.finditer(
            r"\*\*(MD\d+)\s*—\s*([^*]+?)\*\*\s*\(([^)]+)\)",
            section_text,
        ):
            md_label, matchup, probs = line_match.groups()
            # matchup like "Mexico 2-0 South Korea"
            game_match = re.match(r"(.+?)\s+(\d+)\s*[-:]\s*(\d+)\s+(.+)", matchup)
            if not game_match:
                continue
            team_a, ha, hb, team_b = game_match.groups()
            # probs like "MEX 64% / Draw 22% / KOR 14%"
            prob_parts = re.findall(r"(\S+)\s+(\d+)%", probs)
            a_pct = 0
            b_pct = 0
            d_pct = 0
            for label, pct in prob_parts:
                if "Draw" in label or label.lower() == "draw":
                    d_pct = int(pct) / 100
                else:
                    # First non-Draw label is team A, second is team B
                    if a_pct == 0:
                        a_pct = int(pct) / 100
                    else:
                        b_pct = int(pct) / 100
            matches.append({
                "stage": f"Group {letter}",
                "matchday": int(md_label.replace("MD", "")),
                "team_a": team_a.strip(),
                "team_b": team_b.strip(),
                "team_a_win": a_pct,
                "draw": d_pct,
                "team_b_win": b_pct,
                "most_likely_score": {
                    "raw": f"{ha}-{hb}",
                    "home": int(ha),
                    "away": int(hb),
                    "aet": False,
                    "pens": False,
                },
            })
        groups[letter] = {
            "letter": letter,
            "teams": teams,
            "matches": matches,
        }

    # Final matchup (from Section 1)
    final_match = re.search(r"Projected final:\s*\*\*([^*]+)\*\*", report_md)
    final_matchup = final_match.group(1).strip() if final_match else None

    return {
        "run_id": run_id,
        "created_at": summary.get("created_at", ""),
        "round": 2,
        "format": "inline-list",
        "verdict": {
            "prediction": verdict["prediction"],
            "confidence": verdict["confidence"],
            "key_dynamics": verdict["key_dynamics"],
            "signals": verdict["signals"],
        },
        "champion_table": champ_table,
        "groups": groups,
        "final": {
            "matchup": final_matchup,
            "champion": "Argentina",
            "confidence": 0.22,
        },
        "report_markdown": report_md,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: parse-round2.py <run_id> <run_dir>", file=sys.stderr)
        sys.exit(1)
    run_id = sys.argv[1]
    run_dir = Path(sys.argv[2])
    if not run_dir.exists():
        print(f"Error: {run_dir} not found", file=sys.stderr)
        sys.exit(1)

    data = parse_round2(run_id, run_dir)
    out_path = DATA_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Parsed Round 2 {run_id} → {out_path}")
    print(f"  Groups: {sum(len(g['matches']) for g in data['groups'].values())} matches")
    print(f"  Champion table: {data['champion_table']}")
    print(f"  Final: {data['final']['matchup']}")


if __name__ == "__main__":
    main()
