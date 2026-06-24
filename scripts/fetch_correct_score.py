#!/usr/bin/env python3
"""Flashscore correct score scraper (C 方案: 直接抓 flashscore 网页).

绕过 DraftKings Akamai WAF (cloudscraper/curl_cffi 都过不去)。
Flashscore 走全球 CDN + 较松 WAF, Playwright headless 渲染 OK。

流程:
1. 抓 flashscore World Cup 2026 主页 → 拿所有 match detail URL + match id
2. 每场: Playwright 渲染 detail page → click Odds tab → click Correct score
   → 抓渲染后 HTML
3. 解析 ui-table__row → (score, prev, current) × bookmakers
4. 选 best bookmaker (decimal 最低 = 赔率最好) → 转 American odds
5. 跟 fetch_odds.py 输出对齐: group, team_a, team_b, date, is_played
6. 输出 data/real/wc_2026_correct_score.json

波胆格式 (跟现有 OddsBlock 风格一致):
{
  "fetched_at": "2026-06-24T...",
  "source": "Flashscore (Bet365 + 其他 6 家)",
  "match_count": 27,
  "matches": [{
    "group": "K", "team_a": "Colombia", "team_b": "DR Congo",
    "date": "2026-06-24", "kickoff_utc": "...", "is_played": false,
    "correct_score": {
      "provider": "Bet365 (best of 6 bookmakers)",
      "scores": [
        {"home": 1, "away": 0, "odds_decimal": 6.50, "odds_american": "+550",
         "prob_norm": 0.139, "n_bookmakers": 6}
      ]
    }
  }]
}
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "real" / "wc_2026_correct_score.json"
WC_URL = "https://www.flashscore.com/football/world/world-championship-2026/"

# 跟 fetch_odds.py 一致: flashscore 队伍名 → MiroFish/ESPN 标准名
# 必要时按模糊匹配 (lowercase + 主要关键字)
TEAM_ALIAS = {
    "bosnia-herzegovina": "Bosnia",
    "czech-republic": "Czech Republic",
    "d-r-congo": "DR Congo",
    "ivory-coast": "Ivory Coast",
    "south-korea": "South Korea",
    "south-africa": "South Africa",
    "cape-verde": "Cape Verde",
    "saudi-arabia": "Saudi Arabia",
    "new-zealand": "New Zealand",
    "usa": "USA",
}

def canon(name: str) -> str:
    n = name.strip().lower().replace("_", "-")
    return TEAM_ALIAS.get(n, n.replace("-", " ").title().replace("Dr Congo", "DR Congo"))


def parse_correct_score_html(html: str) -> dict:
    """Return {score: {best_decimal, n_bookmakers, prev, all_bookmakers}}"""
    rows_raw = re.split(r'class="ui-table__row[^"]*"', html)
    scores = {}
    for raw in rows_raw[1:]:
        if len(raw) > 8000:
            continue
        m = re.search(r'wcl-oddsValue[^>]*>\s*(\d+)\s*[:\-]\s*(\d+)\s*<', raw)
        if not m:
            continue
        score = f"{m.group(1)}-{m.group(2)}"
        cells = re.findall(
            r'class="oddsCell__odd[^"]*"[^>]*data-analytics-bookmaker-id="(\d+)"[^>]*title="([\d.]+)\s*»\s*([\d.]+)"',
            raw
        )
        if not cells:
            cells = re.findall(
                r'data-analytics-bookmaker-id="(\d+)"[^>]*?title="([\d.]+)\s*»\s*([\d.]+)"',
                raw
            )
        if not cells:
            continue
        bks = [{"id": bid, "prev": float(p), "current": float(c)} for bid, p, c in cells]
        # best = 最低 current (implied prob 最高)
        best = min(bks, key=lambda b: b["current"])
        if score not in scores or best["current"] < scores[score]["best_decimal"]:
            scores[score] = {
                "best_decimal": best["current"],
                "n_bookmakers": len(bks),
                "prev": best["prev"],
            }
    return scores


def decimal_to_american(d: float) -> str:
    if d < 1.01:
        return "+100000"
    if d >= 2.0:
        a = (d - 1) * 100
        return f"+{int(round(a))}"
    a = -100 / (d - 1)
    return f"{int(round(a))}"


def decimal_to_prob(d: float) -> float:
    """Implied probability (含 vig, 未归一)."""
    return round(1.0 / d, 4)


def get_match_links(page) -> list:
    """从 WC 主页拿所有 match detail URL."""
    # match link 格式: /match/football/<slug>-<id>/<slug>-<id>/
    anchors = page.evaluate("""
        () => {
            const out = [];
            for (const a of document.querySelectorAll('a[href*="/match/football/"]')) {
                out.push(a.getAttribute('href'));
            }
            return Array.from(new Set(out));
        }
    """)
    return ["https://www.flashscore.com" + a for a in anchors]


def fetch_match_html(page, url: str, max_wait_s=30):
    """打开 detail page, click Odds + Correct score, 返回渲染后 HTML。"""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  goto err: {e}", file=sys.stderr)
        return None
    time.sleep(3)
    try:
        page.locator("a:has-text('Odds'), [data-tab*='odds' i]").first.click()
        time.sleep(2)
    except Exception:
        pass
    try:
        page.locator("a:has-text('Correct score'), button:has-text('Correct score')").first.click()
        time.sleep(3)
    except Exception as e:
        print(f"  cs click err: {e}", file=sys.stderr)
    return page.content()


def extract_meta_from_url(url: str) -> tuple:
    """从 URL 解析 (team_a_slug, team_b_slug)."""
    m = re.search(r'/match/football/([^/]+)/([^/]+)/?', url)
    if not m:
        return ("", "")
    return (m.group(1), m.group(2))


def main():
    print(f"Flashscore correct score scraper (Playwright headless)")
    print(f"WC URL: {WC_URL}")
    matches_out = []
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        # Step 1: get match links
        print("Step 1: loading WC page, extracting match URLs...")
        page.goto(WC_URL, timeout=45000, wait_until="domcontentloaded")
        time.sleep(5)
        # scroll to load lazy
        for y in [600, 1500, 3000, 6000, 9000, 12000]:
            page.evaluate(f"window.scrollTo(0, {y})")
            time.sleep(0.5)
        time.sleep(2)
        links = get_match_links(page)
        print(f"  {len(links)} match URLs")
        # Step 2: visit each
        for i, url in enumerate(links):
            slug_a, slug_b = extract_meta_from_url(url)
            ta_raw = slug_a.rsplit("-", 1)[0]
            tb_raw = slug_b.rsplit("-", 1)[0]
            ta = canon(ta_raw)
            tb = canon(tb_raw)
            t1 = time.time()
            html = fetch_match_html(page, url)
            if not html:
                continue
            scores = parse_correct_score_html(html)
            if not scores:
                print(f"  [{i+1}/{len(links)}] {ta} vs {tb}: NO SCORES ({time.time()-t1:.1f}s)")
                continue
            scores_arr = []
            for s, info in sorted(scores.items(), key=lambda x: x[1]["best_decimal"]):
                h, a = s.split("-")
                scores_arr.append({
                    "home": int(h),
                    "away": int(a),
                    "odds_decimal": info["best_decimal"],
                    "odds_american": decimal_to_american(info["best_decimal"]),
                    "prob_raw": decimal_to_prob(info["best_decimal"]),
                    "n_bookmakers": info["n_bookmakers"],
                    "prev_decimal": info["prev"],
                })
            # 归一化扣 vig
            total = sum(x["prob_raw"] for x in scores_arr)
            for x in scores_arr:
                x["prob_norm"] = round(x["prob_raw"] / total, 4) if total > 0 else 0
                del x["prob_raw"]
            matches_out.append({
                "group": None,  # flashscore URL 没 group 字段, 由 fetch_odds.py join 时按 team match
                "team_a": ta,
                "team_b": tb,
                "date": None,
                "kickoff_utc": None,
                "is_played": None,
                "source_url": url,
                "correct_score": {
                    "provider": "Bet365 (best of 6 bookmakers via flashscore)",
                    "scores": scores_arr,
                },
            })
            print(f"  [{i+1}/{len(links)}] {ta} vs {tb}: {len(scores_arr)} scores ({time.time()-t1:.1f}s)")
        browser.close()

    # Step 3: 与 fetch_odds.py 输出 join (按 team_a + team_b 模糊匹配, 补 group/date/is_played)
    odds_path = ROOT / "data" / "real" / "wc_2026_odds.json"
    if odds_path.exists():
        odds = json.loads(odds_path.read_text())
        # index by sorted team pair
        idx = {}
        for m in odds["matches"]:
            k = tuple(sorted([m["team_a"].lower(), m["team_b"].lower()]))
            idx[k] = m
        joined = 0
        for m in matches_out:
            k = tuple(sorted([m["team_a"].lower(), m["team_b"].lower()]))
            o = idx.get(k)
            if o:
                m["group"] = o["group"]
                m["date"] = o["date"]
                m["kickoff_utc"] = o["kickoff_utc"]
                m["is_played"] = o["is_played"]
                joined += 1
        print(f"\njoined {joined}/{len(matches_out)} with ESPN odds data")
    else:
        print(f"\n⚠️  {odds_path} not found, group/date fields empty")

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Flashscore (Bet365 + 5 other bookmakers, best odds)",
        "scraper": "playwright headless chrome",
        "match_count": len(matches_out),
        "matches": matches_out,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    elapsed = time.time() - t0
    print(f"\n✓ Wrote {len(matches_out)} matches → {OUT}")
    print(f"  total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
