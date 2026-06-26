#!/usr/bin/env bash
# daily-update.sh — End-to-end pipeline: MiroFish re-run → parse → git push → Vercel deploy.
#
# Idempotent: safe to run twice. If the upstream simulation fails, the existing
# site stays live and the script exits non-zero so the cron caller can alert.
#
# Env (optional, all read from ~/.bashrc already):
#   VERCEL_TOKEN   — classic Vercel token; if unset we try `vercel whoami` cached login
#   VERCEL_SCOPE   — Vercel team scope (default: interline)
#   SKIP_MIROFISH  — set to 1 to skip the simulation step (parse + deploy only)
#   SKIP_DEPLOY    — set to 1 to skip the Vercel deploy step
#   MINIMAX_API_KEY — required for translate_narrative.py --api mode (translates
#                     MiroFish's English narrative to Chinese). Without it,
#                     the script falls back to --dict (only covers the 2 pinned
#                     runs; new runs will keep English narrative).
#
# Outputs to stdout are markdown-friendly so the cc-connect cron summary reads
# cleanly in the chat.

set -uo pipefail
# Note: NOT `set -e` — we want to handle each step's failure explicitly so the
# summary at the end is useful.

# ---------- Load tokens (if env file exists) ----------
# Tokens file: ~/.wc-predict-tokens.env  (chmod 600, owner-only).
# Sourcing here means cron context (no TTY, no shell rc) still gets GH_TOKEN
# and VERCEL_TOKEN. If the file is absent, we fall back to whatever the
# ambient shell provides (e.g. interactive sessions with cached creds).
TOKENS_FILE="${WC_PREDICT_TOKENS_FILE:-$HOME/.wc-predict-tokens.env}"
if [[ -f "$TOKENS_FILE" ]]; then
  # Validate perms — refuse to source a world/group-readable file to avoid
  # leaking secrets to other local users.
  TOKENS_PERMS=$(stat -c "%a" "$TOKENS_FILE")
  if [[ "$TOKENS_PERMS" != "600" && "$TOKENS_PERMS" != "400" ]]; then
    echo "[boot] ⚠️  $TOKENS_FILE has perms $TOKENS_PERMS, expected 600/400 — refusing to source" >&2
  else
    set -a
    # shellcheck disable=SC1090
    source "$TOKENS_FILE"
    set +a
    echo "[boot] loaded tokens from $TOKENS_FILE (GH_TOKEN=${GH_TOKEN:+set}, VERCEL_TOKEN=${VERCEL_TOKEN:+set})"
  fi
else
  echo "[boot] no $TOKENS_FILE — relying on ambient env"
fi

WCP=/home/king/wc-predict
MF=/home/king/mirofish-cli
LOG_DIR=$WCP/logs
mkdir -p "$LOG_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="$LOG_DIR/daily-update-$TS.log"

VERCEL_SCOPE="${VERCEL_SCOPE:-interline}"
MIROFISH_BIN="$MF/.venv/bin/mirofish"
PYTHON=python3

# Tee everything to the log file
exec > >(tee -a "$LOG_FILE") 2>&1
echo "===== daily-update started at $TS ====="

cd "$WCP"

# ---------- Step 0.45: Refresh Elo rankings (eloratings.net, Playwright-rendered) ----------
# Updates data/elo/wc_2026_elo.json with fresher Elo ratings. Idempotent.
# 2026-06-26: switched from Wikipedia to eloratings.net (Slick-grid SPA via Playwright).
echo "[0.45/5] Refresh Elo rankings (eloratings.net /World)..."
if timeout 60 "$PYTHON" "$WCP/scripts/fetch_elo_ranking.py" 2>&1 | tail -3; then
  echo "[0.45/5] ✓ rankings refreshed"
else
  echo "[0.45/5] ⚠️ fetch_elo_ranking failed — keeping existing elo"
fi

# ---------- Step 0.5: Elo-Poisson baseline (must run before MiroFish) ----------
# Generates data/elo/wc_2026_baseline.{json,md} — a math-based score-distribution
# baseline (μ=1.4, neutral venue, independent Poisson on each side). The .md
# table is injected into the MiroFish --requirement below as anchoring context,
# so the LLM picks top-3 scores with numeric confidence instead of zero-shot
# guessing. Top-3 + exact-score is the new accuracy metric (胜方命中 is no
# longer sufficient).
echo "[0.5/5] Elo-Poisson baseline..."
if "$PYTHON" "$WCP/scripts/elo_poisson.py" 2>&1 | tail -8; then
  if [[ -f "$WCP/data/elo/wc_2026_baseline.md" ]]; then
    BASELINE_MD=$("$PYTHON" -c "import sys;print(open('$WCP/data/elo/wc_2026_baseline.md').read())")
    BASELINE_BYTES=$(stat -c %s "$WCP/data/elo/wc_2026_baseline.md")
    echo "[0.5/5] ✓ baseline built ($BASELINE_BYTES bytes, $(echo "$BASELINE_MD" | grep -c '^|') rows)"
  else
    BASELINE_MD=""
    echo "[0.5/5] ⚠️  baseline.md missing — proceeding without context injection"
  fi
else
  BASELINE_MD=""
  echo "[0.5/5] ⚠️  Elo-Poisson failed — proceeding without context injection"
fi

# ---------- Step 0.7: Bookmaker odds (DraftKings via ESPN) ----------
# Generates data/real/wc_2026_odds.json — 1X2 + O/U + 让球 for all pre matches
# (6/20-7/19). Injected into MiroFish --requirement as a calibration prior
# (bookmaker implied prob, 30% weight blended with the LLM's reasoning). This
# is the LLM-side ("layer 2") half of #176. The post-process half lives in
# parse-report.py::_enrich_with_odds.
echo "[0.7/5] Bookmaker odds (DraftKings via ESPN)..."
if "$PYTHON" "$WCP/scripts/fetch_odds.py" 2>&1 | tail -5; then
  if [[ -f "$WCP/data/real/wc_2026_odds.json" ]]; then
    ODDS_MD=$("$PYTHON" -c "
import json
d = json.load(open('$WCP/data/real/wc_2026_odds.json'))
rows = ['| UTC date | Group | Matchup | Home% | Draw% | Away% | O/U | Provider |',
        '|---|---|---|---|---|---|---|---|']
for m in d.get('matches', []):
    o = m['odds']
    rows.append(f\"| {m['date']} | {m['group']} | {m['team_a']} vs {m['team_b']} | {o['home_prob_norm']*100:.1f} | {o['draw_prob_norm']*100:.1f} | {o['away_prob_norm']*100:.1f} | {o['over_under']} | {o['provider']} |\")
print('\n'.join(rows))
")
    ODDS_COUNT=$(echo "$ODDS_MD" | grep -c '^| [0-9]')
    echo "[0.7/5] ✓ odds built ($ODDS_COUNT matches)"
  else
    ODDS_MD=""
    echo "[0.7/5] ⚠️  odds.json missing — proceeding without bookmaker context"
  fi
else
  ODDS_MD=""
  echo "[0.7/5] ⚠️  fetch_odds failed — proceeding without bookmaker context"
fi

# ---------- Step 0.75: Correct-score market (Flashscore, Playwright) ----------
# Generates data/real/wc_2026_correct_score.json — exact-score implied probs
# (multi-bookmaker consensus: Bet365 + 6 others). Injected into MiroFish
# prompt as a numeric anchor for top_3_scores (LLM should bias toward
# scores with highest market consensus).
# NOTE: Playwright headless Chromium — slower than HTTP APIs (~2-4 min for
# 73 matches). Failures are silent (skip step, MiroFish proceeds without).
echo "[0.75/5] Correct-score market (Flashscore)..."
if [[ -f "$WCP/.venv/bin/python" ]]; then
  PVENV="$WCP/.venv/bin/python"
elif command -v playwright >/dev/null 2>&1; then
  PVENV="$(command -v playwright | xargs dirname | xargs dirname)/bin/python"
else
  PVENV="$PYTHON"
fi
if timeout 360 "$PVENV" "$WCP/scripts/fetch_correct_score.py" 2>&1 | tail -5; then
  if [[ -f "$WCP/data/real/wc_2026_correct_score.json" ]]; then
    # Build MD: top score per match with prob
    CS_MD=$("$PVENV" -c "
import json
d = json.load(open('$WCP/data/real/wc_2026_correct_score.json'))
rows = ['| UTC date | Group | Matchup | Top score | Prob | #books |',
        '|---|---|---|---|---|---|']
for m in d.get('matches', []):
    cs = m.get('correct_score', {})
    scores = cs.get('scores', [])
    if not scores:
        continue
    top = scores[0]
    rows.append(f\"| {m.get('date','')} | {m.get('group','-')} | {m['team_a']} vs {m['team_b']} | {top['home']}-{top['away']} | {top['prob_norm']*100:.1f}% | {top['n_bookmakers']} |\")
print('\n'.join(rows))
" 2>/dev/null)
    CS_COUNT=$(echo "$CS_MD" | grep -c '^| [0-9]')
    echo "[0.75/5] ✓ correct-score built ($CS_COUNT matches)"
  else
    CS_MD=""
    echo "[0.75/5] ⚠️  correct_score.json missing — proceeding without"
  fi
else
  CS_MD=""
  echo "[0.75/5] ⚠️ fetch_correct_score failed/timeout — proceeding without"
fi

# ---------- Step 0.78 (REMOVED 2026-06-26): Head-to-head history (Wikipedia SOCKS5) ----------
# Wikipedia banned as data source per wc-predict-wiki-ban. fetch_h2h.py disabled.
# H2H removed from MiroFish prompt — LLM relies on Elo + form + odds + venue instead.
H2H_MD=""
echo "[0.78/5] ⏭  h2h removed (Wikipedia ban) — proceeding without"

# ---------- Step 0.8: Venue + weather for R32 (open-meteo) ----------


# Generates data/real/wc_2026_venue.json — 16 R32 venues + open-meteo forecast.
# Injected into MiroFish prompt as a "knockout venue context" — temperature,
# rain, humidity, wind for the 16 R32 matches. Group stage skips (not enough
# marginal value; open-meteo free-tier rate limits).
echo "[0.8/5] Venue + weather (R32 open-meteo)..."
if timeout 90 "$PYTHON" "$WCP/scripts/fetch_venue.py" 2>&1 | tail -3; then
  if [[ -f "$WCP/data/real/wc_2026_venue.json" ]]; then
    VENUE_MD=$("$PYTHON" -c "
import json
d = json.load(open('$WCP/data/real/wc_2026_venue.json'))
rows = ['| Match | Venue | City | Kickoff (CST) | Temp | Rain | Wind |',
        '|---|---|---|---|---|---|---|']
for m in d.get('matches', []):
    w = m.get('weather') or {}
    v = m['venue']
    rows.append(f\"| M{m['match_id']} ({m['team_a']} vs {m['team_b']}) | {v['name']} | {v['city']} | {m['kickoff_local']} | {w.get('temp_c','-')}°C | {w.get('rain_mm','-')}mm | {w.get('wind_kph','-')}km/h |\")
print('\n'.join(rows))
" 2>/dev/null)
    VENUE_COUNT=$(echo "$VENUE_MD" | grep -c '^| M[0-9]')
    echo "[0.8/5] ✓ venue+weather built ($VENUE_COUNT R32 matches)"
  else
    VENUE_MD=""
    echo "[0.8/5] ⚠️  venue.json missing — proceeding without"
  fi
else
  VENUE_MD=""
  echo "[0.8/5] ⚠️ fetch_venue failed — proceeding without"
fi

# ---------- Step 1: MiroFish re-run ----------
NEW_RUN_ID=""
if [[ "${SKIP_MIROFISH:-0}" == "1" ]]; then
  echo "[1/5] SKIP_MIROFISH=1 — skipping simulation"
else
  echo "[1/5] MiroFish re-run (round 3)..."
  cd "$MF"
  set -a; source .env; set +a
  # Use the same launcher shape as run_m3_round3.sh but capture the run id.
  # We invoke mirofish with --json and parse the run_id from the last JSON
  # line that contains "run_id".
  MF_OUT=$("$MIROFISH_BIN" run \
    --files wc2026_remaining.md \
    --max-rounds 5 \
    --requirement "Predict every remaining 2026 FIFA World Cup match (group stage MD2+MD3, Round of 32, Round of 16, QF, SF, Final) with per-match team_a_win_prob / draw_prob / team_b_win_prob / most_likely_score / aet_prob / penalties_prob. **For every match, ALSO output top_3_scores: [{score: 'H-A', prob: 0.0X}, ...] — the top 3 most likely exact scores with their probability percentages. Use the Elo-Poisson baseline table at the END of this requirement as your numeric anchor (μ=1.4, neutral venue); adjust modestly based on recent form / H2H / injuries / tactical matchup. The top_3_scores list is what gets displayed to users and scored against real results — exact score match is the only thing that counts as a correct prediction.** Identify the 8 best 3rd-place teams, list the predicted 32-team knockout bracket, champion pick with confidence, top 5 upset-risk matches, and final matchup with most likely score (90min / AET / penalties breakdown).

R6/R7 已知问题修复 (R8 MUST COMPLETE ALL SECTIONS):
- R6/R7 MiroFish LLM 输出戛然而止在 Group H 或 Round of 32 段中, R32/R16/QF/SF/Final/Best 3rd 段缺失.
- R8 你必须输出完整 report.md, 包括所有 8 个章节 (groups A→L, 8 best 3rd, R32, R16, QF, SF, Final, Champion Outlook, Upset Risks).
- 不要在 Group H 之后停下; 严格按 OUTPUT ORDER 输出全部 9 段.
- max_tokens 8192 足够, 不要主动截断.

6/22-6/25 已踢比赛结果 (强制 anchor, LLM 必须基于这些结果校准 MD3 + R32 预测):
| UTC date | Group | Matchup | Score | 备注 |
|---|---|---|---|---|
| 6/22 01:00 | G | New Zealand vs Egypt | 1-3 | Egypt G 拿 3 分, NZ 0 分 |
| 6/22 17:00 | J | Argentina vs Austria | 2-0 | Argentina J 9 分, Austria J 0 分 |
| 6/22 21:00 | I | France vs Iraq | 3-0 | France I 9 分 (除非 MD3 输), Iraq I 0 分 |
| 6/23 00:00 | I | Norway vs Senegal | 3-2 | Norway I 3 分, Senegal I 3 分 (挪威胜) |
| 6/23 03:00 | J | Algeria vs Jordan | 2-1 | Algeria J 3 分, Jordan J 0 分 |
| 6/23 17:00 | K | Portugal vs Uzbekistan | 5-0 | Portugal K 9 分 (除非 MD3 输), Uzbekistan K 0 分 |
| 6/23 20:00 | L | England vs Ghana | 0-0 | England L 4 分, Ghana L 1 分 |
| 6/24 02:00 | K | Colombia vs DR Congo | 1-0 | Colombia K 6 分 (1st, locked, GD+5), DR Congo K 1 分 |
| 6/24 19:00 | A | Mexico vs South Korea | 2-0 | Mexico A 9 分 (1st, locked), South Korea A 3 分 |
| 6/24 19:00 | B | Canada vs Switzerland | 1-2 | Canada B 1 分, Switzerland B 6 分 (1st) |
| 6/24 22:00 | C | Brazil vs Scotland | 3-1 | Brazil C 9 分 (1st, locked), Scotland C 3 分 |
| 6/24 22:00 | C | Haiti vs Morocco | 2-4 | Haiti C 0 分, Morocco C 3 分 |
| 6/25 01:00 | A | Czech Republic vs South Africa | 0-3 | CZE A 3 分 (输球), RSA A 3 分 (赢球). A: MEX 9, KOR 3, RSA 3, CZE 3 — KOR/RSA/CZE 算 GD 决 2nd, CZE GD -1, RSA GD 0, KOR GD 0 (KOR/RSA 决) |
| 6/25 01:00 | A | South Korea vs South Africa | 0-1 | RSA A 6 分 (2nd, locked, GD+1), KOR A 3 分 (3rd). A 终: MEX 9, RSA 6, KOR 3, CZE 0 |

校准: France I 9 分 (1st, locked), Senegal I 3 分, Norway I 3 分, Iraq I 0. I: France 1st, Norway/Senegal 2nd 算 GD.
Argentina J 9 分 (1st, locked). Austria 0 分 → 4th. Algeria J 3, Jordan J 0.
England L 4 分 (赢 Ghana 0-0 + 之前赢 Croatia), Ghana 1 分, Croatia 0 分, Panama 0 分. England 1st locked, Ghana 2nd locked.
Portugal K 9 分 (1st, locked). Colombia K 6 (赢 1-0 + 之前 5-0 vs Uzb), DR Congo K 1, Uzbekistan K 0. 2nd = Colombia.
Brazil C 9 分 (1st, locked), Morocco C 3 (赢 Haiti), Scotland C 3 (输巴西), Haiti C 0. 2nd = Morocco (GD) 或 Scotland (GD 需算: MAR GD+3 - SCO GD-1 → MAR 2nd).
Egypt G 3 (赢 NZ), Belgium G 9 (赢 Iran), Iran G 4, NZ 0. Belgium 1st, Egypt/Iran 2nd 算 GD (EGY GD+2 - IRN GD? 待算). 8 best 3rd candidate: Iran / Egypt.
Mexico A 9 (1st, locked), South Africa A 6 (2nd, locked). 8 best 3rd: South Korea A 3, CZE A 0 (排除).
Switzerland B 6 (1st, locked), Canada B 1. 2nd 待算 (B 还在踢, 6/25 23:00Z 还有 2 场). 8 best 3rd candidate: 待 B 决出.

D 组 (USA, Paraguay, Australia, Turkey) MD3 还有 2 场: 6/26 02:00Z Paraguay vs Australia + Turkey vs USA. D 不锁.
E 组 (Germany, Ecuador, Ivory Coast, Curaçao) MD3 6/25 20:00Z: Germany vs Ecuador + Ivory Coast vs Curaçao. 6/25 已部分踢, 但 odds 文件看是 pre-game. E 不锁.
F 组 (Netherlands, Sweden, Japan, Tunisia) MD3 6/25 23:00Z: Japan vs Sweden + Tunisia vs Netherlands. F 不锁.

ROUND OF 32 PAIRINGS — FIFA OFFICIAL (Match 73-88, MUST USE EXACTLY, DO NOT REORDER OR REASSIGN):
- Match 73: Runner-up A vs Runner-up B
- Match 74: Winner E vs Best 3rd (A/B/C/D/F)
- Match 75: Winner F vs Runner-up C
- Match 76: Winner C vs Runner-up F
- Match 77: Winner I vs Best 3rd (C/D/F/G/H)
- Match 78: Runner-up E vs Runner-up I
- Match 79: Winner A vs Best 3rd (C/E/F/H/I)
- Match 80: Winner L vs Best 3rd (E/H/I/J/K)
- Match 81: Winner D vs Best 3rd (B/E/F/I/J)
- Match 82: Winner G vs Best 3rd (A/E/H/I/J)
- Match 83: Runner-up K vs Runner-up L
- Match 84: Winner H vs Runner-up J
- Match 85: Winner B vs Best 3rd (E/F/G/I/J)
- Match 86: Winner J vs Runner-up H
- Match 87: Winner K vs Best 3rd (D/E/I/J/L)
- Match 88: Runner-up D vs Runner-up G

8 best 3rd-place teams must be DISTINCT (no duplicates) and each must satisfy the parens in the matches they fill. Write R32 16 场 in Match 73 → 88 ascending order.

CRITICAL 6/20-6/24 FIX (R5 BUG, R6 MUST CORRECT — matchup dates are MANDATORY):
The 24 group-stage matches below MUST appear in your group tables at the correct MD. R5 (25c1443aa500) wrote all 4 of these with WRONG matchups (e.g. 'Brazil vs Morocco' for C MD2 instead of 'Brazil vs Haiti'). R6 MUST use the EXACT matchup below; the date/MD on the LEFT column is the source of truth.
| UTC date | Beijing date | Group | Matchup | MD |
|---|---|---|---|---|
| 6/20 00:30 | 6/20 08:30 | C | Brazil vs Haiti | MD2 |
| 6/20 03:00 | 6/20 11:00 | D | Paraguay vs Turkey | MD2 |
| 6/20 17:00 | 6/21 01:00 | F | Netherlands vs Sweden | MD2 |
| 6/20 20:00 | 6/21 04:00 | E | Germany vs Ivory Coast | MD2 |
| 6/21 00:00 | 6/21 08:00 | E | Ecuador vs Curaçao | MD2 |
| 6/21 04:00 | 6/21 12:00 | F | Japan vs Tunisia | MD2 |
| 6/21 16:00 | 6/22 00:00 | H | Saudi Arabia vs Spain | MD2 |
| 6/21 19:00 | 6/22 03:00 | G | Belgium vs Iran | MD2 |
| 6/21 22:00 | 6/22 06:00 | H | Cape Verde vs Uruguay | MD2 |
| 6/22 01:00 | 6/22 09:00 | G | Egypt vs New Zealand | MD2 |
| 6/22 17:00 | 6/23 01:00 | J | Argentina vs Austria | MD2 |
| 6/22 21:00 | 6/23 05:00 | I | France vs Iraq | MD2 |
| 6/23 00:00 | 6/23 08:00 | I | Norway vs Senegal | MD2 |
| 6/23 03:00 | 6/23 11:00 | J | Algeria vs Jordan | MD2 |
| 6/23 17:00 | 6/24 01:00 | K | Portugal vs Uzbekistan | MD2 |
| 6/23 20:00 | 6/24 04:00 | L | England vs Ghana | MD2 |
| 6/23 23:00 | 6/24 07:00 | L | Croatia vs Panama | MD2 |
| 6/24 02:00 | 6/24 10:00 | K | Colombia vs DR Congo | MD3 |
| 6/24 19:00 | 6/25 03:00 | A | Mexico vs South Korea | MD3 |
| 6/24 19:00 | 6/25 03:00 | B | Canada vs Switzerland | MD3 |
| 6/24 22:00 | 6/25 06:00 | C | Brazil vs Scotland | MD3 |
| 6/24 22:00 | 6/25 06:00 | C | Haiti vs Morocco | MD3 |
| 6/25 20:00 | 6/26 04:00 | E | Germany vs Ecuador | MD3 |
| 6/25 20:00 | 6/26 04:00 | E | Ivory Coast vs Curaçao | MD3 |
| 6/25 23:00 | 6/26 07:00 | F | Japan vs Sweden | MD3 |
| 6/25 23:00 | 6/26 07:00 | F | Tunisia vs Netherlands | MD3 |
| 6/26 02:00 | 6/26 10:00 | D | Paraguay vs Australia | MD3 |
| 6/26 02:00 | 6/26 10:00 | D | Turkey vs USA | MD3 |
| 6/26 19:00 | 6/27 03:00 | I | Norway vs France | MD3 |
| 6/26 19:00 | 6/27 03:00 | I | Senegal vs Iraq | MD3 |
| 6/26 22:00 | 6/27 06:00 | L | England vs Croatia | MD3 |
| 6/26 22:00 | 6/27 06:00 | L | Ghana vs Panama | MD3 |
| 6/27 01:00 | 6/27 09:00 | G | Egypt vs Belgium | MD3 |
| 6/27 01:00 | 6/27 09:00 | G | Iran vs New Zealand | MD3 |

OUTPUT ORDER (CRITICAL — DO NOT REORDER — UI renders groups→QF→SF→Final→Champion in this exact order):
  ① 12 组 final standings (A→L)
  ② 8 个 best 3rd-place
  ③ 32 强名单 (16 组 R32 对阵)
  ④ R32 → R16 → QF → SF → 3rd place → Final 各场
  ⑤ 关键动态 (5 条)
  ⑥ Upset Risk (前 5)
  ⑦ 决赛预测 (90min / AET / Penalties 三段)
  ⑧ 冠军 (前 5 热门 + 黑马)
  ⑨ 总结 verdict.prediction (1-2 段)
Write groups first, champion last. Never lead with the champion.

CRITICAL GROUP-LOCK CONSTRAINT (overrides any prior knowledge):
- The input file defines EXACT group assignments. Use them VERBATIM. Do NOT consult 2026 FIFA WC seed-draw training data.
- France is in Group I (with Norway, Senegal, Iraq). NOT Group C.
- Brazil is in Group C (with Morocco, Scotland, Haiti). NOT Group D.
- England is in Group L (with Croatia, Ghana, Panama). NOT Group G.
- Netherlands is in Group F (with Sweden, Japan, Tunisia). NOT Group I.
- Spain is in Group H (with Uruguay, Saudi Arabia, Cape Verde). NOT Group E.
- Germany is in Group E (with Ecuador, Ivory Coast, 4th). NOT Group C.
- USA is in Group D (with Paraguay, Australia, Turkey). NOT Group D-real.
- Belgium is in Group G (with Iran, Egypt, New Zealand). NOT Group B.
- Mexico is in Group A. Argentina is in Group J. Portugal is in Group K. Croatia is in Group L.
- Morocco is in Group C (with Brazil). NOT Group F.
- Uruguay is in Group H (with Spain). NOT Group F.
- Japan is in Group F (with Netherlands). NOT Group H.
- Sweden is in Group F. Tunisia is in Group F.
- Switzerland is in Group B. Qatar is in Group B. Bosnia is in Group B.
- Colombia is in Group K (with Portugal). NOT Group F-real.
- Ecuador is in Group E. Ivory Coast is in Group E. Curaçao/4th in Group E.
- South Korea is in Group A. Czech Republic is in Group A. South Africa is in Group A.
- Canada is in Group B (host).
- DR Congo is in Group K (with Portugal). Uzbekistan is in Group K.
- Ghana is in Group L. Panama is in Group L.
- Cape Verde is in Group H. Saudi Arabia is in Group H.
- Iran is in Group G. Egypt is in Group G. New Zealand is in Group G.
- Senegal is in Group I. Norway is in Group I. Iraq is in Group I.
- Algeria is in Group J. Austria is in Group J. Jordan is in Group J.
- Paraguay is in Group D. Australia is in Group D. Turkey is in Group D.
- Haiti is in Group C. Scotland is in Group C.

ALL 12 GROUPS A-L must be present in your report, labeled EXACTLY as above. Group letters in your output (Group A, Group B, ...) MUST match the input table.

NUMERIC ANCHOR (Elo-Poisson baseline, μ=1.4, neutral venue) — use this to set per-match top_3_scores with probability:
${BASELINE_MD}

BOOKMAKER PRIOR (DraftKings via ESPN, 1X2 vig-removed, 30% weight calibration) — use as a market consensus reference for 1X2 probability. Treat as a soft prior (do not blindly follow if your reasoning strongly disagrees, e.g. lineup news); blend ~30% bookmaker + ~70% LLM reasoning. Only available for matches with published odds (pre-round matches 6/20-7/19).
${ODDS_MD}

CORRECT-SCORE MARKET (Flashscore via Bet365 + 6 books, exact-score implied prob) — use as a numeric anchor for top_3_scores. The market consensus top score (with highest prob_norm) is what the betting market thinks is most likely; your top_3_scores list should include it. n_bookmakers ≥ 3 = strong consensus; n_bookmakers = 1-2 = weak, treat as soft prior.
${CS_MD}

VENUE + WEATHER (open-meteo, R32 only) — temperature / rain / wind for the 16 R32 matches. Adjust score projections modestly: high temp (>30°C) + high humidity favors under (fewer late goals), rain favors defensive draws, strong wind favors home team in low-scoring games. Group stage skips (venue marginal at most).
${VENUE_MD}

(H2H history removed 2026-06-26 per wc-predict-wiki-ban — no Wikipedia data sources.)" \
    --json 2>&1 | tail -200) || true

  NEW_RUN_ID=$(echo "$MF_OUT" | grep -oE '"run_id"[[:space:]]*:[[:space:]]*"run_[a-f0-9]+"' | head -1 | grep -oE 'run_[a-f0-9]+')
  if [[ -z "$NEW_RUN_ID" ]]; then
    echo "[1/5] ⚠️ MiroFish did not emit a run_id; falling back to latest in uploads/runs/"
    NEW_RUN_ID=$(ls -1t "$MF/uploads/runs/" | head -1)
  fi
  echo "[1/5] ✓ MiroFish run = $NEW_RUN_ID"
  cd "$WCP"
fi

# ---------- Step 1.5: refresh real WC results (ESPN scoreboard, single source) ----------
# Runs unconditionally (no MiroFish needed). Fetches 28-100 matches from ESPN's
# public scoreboard endpoint (no API key) into data/real/wc_2026_results.json.
# This keeps the PlayedVsPredicted banner + /groups/[letter] "真实 X-Y" badges
# in sync with the actual tournament progress, even if MiroFish fails/skips.
echo "[1.5/5] refresh real WC results from ESPN..."
if "$PYTHON" scripts/fetch_real_results.py 2>&1 | tail -10; then
  REAL_COUNT=$(python3 -c "import json;print(json.load(open('data/real/wc_2026_results.json'))['match_count'])" 2>/dev/null || echo 0)
  echo "[1.5/5] ✓ real results refreshed ($REAL_COUNT played matches)"
else
  echo "[1.5/5] ⚠️ fetch failed — site will keep showing last good real data"
fi

# ---------- Step 2: parse the new run + refresh round-2 baseline ----------
echo "[2/5] parse-report.py + parse-round2.py..."
if [[ -n "$NEW_RUN_ID" && -d "$MF/uploads/runs/$NEW_RUN_ID" ]]; then
  "$PYTHON" scripts/parse-report.py "$NEW_RUN_ID" "$MF/uploads/runs/$NEW_RUN_ID" || {
    echo "[2/5] ❌ parse-report failed for $NEW_RUN_ID"
  }
else
  echo "[2/5] ⚠️ run dir not found, skipping parse-report"
fi
# Always re-parse round 2 baseline (cheap, idempotent)
"$PYTHON" scripts/parse-round2.py run_a18431af48fd "$MF/uploads/runs/run_a18431af48fd" >/dev/null || true

# ---------- Step 2.5: translate narrative fields (verdict.prediction / key_dynamics /
# signals / upset_risks / best_thirds / final.tiers / final.combined_text / report_markdown)
# These are MiroFish LLM English outputs; UI is zero-English so we must translate them.
# Two modes:
#   --api    : calls MiniMax M3 API (needs MINIMAX_API_KEY in env / tokens file)
#   --dict   : uses built-in CN dictionary (only for the 2 known pinned runs)
# We default to --api (cron future runs); --dict is a fallback if no API key set.
echo "[2.5/5] translate narrative fields to Chinese..."
if [[ -n "${MINIMAX_API_KEY:-}" ]]; then
  if MINIMAX_API_KEY="$MINIMAX_API_KEY" "$PYTHON" scripts/translate_narrative.py --api "$NEW_RUN_ID" 2>&1 | tail -5; then
    echo "[2.5/5] ✓ narrative translated (api mode)"
  else
    echo "[2.5/5] ⚠️ api translate failed, falling back to dict mode for known runs"
    "$PYTHON" scripts/translate_narrative.py --dict 2>&1 | tail -5 || true
  fi
else
  # No API key — try the built-in dict (covers the 2 pinned runs only)
  "$PYTHON" scripts/translate_narrative.py --dict 2>&1 | tail -5 || true
  echo "[2.5/5] (no MINIMAX_API_KEY — dict mode; new runs may keep English narrative)"
fi

# ---------- Step 3: local build sanity check ----------
echo "[3/5] next build (sanity check)..."
if npm run build 2>&1 | tail -40; then
  echo "[3/5] ✓ build passed"
else
  echo "[3/5] ❌ build failed — aborting before deploy"
  echo "===== daily-update ABORTED at $TS ====="
  exit 2
fi

# ---------- Step 4: git commit + push ----------
echo "[4/5] git commit + push..."
git add data/runs/ data/real/ lib/data.ts app/page.tsx app/simulations/page.tsx app/report/\[id\]/page.tsx app/groups/\[letter\]/page.tsx components/PlayedVsPredicted.tsx components/MatchRow.tsx scripts/daily-update.sh scripts/fetch_real_results.py scripts/translate_narrative.py 2>/dev/null || true
if git diff --cached --quiet; then
  echo "[4/5] no changes to commit"
else
  git -c user.email=wc-predict@local -c user.name="wc-predict cron" \
    commit -m "chore(daily): refresh run $NEW_RUN_ID ($TS)" >/dev/null || \
    echo "[4/5] ⚠️ git commit failed"
  # Push: try with credential-helper-based auth first (works in interactive
  # sessions with cached PAT); fall back to env-var-embedded token. We check
  # the captured output for the success marker `-> master` instead of relying
  # on exit code, because `git push | tail` always returns tail's exit 0.
  PUSH_OK=0
  PUSH_OUT=""
  # `ugrep` (system default on this box) parses tokens after `-qE` as options
  # if they start with `-`, so we use `-e` with the pattern AND `--` to
  # terminate option parsing. Pattern matches git's success line: `master -> master`.
  PUSH_RE='->[[:space:]]*master'
  if PUSH_OUT=$(git push origin master 2>&1 | tail -3); then
    if printf '%s\n' "$PUSH_OUT" | grep -qE -e "$PUSH_RE" -- ; then
      PUSH_OK=1
    fi
  fi
  if [[ "$PUSH_OK" -eq 0 && -n "${GH_TOKEN:-}" ]]; then
    PUSH_OUT=$(git push "https://x-access-token:${GH_TOKEN}@github.com/kinglongleee-ui/wc-predict-2026.git" master 2>&1 | tail -3) || true
    if printf '%s\n' "$PUSH_OUT" | grep -qE -e "$PUSH_RE" -- ; then
      PUSH_OK=1
    fi
  fi
  if [[ "$PUSH_OK" -eq 1 ]]; then
    echo "[4/5] ✓ git push succeeded"
  else
    echo "[4/5] ⚠️ git push failed (no GH_TOKEN and no cached credential)"
    [[ -n "$PUSH_OUT" ]] && echo "[4/5]   last output: $PUSH_OUT"
  fi
fi

# ---------- Step 5: Vercel deploy ----------
DEPLOY_URL=""
if [[ "${SKIP_DEPLOY:-0}" == "1" ]]; then
  echo "[5/5] SKIP_DEPLOY=1 — skipping Vercel deploy"
else
  echo "[5/5] vercel deploy --prod..."
  if [[ -n "${VERCEL_TOKEN:-}" ]]; then
    DEPLOY_OUT=$(npx vercel deploy --prod --yes --scope "$VERCEL_SCOPE" --token "$VERCEL_TOKEN" 2>&1 | tail -20) || true
  else
    DEPLOY_OUT=$(npx vercel deploy --prod --yes --scope "$VERCEL_SCOPE" 2>&1 | tail -20) || true
  fi
  DEPLOY_URL=$(echo "$DEPLOY_OUT" | grep -oE 'https://[a-z0-9-]+\.vercel\.app' | head -1)
  echo "[5/5] deploy URL: ${DEPLOY_URL:-<not found>}"
fi

echo "===== daily-update finished at $(date -u +%Y%m%dT%H%M%SZ) ====="
echo "RUN_ID=$NEW_RUN_ID"
echo "DEPLOY_URL=$DEPLOY_URL"
echo "LOG=$LOG_FILE"

# ---------- Status file (cc-connect cron reads this) ----------
STATUS_FILE=/tmp/daily-update-status.json
cat > "$STATUS_FILE" <<EOF
{
  "ts": "$TS",
  "finished_at": "$(date -u +%Y%m%dT%H%M%SZ)",
  "run_id": "$NEW_RUN_ID",
  "deploy_url": "$DEPLOY_URL",
  "log": "$LOG_FILE",
  "mirofish_skipped": "${SKIP_MIROFISH:-0}",
  "deploy_skipped": "${SKIP_DEPLOY:-0}"
}
EOF
echo "STATUS=$STATUS_FILE"
