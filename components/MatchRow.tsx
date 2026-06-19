import Link from "next/link";
import { ProbabilityBar } from "./ProbabilityBar";
import { teamFlag, teamNameZh, stageZh, predictOutcome } from "@/lib/data";
import { matchHref } from "@/lib/matchUrl";
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
              {hit ? "✓ 已比赛 · 胜方预测命中" : "✗ 已比赛 · 胜方预测未中"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {match.top_3_scores && match.top_3_scores.length > 0 ? (
            <div className="flex items-center gap-1 text-xs">
              <span className="text-[10px] uppercase tracking-wider text-gray-500 mr-1">Top 3 比分</span>
              {match.top_3_scores.map((s, i) => {
                const playedHit =
                  played && s.home === played.score_a && s.away === played.score_b;
                return (
                  <div
                    key={i}
                    className={`px-1.5 py-0.5 rounded font-mono font-semibold ${
                      playedHit
                        ? "bg-emerald-600 text-white ring-1 ring-emerald-300"
                        : i === 0
                          ? "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                          : "bg-gray-50 dark:bg-gray-900 text-gray-600 dark:text-gray-400"
                    }`}
                    title={`${i === 0 ? "最可能" : `第 ${i + 1} 可能`} · 概率 ${(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(1)}%${
                      playedHit ? " · ✓ 命中真实比分!" : ""
                    }`}
                  >
                    {s.home}-{s.away}{" "}
                    <span className="text-[10px] opacity-70">
                      {(s.pct ?? Math.round(s.prob * 1000) / 10).toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          ) : score.raw ? (
            <div className="text-sm font-mono font-semibold px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
              最可能比分: {teamFlag(match.team_a)} {score.home}-{score.away} {teamFlag(match.team_b)}
              {score.aet && <span className="text-orange-600 dark:text-orange-400 ml-1">加时</span>}
              {score.pens && <span className="text-purple-600 dark:text-purple-400 ml-1">点球</span>}
            </div>
          ) : null}
          {played && (
            <div
              className={`text-sm font-mono font-bold px-2 py-0.5 rounded ${
                hit
                  ? "bg-emerald-600 text-white"
                  : "bg-orange-600 text-white"
              }`}
              title={`ESPN 公开赛事 API · ${played.source_wiki_page} · 非 FIFA 官方`}
            >
              真实: {played.score_a}-{played.score_b}
            </div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 mb-3">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className="text-right font-semibold hover:underline cursor-pointer"
        >
          {teamFlag(match.team_a)} {teamNameZh(match.team_a)}
        </Link>
        <div className="text-gray-400 text-sm">对</div>
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className="text-left font-semibold hover:underline cursor-pointer"
        >
          {teamNameZh(match.team_b)} {teamFlag(match.team_b)}
        </Link>
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