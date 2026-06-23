#!/usr/bin/env python3
"""Fetch 2026 WC betting odds (DraftKings via ESPN scoreboard) — 1X2 + O/U.

ESPN scoreboard `competitions[].odds[]` 字段:
  - moneyline: 主胜 American odds (e.g. -140)
  - drawOdds.moneyLine: 平局 (e.g. +310)
  - details: 字符串格式 "TEAM -XXX" — 客胜在 details 里
  - overUnder: 大小球线 (e.g. 2.5)
  - pointSpread.odds: 让球
  - provider.name: "DraftKings" (priority=1)

American → implied prob:
  +X  → 100 / (X + 100)
  -Y  →  Y / (Y + 100)
归一化扣 vig:  p_norm = p_raw / sum(p_raw)  (3 向加和 = 1/overround)

输出: data/real/wc_2026_odds.json
  { matches: [{group, team_a, team_b, date, kickoff_utc, odds: {
     provider, home, draw, away, home_prob, draw_prob, away_prob,
     over_under, point_spread, fetched_at
   }}], fetched_at, source }
"""
from __future__ import annotations
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'real' / 'wc_2026_odds.json'
ESPN_API = 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard'
UA = 'wc-predict-ecru/1.0 (https://github.com/kinglongleele-ui/wc-predict-2026)'

# 同 fetch_real_results.py: ESPN_TO_MIROFISH
ESPN_TO_MIROFISH = {
    "Czechia": "Czech Republic",
    "Bosnia-Herzegovina": "Bosnia",
    "United States": "USA",
    "Türkiye": "Turkey",
    "Congo DR": "DR Congo",
}


def _http_get(url: str) -> bytes:
    """ESPN 走 DIRECT, 跟 fetch_real_results.py 一样绕开 mihomo fake-IP."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=20).read()


def espn_window() -> str:
    """跟 fetch_real_results.py 同窗口: 06-11 → 07-19."""
    today = datetime.now(timezone.utc).date()
    start = datetime(2026, 6, 11, tzinfo=timezone.utc).date()
    end = datetime(2026, 7, 19, tzinfo=timezone.utc).date()
    return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"


def _american_to_prob(odds_str: str | int | None) -> float | None:
    """American odds → implied probability (含 vig).
    +310 → 100/410 = 0.2439
    -140 → 140/240 = 0.5833
    返回 None 表示无法解析。
    """
    if odds_str is None:
        return None
    s = str(odds_str).strip()
    if not s:
        return None
    m = re.match(r'^[+-](\d+)$', s)
    if not m:
        return None
    n = int(m.group(1))
    if s.startswith('+'):
        return 100 / (n + 100)
    if s.startswith('-'):
        return n / (n + 100)
    return None


def _extract_american(side_obj) -> str | None:
    """side_obj = moneyline.{home,away,draw} = {open:{odds:'-140'}, close:{odds:'-140'}}
    优先取 close (临场/收盘线), fallback 到 open.
    """
    if not isinstance(side_obj, dict):
        return None
    for src in ('close', 'open'):
        inner = side_obj.get(src)
        if isinstance(inner, dict):
            odds = inner.get('odds')
            if odds is not None:
                return str(odds)
    return None


def _parse_odds_block(odds_obj: dict) -> dict | None:
    """解析 ESPN odds[0] dict → 标准 1X2 + O/U.
    返回 None 表示字段缺失 (无 odds 或结构异常).
    moneyline 实际是 {home:{open,close}, away:..., draw:...}
    moneyline 字段本身可能为 None (early 已比赛 odds 不带 ml), 直接 None skip.
    """
    moneyline = odds_obj.get('moneyline')
    if not isinstance(moneyline, dict):
        return None
    home_str = _extract_american(moneyline.get('home'))
    away_str = _extract_american(moneyline.get('away'))
    draw_str = _extract_american(moneyline.get('draw'))
    if home_str is None or away_str is None or draw_str is None:
        return None

    home_p = _american_to_prob(home_str)
    draw_p = _american_to_prob(draw_str)
    away_p = _american_to_prob(away_str)
    if home_p is None or draw_p is None or away_p is None:
        return None
    # 归一化扣 vig
    total = home_p + draw_p + away_p
    if total <= 0:
        return None
    return {
        'home_odds_american': home_str,
        'draw_odds_american': draw_str,
        'away_odds_american': away_str,
        'home_prob_raw': round(home_p, 4),
        'draw_prob_raw': round(draw_p, 4),
        'away_prob_raw': round(away_p, 4),
        'overround': round(total, 4),  # > 1 = bookmaker margin
        'home_prob_norm': round(home_p / total, 4),
        'draw_prob_norm': round(draw_p / total, 4),
        'away_prob_norm': round(away_p / total, 4),
        'over_under': odds_obj.get('overUnder'),
        'provider': (odds_obj.get('provider') or {}).get('name', 'Unknown'),
    }


def fetch_espn_odds() -> list[dict]:
    """返回 [{group, team_a, team_b, date, kickoff_utc, odds, is_played}, ...]
    含 pre + post 全部比赛。
    """
    url = f"{ESPN_API}?dates={espn_window()}"
    try:
        raw = _http_get(url)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  ESPN odds: SKIP ({type(e).__name__}: {e})", file=sys.stderr)
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ESPN odds: SKIP (JSON decode error: {e})", file=sys.stderr)
        return []
    events = data.get('events', [])
    out: list[dict] = []
    for ev in events:
        comps = ev.get('competitions', [])
        if not comps:
            continue
        comp = comps[0]
        # Group: altGameNote = "FIFA World Cup, Group A" / "FIFA World Cup, Round of 32"
        note = comp.get('altGameNote') or ''
        gm = re.search(r'Group\s+([A-L])', note)
        if gm:
            group = gm.group(1)
        else:
            # 淘汰赛: R32, R16, QF, SF, Final
            if 'Round of 32' in note or 'Round of 16' in note or 'Quarterfinal' in note \
                    or 'Semifinal' in note or 'Final' in note:
                group = 'KNOCKOUT'
            else:
                continue  # 跳过未知分组
        competitors = comp.get('competitors', [])
        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue
        team_a = ESPN_TO_MIROFISH.get(home['team']['displayName'], home['team']['displayName'])
        team_b = ESPN_TO_MIROFISH.get(away['team']['displayName'], away['team']['displayName'])
        state = comp.get('status', {}).get('type', {}).get('state', '')
        odds_arr = comp.get('odds', [])
        if not odds_arr:
            continue
        # odds_arr 里可能有 None (ESPN 有时塞占位)
        first_odds = next((o for o in odds_arr if isinstance(o, dict)), None)
        if first_odds is None:
            continue
        odds_parsed = _parse_odds_block(first_odds)
        if odds_parsed is None:
            continue
        out.append({
            'group': group,
            'team_a': team_a,
            'team_b': team_b,
            'date': (ev.get('date', '') or '')[:10] or None,
            'kickoff_utc': ev.get('date'),
            'is_played': state == 'post',
            'odds': odds_parsed,
        })
    return out


def main():
    print(f"Fetching ESPN DraftKings odds for 2026 WC ({espn_window()})...")
    matches = fetch_espn_odds()
    fetched_at = datetime.now(timezone.utc).isoformat()
    pre_count = sum(1 for m in matches if not m['is_played'])
    post_count = sum(1 for m in matches if m['is_played'])
    payload = {
        'fetched_at': fetched_at,
        'source': 'ESPN:DraftKings',
        'window': espn_window(),
        'match_count': len(matches),
        'pre_count': pre_count,
        'post_count': post_count,
        'matches': matches,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✓ Wrote {len(matches)} matches ({pre_count} pre + {post_count} post) → {OUT}")
    # 抽样 3 场
    for m in matches[:3]:
        o = m['odds']
        print(f"  [{m['group']}] {m['team_a']} vs {m['team_b']} ({m['date']}): "
              f"home={o['home_odds_american']} ({o['home_prob_norm']:.1%}), "
              f"draw={o['draw_odds_american']} ({o['draw_prob_norm']:.1%}), "
              f"away={o['away_odds_american']} ({o['away_prob_norm']:.1%}), "
              f"vig={o['overround']:.3f}, O/U={o['over_under']}")


if __name__ == "__main__":
    main()
