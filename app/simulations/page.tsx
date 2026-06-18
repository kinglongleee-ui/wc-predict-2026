import Link from "next/link";
import { getLatestRound3Run, getRound2Run, formatPct, teamFlag } from "@/lib/data";

export default function SimulationsPage() {
  const r3 = getLatestRound3Run();
  const r2 = getRound2Run();
  if (!r3) return <div>数据未找到</div>;

  const r3Champion = r3.final.champion?.replace(/\s*—\s*confidence.*$/, "").trim() || "—";
  const r2Champion = r2?.final.champion || "—";

  return (
    <div className="space-y-8">
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 返回首页</Link>
        <h1 className="text-3xl font-bold mt-2">🔄 多轮模拟对比</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Round 2 (run_a18431af48fd) vs Round 3 (run_b37f734df790) — 5 rounds · 更强约束
        </p>
      </div>

      {/* Headline drift */}
      <section className="rounded-2xl border-2 border-purple-300 dark:border-purple-900/50 bg-gradient-to-br from-purple-50/50 to-emerald-50/50 dark:from-purple-950/20 dark:to-emerald-950/10 p-6">
        <h2 className="text-xl font-bold mb-4">🏆 冠军预测漂移</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="text-xs text-gray-500 uppercase mb-2">Round 2</div>
            <div className="text-4xl font-black">
              {teamFlag(r2Champion)} {r2Champion}
            </div>
            <div className="text-2xl font-mono text-gray-600 dark:text-gray-400 mt-1">
              {formatPct(r2?.final.confidence || 0)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              {r2?.final.matchup}
            </div>
          </div>

          <div>
            <div className="text-xs text-gray-500 uppercase mb-2">Round 3 (current)</div>
            <div className="text-4xl font-black">
              {teamFlag(r3Champion)} {r3Champion}
            </div>
            <div className="text-2xl font-mono text-emerald-600 dark:text-emerald-400 mt-1">
              {formatPct(r3.final.confidence || 0)}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              {r3.final.matchup}
            </div>
          </div>
        </div>
        <div className="mt-6 p-4 rounded-lg bg-white/60 dark:bg-black/30 text-sm leading-relaxed">
          <strong>关键变化:</strong> Round 3 引入了"阿根廷 QF 被法国点球淘汰"剧情
          (报告第 6 节 France vs Argentina QF: 1-1 → 2-2 → 4-3 pens, 30% AET 18% pens)，
          因此最终决赛对手从 <span className="font-semibold">阿根廷</span> 变成 <span className="font-semibold">西班牙</span>。
          冠军仍属法国, 但置信度从 22% (Monte Carlo) 升到 64% (MiroFish Round 3 报告输出)。
        </div>
      </section>

      {/* Champion probability table (Round 2 has full table) */}
      {r2?.champion_table && (
        <section>
          <h2 className="text-2xl font-bold mb-3">📊 Round 2 冠军概率表 (10,000-iter Monte Carlo)</h2>
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="text-left p-3">#</th>
                  <th className="text-left p-3">球队</th>
                  <th className="text-right p-3">Round 2 概率</th>
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
                        {teamFlag(team)} {team}
                      </td>
                      <td className="p-3 text-right font-mono">{formatPct(prob)}</td>
                      <td className="p-3 text-right">
                        {team === "Argentina" ? (
                          <span className="text-orange-600">↓ dropped to QF exit</span>
                        ) : team === "France" ? (
                          <span className="text-emerald-600">↑ champion</span>
                        ) : team === "Spain" ? (
                          <span className="text-emerald-600">↑ new finalist</span>
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
            <div className="text-xs text-gray-500 uppercase mb-2">Round 2 关键叙事</div>
            <ul className="space-y-1 text-sm">
              {r2?.verdict.key_dynamics.slice(0, 5).map((d, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-purple-500">▸</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-5">
            <div className="text-xs text-gray-500 uppercase mb-2">Round 3 关键叙事</div>
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
        <div className="font-semibold mb-2">📐 方法论差异</div>
        <ul className="space-y-1 text-gray-600 dark:text-gray-400 leading-relaxed">
          <li>
            <strong>Round 2</strong>: 10,000-iter Monte Carlo 模拟 48 场小组赛 + 全淘汰赛，输出概率分布。
            数据源: agent 推文。
          </li>
          <li>
            <strong>Round 3</strong>: 5 rounds 强化约束 (强约束: 12 组全列 + 全部 KO 阶段 + 3 档比分)。
            数据源: Round 2 基础 + 新增 Claude Opus 4 Sonnet/Haiku 调度。
          </li>
          <li>
            <strong>核心分歧</strong>: Round 2 给阿根廷 22% (easiest projected path),
            Round 3 在 QF 让阿根廷被法国点球淘汰 (4-3 比分, 18% 概率分支) — 同一份模拟, 不同抽样窗口。
          </li>
        </ul>
      </section>
    </div>
  );
}
