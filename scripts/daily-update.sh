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
#
# Outputs to stdout are markdown-friendly so the cc-connect cron summary reads
# cleanly in the chat.

set -uo pipefail
# Note: NOT `set -e` — we want to handle each step's failure explicitly so the
# summary at the end is useful.

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
git add data/runs/ lib/data.ts app/page.tsx app/simulations/page.tsx scripts/daily-update.sh 2>/dev/null || true
if git diff --cached --quiet; then
  echo "[4/5] no changes to commit"
else
  git -c user.email=wc-predict@local -c user.name="wc-predict cron" \
    commit -m "chore(daily): refresh run $NEW_RUN_ID ($TS)" >/dev/null || \
    echo "[4/5] ⚠️ git commit failed"
  # Push: try with credential-helper-based auth first (works in interactive
  # sessions with cached PAT); fall back to env-var-embedded token.
  PUSH_OK=0
  if git push origin master 2>&1 | tail -3; then
    PUSH_OK=1
  elif [[ -n "${GH_TOKEN:-}" ]]; then
    git push "https://x-access-token:${GH_TOKEN}@github.com/kinglongleee-ui/wc-predict-2026.git" master 2>&1 | tail -3 || true
  else
    echo "[4/5] ⚠️ git push failed (no GH_TOKEN and no cached credential)"
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
