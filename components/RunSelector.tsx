"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState, useEffect } from "react";

type RunOpt = {
  run_id: string;
  label: string;
  date: string;
  champion_zh: string;
};

export function RunSelector({ runs, currentRunId }: { runs: RunOpt[]; currentRunId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [open]);

  // Default to latest R12 if no current
  const current = runs.find((r) => r.run_id === currentRunId) || runs[0];

  const handleSelect = (run_id: string) => {
    setOpen(false);
    if (!run_id) return;
    // Navigate to /report/<run_id> for detail view
    router.push(`/report/${run_id}`);
  };

  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setOpen(!open)}
        className="px-3 py-1.5 text-sm font-bold rounded-lg bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-900/60 flex items-center gap-1"
      >
        📊 {current?.label || "选择 Run"}
        <span className="text-xs opacity-70">▼</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 max-h-96 overflow-y-auto bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-lg shadow-lg z-50">
          <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-100 dark:border-gray-900">
            {runs.length} 个模拟 run (按时间倒序)
          </div>
          {runs.map((r) => (
            <button
              key={r.run_id}
              onClick={() => handleSelect(r.run_id)}
              className={`w-full text-left px-3 py-2 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 flex items-center justify-between ${
                r.run_id === currentRunId ? "bg-emerald-50 dark:bg-emerald-950/20" : ""
              }`}
            >
              <div>
                <div className="font-bold text-sm">{r.label}</div>
                <div className="text-xs text-gray-500 font-mono">{r.run_id.slice(0, 8)}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-gray-600 dark:text-gray-400">{r.date}</div>
                <div className="text-xs text-emerald-600 dark:text-emerald-400">{r.champion_zh}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
