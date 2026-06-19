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

// FIFA WC 2026 真实赛程 — ESPN scoreboard API 抓的 72 场 (12 组 × 6 场/组), 2026-06-19
// 端点: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260628
// key 格式: "<组字母>|<sorted team A|team B>" (MiroFish 全称, ESPN "Czechia" 已统一为 MiroFish "Czech Republic")
// value: { date: "YYYY-MM-DD", time_utc: "HH:MM" } (ESPN 原始 ISO 时间戳已转 UTC)
// 之前用 GROUP_MD_DATES 只存"该组该比赛日首场日期"近似, 但 MD2/MD3 跨 2 天 (A MD2 = 6/18 + 6/19),
// 导致 1/2 MD 比赛日期错位 1 天。改用 per-matchup 精确查表。
const ESPN_MATCH_SCHEDULE: Record<string, { date: string; time_utc: string }> = {
  "A|Czech Republic|Mexico": { date: "2026-06-25", time_utc: "01:00" },
  "A|Czech Republic|South Africa": { date: "2026-06-18", time_utc: "16:00" },
  "A|Czech Republic|South Korea": { date: "2026-06-12", time_utc: "02:00" },
  "A|Mexico|South Africa": { date: "2026-06-11", time_utc: "19:00" },
  "A|Mexico|South Korea": { date: "2026-06-19", time_utc: "01:00" },
  "A|South Africa|South Korea": { date: "2026-06-25", time_utc: "01:00" },
  "B|Bosnia|Canada": { date: "2026-06-12", time_utc: "19:00" },
  "B|Bosnia|Qatar": { date: "2026-06-24", time_utc: "19:00" },
  "B|Bosnia|Switzerland": { date: "2026-06-18", time_utc: "19:00" },
  "B|Canada|Qatar": { date: "2026-06-18", time_utc: "22:00" },
  "B|Canada|Switzerland": { date: "2026-06-24", time_utc: "19:00" },
  "B|Qatar|Switzerland": { date: "2026-06-13", time_utc: "19:00" },
  "C|Brazil|Haiti": { date: "2026-06-20", time_utc: "00:30" },
  "C|Brazil|Morocco": { date: "2026-06-13", time_utc: "22:00" },
  "C|Brazil|Scotland": { date: "2026-06-24", time_utc: "22:00" },
  "C|Haiti|Morocco": { date: "2026-06-24", time_utc: "22:00" },
  "C|Haiti|Scotland": { date: "2026-06-14", time_utc: "01:00" },
  "C|Morocco|Scotland": { date: "2026-06-19", time_utc: "22:00" },
  "D|Australia|Paraguay": { date: "2026-06-26", time_utc: "02:00" },
  "D|Australia|Turkey": { date: "2026-06-14", time_utc: "04:00" },
  "D|Australia|USA": { date: "2026-06-19", time_utc: "19:00" },
  "D|Paraguay|Turkey": { date: "2026-06-20", time_utc: "03:00" },
  "D|Paraguay|USA": { date: "2026-06-13", time_utc: "01:00" },
  "D|Turkey|USA": { date: "2026-06-26", time_utc: "02:00" },
  "E|Curaçao|Ecuador": { date: "2026-06-21", time_utc: "00:00" },
  "E|Curaçao|Germany": { date: "2026-06-14", time_utc: "17:00" },
  "E|Curaçao|Ivory Coast": { date: "2026-06-25", time_utc: "20:00" },
  "E|Ecuador|Germany": { date: "2026-06-25", time_utc: "20:00" },
  "E|Ecuador|Ivory Coast": { date: "2026-06-14", time_utc: "23:00" },
  "E|Germany|Ivory Coast": { date: "2026-06-20", time_utc: "20:00" },
  "F|Japan|Netherlands": { date: "2026-06-14", time_utc: "20:00" },
  "F|Japan|Sweden": { date: "2026-06-25", time_utc: "23:00" },
  "F|Japan|Tunisia": { date: "2026-06-21", time_utc: "04:00" },
  "F|Netherlands|Sweden": { date: "2026-06-20", time_utc: "17:00" },
  "F|Netherlands|Tunisia": { date: "2026-06-25", time_utc: "23:00" },
  "F|Sweden|Tunisia": { date: "2026-06-15", time_utc: "02:00" },
  "G|Belgium|Egypt": { date: "2026-06-15", time_utc: "19:00" },
  "G|Belgium|Iran": { date: "2026-06-21", time_utc: "19:00" },
  "G|Belgium|New Zealand": { date: "2026-06-27", time_utc: "03:00" },
  "G|Egypt|Iran": { date: "2026-06-27", time_utc: "03:00" },
  "G|Egypt|New Zealand": { date: "2026-06-22", time_utc: "01:00" },
  "G|Iran|New Zealand": { date: "2026-06-16", time_utc: "01:00" },
  "H|Cape Verde|Saudi Arabia": { date: "2026-06-27", time_utc: "00:00" },
  "H|Cape Verde|Spain": { date: "2026-06-15", time_utc: "16:00" },
  "H|Cape Verde|Uruguay": { date: "2026-06-21", time_utc: "22:00" },
  "H|Saudi Arabia|Spain": { date: "2026-06-21", time_utc: "16:00" },
  "H|Saudi Arabia|Uruguay": { date: "2026-06-15", time_utc: "22:00" },
  "H|Spain|Uruguay": { date: "2026-06-27", time_utc: "00:00" },
  "I|France|Iraq": { date: "2026-06-22", time_utc: "21:00" },
  "I|France|Norway": { date: "2026-06-26", time_utc: "19:00" },
  "I|France|Senegal": { date: "2026-06-16", time_utc: "19:00" },
  "I|Iraq|Norway": { date: "2026-06-16", time_utc: "22:00" },
  "I|Iraq|Senegal": { date: "2026-06-26", time_utc: "19:00" },
  "I|Norway|Senegal": { date: "2026-06-23", time_utc: "00:00" },
  "J|Algeria|Argentina": { date: "2026-06-17", time_utc: "01:00" },
  "J|Algeria|Austria": { date: "2026-06-28", time_utc: "02:00" },
  "J|Algeria|Jordan": { date: "2026-06-23", time_utc: "03:00" },
  "J|Argentina|Austria": { date: "2026-06-22", time_utc: "17:00" },
  "J|Argentina|Jordan": { date: "2026-06-28", time_utc: "02:00" },
  "J|Austria|Jordan": { date: "2026-06-17", time_utc: "04:00" },
  "K|Colombia|DR Congo": { date: "2026-06-24", time_utc: "02:00" },
  "K|Colombia|Portugal": { date: "2026-06-27", time_utc: "23:30" },
  "K|Colombia|Uzbekistan": { date: "2026-06-18", time_utc: "02:00" },
  "K|DR Congo|Portugal": { date: "2026-06-17", time_utc: "17:00" },
  "K|DR Congo|Uzbekistan": { date: "2026-06-27", time_utc: "23:30" },
  "K|Portugal|Uzbekistan": { date: "2026-06-23", time_utc: "17:00" },
  "L|Croatia|England": { date: "2026-06-17", time_utc: "20:00" },
  "L|Croatia|Ghana": { date: "2026-06-27", time_utc: "21:00" },
  "L|Croatia|Panama": { date: "2026-06-23", time_utc: "23:00" },
  "L|England|Ghana": { date: "2026-06-23", time_utc: "20:00" },
  "L|England|Panama": { date: "2026-06-27", time_utc: "21:00" },
  "L|Ghana|Panama": { date: "2026-06-17", time_utc: "23:00" },
};
function lookupMatchDate(group: string, teamA: string, teamB: string): { date: string; time_utc: string } | null {
  const a = normalizeTeam(teamA);
  const b = normalizeTeam(teamB);
  const key = `${group}|${[a, b].sort().join("|")}`;
  return ESPN_MATCH_SCHEDULE[key] ?? null;
}
// 兜底: 查不到精确表时, 取该组 MD 内所有比赛的"最早日期"作为近似
function approxMatchDate(group: string, matchday: number): string {
  const all = Object.entries(ESPN_MATCH_SCHEDULE)
    .filter(([k]) => k.startsWith(`${group}|`))
    .map(([, v]) => v.date)
    .sort();
  // 简化: 同一 group 内, MD 越大日期越晚; 这里按位置估算 (12 组都没填第 4 场)
  if (all.length === 0) return "2026-07-01";
  return all[Math.min(matchday - 1, all.length - 1)] ?? all[0];
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
    hit: boolean;             // 胜方命中 (MiroFish win-prob max == real outcome)
    top1_hit: boolean;        // 比分完全命中 (Top-1 比分 == 真实比分) — A+B 新指标
    top3_hit: boolean;        // Top-3 比分包含真实比分 — A+B 新指标
    mirofish_conf: number;
    groupLetter: string;
    simulated: boolean;       // MiroFish 是否模拟了这场
    top_3?: { home: number; away: number; prob: number; pct?: number }[];
    real_date?: string;       // 真实比赛日期 (ISO YYYY-MM-DD), 来自 ESPN, 用于排序
  };
  const rows: Row[] = [];
  for (const rm of real.matches) {
    const g = r3.groups[rm.group];
    if (!g) continue;
    const ra = normalizeTeam(rm.team_a);
    const rb = normalizeTeam(rm.team_b);
    const m = g.matches.find((mm) => {
      const ma = normalizeTeam(mm.team_a);
      const mb = normalizeTeam(mm.team_b);
      return (ma === ra && mb === rb) || (ma === rb && mb === ra);
    });
    const realWinName = rm.score_a > rm.score_b ? teamNameZh(rm.team_a) : rm.score_a < rm.score_b ? teamNameZh(rm.team_b) : "平局";
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
        real_winner: realWinName,
        hit: false, top1_hit: false, top3_hit: false,
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
    const predWinName = pred === "a" ? teamNameZh(m.team_a) : pred === "b" ? teamNameZh(m.team_b) : "平局";
    // Top-1 / Top-3 exact-score hits (A+B new metric)
    const top3 = m.top_3_scores && m.top_3_scores.length > 0 ? m.top_3_scores : undefined;
    const top1 = top3?.[0];
    const top1_hit = !!top1 && top1.home === rm.score_a && top1.away === rm.score_b;
    const top3_hit = !!top3 && top3.some((s) => s.home === rm.score_a && s.away === rm.score_b);
    rows.push({
      group: rm.group,
      team_a: rm.team_a,
      team_b: rm.team_b,
      score_a: rm.score_a,
      score_b: rm.score_b,
      real_score: `${rm.score_a}-${rm.score_b}`,
      pred_score: top1
        ? `${top1.home}-${top1.away}`
        : `${m.most_likely_score.home ?? "—"}-${m.most_likely_score.away ?? "—"}`,
      pred_winner: predWinName,
      real_winner: realWinName,
      hit,
      top1_hit,
      top3_hit,
      mirofish_conf: Math.max(m.team_a_win, m.draw, m.team_b_win),
      groupLetter: rm.group,
      simulated: true,
      top_3: top3,
      real_date: rm.date ?? undefined,
    });
  }

  if (rows.length === 0) return null;

  // 排序 + 拆 section:
  //   - 即将开赛: MiroFish 模拟但 ESPN 还没出结果 (按 ESPN 真实开球时间升序, 最早的在前)
  //   - 已比赛: real 数据里有这场 (按真实比赛日期 asc)
  type UpcomingRow = {
    group: string;
    team_a: string;
    team_b: string;
    matchday: number;
    approx_date: string;     // "YYYY-MM-DD" (查表精确, 不再近似)
    time_utc: string;        // "HH:MM" (ESPN 原始 UTC 开球时间)
    sort_key: string;        // "YYYY-MM-DD HH:MM" 用于排序
    pred_score: string;
    mirofish_conf: number;
    top_3?: { home: number; away: number; prob: number; pct?: number }[];
  };
  const playedRows = rows.slice().sort(
    (a, b) => (a.real_date ?? "").localeCompare(b.real_date ?? "") || a.groupLetter.localeCompare(b.groupLetter),
  );
  const realKeys = new Set(
    real.matches.map((rm) => {
      const a = normalizeTeam(rm.team_a);
      const b = normalizeTeam(rm.team_b);
      return [a, b].sort().join("|");
    }),
  );
  // MiroFish R4 把 MD2/MD3 的 matchup 顺序写反了 (A 组: MiroFish 标 MD2 的 2 场
  // 实际在 6/25 = 真实 MD3, 标 MD3 的 2 场在 6/18-19 = 真实 MD2). 用查到的真实日期反推 MD.
  // 真实 MD 边界 (ESPN): MD1=6/11-17, MD2=6/18-23, MD3=6/24-28
  function realMDFromDate(date: string): number {
    if (date < "2026-06-18") return 1;
    if (date < "2026-06-24") return 2;
    return 3;
  }

  const upcomingRows: UpcomingRow[] = [];
  for (const [gLetter, g] of Object.entries(r3.groups)) {
    for (const m of g.matches) {
      const a = normalizeTeam(m.team_a);
      const b = normalizeTeam(m.team_b);
      const key = [a, b].sort().join("|");
      if (realKeys.has(key)) continue; // 已比赛 → 跳过
      // 精确查表 (per-matchup), 查不到 fallback 近似 (同组同 MD 内最早日期)
      const sched = lookupMatchDate(gLetter, m.team_a, m.team_b);
      const date = sched?.date ?? approxMatchDate(gLetter, m.matchday);
      const time_utc = sched?.time_utc ?? "—";
      const real_md = realMDFromDate(date);
      const top1 = m.top_3_scores?.[0];
      upcomingRows.push({
        group: gLetter,
        team_a: m.team_a,
        team_b: m.team_b,
        matchday: real_md,                // 用真实 MD, 不用 MiroFish 错位的
        approx_date: date,
        time_utc,
        sort_key: `${date} ${time_utc}`,
        pred_score: top1
          ? `${top1.home}-${top1.away}`
          : `${m.most_likely_score.home ?? "—"}-${m.most_likely_score.away ?? "—"}`,
        mirofish_conf: Math.max(m.team_a_win, m.draw, m.team_b_win),
        top_3: m.top_3_scores && m.top_3_scores.length > 0 ? m.top_3_scores : undefined,
      });
    }
  }
  upcomingRows.sort(
    (a, b) =>
      a.sort_key.localeCompare(b.sort_key) ||
      a.matchday - b.matchday ||
      a.group.localeCompare(b.group),
  );

  // 三层命中率: 胜方命中 / Top-1 比分命中 / Top-3 比分命中
  const simulatedRows = rows.filter((r) => r.simulated);
  const hits = simulatedRows.filter((r) => r.hit).length;
  const top1Hits = simulatedRows.filter((r) => r.top1_hit).length;
  const top3Hits = simulatedRows.filter((r) => r.top3_hit).length;
  const hitPct = simulatedRows.length > 0 ? hits / simulatedRows.length : 0;
  const top1Pct = simulatedRows.length > 0 ? top1Hits / simulatedRows.length : 0;
  const top3Pct = simulatedRows.length > 0 ? top3Hits / simulatedRows.length : 0;
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
            🗓 即将开赛 · ✅ 已比赛 vs 🔮 MiroFish 预测 (A+B Top-3 比分模型)
          </div>
          <h2 className="text-xl font-bold">
            Top-1 比分命中 {top1Hits} / {simulatedRows.length} ({formatPct(top1Pct, 1)})
            <span className="text-sm font-normal text-gray-500 ml-2">
              · Top-3 内 {top3Hits} 场 ({formatPct(top3Pct, 1)}) · 胜方命中 {hits} 场
            </span>
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

      {/* 即将开赛 section — MiroFish 已模拟但 ESPN 还没出结果, 排前面 */}
      {upcomingRows.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-bold text-blue-700 dark:text-blue-300">
              🗓 即将开赛 ({upcomingRows.length} 场)
            </h3>
            <span className="text-[10px] text-gray-500">
              按 ESPN 真实开球时间 (UTC) 排序 · 下一场: {(() => {
                const today = new Date().toISOString().slice(0, 10);
                const next = upcomingRows.find((r) => r.sort_key >= `${today} 00:00`) ?? upcomingRows[0];
                if (!next) return "—";
                const md = next.matchday;
                return `${next.approx_date.slice(5)} ${next.time_utc} (MD${md})`;
              })()}
            </span>
          </div>
          <div className="grid md:grid-cols-2 gap-2">
            {upcomingRows.map((r) => {
              const a = r.team_a;
              const b = r.team_b;
              return (
                <Link
                  key={`up-${r.group}-${a}-${b}`}
                  href={`/groups/${r.group}`}
                  className="rounded-lg border border-blue-300 dark:border-blue-800 bg-blue-50/40 dark:bg-blue-950/20 p-3 flex items-center gap-3 hover:shadow-md transition-shadow"
                  title={`MiroFish 预测 ${r.pred_score} · ${r.approx_date} ${r.time_utc} UTC · 比赛日 ${r.matchday} · 置信度 ${formatPct(r.mirofish_conf, 0)}`}
                >
                  <div className="shrink-0 text-center">
                    <div className="text-2xl font-black font-mono leading-none text-blue-700 dark:text-blue-300">
                      🔮
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-blue-600 dark:text-blue-400 mt-1">
                      MD{r.matchday}
                    </div>
                    <div className="text-[9px] text-gray-500 mt-0.5 font-mono">
                      {r.approx_date.slice(5)}
                    </div>
                    <div className="text-[8px] text-gray-400 font-mono">
                      {r.time_utc} UTC
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs mb-0.5">
                      <span>{teamFlag(a)} <span className="font-semibold">{teamNameZh(a)}</span></span>
                      <span className="text-gray-400">vs</span>
                      <span><span className="font-semibold">{teamNameZh(b)}</span> {teamFlag(b)}</span>
                    </div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      预测 <span className="font-mono font-semibold text-blue-700 dark:text-blue-300">{r.pred_score}</span>
                      <span className="ml-2 text-[10px] text-gray-500">
                        {r.group} 组 · 置信度 {formatPct(r.mirofish_conf, 0)}
                      </span>
                    </div>
                    {r.top_3 && r.top_3.length > 0 && (
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className="text-[10px] text-gray-500">Top 3:</span>
                        {r.top_3.map((s, i) => (
                          <span
                            key={i}
                            className={`text-[10px] font-mono px-1 rounded ${
                              i === 0
                                ? "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200"
                                : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                            }`}
                            title={`概率 ${(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(1)}%`}
                          >
                            {s.home}-{s.away} {(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(0)}%
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* 已比赛 section — 排后面, 按真实比赛日期 asc */}
      {playedRows.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-bold text-gray-700 dark:text-gray-300">
              ✅ 已比赛 ({playedRows.length} 场)
            </h3>
            <span className="text-[10px] text-gray-500">按真实比赛日期从早到晚</span>
          </div>
          <div className="grid md:grid-cols-2 gap-2">
            {playedRows.map((r) => {
          const a = r.team_a;
          const b = r.team_b;
          // 四种边框颜色: Top-1 比分命中=深绿, Top-3 内=浅绿, 胜方中但比分错=黄,
          //                胜方也错=橙, 未模拟=灰
          const cardClass = !r.simulated
            ? "border-gray-300 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30 opacity-70"
            : r.top1_hit
              ? "border-emerald-500 bg-emerald-100/70 dark:bg-emerald-950/40 ring-1 ring-emerald-400/50"
              : r.top3_hit
                ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20"
                : r.hit
                  ? "border-yellow-400 dark:border-yellow-700 bg-yellow-50/50 dark:bg-yellow-950/20"
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
                  <>
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      预测 <span className="font-mono font-semibold">{r.pred_score}</span>
                      {" · "}
                      <span className={r.hit ? "text-emerald-700 dark:text-emerald-400" : "text-orange-700 dark:text-orange-400"}>
                        {r.pred_winner} 胜
                      </span>
                    </div>
                    {r.top_3 && r.top_3.length > 0 && (
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className="text-[10px] text-gray-500">Top 3:</span>
                        {r.top_3.map((s, i) => {
                          const isHit = s.home === r.score_a && s.away === r.score_b;
                          return (
                            <span
                              key={i}
                              className={`text-[10px] font-mono px-1 rounded ${
                                isHit
                                  ? "bg-emerald-600 text-white font-bold"
                                  : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                              }`}
                              title={`概率 ${(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(1)}%${isHit ? " · ✓ 命中!" : ""}`}
                            >
                              {s.home}-{s.away} {(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(0)}%
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-xs text-gray-500 italic">
                    MiroFish 未模拟此场 · 真实 {r.real_winner}
                  </div>
                )}
                <div className="text-[10px] text-gray-500 mt-0.5">
                  {r.simulated ? `MiroFish 置信度 ${formatPct(r.mirofish_conf, 0)}` : "等待 MiroFish R5 补全 6 场 schedule"}
                </div>
              </div>

              {/* 命中状态: Top-1 / Top-3 / 胜方 / 未模拟 */}
              <div
                className={`shrink-0 text-base font-black ${
                  !r.simulated
                    ? "text-gray-400"
                    : r.top1_hit
                      ? "text-emerald-600 dark:text-emerald-300"
                      : r.top3_hit
                        ? "text-emerald-500 dark:text-emerald-500"
                        : r.hit
                          ? "text-yellow-600 dark:text-yellow-400"
                          : "text-orange-600 dark:text-orange-400"
                }`}
                title={
                  !r.simulated
                    ? `真实: ${r.real_winner} · MiroFish 未模拟`
                    : r.top1_hit
                      ? `Top-1 比分命中! 预测 ${r.pred_score} = 真实 ${r.real_score}`
                      : r.top3_hit
                        ? `Top-3 内: 真实 ${r.real_score} 在 Top-3 列表中`
                        : r.hit
                          ? `胜方对但比分错: 预测 ${r.pred_score} ≠ 真实 ${r.real_score}`
                          : `预测: ${r.pred_winner} 胜 ${r.pred_score} · 真实: ${r.real_winner} ${r.real_score}`
                }
              >
                {!r.simulated ? "—" : r.top1_hit ? "★" : r.top3_hit ? "✓" : r.hit ? "△" : "✗"}
              </div>
            </Link>
          );
        })}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 mt-3">
        <span className="font-semibold">★ 深绿</span> = Top-1 比分完全命中 ·{" "}
        <span className="font-semibold">✓ 浅绿</span> = 真实比分在 Top-3 列表内 ·{" "}
        <span className="font-semibold">△ 黄</span> = 胜方对但比分错 ·{" "}
        <span className="font-semibold">✗ 橙</span> = 胜方错 ·{" "}
        <span className="font-semibold">— 灰</span> = MiroFish 未模拟 (每组 6 场 schedule 但只跑 4 场) ·
        比分通过 Elo-Poisson 基座 (μ=1.4, 中立场) + MiroFish LLM 微调生成
      </p>
    </section>
  );
}