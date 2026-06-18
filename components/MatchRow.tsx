import { ProbabilityBar } from "./ProbabilityBar";
import { teamFlag } from "@/lib/data";
import type { Match } from "@/lib/types";

type Props = { match: Match };

export function MatchRow({ match }: Props) {
  const score = match.most_likely_score;
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-4 bg-white dark:bg-gray-950">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-wide text-gray-500">
          {match.stage} · MD{match.matchday}
        </div>
        {score.raw && (
          <div className="text-sm font-mono font-semibold px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
            最可能比分: {teamFlag(match.team_a)} {score.home}-{score.away} {teamFlag(match.team_b)}
            {score.aet && <span className="text-orange-600 dark:text-orange-400 ml-1">AET</span>}
            {score.pens && <span className="text-purple-600 dark:text-purple-400 ml-1">PEN</span>}
          </div>
        )}
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 mb-3">
        <div className="text-right font-semibold">
          {teamFlag(match.team_a)} {match.team_a}
        </div>
        <div className="text-gray-400 text-sm">vs</div>
        <div className="text-left font-semibold">
          {match.team_b} {teamFlag(match.team_b)}
        </div>
      </div>
      <ProbabilityBar
        a={match.team_a_win}
        draw={match.draw}
        b={match.team_b_win}
        aLabel={match.team_a}
        bLabel={match.team_b}
      />
    </div>
  );
}
