#!/usr/bin/env python3
"""事后命中率对比: MiroFish 纯预测 vs DraftKings raw vs Blended (30%)。

输入:
  data/runs/run_<id>.json         (MiroFish 输出, 含 team_a_win/draw/team_b_win + odds 注入)
  data/real/wc_2026_results.json  (fetch_real_results.py 输出, 含真实 score + winner)
  data/real/wc_2026_odds.json     (fetch_odds.py 输出, 含 home_prob_norm 等)

输出 (stdout):
  - 总命中率对比表 (Top-1 result + 1X2 winner)
  - 偏差 / 一致 / 反向案例分类
  - 写入 data/analysis/<run_id>_hit_rate.json (供后续报告)
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_run(run_id: str) -> dict:
    p = ROOT / 'data' / 'runs' / f'run_{run_id}.json'
    if not p.exists():
        sys.exit(f"❌ Run not found: {p}")
    return json.loads(p.read_text(encoding='utf-8'))


def _load_results() -> dict:
    p = ROOT / 'data' / 'real' / 'wc_2026_results.json'
    if not p.exists():
        sys.exit(f"❌ Results not found: {p}")
    return json.loads(p.read_text(encoding='utf-8'))


def _match_key(team_a: str, team_b: str) -> tuple[str, str]:
    """归一化 (sorted) 配对 key, 不区分主客。"""
    return tuple(sorted([team_a.lower(), team_b.lower()]))


def _extract_score(real_match: dict) -> tuple[int | None, int | None]:
    """fetch_real_results.py 输出用 score_a/score_b 字段, 不是 score.home/away。"""
    # 兼容两种 schema
    if 'score_a' in real_match and 'score_b' in real_match:
        return real_match.get('score_a'), real_match.get('score_b')
    if 'score' in real_match and isinstance(real_match['score'], dict):
        return real_match['score'].get('home'), real_match['score'].get('away')
    return None, None


def _winner_label(real_match: dict) -> str:
    """真实比赛结果 → 'H' / 'D' / 'A'。"""
    h, a = _extract_score(real_match)
    if h is None or a is None:
        return ''
    if h == a:
        return 'D'
    return 'H' if h > a else 'A'


def _pred_label(probs: dict) -> str:
    """预测概率 → max prob 的 'H' / 'D' / 'A'。"""
    return max(['H', 'D', 'A'], key=lambda k: probs[k])


def _brier(probs: dict, true_label: str) -> float:
    """Brier score: sum((p_i - actual_i)^2), 越小越好 (0=完美, 2=最差)."""
    actual = {'H': 0.0, 'D': 0.0, 'A': 0.0}
    actual[true_label] = 1.0
    return sum((probs[k] - actual[k]) ** 2 for k in ('H', 'D', 'A'))


def main(run_id: str):
    run = _load_run(run_id)
    results = _load_results()

    # results.matches: [{team_a, team_b, score: {home, away}, winner}, ...]
    real_lookup = {}
    for m in results.get('matches', []):
        key = _match_key(m['team_a'], m['team_b'])
        real_lookup[key] = m

    # 收集 MiroFish 比赛 (有 odds 注入 + is_played)
    matched = []  # [(letter, mf_match, real_match), ...]
    unmatched = []
    for letter, g in run.get('groups', {}).items():
        for m in g.get('matches', []):
            if not m.get('odds'):
                continue  # 只统计有 odds 注入的比赛
            real = real_lookup.get(_match_key(m['team_a'], m['team_b']))
            if real:
                matched.append((letter, m, real))
            else:
                unmatched.append(f'[{letter}] {m["team_a"]} vs {m["team_b"]}')

    if not matched:
        sys.exit(f"❌ No matches with both odds + real results found.")

    print(f'Run: {run_id} ({run.get("created_at", "?")[:10]})')
    print(f'已比赛 + 带 odds: {len(matched)} 场')
    if unmatched:
        print(f'未匹配 (没真实结果): {len(unmatched)} 场 — {unmatched[:5]}{"..." if len(unmatched) > 5 else ""}')
    print()

    # 三方预测 vs 真实
    p_mf_correct = p_odds_correct = p_blend_correct = 0
    brier_mf = brier_odds = brier_blend = 0.0
    details = []

    print('=' * 110)
    print(f'{"比赛":<32} {"真":>3} {"MF":>3} {"Od":>3} {"Bl":>3} | BrierMF | BrierOd | BrierBl | MFprobs       | Blprobs       | Real')
    print('=' * 110)

    for letter, m, real in matched:
        true_label = _winner_label(real)
        if not true_label:
            continue

        o = m['odds']
        probs_mf = {'H': m['team_a_win'], 'D': m['draw'], 'A': m['team_b_win']}
        probs_odds = {'H': o['home_prob_norm'], 'D': o['draw_prob_norm'], 'A': o['away_prob_norm']}
        probs_blend = {'H': o['blended_home'], 'D': o['blended_draw'], 'A': o['blended_away']}

        pred_mf = _pred_label(probs_mf)
        pred_odds = _pred_label(probs_odds)
        pred_blend = _pred_label(probs_blend)

        if pred_mf == true_label: p_mf_correct += 1
        if pred_odds == true_label: p_odds_correct += 1
        if pred_blend == true_label: p_blend_correct += 1

        bs_mf = _brier(probs_mf, true_label)
        bs_odds = _brier(probs_odds, true_label)
        bs_blend = _brier(probs_blend, true_label)
        brier_mf += bs_mf
        brier_odds += bs_odds
        brier_blend += bs_blend

        match_str = f'{m["team_a"][:14]} vs {m["team_b"][:13]}'
        h, a = _extract_score(real)
        real_str = f'{h}-{a}'
        correct_mf = '✓' if pred_mf == true_label else '✗'
        correct_odds = '✓' if pred_odds == true_label else '✗'
        correct_blend = '✓' if pred_blend == true_label else '✗'

        print(f'{match_str:<32} {true_label:>3} {pred_mf:>2}{correct_mf} {pred_odds:>2}{correct_odds} {pred_blend:>2}{correct_blend} | '
              f'{bs_mf:.4f}  | {bs_odds:.4f}  | {bs_blend:.4f}  | '
              f'H{m["team_a_win"]:.2f} D{m["draw"]:.2f} A{m["team_b_win"]:.2f} | '
              f'H{o["blended_home"]:.2f} D{o["blended_draw"]:.2f} A{o["blended_away"]:.2f} | {real_str}')

        details.append({
            'match': f'{m["team_a"]} vs {m["team_b"]}',
            'group': letter,
            'true_label': true_label,
            'pred_mf': pred_mf,
            'pred_odds': pred_odds,
            'pred_blend': pred_blend,
            'brier_mf': round(bs_mf, 4),
            'brier_odds': round(bs_odds, 4),
            'brier_blend': round(bs_blend, 4),
            'mf_correct': pred_mf == true_label,
            'odds_correct': pred_odds == true_label,
            'blend_correct': pred_blend == true_label,
            'real_score': real_str,
        })

    n = len(matched)
    print()
    print('=' * 90)
    print('【汇总]')
    print(f'  样本数: {n}')
    print(f'  MiroFish 纯预测  命中率: {p_mf_correct}/{n} = {p_mf_correct/n:.1%}    平均 Brier: {brier_mf/n:.4f}')
    print(f'  DraftKings raw   命中率: {p_odds_correct}/{n} = {p_odds_correct/n:.1%}    平均 Brier: {brier_odds/n:.4f}')
    print(f'  Blended (30%)    命中率: {p_blend_correct}/{n} = {p_blend_correct/n:.1%}    平均 Brier: {brier_blend/n:.4f}')
    print()

    # 写 JSON
    out_dir = ROOT / 'data' / 'analysis'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'run_{run_id}_hit_rate.json'
    out_path.write_text(json.dumps({
        'run_id': run_id,
        'created_at': run.get('created_at'),
        'sample_count': n,
        'accuracy': {
            'mf':   {'correct': p_mf_correct, 'rate': round(p_mf_correct/n, 4)},
            'odds': {'correct': p_odds_correct, 'rate': round(p_odds_correct/n, 4)},
            'blend':{'correct': p_blend_correct, 'rate': round(p_blend_correct/n, 4)},
        },
        'brier': {
            'mf':    round(brier_mf/n, 4),
            'odds':  round(brier_odds/n, 4),
            'blend': round(brier_blend/n, 4),
        },
        'matches': details,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✓ 写入 {out_path}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <run_id>")
    main(sys.argv[1])
