#!/usr/bin/env python3
"""Elo-Poisson baseline score prediction for WC 2026.

Inputs:
  - data/elo/wc_2026_elo.json (48 teams, sourced from Wikipedia FIFA Top 20 +
    curated snapshot for the rest)
  - data/runs/<latest>.json (MiroFish R3/R4 group/bracket schedule)

Model:
  - Δ = Elo_a − Elo_b (WC is at neutral venues, no home advantage)
  - λ_a = μ · σ(Δ / 400),  λ_b = μ · σ(−Δ / 400)  where μ = 1.4
  - σ(x) = 1 / (1 + 10^(−x))   ← logistic used in standard Elo win-prob
  - P(home = h, away = a) = Poisson(h; λ_a) · Poisson(a; λ_b)
  - Independently model each team's goals (standard bivariate-Poisson
    simplification; correlation handled implicitly via shared Elo gap).

Output:
  - data/elo/wc_2026_baseline.json
    {
      meta: {generated_at, mu, max_goals, source},
      matches: [
        {key, stage, team_a, team_b, lambda_a, lambda_b,
         top_3: [{home, away, prob, pct}, ...],
         win_a, draw, win_b},
        ...
      ]
    }

Used as:
  1. Context injected into MiroFish prompt (daily-update.sh step 0.5/5)
     — gives the LLM a numeric baseline to anchor on, not just "feel".
  2. Fallback top_3_scores when MiroFish doesn't provide them.
  3. Sanity check: MiroFish's "most_likely_score" should be within top 3 here
     for the prediction to be considered reasonable.

Why Elo-Poisson (not just LLM):
  LLM zero-shot score prediction = ~10-15% exact-score hit rate.
  Elo-Poisson on real WC matches = ~22-28% top-1, ~45-55% top-3.
  Source: Dixon-Coles 1997, Štrumbelj 2014, etc. Best public models using
  Elo + xG reach 30-35% top-1.
"""
from __future__ import annotations
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ELO_FILE = ROOT / "data" / "elo" / "wc_2026_elo.json"
BASELINE_OUT = ROOT / "data" / "elo" / "wc_2026_baseline.json"
RUNS_DIR = ROOT / "data" / "runs"

# Model parameters
MU = 1.4          # average goals per team per game (WC 2022 ≈ 1.35, 2018 ≈ 1.32)
MAX_GOALS = 6     # compute probability for scorelines 0-0 through 6-6


def elo_to_lambda(elo_a: float, elo_b: float, mu: float = MU) -> tuple[float, float]:
    """Convert Elo difference to expected goals for each team.

    Δ > 0 means team A is stronger.
    Returns (λ_a, λ_b) such that Poisson(λ_a) and Poisson(λ_b) are the
    independent goal distributions.
    """
    delta = elo_a - elo_b
    # 1 / (1 + 10^(-Δ/400)) is the standard Elo win probability formula;
    # using it as a fraction of μ gives a sensible scaling (Δ=0 → both 0.7;
    # Δ=+200 → 1.06/0.34; Δ=+400 → 1.31/0.09).
    p_a = 1.0 / (1.0 + 10.0 ** (-delta / 400.0))
    p_b = 1.0 - p_a
    return mu * p_a, mu * p_b


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(λ), computed in log space to avoid overflow."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    # log P = k·log(λ) − λ − log(k!)
    log_p = k * math.log(lam) - lam - math.lgamma(k + 1)
    return math.exp(log_p)


def score_distribution(lam_a: float, lam_b: float, max_goals: int = MAX_GOALS) -> dict:
    """Compute full bivariate-Poisson score probability grid.

    Returns {(h, a): probability} for h, a in [0, max_goals].
    Probabilities sum to ≈ 1 (residual < 1% for high-scoring outliers).
    """
    probs = {}
    for h in range(max_goals + 1):
        p_h = poisson_pmf(h, lam_a)
        if p_h < 1e-12:
            continue
        for a in range(max_goals + 1):
            p_a = poisson_pmf(a, lam_b)
            if p_a < 1e-12:
                continue
            p = p_h * p_a
            if p >= 1e-6:  # skip negligible cells
                probs[(h, a)] = p
    return probs


def top_n_scores(probs: dict, n: int = 3) -> list[dict]:
    """Return top-n most probable (home, away) tuples with their probabilities."""
    items = sorted(probs.items(), key=lambda x: -x[1])[:n]
    return [
        {"home": h, "away": a, "prob": round(p, 4), "pct": round(p * 100, 1)}
        for (h, a), p in items
    ]


def outcome_probs(probs: dict) -> tuple[float, float, float]:
    """Aggregate score distribution into (P(a wins), P(draw), P(b wins))."""
    win_a = draw = win_b = 0.0
    for (h, a), p in probs.items():
        if h > a:
            win_a += p
        elif h < a:
            win_b += p
        else:
            draw += p
    return round(win_a, 4), round(draw, 4), round(win_b, 4)


def load_elo_ratings() -> dict[str, float]:
    data = json.loads(ELO_FILE.read_text(encoding="utf-8"))
    return data["ratings"]


def get_canonical_run() -> Path | None:
    """Pick the canonical R3/R4 run (the one with the most populated schedule).

    mtime ordering is unreliable here: the R2 baseline (a18431) is the
    "official" reference but has 0 group matches; R3/R4 runs may have been
    written later but they're what we want for the schedule.
    """
    if not RUNS_DIR.exists():
        return None
    candidates = list(RUNS_DIR.glob("*.json"))
    if not candidates:
        return None
    def richness(p: Path) -> tuple[int, int, float]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return (0, 0, 0.0)
        n_groups = sum(len(g.get("matches") or []) for g in (d.get("groups") or {}).values())
        n_bracket = sum(len(d.get("bracket", {}).get(s) or []) for s in ["r32", "r16", "qf", "sf"])
        # Combined score (groups + bracket) — gives the prompt the full schedule.
        return (n_groups + n_bracket, 0, p.stat().st_mtime)
    candidates.sort(key=richness, reverse=True)
    return candidates[0]


def extract_schedule(run: dict) -> list[dict]:
    """Walk the MiroFish run structure and pull out every (team_a, team_b) pair.

    Sources (in priority order, dedup by sorted pair):
      1. R3/R4 group matches (12 groups × 6 = 72 fixtures)
      2. R32 / R16 / QF / SF / Final bracket matches (15 + 1 + 2 + 4 + 1 = wait,
         R32 has 16, R16 has 8, QF has 4, SF has 2, Final has 1 = 31)
         R3 also includes 3rd place playoff.
    """
    schedule: list[dict] = []
    seen = set()

    def add(stage: str, team_a: str, team_b: str, group: str | None = None) -> None:
        if not team_a or not team_b or team_a == team_b:
            return
        key = tuple(sorted([team_a, team_b]))
        if key in seen:
            return
        seen.add(key)
        schedule.append({"stage": stage, "team_a": team_a, "team_b": team_b, "group": group})

    # 1. Group matches
    for letter, g in (run.get("groups") or {}).items():
        for m in g.get("matches") or []:
            add(f"Group {letter}", m["team_a"], m["team_b"], group=letter)

    # 2. Knockout
    for stage in ["r32", "r16", "qf", "sf"]:
        for m in run.get("bracket", {}).get(stage) or []:
            add(stage.upper(), m.get("team_a") or "", m.get("team_b") or "")
    if run.get("bracket", {}).get("final_matchup"):
        fm = run["bracket"]["final_matchup"]
        if " vs " in fm:
            a, b = fm.split(" vs ", 1)
            add("FINAL", a.strip(), b.strip())

    return schedule


def predict_one(team_a: str, team_b: str, ratings: dict[str, float]) -> dict:
    """Compute top-3 scores + outcome probs for a single match.

    If a team is missing from the Elo table, fall back to μ/2 each (50/50).
    """
    elo_a = ratings.get(team_a)
    elo_b = ratings.get(team_b)
    if elo_a is None or elo_b is None:
        lam_a = lam_b = MU / 2
        missing = [t for t, e in [(team_a, elo_a), (team_b, elo_b)] if e is None]
        print(f"  ⚠️  missing Elo for {missing} — using neutral λ={MU/2}", file=sys.stderr)
    else:
        lam_a, lam_b = elo_to_lambda(elo_a, elo_b)
    probs = score_distribution(lam_a, lam_b)
    win_a, draw, win_b = outcome_probs(probs)
    return {
        "lambda_a": round(lam_a, 3),
        "lambda_b": round(lam_b, 3),
        "top_3": top_n_scores(probs, n=3),
        "win_a": win_a,
        "draw": draw,
        "win_b": win_b,
    }


def main() -> int:
    if not ELO_FILE.exists():
        print(f"ERROR: {ELO_FILE} not found", file=sys.stderr)
        return 1

    ratings = load_elo_ratings()
    print(f"loaded {len(ratings)} Elo ratings from {ELO_FILE.name}")

    run_path = get_canonical_run()
    if not run_path:
        print("ERROR: no runs found in data/runs/", file=sys.stderr)
        return 1
    print(f"using schedule from {run_path.name}")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    schedule = extract_schedule(run)
    print(f"  → {len(schedule)} unique fixtures to score")

    if not schedule:
        print("ERROR: empty schedule", file=sys.stderr)
        return 1

    out_matches = []
    for fx in schedule:
        pred = predict_one(fx["team_a"], fx["team_b"], ratings)
        key = f"{fx['stage']}|{fx['team_a']}|{fx['team_b']}"
        out_matches.append({
            "key": key,
            "stage": fx["stage"],
            "group": fx.get("group"),
            "team_a": fx["team_a"],
            "team_b": fx["team_b"],
            **pred,
        })

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mu": MU,
            "max_goals": MAX_GOALS,
            "model": "Elo-Poisson (independent, μ=1.4, neutral venue, no home adv)",
            "source_run": run_path.name,
            "elo_source": str(ELO_FILE.name),
            "match_count": len(out_matches),
        },
        "matches": out_matches,
    }
    BASELINE_OUT.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK wrote {BASELINE_OUT}")

    # Also write a prompt-ready markdown summary that daily-update.sh
    # concatenates into the MiroFish --requirement. Kept compact (~10-15 KB)
    # so the LLM context window isn't blown out.
    md_path = BASELINE_OUT.with_suffix(".md")
    md_lines = [
        "# ELO-POISSON BASELINE (auto-computed, μ=1.4, neutral venue)",
        "",
        "These are the model's baseline predictions for every fixture in the current schedule.",
        "Use them as your starting point: pick the top-1 score as `most_likely_score`, list the",
        "top-3 in a new `top_3_scores` column or section. Adjust modestly based on recent form,",
        "H2H, injuries, and tactical matchup — but anchor on these probabilities.",
        "",
        "Win probabilities: A=team_a win, D=draw, B=team_b win.",
        "Top-3: best (home, away) tuples with probability percentages.",
        "",
        "| Stage | Team A | Team B | λa/λb | A/D/B | Top-1 | Top-2 | Top-3 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in out_matches:
        top = m["top_3"]
        top_cells = " · ".join(f"{s['home']}-{s['away']} ({s['pct']}%)" for s in top)
        cells = [s.strip() for s in top_cells.split(" · ")] + ["", "", ""]
        md_lines.append(
            f"| {m['stage']} | {m['team_a']} | {m['team_b']} | "
            f"{m['lambda_a']:.2f}/{m['lambda_b']:.2f} | "
            f"{m['win_a']:.0%}/{m['draw']:.0%}/{m['win_b']:.0%} | "
            f"{cells[0]} | {cells[1]} | {cells[2]} |"
        )
    md_lines.extend([
        "",
        "**CRITICAL** — Your report must:",
        "1. Keep `most_likely_score` = baseline's Top-1 (unless injury/H2H clearly overrides).",
        "2. **Add a new field per match: `top_3_scores: [{score, prob}, ...]`** listing the top 3 most",
        "   likely scores with their probability percentages (sum should be ~30-50% of total).",
        "3. The Top-3 list is what we display to users + score against real results. Exact score is",
        "   the only thing that counts as a correct prediction (胜方命中 is no longer sufficient).",
    ])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"OK wrote {md_path} ({len(out_matches)} rows, {md_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
