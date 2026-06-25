#!/usr/bin/env bash
# run_r12.sh — R12 MiroFish re-run with SHORTER prompt.
# Why shorter: R11 attempt got "report agent empty response" likely due to prompt
# length blowing context. 281-line wc2026_remaining.md → 129 lines, --requirement
# stripped of verbose English reminders (the file already has Chinese OUTPUT ORDER + JSON schema).
set -uo pipefail

MF=/home/king/mirofish-cli
WCP=/home/king/wc-predict
MIROFISH_BIN="$MF/.venv/bin/mirofish"

cd "$MF"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
# HF 强走本地 cache, 不去 huggingface.co 探 HEAD (proxy 不通, 会卡 simulation 5+ min)
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# 注入最新 Elo baseline + DraftKings odds (数字 anchor, 比 prompt 文字约束有效)
BASELINE_MD=""
ODDS_MD=""
if [[ -f "$WCP/data/elo/wc_2026_baseline.md" ]]; then
  BASELINE_MD=$(python3 -c "import sys;print(open('$WCP/data/elo/wc_2026_baseline.md').read())")
fi
if [[ -f "$WCP/data/real/wc_2026_odds.json" ]]; then
  ODDS_MD=$(python3 -c "
import json
d = json.load(open('$WCP/data/real/wc_2026_odds.json'))
rows = ['| UTC | Group | Matchup | H% | D% | A% | O/U |',
        '|---|---|---|---|---|---|---|']
for m in d.get('matches', []):
    h = m.get('home_win_pct'); a = m.get('away_win_pct'); dr = m.get('draw_pct')
    if h is None or a is None: continue
    rows.append(f\"| {m.get('utc_date','')} | {m.get('group','')} | {m.get('team_a','')} vs {m.get('team_b','')} | {h:.0%} | {dr:.0%} | {a:.0%} | {m.get('over_under','')} |\")
print('\n'.join(rows))
")
fi

# 短版 requirement: 不再复述 R32 配对表 (文件第 3 节已有), 不复述 group lock (文件第 1 节已有),
# 不复述 24 场 must-include (文件第 2 节已有), 不复述 output order (文件第 4 节已有).
# 只保留: 数字 anchor (Elo) + 博彩 prior (odds) + 2 条硬提示 (top_3_scores + 完整输出).
MF_OUT=$("$MIROFISH_BIN" run \
  --files wc2026_remaining_r12.md \
  --max-rounds 5 \
  --requirement "按 wc2026_remaining_r12.md 预测 2026 世界杯 6/20-7/19 全部剩余比赛。输出严格按文件第 4 节顺序 (12 组 → 8 best 3rd → R32 → R16 → QF → SF → Final → Champion)。

CRITICAL:
- 每场给 top_3_scores: [{score: 'H-A', prob: 0.0X}, ...] (3 个最可能比分 + 概率) — 这是用户看到的唯一命中率指标。
- R32 严格按 Match 73-88 升序, 8 best 3rd 互不重复。
- max_tokens 8192, 不要主动截断, 必须写完全部 9 段。

NUMERIC ANCHOR (Elo-Poisson, μ=1.4, neutral venue):
${BASELINE_MD}

BOOKMAKER PRIOR (DraftKings, 30% weight calibration):
${ODDS_MD}" \
  --json 2>&1 | tail -200) || true

NEW_RUN_ID=$(echo "$MF_OUT" | grep -oE '"run_id"[[:space:]]*:[[:space:]]*"run_[a-f0-9]+"' | head -1 | grep -oE 'run_[a-f0-9]+')
if [[ -z "$NEW_RUN_ID" ]]; then
  echo "⚠️ mirofish did not emit run_id, falling back to latest in uploads/runs/"
  NEW_RUN_ID=$(ls -1t "$MF/uploads/runs/" | head -1)
fi
echo "R12 MiroFish run = $NEW_RUN_ID"
echo "$NEW_RUN_ID" > /tmp/r12_run_id.txt
