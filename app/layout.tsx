import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "2026 FIFA World Cup Prediction · MiroFish",
  description: "Multi-agent social simulation predicting the 2026 FIFA World Cup knockout bracket.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-black sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
            <Link href="/" className="text-lg font-bold tracking-tight">
              🏆 <span className="bg-gradient-to-r from-emerald-600 to-orange-500 bg-clip-text text-transparent">WC 2026 Predictor</span>
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/" className="hover:text-emerald-600">概览</Link>
              <Link href="/groups" className="hover:text-emerald-600">12 组</Link>
              <Link href="/simulations" className="hover:text-emerald-600">多轮对比</Link>
              <Link href="/report/run_b37f734df790" className="hover:text-emerald-600">完整报告</Link>
            </nav>
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
              multi-agent social simulation
            </span>
            <span>
              数据: run_b37f734df790 (Round 3) + run_a18431af48fd (Round 2) · 2026-06-18
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
