import Link from "next/link";
import { getLatestRound3Run, getSecondLatestRound3Run, getRound2Run, formatPct, teamFlag, teamNameZh, normalizeChampion, matchupZh } from "@/lib/data";

export default function SimulationsPage() {
  const r3 = getLatestRound3Run();
  const prev = getSecondLatestRound3Run();
  const r2 = getRound2Run();
  if (!r3) return <div>数据未找到</div>;

  const r3Champion = normalizeChampion(r3.final.champion);
  // Compare against second-latest R3 run when available; fall back to the
  // pinned Round 2 baseline (run_a18431af48fd).
  const compareRun = prev || r2;
  const compareLabel = prev
    ? `上一轮 (${prev.run_id})`
    : r2
    ? `第 2 轮 (${r2.run_id})`
    : null;
  const compareChampion = prev
    ? normalizeChampion(prev.final.champion)
    : (r2?.final.champion || "—");

  return (
    <div className="space-y-8">
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 返回首页</Link>
        <h1 className="text-3xl font-bold mt-2">🔄 多轮模拟对比</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {compareLabel ? `${compareLabel} 对比 最新 (${r3.run_id})` : `最新 (${r3.run_id})`} — MiroFish 多智能体自治模拟
        </p>
      </div>

      {/* Headline drift */}
      {compareLabel && (
        <section className="rounded-2xl border-2 border-purple-300 dark:border-purple-900/50 bg-gradient-to-br from-purple-50/50 to-emerald-50/50 dark:from-purple-950/20 dark:to-emerald-950/10 p-6">
          <h2 className="text-xl font-bold mb-4">🏆 冠军预测漂移</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <div className="text-xs text-gray-500 uppercase mb-2">{compareLabel}</div>
              <div className="text-4xl font-black">
                {teamFlag(compareChampion)} {teamNameZh(compareChampion)}
              </div>
              <div className="text-2xl font-mono text-gray-600 dark:text-gray-400 mt-1">
                {formatPct(compareRun?.final.confidence || 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                {matchupZh(compareRun?.final.matchup)}
              </div>
            </div>

            <div>
              <div className="text-xs text-gray-500 uppercase mb-2">最新 ({r3.run_id})</div>
              <div className="text-4xl font-black">
                {teamFlag(r3Champion)} {teamNameZh(r3Champion)}
              </div>
              <div className="text-2xl font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                {formatPct(r3.final.confidence || 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                {matchupZh(r3.final.matchup)}
              </div>
            </div>
          </div>
          <div className="mt-6 p-4 rounded-lg bg-white/60 dark:bg-black/30 text-sm leading-relaxed">
            <strong>关键变化:</strong>{" "}
            上一轮冠军是 <span className="font-semibold">{teamNameZh(compareChampion)}</span>
            {compareRun?.final.matchup ? <> (决赛对阵: {matchupZh(compareRun.final.matchup)})</> : null},
            本轮更新为 <span className="font-semibold">{teamNameZh(r3Champion)}</span>
            (决赛对阵: {matchupZh(r3.final.matchup) || "—"})。
          </div>
        </section>
      )}

      {/* Champion probability table (Round 2 has full table) */}
      {r2?.champion_table && (
        <section>
          <h2 className="text-2xl font-bold mb-3">📊 第 2 轮冠军概率表 (10,000 次蒙特卡洛模拟)</h2>
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="text-left p-3">#</th>
                  <th className="text-left p-3">球队</th>
                  <th className="text-right p-3">第 2 轮概率</th>
                  <th className="text-right p-3">变化</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(r2.champion_table)
                  .sort(([, a], [, b]) => b - a)
                  .map(([team, prob], i) => (
                    <tr key={team} className="border-t border-gray-100 dark:border-gray-900">
                      <td className="p-3 font-mono text-gray-500">{i + 1}</td>
                      <td className="p-3 font-semibold">
                        {teamFlag(team)} {teamNameZh(team)}
                      </td>
                      <td className="p-3 text-right font-mono">{formatPct(prob)}</td>
                      <td className="p-3 text-right">
                        {team === "Argentina" ? (
                          <span className="text-orange-600">↓ 跌至八强出局</span>
                        ) : team === "France" ? (
                          <span className="text-emerald-600">↑ 最终夺冠</span>
                        ) : team === "Spain" ? (
                          <span className="text-emerald-600">↑ 新晋决赛</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Verdict comparison */}
      <section>
        <h2 className="text-2xl font-bold mb-3">🧠 关键判断变化</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-5">
            <div className="text-xs text-gray-500 uppercase mb-2">{compareLabel || "上轮"} 关键叙事</div>
            <ul className="space-y-1 text-sm">
              {compareRun?.verdict.key_dynamics.slice(0, 5).map((d, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-purple-500">▸</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-5">
            <div className="text-xs text-gray-500 uppercase mb-2">最新 ({r3.run_id}) 关键叙事</div>
            <ul className="space-y-1 text-sm">
              {r3.verdict.key_dynamics.map((d, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-emerald-500">▸</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Methodology note */}
      <section className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-5 text-sm">
        <div className="font-semibold mb-2">📐 方法论</div>
        <ul className="space-y-1 text-gray-600 dark:text-gray-400 leading-relaxed">
          <li>
            <strong>第 2 轮</strong>: 10,000 次蒙特卡洛模拟 48 场小组赛 + 全淘汰赛, 输出概率分布。
            数据源: 智能体推文。
          </li>
          <li>
            <strong>第 3 轮及之后</strong>: 5 轮强化约束 (硬性要求: 12 组全列 + 全部淘汰赛阶段 + 3 档比分)。
            数据源: 第 2 轮基础 + MiroFish 多智能体 (OASIS + GraphRAG + Zep) 调度。
          </li>
          <li>
            <strong>决策方式</strong>: 全部基于 MiroFish 多智能体自治运行, 人类只设置提示词与解析输出。
            cron 每天自动重跑一次, 首页和 /simulations 自动接上最新一轮。
          </li>
        </ul>
      </section>
    </div>
  );
}
