#!/usr/bin/env python3
"""Fetch real 2026 WC results from Wikipedia wikitext (action=parse API).

Used by /bracket and /groups pages to render "已比赛 vs 预测" color badge.

Output: data/real/wc_2026_results.json
  { matches: [{group, team_a, score_a, team_b, score_b, date, source_wiki_page}], fetched_at: ISO8601 }
"""
from __future__ import annotations
import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'real' / 'wc_2026_results.json'
API = 'https://en.wikipedia.org/w/api.php'
GROUPS = 'ABCDEFGHIJKL'
UA = 'wc-predict-ecru/1.0 (https://github.com/kinglongleee-ui/wc-predict-2026)'

DASHES = '[–—\-]'
SCORE_RE = re.compile(
    rf'\b([A-Z][a-zA-Z]{{2,15}})\s+(\d+)\s*{DASHES}\s*(\d+)\s+([A-Z][a-zA-Z]{{2,15}})\b'
)
DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')


def fetch_group(letter: str) -> str:
    page = f'2026_FIFA_World_Cup_Group_{letter}'
    url = f'{API}?action=parse&page={page}&format=json&prop=wikitext'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=12) as r:
        d = json.loads(r.read())
    return d.get('parse', {}).get('wikitext', {}).get('*', '') or ''


def parse_group(letter: str, text: str) -> list[dict]:
    matches: list[dict] = []
    for m in SCORE_RE.finditer(text):
        team_a, score_a, score_b, team_b = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        # find nearest preceding date (YYYY-MM-DD) within ~600 chars
        start = max(0, m.start() - 600)
        ctx = text[start:m.start()]
        date_match = DATE_RE.findall(ctx)
        date = date_match[-1] if date_match else None
        matches.append({
            'group': letter,
            'team_a': team_a,
            'score_a': score_a,
            'team_b': team_b,
            'score_b': score_b,
            'date': date,
            'source_wiki_page': f'2026_FIFA_World_Cup_Group_{letter}',
        })
    # de-dupe (Ghana 1-0 Panama appears twice in Group L)
    seen: set[tuple] = set()
    uniq: list[dict] = []
    for mt in matches:
        key = (mt['group'], mt['team_a'], mt['team_b'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(mt)
    return uniq


def main() -> int:
    all_matches: list[dict] = []
    for letter in GROUPS:
        try:
            text = fetch_group(letter)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            print(f'  Group {letter}: SKIP ({e})', file=sys.stderr)
            continue
        ms = parse_group(letter, text)
        print(f'  Group {letter}: {len(ms)} played match(es)')
        all_matches.extend(ms)

    payload = {
        'fetched_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'Wikipedia wikitext action=parse (12 Group_A-L pages)',
        'match_count': len(all_matches),
        'matches': all_matches,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nOK wrote {OUT} ({len(all_matches)} matches)')
    return 0


if __name__ == '__main__':
    sys.exit(main())