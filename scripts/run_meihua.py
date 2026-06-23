#!/usr/bin/env python3
"""批量给 R6 (run_ea1419a0e22f) 全部比赛跑梅花易数起卦。

输入: data/runs/run_<id>.json  (MiroFish 输出, 含 bracket.r32 + 各组 group matches)
输出: data/meihua/run_<id>_meihua.json  (73 场卦象 + Top3 比分)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from meihua_qigua import qi_gua  # noqa: E402


def _normalize_team(name: str) -> str:
    """MiroFish 输出偶尔带 (A1) / [H] / 中文括号等后缀, 起卦需要纯队名."""
    s = name.strip()
    # 去掉尾部 (A1) / (1A) / [A1] 等
    import re
    s = re.sub(r'\s*[\(\[](?:[A-L]\d|\d[A-L])[\)\]]\s*$', '', s)
    return s


def _iter_matches(run: dict):
    """生成器: 遍历 12 组 + R32 + R16 + QF + SF + Final 全 73 场."""
    # 12 组
    for letter, g in run.get('groups', {}).items():
        for m in g.get('matches', []):
            yield {
                'stage': f'group_{letter}',
                'matchday': m.get('matchday'),
                'team_a': _normalize_team(m['team_a']),
                'team_b': _normalize_team(m['team_b']),
                'kickoff_utc': m.get('kickoff_utc'),
            }
    # R32
    for i, m in enumerate(run.get('bracket', {}).get('r32', []), start=73):
        yield {
            'stage': 'r32',
            'match_num': i,
            'bracket_idx': m.get('bracket_idx', i - 73),
            'team_a': _normalize_team(m['team_a']),
            'team_b': _normalize_team(m['team_b']),
            'kickoff_utc': m.get('kickoff_utc'),
        }
    # R16
    for i, m in enumerate(run.get('bracket', {}).get('r16', []), start=89):
        yield {
            'stage': 'r16',
            'match_num': i,
            'bracket_idx': m.get('bracket_idx', i - 89),
            'team_a': _normalize_team(m['team_a']),
            'team_b': _normalize_team(m['team_b']),
            'kickoff_utc': m.get('kickoff_utc'),
        }
    # QF
    for i, m in enumerate(run.get('bracket', {}).get('qf', []), start=97):
        yield {
            'stage': 'qf',
            'match_num': i,
            'bracket_idx': m.get('bracket_idx', i - 97),
            'team_a': _normalize_team(m['team_a']),
            'team_b': _normalize_team(m['team_b']),
            'kickoff_utc': m.get('kickoff_utc'),
        }
    # SF
    for i, m in enumerate(run.get('bracket', {}).get('sf', []), start=101):
        yield {
            'stage': 'sf',
            'match_num': i,
            'bracket_idx': m.get('bracket_idx', i - 101),
            'team_a': _normalize_team(m['team_a']),
            'team_b': _normalize_team(m['team_b']),
            'kickoff_utc': m.get('kickoff_utc'),
        }
    # Final
    final = run.get('final', {})
    if final.get('matchup'):
        import re
        parts = re.split(r'\s+vs\s+|\s+v\s+', final['matchup'], maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            yield {
                'stage': 'final',
                'match_num': 103,
                'team_a': parts[0].strip(),
                'team_b': parts[1].strip(),
                'kickoff_utc': None,  # Final UTC 暂无
            }


# WC 2026 R32/R16/QF/SF/Final 官方 UTC 时刻 (Match 73-88 = R32, 89-96 = R16, 97-100 = QF, 101-102 = SF, 103 = Final)
KNOCKOUT_KICKOFFS = {
    73:  '2026-06-28T17:00:00Z',
    74:  '2026-06-28T20:00:00Z',
    75:  '2026-06-28T23:00:00Z',
    76:  '2026-06-29T01:00:00Z',
    77:  '2026-06-29T17:00:00Z',
    78:  '2026-06-29T20:00:00Z',
    79:  '2026-06-29T23:00:00Z',
    80:  '2026-06-30T01:00:00Z',
    81:  '2026-06-30T17:00:00Z',
    82:  '2026-06-30T20:00:00Z',
    83:  '2026-06-30T23:00:00Z',
    84:  '2026-07-01T01:00:00Z',
    85:  '2026-07-01T17:00:00Z',
    86:  '2026-07-01T20:00:00Z',
    87:  '2026-07-01T23:00:00Z',
    88:  '2026-07-02T01:00:00Z',
    89:  '2026-07-05T17:00:00Z',
    90:  '2026-07-05T21:00:00Z',
    91:  '2026-07-06T17:00:00Z',
    92:  '2026-07-06T21:00:00Z',
    93:  '2026-07-07T17:00:00Z',
    94:  '2026-07-07T21:00:00Z',
    95:  '2026-07-08T17:00:00Z',
    96:  '2026-07-08T21:00:00Z',
    97:  '2026-07-11T20:00:00Z',
    98:  '2026-07-12T00:00:00Z',
    99:  '2026-07-12T20:00:00Z',
    100: '2026-07-13T00:00:00Z',
    101: '2026-07-15T20:00:00Z',
    102: '2026-07-16T00:00:00Z',
    103: '2026-07-19T20:00:00Z',
}


def _lookup_group_kickoff(team_a: str, team_b: str, results: dict) -> str | None:
    """小组赛 kickoff 兜底: 从 wc_2026_results.json (date) + 已知 MD1/MD2/MD3 默认小时 拼 ISO UTC。

    已踢过的 (date 字段) 用真实日期 + 默认 17:00 UTC;
    未来 MD2/MD3 用 wc2026_remaining.md hardcode 表 (24 场);
    找不到则返回 None (run 中其他场次用 R6 JSON kickoff_utc)。
    """
    # 1) wc_2026_results.json (date 字段已知)
    for m in results.get('matches', []):
        if _normalize_team(m['team_a']).lower() == team_a.lower() and _normalize_team(m['team_b']).lower() == team_b.lower():
            d = m.get('date', '')
            if d:
                # 已比赛 — 用 17:00 UTC 默认 (开幕战多数是这个时段附近)
                return f"{d}T17:00:00Z"
    # 2) MD2/MD3 hardcode (wc2026_remaining.md 表)
    md23 = {
        ('Brazil', 'Haiti'): '2026-06-20T00:30:00Z',
        ('Paraguay', 'Turkey'): '2026-06-20T03:00:00Z',
        ('Netherlands', 'Sweden'): '2026-06-20T17:00:00Z',
        ('Germany', 'Ivory Coast'): '2026-06-20T20:00:00Z',
        ('Ecuador', 'Curaçao'): '2026-06-21T00:00:00Z',
        ('Japan', 'Tunisia'): '2026-06-21T04:00:00Z',
        ('Saudi Arabia', 'Spain'): '2026-06-21T16:00:00Z',
        ('Belgium', 'Iran'): '2026-06-21T19:00:00Z',
        ('Cape Verde', 'Uruguay'): '2026-06-21T22:00:00Z',
        ('Egypt', 'New Zealand'): '2026-06-22T01:00:00Z',
        ('Argentina', 'Austria'): '2026-06-22T17:00:00Z',
        ('France', 'Iraq'): '2026-06-22T21:00:00Z',
        ('Norway', 'Senegal'): '2026-06-23T00:00:00Z',
        ('Algeria', 'Jordan'): '2026-06-23T03:00:00Z',
        ('Portugal', 'Uzbekistan'): '2026-06-23T17:00:00Z',
        ('England', 'Ghana'): '2026-06-23T20:00:00Z',
        ('Croatia', 'Panama'): '2026-06-23T23:00:00Z',
        ('Colombia', 'DR Congo'): '2026-06-24T02:00:00Z',
        ('Mexico', 'South Korea'): '2026-06-24T19:00:00Z',
        ('Canada', 'Switzerland'): '2026-06-24T19:00:00Z',
        ('Brazil', 'Scotland'): '2026-06-24T22:00:00Z',
        ('Haiti', 'Morocco'): '2026-06-24T22:00:00Z',
        ('Germany', 'Ecuador'): '2026-06-25T20:00:00Z',
        ('Ivory Coast', 'Curaçao'): '2026-06-25T20:00:00Z',
    }
    for (a, b), iso in md23.items():
        if team_a.lower() == a.lower() and team_b.lower() == b.lower():
            return iso
        # 也匹配反向 (主客队可能 swap)
        if team_a.lower() == b.lower() and team_b.lower() == a.lower():
            return iso
    return None


def main(run_id: str):
    run_path = ROOT / 'data' / 'runs' / f'run_{run_id}.json'
    if not run_path.exists():
        sys.exit(f"❌ Run not found: {run_path}")
    run = json.loads(run_path.read_text(encoding='utf-8'))

    # 加载真实结果 (用作小组赛 kickoff 兜底)
    results_path = ROOT / 'data' / 'real' / 'wc_2026_results.json'
    results = {}
    if results_path.exists():
        results = json.loads(results_path.read_text(encoding='utf-8'))

    out = {'run_id': run_id, 'generated_at': None, 'matches': []}
    from datetime import datetime, timezone
    out['generated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    skipped = []
    for m in _iter_matches(run):
        kickoff = m.pop('kickoff_utc', None)
        # 兜底: 小组赛用 real_results + hardcode 表
        if not kickoff and m['stage'].startswith('group_'):
            kickoff = _lookup_group_kickoff(m['team_a'], m['team_b'], results)
        # Final 兜底: 7/19 20:00 UTC
        if not kickoff and m['stage'] == 'final':
            kickoff = KNOCKOUT_KICKOFFS[103]
        # R32/R16/QF/SF 兜底: KNOCKOUT_KICKOFFS 表按 match_num
        if not kickoff and m['stage'] in ('r32', 'r16', 'qf', 'sf'):
            kickoff = KNOCKOUT_KICKOFFS.get(m.get('match_num'))

        if not kickoff:
            skipped.append(f"{m['stage']} {m.get('match_num', m.get('matchday'))}: {m['team_a']} vs {m['team_b']} (no kickoff_utc)")
            m['meihua'] = None
        else:
            m['kickoff_utc_used'] = kickoff
            try:
                m['meihua'] = qi_gua(kickoff, m['team_a'], m['team_b'])
            except Exception as e:
                m['meihua'] = None
                m['meihua_error'] = str(e)
                skipped.append(f"{m['stage']} {m.get('match_num', m.get('matchday'))}: {e}")
        out['matches'].append(m)

    out_dir = ROOT / 'data' / 'meihua'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'run_{run_id}_meihua.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"✓ {len(out['matches'])} matches processed ({len(skipped)} skipped)")
    for s in skipped[:10]:
        print(f"  - skip: {s}")
    if len(skipped) > 10:
        print(f"  ... +{len(skipped) - 10} more")
    print(f"✓ 写入 {out_path}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <run_id>")
    main(sys.argv[1])