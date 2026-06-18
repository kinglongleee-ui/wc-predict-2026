import clsx from "clsx";

type Props = {
  a: number;
  draw: number;
  b: number;
  aLabel: string;
  bLabel: string;
  showLabels?: boolean;
};

export function ProbabilityBar({ a, draw, b, aLabel, bLabel, showLabels = true }: Props) {
  const total = a + draw + b;
  const aPct = total > 0 ? (a / total) * 100 : 33.3;
  const dPct = total > 0 ? (draw / total) * 100 : 33.3;
  const bPct = total > 0 ? (b / total) * 100 : 33.3;
  return (
    <div className="w-full">
      {showLabels && (
        <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
          <span>{aLabel} {(a * 100).toFixed(0)}%</span>
          <span>平 {(draw * 100).toFixed(0)}%</span>
          <span>{(b * 100).toFixed(0)}% {bLabel}</span>
        </div>
      )}
      <div className="flex h-2.5 w-full rounded-full overflow-hidden bg-gray-200 dark:bg-gray-800">
        <div
          className="bg-emerald-500 transition-all"
          style={{ width: `${aPct}%` }}
          title={`${aLabel}: ${(a * 100).toFixed(0)}%`}
        />
        <div
          className="bg-gray-400 transition-all"
          style={{ width: `${dPct}%` }}
          title={`平局: ${(draw * 100).toFixed(0)}%`}
        />
        <div
          className="bg-orange-500 transition-all"
          style={{ width: `${bPct}%` }}
          title={`${bLabel}: ${(b * 100).toFixed(0)}%`}
        />
      </div>
    </div>
  );
}

type BadgeProps = {
  prob: number;
  variant?: "win" | "draw" | "loss";
};

export function ProbabilityBadge({ prob, variant = "win" }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold",
        variant === "win" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
        variant === "draw" && "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        variant === "loss" && "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
      )}
    >
      {(prob * 100).toFixed(0)}%
    </span>
  );
}
