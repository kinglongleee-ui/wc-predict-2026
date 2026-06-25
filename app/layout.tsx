import type { Metadata } from "next";
import Link from "next/link";
import { getLatestRound3Run, getRound2Run, listRuns, normalizeChampion, teamNameZh } from "@/lib/data";
import { RunSelector } from "@/components/RunSelector";
import "./globals.css";

export const metadata: Metadata = {
  title: "2026 世界杯预测 · MiroFish 多智能体模拟",
  description: "MiroFish 多智能体社交模拟预测 2026 世界杯淘汰赛阶段。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Resolve latest R3 + R2 runs at build time so the header "完整报告" link
  // and footer "数据" line stay in sync with cron-driven refreshes.
  const r3 = getLatestRound3Run();
  const r2 = getRound2Run();
  const allRuns = listRuns();
  const reportHref = r3 ? `/report/${r3.run_id}` : "/report/run_b37f734df790";
  const today = new Date().toISOString().slice(0, 10);

  // 构造 run selector 选项: 按 created_at 倒序, label R12, R11, ...
  const sortedDesc = [...allRuns].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const runOptions = sortedDesc.map((r, i) => ({
    run_id: r.run_id,
    label: `R${sortedDesc.length - i}`,
    date: (r.created_at || "").slice(0, 10),
    champion_zh: teamNameZh(normalizeChampion(r.final?.champion || "")),
  }));

  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-black sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
            <Link href="/" className="text-lg font-bold tracking-tight">
              🏆 <span className="bg-gradient-to-r from-emerald-600 to-orange-500 bg-clip-text text-transparent">2026 世界杯预测站</span>
            </Link>
            <div className="flex items-center gap-3">
              <RunSelector runs={runOptions} currentRunId={r3?.run_id || ""} />
              <nav className="flex gap-3 text-sm">
                <Link href="/" className="hover:text-emerald-600">概览</Link>
                <Link href="/groups" className="hover:text-emerald-600">12 组</Link>
                <Link href="/simulations" className="hover:text-emerald-600">多轮</Link>
                <Link href={reportHref} className="hover:text-emerald-600">报告</Link>
              </nav>
            </div>
          </div>
        </header>
        <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-gray-200 dark:border-gray-800 text-xs text-gray-500 py-4 mt-8">
          <div className="max-w-6xl mx-auto px-4 flex flex-wrap items-center justify-between gap-2">
            <span>
              预测来源:{" "}
              <a href="https://github.com/666ghj/MiroFish" className="underline hover:text-emerald-600">
                MiroFish
              </a>{" "}
              多智能体社交模拟 · {allRuns.length} 个 run
            </span>
            <span>
              数据: {r3 ? `${r3.run_id} (${r3.summary?.rounds || 5} 轮)` : "待更新"} {r2 ? `+ ${r2.run_id} (R2 baseline)` : ""} · 更新于 {today}
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}

