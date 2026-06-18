import Link from "next/link";
import { getLatestRound3Run, loadRealResults, teamFlag, teamNameZh, predictOutcome, formatPct } from "@/lib/data";

// 把 MiroFish groups.X.matches[] 和 data/real/wc_2026_results.json 配对, 渲染
// "已比赛 vs 预测" 对比条: 真实比分 / MiroFish 预测比分 / 胜方命中状态。
export function PlayedVsPredicted() {
  const r3 = getLatestRound3Run();
  const real = loadRealResults();

  if (!r3 || !real || real.matches.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 p-4 text-sm text-gray-500">
        暂无已比赛数据。FIFA WC 2026 小组赛首轮进行中。
      </section>
    );
  }

  type Row = {
    group: string;
    team_a: string;
    team_b: string;
    score_a: number;
    score_b: number;
    real_score: string;
    pred_score: string;
    pred_winner: string;
    real_winner: string;
    hit: boolean;
    mirofish_conf: number;
    groupLetter: string;
  };
  const rows: Row[] = [];
  for (const rm of real.matches) {
    const g = r3.groups[rm.group];
    if (!g) continue;
    // 在 MiroFish 模拟里找 (team_a, team_b) 这场 (顺序无关)
    const m = g.matches.find(
      (mm) =>
        (mm.team_a === rm.team_a && mm.team_b === rm.team_b) ||
        (mm.team_a === rm.team_b && mm.team_b === rm.team_a),
    );
    if (!m) continue;
    const pred = predictOutcome({
      team_a_win: m.team_a_win,
      draw: m.draw,
      team_b_win: m.team_b_win,
    });
    const realOut = rm.score_a > rm.score_b ? "a" : rm.score_a < rm.score_b ? "b" : "draw";
    const hit = pred === realOut;
    const realWinName = realOut === "a" ? teamNameZh(rm.team_a) : realOut === "b" ? teamNameZh(rm.team_b) : "平局";
    const predWinName = pred === "a" ? teamNameZh(m.team_a) : pred === "b" ? teamNameZh(m.team_b) : "平局";
    rows.push({
      group: rm.group,
      team_a: rm.team_a,
      team_b: rm.team_b,
      score_a: rm.score_a,
      score_b: rm.score_b,
      real_score: `${rm.score_a}-${rm.score_b}`,
      pred_score: `${m.most_likely_score.home ?? "—"}-${m.most_likely_score.away ?? "—"}`,
      pred_winner: predWinName,
      real_winner: realWinName,
      hit,
      mirofish_conf: Math.max(m.team_a_win, m.draw, m.team_b_win),
      groupLetter: rm.group,
    });
  }

  if (rows.length === 0) return null;

  const hits = rows.filter((r) => r.hit).length;
  const hitPct = hits / rows.length;

  return (
    <section className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gradient-to-br from-emerald-50/40 via-white to-orange-50/40 dark:from-emerald-950/15 dark:via-black dark:to-orange-950/15 p-5">
      {/* 数据来源免责声明 — 非 FIFA 官方, 显式标 Wikipedia 局限 */}
      <div className="mb-3 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
        <span className="font-bold">⚠️ 数据来源声明</span> —
        下方"真实比分"抓取自 <span className="font-semibold">Wikipedia 用户编辑内容</span>,
        <span className="font-semibold">非 FIFA 官方数据</span>。
        Wikipedia 由志愿者维护,可能存在错填、漏填或延迟。
        本站预测仅供学习参考,实际比分请以
        <a
          href="https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/26/scores-fixtures"
          target="_blank"
          rel="noopener noreferrer"
          className="underline mx-1"
        >
          FIFA 官方赛事页
        </a>
        为准。
      </div>

      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-1">
            ✅ 已比赛 vs 🔮 MiroFish 预测
          </div>
          <h2 className="text-xl font-bold">
            {hits} / {rows.length} 场胜方预测命中 ({formatPct(hitPct, 0)})
          </h2>
        </div>
        <div className="text-xs text-gray-500">
          抓取时间: {real.fetched_at} (UTC)
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-2">
        {rows.map((r) => {
          const a = r.team_a;
          const b = r.team_b;
          const realHome = r.group === r.group; // home/away 无影响 (显示只看比分)
          return (
            <Link
              key={`${r.group}-${a}-${b}`}
              href={`/groups/${r.groupLetter}`}
              className={`rounded-lg border p-3 flex items-center gap-3 hover:shadow-md transition-shadow ${
                r.hit
                  ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20"
                  : "border-orange-300 dark:border-orange-800 bg-orange-50/50 dark:bg-orange-950/20"
              }`}
            >
              {/* 真实比分大字 */}
              <div className="shrink-0 text-center">
                <div className="text-3xl font-black font-mono leading-none">
                  {r.score_a}
                  <span className="text-gray-400 mx-1">–</span>
                  {r.score_b}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mt-1">
                  {r.group} 组 · 真实
                </div>
              </div>

              {/* 预测对比 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs mb-0.5">
                  <span>{teamFlag(a)} <span className="font-semibold">{teamNameZh(a)}</span></span>
                  <span className="text-gray-400">vs</span>
                  <span><span className="font-semibold">{teamNameZh(b)}</span> {teamFlag(b)}</span>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  预测 <span className="font-mono font-semibold">{r.pred_score}</span>
                  {" · "}
                  <span className={r.hit ? "text-emerald-700 dark:text-emerald-400" : "text-orange-700 dark:text-orange-400"}>
                    {r.pred_winner} 胜
                  </span>
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">
                  MiroFish 置信度 {formatPct(r.mirofish_conf, 0)}
                </div>
              </div>

              {/* 命中状态 */}
              <div
                className={`shrink-0 text-base font-black ${
                  r.hit ? "text-emerald-600 dark:text-emerald-400" : "text-orange-600 dark:text-orange-400"
                }`}
                title={`预测: ${r.pred_winner} 胜 · 真实: ${r.real_winner}`}
              >
                {r.hit ? "✓" : "✗"}
              </div>
            </Link>
          );
        })}
      </div>

      <p className="text-xs text-gray-500 mt-3">
        绿色 ✓ = MiroFish 预测的胜方与真实胜方一致 · 橙色 ✗ = 预测错了胜方 ·
        比分/进球不参与对比 (只对比胜平负)
      </p>
    </section>
  );
}