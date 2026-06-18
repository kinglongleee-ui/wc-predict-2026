import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { loadRun } from "@/lib/data";

type Props = { params: { id: string } };

export default function ReportPage({ params }: Props) {
  const run = loadRun(params.id);
  if (!run) notFound();

  return (
    <div className="space-y-4">
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 返回首页</Link>
        <h1 className="text-3xl font-bold mt-2">📄 完整报告</h1>
        <div className="flex flex-wrap gap-2 mt-2 text-xs">
          <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 font-mono">
            {run.run_id}
          </span>
          <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800">
            第 {run.round ?? 3} 轮
          </span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-mono">
            置信度 {((run.verdict.confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <article className="prose dark:prose-invert max-w-none rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {run.report_markdown}
        </ReactMarkdown>
      </article>
    </div>
  );
}
