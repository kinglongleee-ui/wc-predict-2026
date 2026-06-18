import { ProbabilityBar } from "./ProbabilityBar";
import { teamFlag, teamNameZh, stageZh, predictOutcome } from "@/lib/data";
import type { Match } from "@/lib/types";
import type { RealMatch } from "@/lib/data";

type Props = {
  match: Match;
  played?: RealMatch | null;
};

export function MatchRow({ match, played }: Props) {
  const score = match.most_likely_score;

  // 是否 MiroFish 预测对了胜平负?
  const predict = predictOutcome({
    team_a_win: match.team_a_win,
    draw: match.draw,
    team_b_win: match.team_b_win,
  });
  const realOut = played ? (
    played.score_a > played.score_b ? "a" : played.score_a < played.score_b ? "b" : "draw"
  ) : null;
  const hit = played && predict === realOut;

  // 边框 + 背景: 命中→emerald 绿, 未中→orange 橙, 未赛→gray
  const ringClass = played
    ? hit
      ? "border-emerald-500/70 bg-emerald-50/50 dark:bg-emerald-950/15"
      : "border-orange-500/70 bg-orange-50/50 dark:bg-orange-950/15"
    : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950";

  return (
    <div className={`border rounded-lg p-4 ${ringClass}`}>
      <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="text-xs uppercase tracking-wide text-gray-500">
            {stageZh(match.stage)} · 比赛日 {match.matchday}
          </div>
          {played && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                hit
                  ? "bg-emerald-200 text-emerald-900 dark:bg-emerald-800 dark:text-emerald-100"
                  : "bg-orange-200 text-orange-900 dark:bg-orange-800 dark:text-orange-100"
              }`}
              title={`MiroFish 预测: ${predict === "draw" ? "平" : predict === "a" ? teamNameZh(match.team_a) + " 胜" : teamNameZh(match.team_b) + " 胜"}`}
            >
              {hit ? "✓ 已比赛 · 预测命中" : "✗ 已比赛 · 预测未中"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {score.raw && (
            <div className="text-sm font-mono font-semibold px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
              最可能比分: {teamFlag(match.team_a)} {score.home}-{score.away} {teamFlag(match.team_b)}
              {score.aet && <span className="text-orange-600 dark:text-orange-400 ml-1">加时</span>}
              {score.pens && <span className="text-purple-600 dark:text-purple-400 ml-1">点球</span>}
            </div>
          )}
          {played && (
            <div
              className={`text-sm font-mono font-bold px-2 py-0.5 rounded ${
                hit
                  ? "bg-emerald-600 text-white"
                  : "bg-orange-600 text-white"
              }`}
              title={`Wikipedia 用户编辑 · ${played.source_wiki_page} · 非 FIFA 官方`}
            >
              真实: {played.score_a}-{played.score_b}
            </div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 mb-3">
        <div className="text-right font-semibold">
          {teamFlag(match.team_a)} {teamNameZh(match.team_a)}
        </div>
        <div className="text-gray-400 text-sm">对</div>
        <div className="text-left font-semibold">
          {teamNameZh(match.team_b)} {teamFlag(match.team_b)}
        </div>
      </div>
      <ProbabilityBar
        a={match.team_a_win}
        draw={match.draw}
        b={match.team_b_win}
        aLabel={teamNameZh(match.team_a)}
        bLabel={teamNameZh(match.team_b)}
      />
    </div>
  );
}