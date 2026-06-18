import Link from "next/link";
import { notFound } from "next/navigation";
import { getLatestRound3Run, teamFlag } from "@/lib/data";
import { MatchRow } from "@/components/MatchRow";

type Props = { params: { letter: string } };

export default function GroupDetailPage({ params }: Props) {
  const r3 = getLatestRound3Run();
  if (!r3) return <div>数据未找到</div>;
  const g = r3.groups[params.letter];
  if (!g) notFound();

  return (
    <div className="space-y-6">
      <div>
        <Link href="/groups" className="text-sm text-emerald-600 hover:underline">
          ← 全部小组
        </Link>
        <h1 className="text-3xl font-bold mt-2">
          Group {params.letter}
        </h1>
        <div className="flex flex-wrap gap-2 mt-2 text-lg">
          {g.teams.map((t) => (
            <span key={t} className="px-2 py-1 rounded-md bg-gray-100 dark:bg-gray-800">
              {teamFlag(t)} {t}
            </span>
          ))}
        </div>
      </div>

      {/* Standings */}
      <section>
        <h2 className="text-2xl font-bold mb-3">📊 最终积分</h2>
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="text-left p-3 w-12">#</th>
                <th className="text-left p-3">球队</th>
                <th className="text-right p-3 w-20">积分</th>
                <th className="text-left p-3">备注</th>
              </tr>
            </thead>
            <tbody>
              {g.standings.map((s, i) => (
                <tr
                  key={s.team}
                  className={`border-t border-gray-100 dark:border-gray-900 ${
                    i < 2
                      ? "font-semibold bg-emerald-50/30 dark:bg-emerald-950/10"
                      : ""
                  }`}
                >
                  <td className="p-3 font-mono text-gray-500">{i + 1}</td>
                  <td className="p-3">
                    {teamFlag(s.team)} {s.team}
                  </td>
                  <td className="p-3 text-right font-mono font-semibold">{s.points}</td>
                  <td className="p-3 text-xs text-gray-500">{s.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          ✅ 前 2 名直接晋级 16 强 · ⚠️ 第 3 名进入 8 个最佳第 3 名排序
        </p>
      </section>

      {/* Matches */}
      <section>
        <h2 className="text-2xl font-bold mb-3">⚽ 全部比赛 (MD2 + MD3)</h2>
        <div className="space-y-3">
          {g.matches.map((m, i) => (
            <MatchRow key={i} match={m} />
          ))}
        </div>
      </section>
    </div>
  );
}
