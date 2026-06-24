import Link from "next/link";
import { getLatestRound3Run, teamFlag, teamNameZh, teamSeedLabel, tierLabelZh } from "@/lib/data";
import { matchHref } from "@/lib/matchUrl";
import type { BracketMatch, RunData } from "@/lib/types";

// 首页用的缩水版对阵树:
//  - 不画 R32 16 场细节 (太宽)
//  - 只画 R32 → R16 → QF → SF → Final 的"最可能路径"汇聚图
//  - R32 列压缩成 8 行 (上下半区各 4 场合并, 显示该区最可能的晋级者)
//  - 整体宽度 ~880px, 适配桌面/平板首页不溢出
//
// 跟 /bracket 的区别:
//  - /bracket: 全 16 场 R32 完整细节, 大屏横向滚动
//  - 这里: 8 行"区域冠军"聚合显示, 让首页一眼看全路径

const COL_W = 180;       // 每列宽
const COL_GAP = 32;      // 列间隙 (给连线留呼吸)
const ROW_H = 72;        // 行高 (CARD_H=66, 留 6px 间隙)
const CARD_W = 180;      // 跟 /bracket (200) 接近, 留 20px 给概率%
const CARD_H = 66;       // 紧凑卡 (两行 22px + footer 18px + padding)
const FINAL_COL_W = 200; // 决赛列加宽给冠军徽章

const ROUND_LABELS = ["32 强 (上半区)", "32 强 (下半区)", "16 强", "1/4 决赛", "半决赛", "决赛"];

export function BracketMini() {
  const r3 = getLatestRound3Run();
  if (!r3 || !r3.bracket || r3.bracket.r32.length === 0) return null;

  const bracket = r3.bracket;

  // 把 R32 拆成上半区 (8 场) 和下半区 (8 场)
  // MiroFish bracket.r32 顺序: 上半区 8 场 + 下半区 8 场
  const r32Top = bracket.r32.slice(0, 8);
  const r32Bot = bracket.r32.slice(8, 16);

  // 每个半区推一个"区域冠军" = 该半区 R16 胜者里最可能晋级到 QF 的队
  // 上半区 R16 → QF[0], 下半区 R16 → QF[2] (因为 QF 是 4 场, 上半区进 QF[0]/[1], 下半区进 QF[2]/[3])
  function pickAdvancer(matches: BracketMatch[]): { name: string; prob: number } | null {
    if (!matches.length) return null;
    // 用 R16 列里的胜方 (winner 字段) 作为区域冠军; 没有 winner 就取概率高的队
    const winners = matches.filter((m) => m.winner);
    if (winners.length > 0) {
      // 选 R16 中概率最高的胜方作为代表
      const best = winners.reduce((a, b) =>
        Math.max(a.team_a_win, a.team_b_win) > Math.max(b.team_a_win, b.team_b_win) ? a : b
      );
      const w = best.winner === "a" ? best.team_a : best.team_b;
      const p = best.winner === "a" ? best.team_a_win : best.team_b_win;
      return { name: w, prob: p };
    }
    return null;
  }
  const topAdvancer = pickAdvancer(bracket.r16.slice(0, 4));
  const botAdvancer = pickAdvancer(bracket.r16.slice(4, 8));

  // R16: 用 MiroFish 8 场, 每场胜方连线到 QF
  // QF: 4 场胜方连线到 SF
  // SF: 2 场胜方连线到 Final
  // Final: 从 r3.final.matchup 拿

  const finalMatchup = r3.final.matchup?.split(/\s+vs\s+|\s+v\s+/i) || [];
  const finalA = finalMatchup[0]?.trim() || "—";
  const finalB = finalMatchup[1]?.trim() || "—";

  const totalCols = 6; // 上半R32, 下半R32, R16, QF, SF, Final
  const totalW = totalCols * COL_W + (totalCols - 1) * COL_GAP + 40;
  const totalH = 8 * ROW_H + 60; // R32 上半 8 行 (高度跟单卡 8 行一致)

  // 第 col 列的 k 行 Y 中心 (col 0 和 col 1 是 R32 两个半区, 简单按行号)
  function rowY(colIdx: number, k: number): number {
    return 30 + k * ROW_H + CARD_H / 2;
  }

  // R16 (col 2) 的 k 场 (k=0..7) Y = R32 上半区 (k=0..3) 中点 / R32 下半区 (k=4..7) 中点
  function r16Y(k: number): number {
    if (k < 4) {
      // 上半区: 来自 R32 上半区第 2k / 2k+1 场
      return (rowY(0, 2 * k) + rowY(0, 2 * k + 1)) / 2;
    } else {
      // 下半区
      return (rowY(1, 2 * (k - 4)) + rowY(1, 2 * (k - 4) + 1)) / 2;
    }
  }

  // QF (col 3) k=0..3: 第 2k / 2k+1 场 R16 的中点
  function qfY(k: number): number {
    return (r16Y(2 * k) + r16Y(2 * k + 1)) / 2;
  }

  // SF (col 4) k=0,1: QF 中点
  function sfY(k: number): number {
    return (qfY(2 * k) + qfY(2 * k + 1)) / 2;
  }

  // Final (col 5) Y = SF 两场中点
  const finalY = (sfY(0) + sfY(1)) / 2;

  function colX(colIdx: number): number {
    return 20 + colIdx * (COL_W + COL_GAP);
  }

  // 连线
  const lines: { x1: number; y1: number; x2: number; y2: number; key: string; dashed?: boolean }[] = [];

  // R32 上半 (col 0) → R16 (col 2)
  for (let k = 0; k < 4; k++) {
    const topY = rowY(0, 2 * k);
    const botY = rowY(0, 2 * k + 1);
    const midY = (topY + botY) / 2;
    const x = colX(0) + CARD_W;
    const childX = colX(2);
    lines.push({ x1: x, y1: topY, x2: x + 8, y2: topY, key: `top-t-${k}` });
    lines.push({ x1: x + 8, y1: topY, x2: x + 8, y2: botY, key: `vbar-t-${k}` });
    lines.push({ x1: x + 8, y1: botY, x2: x, y2: botY, key: `bot-t-${k}` });
    lines.push({ x1: childX, y1: midY, x2: x + 8, y2: midY, key: `hchild-t-${k}` });
  }

  // R32 下半 (col 1) → R16 (col 2)
  for (let k = 0; k < 4; k++) {
    const topY = rowY(1, 2 * k);
    const botY = rowY(1, 2 * k + 1);
    const midY = (topY + botY) / 2;
    const x = colX(1) + CARD_W;
    const childX = colX(2);
    lines.push({ x1: x, y1: topY, x2: x + 8, y2: topY, key: `top-b-${k}` });
    lines.push({ x1: x + 8, y1: topY, x2: x + 8, y2: botY, key: `vbar-b-${k}` });
    lines.push({ x1: x + 8, y1: botY, x2: x, y2: botY, key: `bot-b-${k}` });
    lines.push({ x1: childX, y1: midY, x2: x + 8, y2: midY, key: `hchild-b-${k}` });
  }

  // R16 (col 2) → QF (col 3)
  for (let k = 0; k < 4; k++) {
    const topY = r16Y(2 * k);
    const botY = r16Y(2 * k + 1);
    const midY = (topY + botY) / 2;
    const x = colX(2) + CARD_W;
    const childX = colX(3);
    lines.push({ x1: x, y1: topY, x2: x + 8, y2: topY, key: `r16-top-${k}` });
    lines.push({ x1: x + 8, y1: topY, x2: x + 8, y2: botY, key: `r16-vbar-${k}` });
    lines.push({ x1: x + 8, y1: botY, x2: x, y2: botY, key: `r16-bot-${k}` });
    lines.push({ x1: childX, y1: midY, x2: x + 8, y2: midY, key: `r16-hchild-${k}` });
  }

  // QF (col 3) → SF (col 4)
  for (let k = 0; k < 2; k++) {
    const topY = qfY(2 * k);
    const botY = qfY(2 * k + 1);
    const midY = (topY + botY) / 2;
    const x = colX(3) + CARD_W;
    const childX = colX(4);
    lines.push({ x1: x, y1: topY, x2: x + 8, y2: topY, key: `qf-top-${k}` });
    lines.push({ x1: x + 8, y1: topY, x2: x + 8, y2: botY, key: `qf-vbar-${k}` });
    lines.push({ x1: x + 8, y1: botY, x2: x, y2: botY, key: `qf-bot-${k}` });
    lines.push({ x1: childX, y1: midY, x2: x + 8, y2: midY, key: `qf-hchild-${k}` });
  }

  // SF (col 4) → Final (col 5)
  {
    const topY = sfY(0);
    const botY = sfY(1);
    const x = colX(4) + CARD_W;
    const childX = colX(5);
    lines.push({ x1: x, y1: topY, x2: x + 8, y2: topY, key: `sf-top` });
    lines.push({ x1: x + 8, y1: topY, x2: x + 8, y2: botY, key: `sf-vbar` });
    lines.push({ x1: x + 8, y1: botY, x2: x, y2: botY, key: `sf-bot` });
    lines.push({ x1: childX, y1: finalY, x2: x + 8, y2: finalY, key: `sf-hfinal` });
  }

  const championName = r3.final.champion || finalA;
  const championConf = r3.final.confidence || 0.22;

  return (
    <section className="rounded-2xl border border-pink-200 dark:border-pink-900/40 bg-gradient-to-br from-pink-50/40 via-white to-yellow-50/40 dark:from-pink-950/15 dark:via-black dark:to-yellow-950/10 p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-1">
            🌳 MiroFish 淘汰赛路径
          </div>
          <h2 className="text-xl font-bold">32 强 → 16 强 → 1/4 → 半决赛 → 决赛</h2>
        </div>
        <Link
          href="/bracket"
          className="text-xs px-3 py-1.5 rounded-full bg-pink-100 dark:bg-pink-900/40 text-pink-700 dark:text-pink-300 hover:bg-pink-200"
        >
          查看完整对阵 →
        </Link>
      </div>

      {/* 图例 */}
      <div className="flex flex-wrap gap-4 text-xs text-gray-600 dark:text-gray-400 px-1 mb-3">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-emerald-500/80" />
          胜方高亮
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 bg-gray-400" />
          父-子连线
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded border border-orange-400 bg-orange-50/50" />
          平局走加时/点球
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded border-l-4 border-l-emerald-500 border-gray-300 bg-white" />
          上半区
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded border-l-4 border-l-orange-500 border-gray-300 bg-white" />
          下半区
        </span>
        <span className="flex items-center gap-1.5">
          🔮
          MiroFish 预测比分 (跟真实比分在小组赛 PlayedVsPredicted 块对比)
        </span>
      </div>

      {/* 树状图主体 — 缩略版 */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-x-auto">
        <div className="relative mx-auto" style={{ width: totalW, height: totalH + 80 }}>
          {/* 顶部轮次标签 */}
          {ROUND_LABELS.map((label, ci) => (
            <div
              key={label}
              className="absolute top-2 text-xs font-bold uppercase tracking-wider text-gray-500 text-center"
              style={{
                left: ci === 5 ? colX(5) - 10 : colX(ci),
                width: ci === 5 ? FINAL_COL_W : CARD_W,
              }}
            >
              {label}
            </div>
          ))}

          {/* SVG 连线层 */}
          <svg
            className="absolute inset-0 pointer-events-none"
            width={totalW}
            height={totalH + 80}
          >
            {lines.map((l) => (
              <path
                key={l.key}
                d={`M ${l.x1} ${l.y1} L ${l.x2} ${l.y2}`}
                stroke="currentColor"
                className="text-gray-300 dark:text-gray-700"
                strokeWidth="1.5"
                fill="none"
              />
            ))}
          </svg>

          {/* R32 上半 (col 0) — 8 行, 每行一对 (emerald 左边条标识上半区) */}
          {r32Top.map((m, k) => {
            const h = CARD_H;
            const y = rowY(0, k) - h / 2;
            return <MiniR32Card key={`r32t-${k}`} match={m} x={colX(0)} y={y} width={CARD_W} height={h} label={`上半 #${k + 1}`} zone="top" run={r3} />;
          })}
          {/* R32 下半 (col 1) (orange 左边条标识下半区) */}
          {r32Bot.map((m, k) => {
            const h = CARD_H;
            const y = rowY(1, k) - h / 2;
            return <MiniR32Card key={`r32b-${k}`} match={m} x={colX(1)} y={y} width={CARD_W} height={h} label={`下半 #${k + 1}`} zone="bot" run={r3} />;
          })}

          {/* R16 (col 2) — 8 场 */}
          {bracket.r16.map((m, k) => {
            const h = CARD_H;
            const y = r16Y(k) - h / 2;
            return <MiniCard key={`r16-${k}`} match={m} x={colX(2)} y={y} width={CARD_W} height={h} run={r3} />;
          })}

          {/* QF (col 3) — 4 场 */}
          {bracket.qf.map((m, k) => {
            const h = CARD_H;
            const y = qfY(k) - h / 2;
            return <MiniCard key={`qf-${k}`} match={m} x={colX(3)} y={y} width={CARD_W} height={h} run={r3} />;
          })}

          {/* SF (col 4) — 2 场 */}
          {bracket.sf.map((m, k) => {
            const h = CARD_H;
            const y = sfY(k) - h / 2;
            return <MiniCard key={`sf-${k}`} match={m} x={colX(4)} y={y} width={CARD_W} height={h} run={r3} />;
          })}

          {/* Final (col 5) — 单卡 + 冠军徽章 + 预测比分 + 三档概率 */}
          <MiniFinalCard
            x={colX(5) - 10}
            y={finalY - 85}
            width={FINAL_COL_W}
            teamA={finalA}
            teamB={finalB}
            score={
              // 1. 优先从 combined_text 抽 "X-Y (AET, X-Y pens)" 格式
              (r3.final.combined_text?.match(/\d+[-–]\d+(?:\s*\(AET[^)]*(?:\d+[-–]\d+\s*pens)?\))?/)?.[0]) ||
              r3.final.tiers?.find((t) => t.tier === 1)?.label ||
              "决赛"
            }
            champion={championName}
            confidence={championConf}
            tiers={r3.final.tiers}
          />
        </div>
      </div>

      {/* 半区冠军概要 — 把 R32 → SF 的胜方路径用一行文字串起来 */}
      <div className="mt-4 grid md:grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/40 dark:bg-emerald-950/20 p-3">
          <div className="text-[10px] uppercase tracking-wider text-emerald-700 dark:text-emerald-400 font-bold mb-1">
            🟢 上半区路径
          </div>
          {topAdvancer ? (
            <div>
              <span className="font-semibold">{teamFlag(topAdvancer.name)} {teamNameZh(topAdvancer.name)}</span>
              {" "}最可能杀出上半区 ({Math.round(topAdvancer.prob * 100)}% 晋级到 1/4)
            </div>
          ) : (
            <div className="text-gray-500">上半区路径待 R16 数据</div>
          )}
        </div>
        <div className="rounded-lg border border-orange-200 dark:border-orange-900/40 bg-orange-50/40 dark:bg-orange-950/20 p-3">
          <div className="text-[10px] uppercase tracking-wider text-orange-700 dark:text-orange-400 font-bold mb-1">
            🟠 下半区路径
          </div>
          {botAdvancer ? (
            <div>
              <span className="font-semibold">{teamFlag(botAdvancer.name)} {teamNameZh(botAdvancer.name)}</span>
              {" "}最可能杀出下半区 ({Math.round(botAdvancer.prob * 100)}% 晋级到 1/4)
            </div>
          ) : (
            <div className="text-gray-500">下半区路径待 R16 数据</div>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-500 mt-3">
        缩水版: 上半区 16 队 + 下半区 16 队 R32 → 16 强 → 1/4 → 半决赛 → 决赛的胜方汇聚路径 ·
        每张卡片底部 <span className="font-mono">🔮 预测 X-Y</span> 是 MiroFish 最可能比分
        (跟小组赛"已比赛 vs 预测"块的"真实比分"不同) ·
        点击右上角"查看完整对阵"进 /bracket 看 R32 全部 16 场细节
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// 预测比分显示 — 三档: 1) match.score 有 → "X-Y"  2) 无 score → 用胜方 + 概率% 推
// ---------------------------------------------------------------------------
function predictionLabel(match: BracketMatch): string {
  // 1) 直接拿 MiroFish 给的最可能比分
  if (match.score && String(match.score).trim() !== "") return String(match.score);
  // 2) fallback: 胜方队名 + 置信度
  if (match.winner === "a") {
    return `${teamNameZh(match.team_a)} 胜 ${Math.round(match.team_a_win * 100)}%`;
  }
  if (match.winner === "b") {
    return `${teamNameZh(match.team_b)} 胜 ${Math.round(match.team_b_win * 100)}%`;
  }
  // 3) 平局/未决 — 显示最高概率方 + 置信度
  if (match.team_a_win >= match.team_b_win) {
    return `${teamNameZh(match.team_a)} ${Math.round(match.team_a_win * 100)}%`;
  }
  return `${teamNameZh(match.team_b)} ${Math.round(match.team_b_win * 100)}%`;
}

// ---------------------------------------------------------------------------
// MiniR32Card — R32 紧凑卡 (上半/下半区单场)
// ---------------------------------------------------------------------------
function MiniR32Card({
  match,
  x,
  y,
  width,
  height,
  label,
  showProb = true,
  zone,
  run,
}: {
  match: BracketMatch;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  showProb?: boolean;
  zone?: "top" | "bot"; // 上半/下半区 — 给卡左边条颜色
  run: RunData;
}) {
  const aWins = match.winner === "a";
  const bWins = match.winner === "b";
  const isDraw = match.winner === null;

  const accentBar =
    zone === "top"
      ? "border-l-4 border-l-emerald-500"
      : zone === "bot"
      ? "border-l-4 border-l-orange-500"
      : "";

  // 组别种子 (优先 match 自带, 兜底反查 standings)
  const seedA = match.group_a && match.seed_a != null
    ? `${match.group_a}${match.seed_a}`
    : teamSeedLabel(run, match.team_a);
  const seedB = match.group_b && match.seed_b != null
    ? `${match.group_b}${match.seed_b}`
    : teamSeedLabel(run, match.team_b);

  return (
    <div
      className={`absolute rounded border ${accentBar} ${
        isDraw
          ? "border-orange-300 dark:border-orange-700 bg-orange-50/40 dark:bg-orange-950/20"
          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950"
      }`}
      style={{ left: x, top: y, width, height }}
    >
      {/* 区域编号 */}
      <div className="absolute -top-2 left-1 px-1 text-[8px] font-mono text-gray-400 bg-white dark:bg-gray-950">
        {label}
      </div>
      <div className="flex items-center justify-between px-2 h-[22px]">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`text-xs truncate hover:underline cursor-pointer flex items-center gap-0.5 ${
            aWins ? "font-bold text-emerald-700 dark:text-emerald-400" : bWins ? "text-gray-400" : ""
          }`}
        >
          <span className="truncate">{teamFlag(match.team_a)} {teamNameZh(match.team_a)}</span>
          {seedA && <span className="text-[8px] font-mono text-gray-400 shrink-0">[{seedA}]</span>}
        </Link>
        {showProb && (
          <span
            className={`text-[10px] font-mono shrink-0 ml-1 ${
              aWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
            }`}
          >
            {Math.round(match.team_a_win * 100)}%
          </span>
        )}
      </div>
      <div className="flex items-center justify-between px-2 h-[22px] border-t border-gray-100 dark:border-gray-800">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`text-xs truncate hover:underline cursor-pointer flex items-center gap-0.5 ${
            bWins ? "font-bold text-emerald-700 dark:text-emerald-400" : aWins ? "text-gray-400" : ""
          }`}
        >
          <span className="truncate">{teamFlag(match.team_b)} {teamNameZh(match.team_b)}</span>
          {seedB && <span className="text-[8px] font-mono text-gray-400 shrink-0">[{seedB}]</span>}
        </Link>
        {showProb && (
          <span
            className={`text-[10px] font-mono shrink-0 ml-1 ${
              bWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
            }`}
          >
            {Math.round(match.team_b_win * 100)}%
          </span>
        )}
      </div>
      {/* 预测比分 footer — 用 predictionLabel fallback */}
      <div className="px-2 h-[18px] flex items-center justify-end text-[11px] font-mono bg-emerald-50/80 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border-t border-emerald-200 dark:border-emerald-900/50 rounded-b whitespace-nowrap">
        🔮 {predictionLabel(match)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MiniCard — R16 / QF / SF 紧凑卡 (一行两队 + 概率 + 预测比分)
// ---------------------------------------------------------------------------
function MiniCard({
  match,
  x,
  y,
  width,
  height,
  run,
}: {
  match: BracketMatch;
  x: number;
  y: number;
  width: number;
  height: number;
  run: RunData;
}) {
  const aWins = match.winner === "a";
  const bWins = match.winner === "b";
  const isDraw = match.winner === null;

  // 角标: 加时 (AET) 或 点球 (PSO) — 用 aet_pct / pen_pct 数值大小判断
  let overtimeTag: string | null = null;
  if (match.aet_pct != null && match.aet_pct >= 0.15) overtimeTag = `加时${Math.round(match.aet_pct * 100)}%`;
  else if (match.pen_pct != null && match.pen_pct >= 0.08) overtimeTag = `点球${Math.round(match.pen_pct * 100)}%`;

  // 组别种子 (R16+ 通常没有, 兜底反查 standings)
  const seedA = match.group_a && match.seed_a != null
    ? `${match.group_a}${match.seed_a}`
    : teamSeedLabel(run, match.team_a);
  const seedB = match.group_b && match.seed_b != null
    ? `${match.group_b}${match.seed_b}`
    : teamSeedLabel(run, match.team_b);

  return (
    <div
      className={`absolute rounded-md border ${
        isDraw
          ? "border-orange-300 dark:border-orange-700 bg-orange-50/40 dark:bg-orange-950/20"
          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950"
      }`}
      style={{ left: x, top: y, width, height }}
    >
      <div className="flex items-center justify-between px-2 h-[22px]">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`text-xs truncate hover:underline cursor-pointer flex items-center gap-0.5 ${
            aWins ? "font-bold text-emerald-700 dark:text-emerald-400" : bWins ? "text-gray-400" : ""
          }`}
        >
          <span className="truncate">{teamFlag(match.team_a)} {teamNameZh(match.team_a)}</span>
          {seedA && <span className="text-[8px] font-mono text-gray-400 shrink-0">[{seedA}]</span>}
        </Link>
        <span
          className={`text-[10px] font-mono shrink-0 ml-1 ${
            aWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
          }`}
        >
          {Math.round(match.team_a_win * 100)}%
        </span>
      </div>
      <div className="flex items-center justify-between px-2 h-[22px] border-t border-gray-100 dark:border-gray-800">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`text-xs truncate hover:underline cursor-pointer flex items-center gap-0.5 ${
            bWins ? "font-bold text-emerald-700 dark:text-emerald-400" : aWins ? "text-gray-400" : ""
          }`}
        >
          <span className="truncate">{teamFlag(match.team_b)} {teamNameZh(match.team_b)}</span>
          {seedB && <span className="text-[8px] font-mono text-gray-400 shrink-0">[{seedB}]</span>}
        </Link>
        <span
          className={`text-[10px] font-mono shrink-0 ml-1 ${
            bWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
          }`}
        >
          {Math.round(match.team_b_win * 100)}%
        </span>
      </div>
      {/* 预测比分 footer — 改 relative 避免被 overflow-x 裁掉 */}
      <div className="px-2 h-[18px] flex items-center justify-end text-[11px] font-mono bg-emerald-50/80 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border-t border-emerald-200 dark:border-emerald-900/50 rounded-b flex items-center gap-1 whitespace-nowrap">
        <span>🔮 {predictionLabel(match)}</span>
        {overtimeTag && (
          <span className="text-orange-600 dark:text-orange-400">{overtimeTag}</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MiniFinalCard — 决赛卡 + 冠军 + 预测比分 + 三档概率
// ---------------------------------------------------------------------------
function MiniFinalCard({
  x,
  y,
  width,
  teamA,
  teamB,
  score,
  champion,
  confidence,
  tiers,
}: {
  x: number;
  y: number;
  width: number;
  teamA: string;
  teamB: string;
  score: string;
  champion: string;
  confidence: number;
  tiers?: { tier: number; label: string; probability: number | null; content: string }[];
}) {
  return (
    <div
      className="absolute rounded-xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-50 via-white to-yellow-50 dark:from-emerald-950/30 dark:via-black dark:to-yellow-950/20 shadow-md"
      style={{ left: x, top: y, width, height: 155 }}
    >
      <div className="px-2 py-1 text-[10px] uppercase tracking-widest text-emerald-700 dark:text-emerald-400 font-bold border-b border-emerald-500/30">
        🏆 决赛
      </div>
      <div className="flex items-center justify-between px-2 py-1">
        <Link
          href={matchHref(teamA, teamB)}
          className="flex items-center gap-1 text-sm font-bold hover:underline cursor-pointer"
        >
          <span className="text-base leading-none">{teamFlag(teamA)}</span>
          <span>{teamNameZh(teamA)}</span>
        </Link>
      </div>
      <div className="flex items-center justify-between px-2 py-1 border-t border-gray-100 dark:border-gray-800">
        <Link
          href={matchHref(teamA, teamB)}
          className="flex items-center gap-1 text-sm hover:underline cursor-pointer"
        >
          <span className="text-base leading-none">{teamFlag(teamB)}</span>
          <span>{teamNameZh(teamB)}</span>
        </Link>
      </div>
      {/* 预测比分 footer — inline, 不被 overflow-x 裁 */}
      <div className="mx-2 mt-1 px-1.5 h-[18px] flex items-center justify-center text-[11px] font-mono bg-emerald-50/80 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-900/50 rounded whitespace-nowrap">
        🔮 {score}
      </div>
      {/* 三档比分概率 — 在冠军徽章之上挤一行 */}
      {tiers && tiers.length > 0 && (
        <div className="px-2 pt-1 flex flex-wrap gap-1 text-[9px] font-mono text-gray-600 dark:text-gray-400">
          {tiers.map((t) => (
            <span
              key={t.tier}
              className={`px-1 rounded ${
                t.tier === 1
                  ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                  : t.tier === 2
                  ? "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300"
                  : "bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300"
              }`}
              title={t.content}
            >
              {tierLabelZh(t.label)} {t.probability !== null ? `${Math.round(t.probability * 100)}%` : "—"}
            </span>
          ))}
        </div>
      )}
      <div className="px-2 py-1.5 flex flex-col items-center gap-0.5 bg-yellow-100/50 dark:bg-yellow-900/20 rounded-b-lg">
        <span className="text-[9px] text-gray-600 dark:text-gray-400 uppercase tracking-wider">冠军</span>
        <Link
          href={matchHref(teamA, teamB)}
          className="text-sm font-black bg-gradient-to-r from-emerald-600 to-yellow-600 bg-clip-text text-transparent hover:underline cursor-pointer"
        >
          {teamFlag(champion)} {teamNameZh(champion)} {Math.round(confidence * 100)}%
        </Link>
      </div>
    </div>
  );
}