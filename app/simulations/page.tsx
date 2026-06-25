import Link from "next/link";
import { listRuns, getRound2Run, formatPct, teamFlag, teamNameZh, normalizeChampion, matchupZh, loadRun } from "@/lib/data";

export const dynamic = "force-static";

export default function SimulationsPage() {
  const allRuns = listRuns();
  const r2 = getRound2Run();
  if (allRuns.length === 0) return <div>数据未找到</div>;

  // 给每个 run 加 label (按 created_at 倒序编号, 最新是 R12)
  const sortedDesc = [...allRuns].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const runsWithLabel = sortedDesc.map((r, i) => ({
    ...r,
    label: `R${sortedDesc.length - i}`,  // R12, R11, R10, ... R1
  }));

  // 数据完整性评估
  function completeness(r: any) {
    const groups = Object.keys(r.groups || {}).length;
    const best3 = (r.best_thirds || []).length;
    const r32 = (r.bracket?.r32 || []).length;
    const r16 = (r.bracket?.r16 || []).length;
    const qf = (r.bracket?.qf || []).length;
    const sf = (r.bracket?.sf || []).length;
    const hasFinal = !!(r.final && r.final.matchup);
    const total = groups * 4 + best3 * 4 + r32 * 3 + r16 * 2 + qf * 1.5 + sf * 1;
    const max = 12 * 4 + 8 * 4 + 16 * 3 + 8 * 2 + 4 * 1.5 + 2 * 1;
    return {
      groups, best3, r32, r16, qf, sf, hasFinal,
      score: Math.round((total / max) * 100),
    };
  }

  return (
    <div className="space-y-8">
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 返回首页</Link>
        <h1 className="text-3xl font-bold mt-2">🔄 多轮模拟时间轴 (R1-R{allRuns.length})</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {allRuns.length} 个 MiroFish 多智能体模拟 run, 按时间倒序, 展示每轮的冠军预测、数据完整度、关键日期。
        </p>
      </div>

      {/* 时间轴视图 */}
      <section>
        <h2 className="text-2xl font-bold mb-3">📅 时间轴</h2>
        <div className="space-y-3">
          {runsWithLabel.map((r) => {
            const comp = completeness(r);
            const isBaseline = r.run_id === "run_a18431af48fd";
            return (
              <Link
                key={r.run_id}
                href={`/report/${r.run_id}`}
                className={`block rounded-xl border-2 p-4 transition hover:shadow-md ${
                  isBaseline
                    ? "border-orange-300 bg-orange-50/40 dark:bg-orange-950/10"
                    : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 hover:border-emerald-400"
                }`}
              >
                <div className="grid md:grid-cols-12 gap-4 items-center">
                  <div className="md:col-span-1">
                    <div className="text-2xl font-black">{r.label}</div>
                    <div className="text-xs text-gray-500 font-mono">{r.run_id.slice(0, 8)}</div>
                  </div>

                  <div className="md:col-span-2">
                    <div className="text-xs text-gray-500 uppercase">创建时间</div>
                    <div className="text-sm font-mono">{(r.created_at || "").slice(0, 16).replace("T", " ")}</div>
                  </div>

                  <div className="md:col-span-2">
                    <div className="text-xs text-gray-500 uppercase">冠军预测</div>
                    <div className="text-base font-semibold">
                      {teamFlag(r.final?.champion || "")} {teamNameZh(normalizeChampion(r.final?.champion || ""))}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      置信 {formatPct(r.final?.confidence || r.verdict?.confidence || 0)}
                    </div>
                  </div>

                  <div className="md:col-span-2">
                    <div className="text-xs text-gray-500 uppercase">决赛</div>
                    <div className="text-sm">{matchupZh(r.final?.matchup) || "—"}</div>
                  </div>

                  <div className="md:col-span-3">
                    <div className="text-xs text-gray-500 uppercase">数据完整度</div>
                    <div className="flex gap-2 text-xs font-mono mt-1 flex-wrap">
                      <span className={comp.groups === 12 ? "text-emerald-600" : "text-orange-500"}>组 {comp.groups}/12</span>
                      <span className={comp.best3 >= 7 ? "text-emerald-600" : "text-orange-500"}>3rd {comp.best3}/8</span>
                      <span className={comp.r32 === 16 ? "text-emerald-600" : "text-orange-500"}>R32 {comp.r32}/16</span>
                      <span className={comp.r16 === 8 ? "text-emerald-600" : "text-orange-500"}>R16 {comp.r16}/8</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-1.5 mt-2">
                      <div
                        className={`h-1.5 rounded-full ${comp.score > 70 ? "bg-emerald-500" : comp.score > 40 ? "bg-yellow-500" : "bg-red-500"}`}
                        style={{ width: `${comp.score}%` }}
                      />
                    </div>
                  </div>

                  <div className="md:col-span-2 text-right">
                    <div className="text-xs text-gray-500">查看详情 →</div>
                    {isBaseline && (
                      <div className="text-xs text-orange-600 mt-1">📌 R2 基线</div>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* 冠军漂移对比 */}
      <section>
        <h2 className="text-2xl font-bold mb-3">🏆 冠军预测漂移图</h2>
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="text-left p-3">Run</th>
                <th className="text-left p-3">日期</th>
                <th className="text-left p-3">冠军</th>
                <th className="text-right p-3">置信</th>
                <th className="text-left p-3">决赛</th>
                <th className="text-right p-3">完整度</th>
              </tr>
            </thead>
            <tbody>
              {runsWithLabel.map((r) => {
                const comp = completeness(r);
                return (
                  <tr key={r.run_id} className="border-t border-gray-100 dark:border-gray-900">
                    <td className="p-3">
                      <Link href={`/report/${r.run_id}`} className="font-bold text-emerald-600 hover:underline">
                        {r.label}
                      </Link>
                      <span className="text-xs text-gray-500 ml-2">{r.run_id.slice(0, 6)}</span>
                    </td>
                    <td className="p-3 text-xs font-mono text-gray-600 dark:text-gray-400">
                      {(r.created_at || "").slice(0, 10)}
                    </td>
                    <td className="p-3">
                      <span className="font-semibold">
                        {teamFlag(r.final?.champion || "")} {teamNameZh(normalizeChampion(r.final?.champion || ""))}
                      </span>
                    </td>
                    <td className="p-3 text-right font-mono">
                      {formatPct(r.final?.confidence || r.verdict?.confidence || 0)}
                    </td>
                    <td className="p-3 text-sm">{matchupZh(r.final?.matchup) || "—"}</td>
                    <td className="p-3 text-right">
                      <span className={`text-xs font-mono ${comp.score > 70 ? "text-emerald-600" : "text-orange-500"}`}>
                        {comp.score}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 历史叙事 */}
      <section>
        <h2 className="text-2xl font-bold mb-3">📖 历史叙事 (按时间顺序)</h2>
        <ol className="space-y-2 list-decimal pl-6 text-sm leading-relaxed">
          <li><strong>R1 (R2 baseline, 6/18):</strong> run_a18431af48fd — 10,000 次蒙特卡洛模拟, 阿根廷 22% 卫冕 (1990 后最高), 法国 19%, 巴西 18%。决赛 90min 39% / AET 31% / Pen 30%</li>
          <li><strong>R2 (6/18-6/19):</strong> run_b37f734df790 — MiroFish 模拟, 法国 64% 冠军 (Elo 1870), 决赛 France vs Spain</li>
          <li><strong>R3 老 (6/18):</strong> run_d7c8d02bf376 — MiroFish 16 R32 完整, 巴西 C 组头名 9 分</li>
          <li><strong>R3 新 (6/19):</strong> run_e667e173bb3f — MiroFish 模拟, D 组缺 best 3rd, 兜底后正常</li>
          <li><strong>R5 (6/22):</strong> run_3e9d8be4115d — Top-1 命中率 MD1 100%, 短 prompt 改输出顺序</li>
          <li><strong>R6 (6/23):</strong> run_ea1419a0e22f — DraftKings 赔率注入, 法国 68% 冠军 (Elo 1870), 决赛 France vs Argentina</li>
          <li><strong>R7 (6/24):</strong> run_d1f74f4afe69 — MD2 修正, 阿根廷 62% 冠军, 7 best 3rd (D 组缺)</li>
          <li><strong>R8 (6/24):</strong> run_25c1443aa500 — 完整 16+8+4+2+Final 链, 134 兜底触发</li>
          <li><strong>R9 (6/25):</strong> run_905a0881175d — R10 sync 模拟, 12 R32 matchups (134 兜底生成 16 场真实 FIFA 配对)</li>
          <li><strong>R11 (6/25):</strong> run_905a0881175d — 翻译 R11 narrative → 中文</li>
          <li><strong>R12 (6/25 17:30):</strong> run_14dbeb45e10a — <span className="text-emerald-600 font-semibold">deterministic v4</span>: 真实结果 + Elo-Poisson + FIFA Match 73-88, 阿根廷 30% 冠军</li>
        </ol>
      </section>
    </div>
  );
}
