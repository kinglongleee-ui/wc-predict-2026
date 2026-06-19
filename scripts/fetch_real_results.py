#!/usr/bin/env python3
"""Fetch real 2026 WC results from ESPN (primary) + Wikipedia (fallback).

Data sources (tried in order):
  1. ESPN scoreboard `site.api.espn.com/.../fifa.world/scoreboard?dates=YYYYMMDD-YYYYMMDD`
     - 100 events across the WC window (06-11 to 07-19), all 12 groups.
     - Filter state='post' (completed). Group label in `altGameNote='... Group X'`.
     - No API key required. JSON with home/away, score, winner, status.
     - Team displayNames mapped via ESPN_TO_MIROFISH to MiroFish canonical names
       (matches R3 full names + R4 3-letter codes after CODE_TO_TEAM).

  2. Wikipedia wikitext action=parse (fallback if ESPN unreachable / rate-limited).
     - Uses {{#invoke:football box|main ...}} Lua template (team1/team2=3-letter code,
       score={{score link|...|X–Y}}). Old free-text regex no longer matches.

Output: data/real/wc_2026_results.json
  { matches: [{group, team_a, score_a, team_b, score_b, date, source_wiki_page}],
    fetched_at, source }
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'real' / 'wc_2026_results.json'
ESPN_API = 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard'
WIKI_API = 'https://en.wikipedia.org/w/api.php'
GROUPS = 'ABCDEFGHIJKL'
UA = 'wc-predict-ecru/1.0 (https://github.com/kinglongleee-ui/wc-predict-2026)'

# ESPN displayName → MiroFish canonical full English name.
# MiroFish R3 uses full names ("Czech Republic", "South Korea", "USA");
# MiroFish R4 uses 3-letter FIFA codes ("CZE", "KOR", "USA"). ESPN uses its own
# style ("Czechia", "Bosnia-Herzegovina", "United States", "Türkiye", "Congo DR").
ESPN_TO_MIROFISH = {
    "Czechia": "Czech Republic",
    "Bosnia-Herzegovina": "Bosnia",
    "United States": "USA",
    "Türkiye": "Turkey",
    "Congo DR": "DR Congo",
}
CODE_TO_TEAM = {
    "MEX": "Mexico", "KOR": "South Korea", "CZE": "Czech Republic", "RSA": "South Africa",
    "SUI": "Switzerland", "QAT": "Qatar", "BIH": "Bosnia", "CAN": "Canada",
    "BRA": "Brazil", "MAR": "Morocco", "SCO": "Scotland", "HAI": "Haiti",
    "USA": "USA", "PAR": "Paraguay", "AUS": "Australia", "TUR": "Turkey",
    "GER": "Germany", "ECU": "Ecuador", "CIV": "Ivory Coast", "CUW": "Curaçao",
    "NED": "Netherlands", "SWE": "Sweden", "JPN": "Japan", "TUN": "Tunisia",
    "BEL": "Belgium", "IRN": "Iran", "EGY": "Egypt", "NZL": "New Zealand",
    "ESP": "Spain", "URU": "Uruguay", "KSA": "Saudi Arabia", "CPV": "Cape Verde",
    "FRA": "France", "NOR": "Norway", "SEN": "Senegal", "IRQ": "Iraq",
    "ARG": "Argentina", "ALG": "Algeria", "AUT": "Austria", "JOR": "Jordan",
    "POR": "Portugal", "COL": "Colombia", "COD": "DR Congo", "UZB": "Uzbekistan",
    "ENG": "England", "CRO": "Croatia", "GHA": "Ghana", "PAN": "Panama",
}


def _http_get(url: str, headers: dict | None = None, proxy: str | None = None, timeout: int = 20) -> bytes:
    """Fetch URL.
    proxy=''  → force DIRECT connection (bypass any env HTTPS_PROXY — needed for
                ESPN which hangs if mihomo fake-IP intercepts DNS).
    proxy=URL → use that proxy.
    proxy=None → fall back to env HTTPS_PROXY/HTTP_PROXY.
    """
    req = urllib.request.Request(url, headers=headers or {})
    if proxy is not None:
        if proxy == '':
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
        return opener.open(req, timeout=timeout).read()
    env_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
    if env_proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': env_proxy, 'https': env_proxy}))
        return opener.open(req, timeout=timeout).read()
    return urllib.request.urlopen(req, timeout=timeout).read()


# ---------------------------------------------------------------------------
# ESPN (primary)
# ---------------------------------------------------------------------------
def espn_date_window() -> str:
    """YYYYMMDD-YYYYMMDD covering WC 2026 kickoff (06-11) through R32 (~07-19).
    Must start at 2026-06-11, NOT today, so completed group-stage matches
    stay in the response.
    """
    today = datetime.now(timezone.utc).date()
    start = datetime(2026, 6, 11, tzinfo=timezone.utc).date()
    end = max(today, datetime(2026, 7, 19, tzinfo=timezone.utc).date())
    return f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"


def fetch_espn() -> tuple[list[dict], str]:
    """Return (matches, source_label). Empty list on failure.
    ESPN is reachable direct (no proxy). mihomo proxies go through fake-IP DNS
    interception which may hang on certain CDN paths.
    """
    url = f"{ESPN_API}?dates={espn_date_window()}"
    try:
        raw = _http_get(url, headers={'User-Agent': UA}, proxy='', timeout=20)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  ESPN: SKIP ({type(e).__name__}: {e})", file=sys.stderr)
        return [], ''
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ESPN: SKIP (JSON decode error: {e})", file=sys.stderr)
        return [], ''
    events = data.get('events', [])
    matches: list[dict] = []
    for ev in events:
        comps = ev.get('competitions', [])
        if not comps:
            continue
        comp = comps[0]
        if comp.get('status', {}).get('type', {}).get('state') != 'post':
            continue
        # Group from altGameNote (e.g. "FIFA World Cup, Group A")
        note = comp.get('altGameNote') or ''
        gm = re.search(r'Group\s+([A-L])', note)
        if not gm:
            continue
        group = gm.group(1)
        competitors = comp.get('competitors', [])
        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue
        team_a = ESPN_TO_MIROFISH.get(home['team']['displayName'], home['team']['displayName'])
        team_b = ESPN_TO_MIROFISH.get(away['team']['displayName'], away['team']['displayName'])
        try:
            score_a = int(home.get('score', 0))
            score_b = int(away.get('score', 0))
        except (TypeError, ValueError):
            continue
        matches.append({
            'group': group,
            'team_a': team_a,
            'score_a': score_a,
            'team_b': team_b,
            'score_b': score_b,
            'date': (ev.get('date', '') or '')[:10] or None,
            'source_wiki_page': f'ESPN:fifa.world:{ev.get("id", "")}',
        })
    # de-dupe
    seen = set()
    uniq = []
    for m in matches:
        key = (m['group'], m['team_a'], m['team_b'], m['date'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(m)
    uniq.sort(key=lambda m: (m['group'], m['date'] or ''))
    src = f'ESPN scoreboard (fifa.world, dates={espn_date_window()}, {len(uniq)} played)'
    return uniq, src


# ---------------------------------------------------------------------------
# Wikipedia (fallback)
# ---------------------------------------------------------------------------
def fetch_wiki_group(letter: str) -> list[dict]:
    page = f'2026_FIFA_World_Cup_Group_{letter}'
    url = f'{WIKI_API}?action=parse&page={page}&format=json&prop=wikitext'
    raw = _http_get(url, headers={'User-Agent': UA}, timeout=15)
    data = json.loads(raw)
    wt = data.get('parse', {}).get('wikitext', {}).get('*', '') or ''
    return parse_wiki_group(letter, wt)


def _extract_boxes(wt: str) -> list[str]:
    boxes = []
    i = 0
    while True:
        j = wt.find('#invoke:football box', i)
        if j < 0:
            break
        start = wt.rfind('{{', max(0, j - 30), j)
        if start < 0:
            i = j + 1
            continue
        depth = 0
        k = start
        while k < len(wt):
            if wt[k:k + 2] == '{{':
                depth += 1; k += 2; continue
            if wt[k:k + 2] == '}}':
                depth -= 1; k += 2
                if depth == 0:
                    boxes.append(wt[start:k])
                    break
                continue
            k += 1
        i = j + 1
    return boxes


def parse_wiki_group(letter: str, wt: str) -> list[dict]:
    out: list[dict] = []
    for box in _extract_boxes(wt):
        m_date = re.search(r'\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})\}\}', box)
        if not m_date:
            continue
        date = f"{m_date.group(1)}-{int(m_date.group(2)):02d}-{int(m_date.group(3)):02d}"
        m_t1 = re.search(r'team1\s*=\s*\{\{#invoke:flag\|fb-rt\|([A-Z]{3})\}\}', box)
        m_t2 = re.search(r'team2\s*=\s*\{\{#invoke:flag\|fb(?:\|rt)?\|([A-Z]{3})\}\}', box)
        if not m_t1 or not m_t2:
            continue
        m_score = re.search(r'score\s*=\s*\{\{score link\|[^|]+\|([^}]+)\}\}', box)
        if not m_score:
            m_score = re.search(r'score\s*=\s*([0-9]+)\s*[–—\-]\s*([0-9]+)', box)
            if not m_score:
                continue
            sa, sb = m_score.group(1), m_score.group(2)
        else:
            mn = re.search(r'([0-9]+)\s*[–—\-]\s*([0-9]+)', m_score.group(1).strip())
            if not mn:
                continue
            sa, sb = mn.group(1), mn.group(2)
        out.append({
            'group': letter,
            'team_a': CODE_TO_TEAM.get(m_t1.group(1), m_t1.group(1)),
            'score_a': int(sa),
            'team_b': CODE_TO_TEAM.get(m_t2.group(1), m_t2.group(1)),
            'score_b': int(sb),
            'date': date,
            'source_wiki_page': f'2026_FIFA_World_Cup_Group_{letter}',
        })
    # de-dupe
    seen = set()
    uniq = []
    for m in out:
        key = (m['group'], m['team_a'], m['team_b'], m['date'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(m)
    return uniq


def fetch_wiki_all() -> tuple[list[dict], str]:
    all_m: list[dict] = []
    failed = 0
    for letter in GROUPS:
        try:
            ms = fetch_wiki_group(letter)
            print(f"  Wiki Group {letter}: {len(ms)} match(es)")
            all_m.extend(ms)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
            print(f"  Wiki Group {letter}: SKIP ({e})", file=sys.stderr)
            failed += 1
    all_m.sort(key=lambda m: (m['group'], m['date'] or ''))
    src = f'Wikipedia wikitext action=parse (Module:Football box, {len(GROUPS) - failed}/{len(GROUPS)} groups)'
    return all_m, src


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("Source 1: ESPN scoreboard...")
    matches, src = fetch_espn()
    if not matches:
        print("  ESPN failed, falling back to Wikipedia...")
        matches, src = fetch_wiki_all()

    if not matches:
        print("ERROR: no data from any source", file=sys.stderr)
        return 1

    payload = {
        'fetched_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': src,
        'match_count': len(matches),
        'matches': matches,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nOK wrote {OUT} ({len(matches)} matches, source: {src})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
