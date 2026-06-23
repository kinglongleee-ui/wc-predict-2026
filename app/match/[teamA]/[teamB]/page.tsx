// 单场比赛多轮交叉验证详情页
// URL: /match/[teamA]/[teamB]  (teamA/teamB 是 MiroFish 原生名, URL 编码)
// 模板: 跟 chat reply 的 MEX-KOR / USA-AUS 一致
//   - 标题: flag + 中文队名 + 对 + flag + 中文队名 + stage 标签
//   - 对比表: R3 旧 / R3 新 / R4 / 校准后 (4 行)
//   - 我的预测 plain-text 块
//   - 最可能比分排名
//   - 关键判断 (从 matchLookup.notes 来)
//   - 本组其他比赛 follow-up
//   - [ctx: ~XX%] footer

import Link from "next/link";
import { teamFlag, teamNameZh } from "@/lib/data";
import { crossValidate, findRelatedMatchesInGroup, loadMeihuaForMatch } from "@/lib/matchLookup";
import { matchHref } from "@/lib/matchUrl";

type Props = { params: { teamA: string; teamB: string } };

const STAGE_LABEL: Record<string, string> = {
  group: "小组赛",
  r32: "32 强赛",
  r16: "16 强赛",
  qf: "1/4 决赛",
  sf: "半决赛",
  final: "决赛",
};

export default function MatchPage({ params }: Props) {
  const a = decodeURIComponent(params.teamA);
  const b = decodeURIComponent(params.teamB);
  const cv = crossValidate(a, b);

  if (!cv.matches.length) {
    return (
      <div className="p-8 text-center text-gray-500 space-y-3">
        <div className="text-lg">
          三轮模拟都没跑过 {teamFlag(a)} {teamNameZh(a)} 对 {teamFlag(b)} {teamNameZh(b)} 的比赛
        </div>
        <div className="text-xs">
          可能原因: 这场不在小组赛 MD2/MD3 模拟范围, 也不在淘汰赛预测路径上
        </div>
        <div className="mt-3">
          <Link href="/" className="text-emerald-600 hover:underline">← 回首页</Link>
        </div>
      </div>
    );
  }

  // 取首条 match 推断 stage/group/matchday (R3 新优先)
  const m = cv.matches[0];
  // 梅花易数 (R6): 走 stage + group + matchday 反查, 没查到返回 null
  const meihua = loadMeihuaForMatch(
    a, b,
    m.stage as "group" | "r32" | "r16" | "qf" | "sf" | "final",
    m.group, m.matchday,
  );
  const stageLabel = m.stage === "group"
    ? `${m.group} 组 · 比赛日 ${m.matchday}`
    : STAGE_LABEL[m.stage] || m.stage;
  const { a_win, draw, b_win, modal } = cv.calibrated;
  const aPct = Math.round(a_win * 100);
  const dPct = Math.round(draw * 100);
  const bPct = Math.round(b_win * 100);

  // 找分组 / 找相关赛事
  const related = m.stage === "group" ? findRelatedMatchesInGroup(a, b, 2) : null;

  // 找该队伍所属组 (用于"X 组最终预测")
  const groupLetter = m.group;

  // ctx 不确定度 = 1 - max(a_win, b_win), 最小 8%
  const ctx = Math.max(8, Math.round((1 - Math.max(a_win, b_win)) * 100));

  // helper: 拿指定 run 的 modal_score 和 概率 (如果存在)
  const findByRun = (run: "r3_old" | "r3_new" | "r4") => {
    const match = cv.matches.find((x) => x.run === run);
    if (!match) return null;
    return {
      a: Math.round(match.team_a_win * 100),
      d: Math.round(match.draw * 100),
      b: Math.round(match.team_b_win * 100),
      modal: match.modal_score,
    };
  };
  const r3o = findByRun("r3_old");
  const r3n = findByRun("r3_new");
  const r4  = findByRun("r4");

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* 回退链接 */}
      <div>
        <Link href="/" className="text-sm text-emerald-600 hover:underline">← 回首页</Link>
      </div>

      {/* 标题 */}
      <section className="rounded-2xl border border-emerald-200 dark:border-emerald-900/40 bg-gradient-to-br from-emerald-50/40 via-white to-yellow-50/40 dark:from-emerald-950/15 dark:via-black dark:to-yellow-950/10 p-6">
        <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">
          🎯 MiroFish 多轮交叉验证预测
        </div>
        <h1 className="text-3xl md:text-4xl font-black tracking-tight">
          {teamFlag(a)} {teamNameZh(a)} 对 {teamFlag(b)} {teamNameZh(b)}
        </h1>
        <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          {stageLabel} ·{" "}
          <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
            {cv.matches.length >= 4 ? `${cv.matches.length} 轮交叉验证 (含 R6)` :
             cv.matches.length === 3 ? "3 轮交叉验证" :
             cv.matches.length === 2 ? "2 轮交叉验证" :
             "⚠️ 单轮信号"}
          </span>
        </div>
      </section>

      {/* 数据局限提示 */}
      {cv.matches.length < 3 && (
        <div className="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-4 py-2.5 text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
          <span className="font-bold">⚠️ 数据局限:</span>{" "}
          {cv.notes.filter((n) => n.includes("未模拟")).join(" · ") ||
           "部分轮次没模拟到这场, 校准风险高于完整 3 轮"}
        </div>
      )}

      {/* 三源对比表 */}
      <section>
        <h2 className="text-lg font-bold mb-2">📊 三轮数据对比</h2>
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900 text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-2.5">来源</th>
                <th className="p-2.5">{teamNameZh(a)} 胜</th>
                <th className="p-2.5">平局</th>
                <th className="p-2.5">{teamNameZh(b)} 胜</th>
                <th className="p-2.5">最可能比分</th>
              </tr>
            </thead>
            <tbody>
              <Row
                label="R3 旧 (b37f734)"
                data={r3o}
                teamA={a}
                teamB={b}
              />
              <Row
                label="R3 新 (d7c8d02)"
                data={r3n}
                teamA={a}
                teamB={b}
              />
              <Row
                label="R4 (e667e173)"
                data={r4}
                teamA={a}
                teamB={b}
              />
              <tr className="bg-emerald-50 dark:bg-emerald-950/30 font-bold border-t-2 border-emerald-200 dark:border-emerald-800">
                <td className="p-2.5 text-emerald-700 dark:text-emerald-400">
                  🎯 校准后 (热门 +2pp / 平 -3pp / 冷门 +1pp)
                </td>
                <td className="p-2.5 text-center text-emerald-700 dark:text-emerald-400 text-base">
                  {aPct}%
                </td>
                <td className="p-2.5 text-center text-emerald-700 dark:text-emerald-400 text-base">
                  {dPct}%
                </td>
                <td className="p-2.5 text-center text-emerald-700 dark:text-emerald-400 text-base">
                  {bPct}%
                </td>
                <td className="p-2.5 text-center text-emerald-700 dark:text-emerald-400 text-base font-mono">
                  {modal}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 梅花易数 4 段解读 (2026-06-22) — M3 LLM 生成, 模板 fallback */}
      {meihua && (meihua.llm_narrative || meihua.template_fallback) && (
        <section className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-gradient-to-br from-amber-50/40 via-white to-yellow-50/30 dark:from-amber-950/15 dark:via-black dark:to-yellow-950/10 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-widest text-amber-700 dark:text-amber-400">
              ☯ 梅花易数 4 段解读
            </div>
            <div className="text-xs text-gray-500">
              {meihua.llm_narrative ? "M3 生成" : "模板兜底"}
            </div>
          </div>
          <pre className="font-sans text-sm leading-relaxed whitespace-pre-wrap text-gray-800 dark:text-gray-200">
{meihua.llm_narrative || meihua.template_fallback}
          </pre>
        </section>
      )}

      {/* 梅花易数 (2026-06-20) — 时间起卦 + 体用生克 + Top3 比分 */}
      {meihua && (
        <section className="rounded-2xl border border-amber-300 dark:border-amber-700 bg-gradient-to-br from-amber-50/60 via-white to-yellow-50/40 dark:from-amber-950/20 dark:via-black dark:to-yellow-950/15 p-5">
          <div className="text-xs uppercase tracking-widest text-amber-700 dark:text-amber-400 mb-3">
            ☯ 梅花易数 — 时间起卦 (2026-06-20 接入)
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {/* 卦象 + 五行 */}
            <div>
              <div className="text-2xl font-black tracking-wider mb-2">
                <span className="text-amber-700 dark:text-amber-300">{meihua.trigram_upper}</span>
                <span className="mx-2 text-gray-400">/</span>
                <span className="text-amber-700 dark:text-amber-300">{meihua.trigram_lower}</span>
                <span className="ml-2 text-sm font-mono text-gray-500">
                  动 {meihua.changing_line} 爻
                </span>
              </div>
              <div className="text-sm space-y-1">
                <div>
                  <span className="text-gray-500">体卦 (主队):</span>{" "}
                  <span className="font-bold">{teamFlag(a)} {teamNameZh(a)}</span>{" "}
                  <span className="font-mono">{meihua.host_trigram} · {meihua.host_element}</span>
                </div>
                <div>
                  <span className="text-gray-500">用卦 (客队):</span>{" "}
                  <span className="font-bold">{teamFlag(b)} {teamNameZh(b)}</span>{" "}
                  <span className="font-mono">{meihua.guest_trigram} · {meihua.guest_element}</span>
                </div>
                <div className="pt-2 border-t border-amber-200 dark:border-amber-800 mt-2">
                  <span className="text-gray-500">五行关系:</span>{" "}
                  <span className={`font-bold px-2 py-0.5 rounded text-sm ${relationColor(meihua.five_element_relation)}`}>
                    {meihua.five_element_relation}
                  </span>
                  <span className="ml-2 text-xs text-gray-600 dark:text-gray-400">
                    ({relationMeaning(meihua.five_element_relation)})
                  </span>
                </div>
              </div>
            </div>
            {/* Top 3 比分 */}
            <div>
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                🎯 Top 3 最可能比分
              </div>
              <div className="space-y-1">
                {meihua.top_3_scores?.map((s, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between rounded-md px-3 py-1.5 ${
                      i === 0
                        ? "bg-amber-100 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700"
                        : "bg-white/60 dark:bg-gray-950/40 border border-gray-200 dark:border-gray-800"
                    }`}
                  >
                    <span className="font-mono font-bold text-base">
                      <span className="text-gray-400 mr-2">#{i + 1}</span>
                      {s.home}-{s.away}
                    </span>
                    <span className="font-mono text-sm text-amber-700 dark:text-amber-300">
                      {s.pct?.toFixed(0) || (s.prob * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
              <div className="text-xs text-gray-500 mt-2">
                中心分 {meihua.base_score?.home}-{meihua.base_score?.away} ·
                动爻 {meihua.changing_line} 改变五行力量对比
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 我的预测 plain-text */}
      <section className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gradient-to-br from-gray-50 to-white dark:from-gray-950 dark:to-black p-4">
        <h2 className="text-lg font-bold mb-2">🎯 我的预测</h2>
        <pre className="font-mono text-base whitespace-pre-wrap text-gray-800 dark:text-gray-200">
{teamFlag(a)} {teamNameZh(a)}  {aPct}%  |  {modal}  |  {dPct}%  |  {teamNameZh(b)}  {bPct}%</pre>
      </section>

      {/* 最可能比分排名 */}
      {cv.ranked_scores.length > 0 && (
        <section>
          <h2 className="text-lg font-bold mb-2">🏅 最可能比分 (按出现频次)</h2>
          <div className="space-y-1.5">
            {cv.ranked_scores.slice(0, 5).map((s, i) => {
              const isCalibrated = s.score === modal;
              return (
                <div
                  key={s.score}
                  className={`flex items-center gap-3 p-2.5 rounded-lg border ${
                    isCalibrated
                      ? "border-emerald-300 dark:border-emerald-700 bg-emerald-50/50 dark:bg-emerald-950/20"
                      : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"
                  }`}
                >
                  <span className="text-lg font-black text-gray-400 w-6 text-center font-mono">
                    #{i + 1}
                  </span>
                  <span className={`font-mono text-base font-bold ${isCalibrated ? "text-emerald-700 dark:text-emerald-400" : ""}`}>
                    {s.score}
                  </span>
                  <span className="text-xs text-gray-500">
                    {s.count} 轮一致
                    {isCalibrated && <span className="ml-2 text-emerald-600">· 校准后采用</span>}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 关键判断 */}
      <section>
        <h2 className="text-lg font-bold mb-2">🔍 关键判断</h2>
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4">
          <ul className="space-y-1.5 text-sm leading-relaxed">
            {cv.notes.map((n, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-emerald-600 dark:text-emerald-400 shrink-0">•</span>
                <span>{n}</span>
              </li>
            ))}
            <li className="flex gap-2">
              <span className="text-emerald-600 dark:text-emerald-400 shrink-0">•</span>
              <span>
                校准后净胜球往 <span className="font-mono font-bold">{modal}</span> 集中
                — MiroFish {cv.matches.length} 轮里有 {cv.matches.filter((m) => m.modal_score === modal).length} 轮把模态给到 {modal}
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-600 dark:text-emerald-400 shrink-0">•</span>
              <span>
                <span className="font-mono font-bold">{aPct}% vs {bPct}%</span> —{" "}
                {aPct > bPct + 10 ? `${teamNameZh(a)} 大热, ${teamNameZh(b)} 冷门` :
                 bPct > aPct + 10 ? `${teamNameZh(b)} 大热, ${teamNameZh(a)} 冷门` :
                 "两边接近, 接近对等对决"}
              </span>
            </li>
          </ul>
        </div>
      </section>

      {/* X 组最终预测 (只有小组赛显示) */}
      {m.stage === "group" && groupLetter && (
        <section className="rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50/40 dark:bg-purple-950/20 p-4">
          <h2 className="text-lg font-bold mb-2">📋 {groupLetter} 组最终预测 (基于 R3 新)</h2>
          <ol className="space-y-1 text-sm">
            <GroupStandings groupLetter={groupLetter} />
          </ol>
        </section>
      )}

      {/* Follow-up — 相关赛事 */}
      {related && related.others.length > 0 && (
        <section className="rounded-xl border border-pink-200 dark:border-pink-900/40 bg-pink-50/30 dark:bg-pink-950/15 p-4">
          <div className="text-xs uppercase tracking-wider text-pink-700 dark:text-pink-400 font-bold mb-2">
            💡 要不要看 {related.group} 组其他比赛?
          </div>
          <ul className="space-y-1.5 text-sm">
            {related.others.map((r) => (
              <li key={r.team_a + r.team_b}>
                <Link
                  href={matchHref(r.team_a, r.team_b)}
                  className="text-emerald-700 dark:text-emerald-400 hover:underline"
                >
                  {teamFlag(r.team_a)} {teamNameZh(r.team_a)} 对 {teamFlag(r.team_b)} {teamNameZh(r.team_b)}
                </Link>
                <span className="text-xs text-gray-500 ml-2 font-mono">
                  ({Math.round(r.team_a_win * 100)}/{Math.round(r.draw * 100)}/{Math.round(r.team_b_win * 100)} → {r.most_likely_score.raw})
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ctx footer */}
      <p className="text-xs text-gray-400 text-right">
        [ctx: ~{ctx}%]
      </p>
    </div>
  );
}

// 梅花易数五行关系 → 颜色 + 解读
function relationColor(rel: string): string {
  switch (rel) {
    case "体生用": return "bg-yellow-200 dark:bg-yellow-900/50 text-yellow-900 dark:text-yellow-200"; // 主队耗损
    case "用生体": return "bg-emerald-200 dark:bg-emerald-900/50 text-emerald-900 dark:text-emerald-200"; // 主队得利
    case "体克用": return "bg-emerald-200 dark:bg-emerald-900/50 text-emerald-900 dark:text-emerald-200"; // 主队胜
    case "用克体": return "bg-rose-200 dark:bg-rose-900/50 text-rose-900 dark:text-rose-200"; // 主队凶
    case "比和":   return "bg-sky-200 dark:bg-sky-900/50 text-sky-900 dark:text-sky-200"; // 平局倾向
    default:       return "bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300";
  }
}
function relationMeaning(rel: string): string {
  switch (rel) {
    case "体生用": return "体卦生用卦, 主队耗损精力, 不利主队";
    case "用生体": return "用卦生体卦, 客队助力主队, 大利主队";
    case "体克用": return "体卦克用卦, 主队压制客队, 主胜";
    case "用克体": return "用卦克体卦, 客队克制主队, 主凶";
    case "比和":   return "体用比和, 势均力敌, 接近平局";
    default:       return "";
  }
}

// 单行渲染 (兼容"未模拟"状态)
function Row({
  label,
  data,
  teamA,
  teamB,
}: {
  label: string;
  data: { a: number; d: number; b: number; modal: string } | null;
  teamA: string;
  teamB: string;
}) {
  return (
    <tr className="border-t border-gray-100 dark:border-gray-800">
      <td className="p-2.5 text-gray-700 dark:text-gray-300">{label}</td>
      {data ? (
        <>
          <td className="p-2.5 text-center font-mono">{data.a}%</td>
          <td className="p-2.5 text-center font-mono">{data.d}%</td>
          <td className="p-2.5 text-center font-mono">{data.b}%</td>
          <td className="p-2.5 text-center font-mono font-semibold">{data.modal}</td>
        </>
      ) : (
        <td colSpan={4} className="p-2.5 text-center text-xs text-gray-400 italic">
          未模拟这场 (赛程跳过或不在这轮的预测路径)
        </td>
      )}
    </tr>
  );
}

// 显示 X 组积分榜 (R3 新为锚)
function GroupStandings({ groupLetter }: { groupLetter: string }) {
  // 用 require 避免 SSR 问题 — 实际上这是 server component, 直接 require OK
  // 但更干净的方式是从 cv 数据里查 — 简化: 直接从 loadAllRuns 拿
  const runs = require("@/lib/matchLookup").loadAllRuns() as Record<string, any>;
  const standings = runs.r3_new.groups?.[groupLetter]?.standings || [];
  if (!standings.length) {
    return <li className="text-gray-500">积分数据缺失</li>;
  }
  return (
    <>
      {standings.map((s: any, i: number) => (
        <li key={s.team} className={i < 2 ? "font-semibold text-emerald-700 dark:text-emerald-400" : ""}>
          {i + 1}. {teamFlag(s.team)} {teamNameZh(s.team)} — <span className="font-mono">{s.points} 分</span>
          {s.note && <span className="text-xs text-gray-500 ml-2">{s.note}</span>}
        </li>
      ))}
    </>
  );
}
