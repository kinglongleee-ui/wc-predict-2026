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
    --requirement "Predict every remaining 2026 FIFA World Cup match (group stage MD2+MD3, Round of 32, Round of 16, QF, SF, Final) with per-match team_a_win_prob / draw_prob / team_b_win_prob / most_likely_score / aet_prob / penalties_prob. Identify the 8 best 3rd-place teams, list the predicted 32-team knockout bracket, champion pick with confidence, top 5 upset-risk matches, and final matchup with most likely score (90min / AET / penalties breakdown).

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

ALL 12 GROUPS A-L must be present in your report, labeled EXACTLY as above. Group letters in your output (Group A, Group B, ...) MUST match the input table." \
    --json 2>&1 | tail -200) || true

  NEW_RUN_ID=$(echo "$MF_OUT" | grep -oE '"run_id"[[:space:]]*:[[:space:]]*"run_[a-f0-9]+"' | head -1 | grep -oE 'run_[a-f0-9]+')
  if [[ -z "$NEW_RUN_ID" ]]; then
    echo "[1/5] ⚠️ MiroFish did not emit a run_id; falling back to latest in uploads/runs/"
    NEW_RUN_ID=$(ls -1t "$MF/uploads/runs/" | head -1)
  fi
  echo "[1/5] ✓ MiroFish run = $NEW_RUN_ID"
  cd "$WCP"
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
git add data/runs/ lib/data.ts app/page.tsx app/simulations/page.tsx app/report/\[id\]/page.tsx scripts/daily-update.sh scripts/translate_narrative.py 2>/dev/null || true
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
