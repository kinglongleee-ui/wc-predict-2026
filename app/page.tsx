import { getLatestRound3Run, getSecondLatestRound3Run, getRound2Run, formatPct, teamFlag, normalizeChampion } from "@/lib/data";
import { ProbabilityBar, ProbabilityBadge } from "@/components/ProbabilityBar";
import Link from "next/link";

export default function HomePage() {
  const r3 = getLatestRound3Run();
  const prev = getSecondLatestRound3Run();
  const r2 = getRound2Run();
  if (!r3) {
    return (
      <div className="p-8 text-center text-gray-500">
        数据未找到。请先跑 <code className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">npm run parse</code>
      </div>
    );
  }

  const { verdict, final, upset_risks, groups } = r3;
  const finalChampion = normalizeChampion(final.champion);
  const finalConf = final.confidence || verdict.confidence;

  return (
    <div className="space-y-8">
      {/* Champion Hero */}
      <section className="rounded-2xl border-2 border-emerald-500/30 bg-gradient-to-br from-emerald-50 via-white to-orange-50 dark:from-emerald-950/30 dark:via-black dark:to-orange-950/20 p-6 md:p-10">
        <div className="text-xs uppercase tracking-widest text-emerald-700 dark:text-emerald-400 mb-2">
          🏆 2026 FIFA 世界杯 · 冠军预测
        </div>
        <h1 className="text-4xl md:text-6xl font-black tracking-tight">
          {teamFlag(finalChampion)} <span className="bg-gradient-to-r from-emerald-600 to-orange-500 bg-clip-text text-transparent">{finalChampion}</span>
        </h1>
        <div className="mt-2 text-2xl font-semibold text-gray-700 dark:text-gray-300">
          {final.matchup || "vs —"}
        </div>
        <div className="mt-4 flex flex-wrap gap-2 items-center text-sm">
          <span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-mono font-semibold">
            置信度 {formatPct(finalConf)}
          </span>
          <span className="px-3 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono">
            {r3.summary?.rounds || 5} 轮模拟 · {r3.summary?.total_actions || 0} 次智能体行动
          </span>
          {r3.summary?.top_agents?.slice(0, 2).map((a) => (
            <span key={a.agent_id} className="px-3 py-1 rounded-full bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 text-xs">
              {a.agent_name}: {a.total_actions} 次行动
            </span>
          ))}
        </div>
        <p className="mt-4 text-sm md:text-base text-gray-600 dark:text-gray-400 max-w-3xl leading-relaxed">
          {verdict.prediction}
        </p>
      </section>

      {/* Final Tier Breakdown */}
      {final.tiers && final.tiers.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold mb-4">🎯 决赛 — 三档比分概率</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {final.tiers.map((t) => (
              <div key={t.tier} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-5">
                <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                  Tier {t.tier}
                </div>
                <div className="font-semibold text-lg mb-2">{t.label}</div>
                <div className="text-3xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
                  {t.probability !== null ? formatPct(t.probability) : "—"}
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 leading-relaxed">
                  {t.content}
                </p>
              </div>
            ))}
          </div>
          {final.combined_text && (
            <div className="mt-3 text-sm text-gray-600 dark:text-gray-400 text-center font-mono">
              {final.combined_text}
            </div>
          )}
        </section>
      )}

      {/* Multi-round drift */}
      {(r2 || prev) && (
        <section className="rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50/50 dark:bg-purple-950/20 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-bold">🔄 多轮预测漂移 (上一轮 → 最新一轮)</h2>
            <Link href="/simulations" className="text-sm text-purple-600 dark:text-purple-400 hover:underline">
              查看详情 →
            </Link>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {prev ? (
              <div>
                <div className="text-xs text-gray-500 uppercase">上一轮 ({prev.run_id})</div>
                <div className="text-2xl font-bold">
                  {teamFlag(normalizeChampion(prev.final.champion))} {normalizeChampion(prev.final.champion)}{" "}
                  <span className="text-base font-mono text-gray-500">
                    {formatPct(prev.final.confidence || 0)}
                  </span>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {prev.final.matchup}
                </div>
              </div>
            ) : r2 ? (
              <div>
                <div className="text-xs text-gray-500 uppercase">第 2 轮 ({r2.run_id})</div>
                <div className="text-2xl font-bold">
                  {teamFlag(r2.final.champion || "")} {r2.final.champion}{" "}
                  <span className="text-base font-mono text-gray-500">
                    {formatPct(r2.final.confidence || 0)}
                  </span>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {r2.final.matchup}
                </div>
              </div>
            ) : null}
            <div>
              <div className="text-xs text-gray-500 uppercase">最新 ({r3.run_id})</div>
              <div className="text-2xl font-bold">
                {teamFlag(finalChampion)} {finalChampion}{" "}
                <span className="text-base font-mono text-emerald-600">
                  {formatPct(finalConf)}
                </span>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {final.matchup}
              </div>
            </div>
          </div>
          {prev ? (
            <div className="mt-3 text-sm">
              上一轮冠军是 <span className="font-semibold">{normalizeChampion(prev.final.champion)} {formatPct(prev.final.confidence || 0)}</span>,
              本轮更新到 <span className="font-semibold text-emerald-600">{finalChampion} {formatPct(finalConf)}</span>。
            </div>
          ) : r2 ? (
            <div className="mt-3 text-sm">
              冠军从第 2 轮 (蒙特卡洛) 的 <span className="font-semibold">{r2.final.champion || "—"} {formatPct(r2.final.confidence || 0)}</span> 漂移到
              第 3 轮 (多智能体) 的 <span className="font-semibold text-emerald-600">{finalChampion} {formatPct(finalConf)}</span>。
              决赛对阵: {r2.final.matchup} → {final.matchup}。
            </div>
          ) : null}
        </section>
      )}

      {/* Key dynamics */}
      <section>
        <h2 className="text-2xl font-bold mb-4">📊 关键动态</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {verdict.key_dynamics.map((d, i) => (
            <div key={i} className="flex gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
              <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono shrink-0">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="text-sm leading-relaxed">{d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Top 5 Upset Risks */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">⚠️ 前 5 大冷门风险</h2>
          <Link href="/simulations" className="text-sm text-emerald-600 hover:underline">
            完整 5 场 →
          </Link>
        </div>
        <div className="space-y-2">
          {upset_risks.map((u) => (
            <div
              key={u.rank}
              className="flex items-center gap-4 p-3 rounded-lg border border-orange-200 dark:border-orange-900/30 bg-orange-50/30 dark:bg-orange-950/10"
            >
              <div className="text-2xl font-black text-orange-600 dark:text-orange-400 font-mono shrink-0 w-8 text-center">
                #{u.rank}
              </div>
              <div className="flex-1">
                <div className="font-semibold">{u.match}</div>
                <div className="text-xs text-gray-500">
                  {u.stage} · {u.rationale}
                </div>
              </div>
              <ProbabilityBadge prob={u.upset_probability} variant="loss" />
            </div>
          ))}
        </div>
      </section>

      {/* 12 Groups at a glance */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">⚽ 12 个小组 (A-L)</h2>
          <Link href="/groups" className="text-sm text-emerald-600 hover:underline">
            全部小组赛 →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.values(groups).map((g) => {
            const top = g.standings?.[0];
            return (
              <Link
                key={g.letter}
                href={`/groups/${g.letter}`}
                className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-3 hover:border-emerald-500 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="text-lg font-bold">Group {g.letter}</div>
                  <div className="text-xs text-gray-500">{g.teams.length} 队</div>
                </div>
                {top && (
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    头名预测: {teamFlag(top.team)} <span className="font-semibold">{top.team}</span> · {top.points} 分
                  </div>
                )}
                <div className="mt-2 flex -space-x-1">
                  {g.teams.slice(0, 4).map((t) => (
                    <span key={t} className="text-base" title={t}>
                      {teamFlag(t)}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Signals */}
      <section>
        <h2 className="text-2xl font-bold mb-4">🔬 信号源 (5)</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {verdict.signals.map((s, i) => (
            <div
              key={i}
              className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                    s.direction === "positive"
                      ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                      : s.direction === "negative"
                      ? "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                  }`}
                >
                  {s.direction} · {formatPct(s.strength, 0)}
                </span>
              </div>
              <p className="text-sm leading-relaxed">{s.signal}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
