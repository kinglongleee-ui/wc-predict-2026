import Link from "next/link";
import { getLatestRound3Run, loadRealResults, teamFlag, teamNameZh, predictOutcome, formatPct } from "@/lib/data";

// R4 (run_e667) 用 FIFA 三字代码 (MEX/CZE), 真实数据 + R3 用全称 (Mexico/Czech Republic)。
// 归一化函数让 lookup 跟两个方向都兼容。
const CODE_TO_TEAM: Record<string, string> = {
  MEX: "Mexico", KOR: "South Korea", CZE: "Czech Republic", RSA: "South Africa",
  SUI: "Switzerland", QAT: "Qatar", BIH: "Bosnia", CAN: "Canada",
  BRA: "Brazil", MAR: "Morocco", SCO: "Scotland", HAI: "Haiti",
  USA: "USA", PAR: "Paraguay", AUS: "Australia", TUR: "Turkey",
  GER: "Germany", ECU: "Ecuador", CIV: "Ivory Coast", CUW: "Curaçao",
  NED: "Netherlands", SWE: "Sweden", JPN: "Japan", TUN: "Tunisia",
  BEL: "Belgium", IRN: "Iran", EGY: "Egypt", NZL: "New Zealand",
  ESP: "Spain", URU: "Uruguay", KSA: "Saudi Arabia", CPV: "Cape Verde",
  FRA: "France", NOR: "Norway", SEN: "Senegal", IRQ: "Iraq",
  ARG: "Argentina", ALG: "Algeria", AUT: "Austria", JOR: "Jordan",
  POR: "Portugal", COL: "Colombia", COD: "DR Congo", UZB: "Uzbekistan",
  ENG: "England", CRO: "Croatia", GHA: "Ghana", PAN: "Panama",
};
function normalizeTeam(t: string): string {
  const trimmed = t.trim();
  return CODE_TO_TEAM[trimmed] || trimmed; // 三字→全称; 全称→原样
}

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
    simulated: boolean; // MiroFish 是否模拟了这场
  };
  const rows: Row[] = [];
  for (const rm of real.matches) {
    const g = r3.groups[rm.group];
    if (!g) continue;
    // 在 MiroFish 模拟里找 (team_a, team_b) 这场 (顺序无关)。
    // MiroFish R4 用三字代码 (MEX/CZE), 真实数据用全称 (Mexico/Czech Republic);
    // 归一化两个方向都兼容 (e.g. "MEX" === "Mexico" via CODE_TO_TEAM)。
    const ra = normalizeTeam(rm.team_a);
    const rb = normalizeTeam(rm.team_b);
    const m = g.matches.find((mm) => {
      const ma = normalizeTeam(mm.team_a);
      const mb = normalizeTeam(mm.team_b);
      return (ma === ra && mb === rb) || (ma === rb && mb === ra);
    });
    // MiroFish 每组只模拟 6 场 schedule 里的 4 场; 没模拟的也列出, 标 "未模拟"。
    if (!m) {
      rows.push({
        group: rm.group,
        team_a: rm.team_a,
        team_b: rm.team_b,
        score_a: rm.score_a,
        score_b: rm.score_b,
        real_score: `${rm.score_a}-${rm.score_b}`,
        pred_score: "—",
        pred_winner: "—",
        real_winner: rm.score_a > rm.score_b ? teamNameZh(rm.team_a) : rm.score_a < rm.score_b ? teamNameZh(rm.team_b) : "平局",
        hit: false,
        mirofish_conf: 0,
        groupLetter: rm.group,
        simulated: false,
      });
      continue;
    }
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
      simulated: true,
    });
  }

  if (rows.length === 0) return null;

  // 命中率只算 MiroFish 实际模拟的场次
  const simulatedRows = rows.filter((r) => r.simulated);
  const hits = simulatedRows.filter((r) => r.hit).length;
  const hitPct = simulatedRows.length > 0 ? hits / simulatedRows.length : 0;
  const unSimulatedCount = rows.filter((r) => !r.simulated).length;

  return (
    <section className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gradient-to-br from-emerald-50/40 via-white to-orange-50/40 dark:from-emerald-950/15 dark:via-black dark:to-orange-950/15 p-5">
      {/* 数据来源说明 — ESPN 实时赛事比分 (非 FIFA 官方) */}
      <div className="mb-3 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
        <span className="font-bold">📊 数据来源</span> —
        "真实比分"抓取自
        <a
          href="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
          target="_blank"
          rel="noopener noreferrer"
          className="underline mx-1 font-semibold"
        >
          ESPN 公开赛事 API
        </a>
        (实时更新 · 每 9 小时拉取一次),<span className="font-semibold">非 FIFA 官方数据</span>。
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
            {hits} / {simulatedRows.length} 场胜方预测命中 ({formatPct(hitPct, 0)})
            {unSimulatedCount > 0 && (
              <span className="text-sm font-normal text-gray-500 ml-2">
                + {unSimulatedCount} 场 MiroFish 未模拟
              </span>
            )}
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
          // 三种边框: 命中=绿, 未中=橙, 未模拟=灰
          const cardClass = !r.simulated
            ? "border-gray-300 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30 opacity-70"
            : r.hit
              ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20"
              : "border-orange-300 dark:border-orange-800 bg-orange-50/50 dark:bg-orange-950/20";
          return (
            <Link
              key={`${r.group}-${a}-${b}`}
              href={`/groups/${r.groupLetter}`}
              className={`rounded-lg border p-3 flex items-center gap-3 hover:shadow-md transition-shadow ${cardClass}`}
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
                {r.simulated ? (
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    预测 <span className="font-mono font-semibold">{r.pred_score}</span>
                    {" · "}
                    <span className={r.hit ? "text-emerald-700 dark:text-emerald-400" : "text-orange-700 dark:text-orange-400"}>
                      {r.pred_winner} 胜
                    </span>
                  </div>
                ) : (
                  <div className="text-xs text-gray-500 italic">
                    MiroFish 未模拟此场 · 真实 {r.real_winner}
                  </div>
                )}
                <div className="text-[10px] text-gray-500 mt-0.5">
                  {r.simulated ? `MiroFish 置信度 ${formatPct(r.mirofish_conf, 0)}` : "等待 MiroFish R5 补全 6 场 schedule"}
                </div>
              </div>

              {/* 命中状态 */}
              <div
                className={`shrink-0 text-base font-black ${
                  !r.simulated
                    ? "text-gray-400"
                    : r.hit
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-orange-600 dark:text-orange-400"
                }`}
                title={r.simulated ? `预测: ${r.pred_winner} 胜 · 真实: ${r.real_winner}` : `真实: ${r.real_winner} · MiroFish 未模拟`}
              >
                {!r.simulated ? "—" : r.hit ? "✓" : "✗"}
              </div>
            </Link>
          );
        })}
      </div>

      <p className="text-xs text-gray-500 mt-3">
        绿色 ✓ = MiroFish 预测的胜方与真实胜方一致 · 橙色 ✗ = 预测错了胜方 ·
        灰色 — = MiroFish 未模拟此场 (每组 schedule 6 场但只跑 4 场) ·
        比分/进球不参与对比 (只对比胜平负)
      </p>
    </section>
  );
}