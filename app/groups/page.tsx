import Link from "next/link";
import { getLatestRound3Run, listGroupLetters, teamFlag, teamNameZh } from "@/lib/data";

export default function GroupsOverviewPage() {
  const r3 = getLatestRound3Run();
  if (!r3) return <div>数据未找到</div>;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 返回首页</Link>
        <h1 className="text-3xl font-bold mt-2">⚽ 12 个小组 (A-L)</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          64 场小组赛预测 · 第 2 + 第 3 比赛日 (第 1 比赛日已结束)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {listGroupLetters().map((letter) => {
          const g = r3.groups[letter];
          if (!g) return null;
          return (
            <Link
              key={letter}
              href={`/groups/${letter}`}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-5 hover:border-emerald-500 transition-colors"
            >
              <div className="flex items-baseline justify-between mb-3">
                <h2 className="text-2xl font-black">{letter} 组</h2>
                <div className="text-xs text-gray-500">
                  {g.teams.length} 队 · {g.matches.length} 场
                </div>
              </div>

              <div className="flex gap-1.5 mb-3 text-xl">
                {g.teams.map((t) => (
                  <span key={t} title={t}>
                    {teamFlag(t)}
                  </span>
                ))}
              </div>

              <div className="space-y-1 text-sm">
                {g.standings.slice(0, 4).map((s, i) => (
                  <div
                    key={s.team}
                    className={`flex items-center justify-between ${
                      i < 2 ? "font-semibold" : "text-gray-500"
                    }`}
                  >
                    <span>
                      <span className="text-xs text-gray-400 mr-1.5 w-4 inline-block">
                        {i + 1}.
                      </span>
                      {teamFlag(s.team)} {teamNameZh(s.team)}
                    </span>
                    <span className="font-mono text-xs">{s.points} 分</span>
                  </div>
                ))}
              </div>

              {g.standings[0] && (
                <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-xs text-emerald-600 dark:text-emerald-400">
                  头名: {teamNameZh(g.standings[0].team)} →
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
