import { getLatestRound3Run, getSecondLatestRound3Run, getRound2Run, formatPct, teamFlag, teamNameZh, normalizeChampion, stageZh, directionZh, matchupZh, tierLabelZh, loadRealResults, buildPlayedIndex, predictOutcome, playedKeyForMatch } from "@/lib/data";
import { ProbabilityBar, ProbabilityBadge } from "@/components/ProbabilityBar";
import { PlayedVsPredicted } from "@/components/PlayedVsPredicted";
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
      {/* Top headline: 先小后大 — 12 组 + 淘汰 + 冠军 一句话概览 */}
      <section className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gradient-to-br from-gray-50 via-white to-gray-50 dark:from-gray-950 dark:via-black dark:to-gray-950 p-6">
        <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">
          2026 世界杯 · 多智能体预测
        </div>
        <h1 className="text-3xl md:text-4xl font-black tracking-tight">
          12 组赛果 → 8 个最佳第 3 名 → 32 强对阵 → 决赛 → 冠军
        </h1>
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 max-w-3xl leading-relaxed">
          本页顺序: 先看 12 组头名预测 (你最近能下的注) → 冷门风险 → 决赛 → 冠军。
          全部由 MiroFish 多智能体跑 {r3.summary?.rounds || 5} 轮, {r3.summary?.total_actions || 0} 次模拟行动。
        </p>
        <div className="mt-3 flex flex-wrap gap-3 text-xs">
          <Link href="#groups" className="px-3 py-1.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-900/60">
            ⚽ 直接看 12 组 →
          </Link>
          <Link href="/bracket" className="px-3 py-1.5 rounded-full bg-pink-100 dark:bg-pink-900/40 text-pink-700 dark:text-pink-300 hover:bg-pink-200 dark:hover:bg-pink-900/60">
            🌳 树状图 →
          </Link>
          <Link href="#upset" className="px-3 py-1.5 rounded-full bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 hover:bg-orange-200 dark:hover:bg-orange-900/60">
            ⚠️ 看冷门风险 →
          </Link>
          <Link href="#champion" className="px-3 py-1.5 rounded-full bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-900/60">
            🏆 看冠军 →
          </Link>
        </div>
      </section>

      {/* 已比赛 vs 预测对比 (小组赛已开打的场次) */}
      <PlayedVsPredicted />

      {/* 12 Groups at a glance — 现在是最显眼的 */}
      <section id="groups">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">⚽ 12 个小组 (A-L)</h2>
          <Link href="/groups" className="text-sm text-emerald-600 hover:underline">
            全部小组赛详情 →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.values(groups).map((g) => {
            const top = g.standings?.[0];
            const second = g.standings?.[1];
            return (
              <Link
                key={g.letter}
                href={`/groups/${g.letter}`}
                className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-3 hover:border-emerald-500 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="text-lg font-bold">{g.letter} 组</div>
                  <div className="text-xs text-gray-500">{g.teams.length} 队</div>
                </div>
                {top && (
                  <div className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                    <div>
                      头名: {teamFlag(top.team)} <span className="font-semibold">{teamNameZh(top.team)}</span> · {top.points} 分
                    </div>
                    {second && (
                      <div className="text-gray-500">
                        次名: {teamNameZh(second.team)} · {second.points} 分
                      </div>
                    )}
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

      {/* Key dynamics — 解释小组赛为什么这样分 */}
      <section>
        <h2 className="text-2xl font-bold mb-4">📊 关键动态 (5 条)</h2>
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

      {/* Top 5 Upset Risks — 小组赛翻车点 */}
      <section id="upset">
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
                  {stageZh(u.stage)} · {u.rationale}
                </div>
              </div>
              <ProbabilityBadge prob={u.upset_probability} variant="loss" />
            </div>
          ))}
        </div>
      </section>

      {/* Signals — 数据依据 */}
      <section>
        <h2 className="text-2xl font-bold mb-4">🔬 信号源 (5 条)</h2>
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
                  {directionZh(s.direction)} · {formatPct(s.strength, 0)}
                </span>
              </div>
              <p className="text-sm leading-relaxed">{s.signal}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Multi-round drift — 上一轮冠军对比 */}
      {(r2 || prev) && (
        <section className="rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50/50 dark:bg-purple-950/20 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-bold">🔄 多轮预测漂移</h2>
            <Link href="/simulations" className="text-sm text-purple-600 dark:text-purple-400 hover:underline">
              查看详情 →
            </Link>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {prev ? (
              <div>
                <div className="text-xs text-gray-500 uppercase">上一轮 ({prev.run_id})</div>
                <div className="text-2xl font-bold">
                  {teamFlag(normalizeChampion(prev.final.champion))} {teamNameZh(normalizeChampion(prev.final.champion))}{" "}
                  <span className="text-base font-mono text-gray-500">
                    {formatPct(prev.final.confidence || 0)}
                  </span>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {matchupZh(prev.final.matchup)}
                </div>
              </div>
            ) : r2 ? (
              <div>
                <div className="text-xs text-gray-500 uppercase">第 2 轮 ({r2.run_id})</div>
                <div className="text-2xl font-bold">
                  {teamFlag(r2.final.champion || "")} {teamNameZh(r2.final.champion || "")}{" "}
                  <span className="text-base font-mono text-gray-500">
                    {formatPct(r2.final.confidence || 0)}
                  </span>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {matchupZh(r2.final.matchup)}
                </div>
              </div>
            ) : null}
            <div>
              <div className="text-xs text-gray-500 uppercase">最新 ({r3.run_id})</div>
              <div className="text-2xl font-bold">
                {teamFlag(finalChampion)} {teamNameZh(finalChampion)}{" "}
                <span className="text-base font-mono text-emerald-600">
                  {formatPct(finalConf)}
                </span>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {matchupZh(final.matchup)}
              </div>
            </div>
          </div>
          {prev ? (
            <div className="mt-3 text-sm">
              上一轮冠军是 <span className="font-semibold">{teamNameZh(normalizeChampion(prev.final.champion))} {formatPct(prev.final.confidence || 0)}</span>,
              本轮更新到 <span className="font-semibold text-emerald-600">{teamNameZh(finalChampion)} {formatPct(finalConf)}</span>。
            </div>
          ) : r2 ? (
            <div className="mt-3 text-sm">
              冠军从第 2 轮 (蒙特卡洛) 的 <span className="font-semibold">{teamNameZh(r2.final.champion || "")} {formatPct(r2.final.confidence || 0)}</span> 漂移到
              第 3 轮 (多智能体) 的 <span className="font-semibold text-emerald-600">{teamNameZh(finalChampion)} {formatPct(finalConf)}</span>。
              决赛对阵: {matchupZh(r2.final.matchup)} → {matchupZh(final.matchup)}。
            </div>
          ) : null}
        </section>
      )}

      {/* Champion — 末尾 */}
      <section id="champion">
        <h2 className="text-2xl font-bold mb-4">🏆 冠军预测</h2>
        <div className="rounded-2xl border-2 border-emerald-500/30 bg-gradient-to-br from-emerald-50 via-white to-orange-50 dark:from-emerald-950/30 dark:via-black dark:to-orange-950/20 p-6 md:p-8">
          <div className="flex items-center gap-4">
            <div className="text-5xl md:text-7xl font-black tracking-tight">
              {teamFlag(finalChampion)} <span className="bg-gradient-to-r from-emerald-600 to-orange-500 bg-clip-text text-transparent">{teamNameZh(finalChampion)}</span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-mono font-semibold text-sm w-fit">
                置信度 {formatPct(finalConf)}
              </span>
              <div className="text-base font-semibold text-gray-700 dark:text-gray-300">
                决赛: {matchupZh(final.matchup)}
              </div>
            </div>
          </div>
          <p className="mt-4 text-sm md:text-base text-gray-600 dark:text-gray-400 max-w-3xl leading-relaxed">
            {verdict.prediction}
          </p>
        </div>

        {/* Final Tier Breakdown */}
        {final.tiers && final.tiers.length > 0 && (
          <div className="mt-5">
            <h3 className="text-lg font-semibold mb-3">🎯 决赛 — 三档比分概率</h3>
            <div className="grid md:grid-cols-3 gap-3">
              {final.tiers.map((t) => (
                <div key={t.tier} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4">
                  <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                    第 {t.tier} 档
                  </div>
                  <div className="font-semibold text-base mb-2">{tierLabelZh(t.label)}</div>
                  <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
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
          </div>
        )}
      </section>
    </div>
  );
}