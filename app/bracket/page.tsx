import Link from "next/link";
import { getLatestRound3Run, teamFlag, teamNameZh, teamSeedLabel } from "@/lib/data";
import { matchHref } from "@/lib/matchUrl";
import type { BracketMatch } from "@/lib/types";

// 树状图几何参数:
//   6 列: R32 上半 / R32 下半 / R16 / QF / SF / Final
//   R32 上下半各 8 场, 平行; 后续 4 列从 R32 父子配对往中央汇聚
const COL_W = 220;        // 单列宽度
const COL_GAP = 36;       // 列间隙 (留给连线)
const ROW_H = 52;         // R32 中每行间距 (留 12px 间隙, 不重叠)
const CARD_W = 200;
const CARD_H = 40;        // R32 紧凑卡 (队名 + 概率 + seed)
const CARD_H_FULL = 60;   // R16/QF/SF 完整卡 (含比分/AET/独立模拟徽章)
const FINAL_COL_W = 240;  // 决赛列稍宽,放冠军大卡

// 6 列轮次标签 — 跟 cols 数组顺序一致
const ROUND_LABELS = ["32 强 (上半区)", "32 强 (下半区)", "16 强", "1/4 决赛", "半决赛", "决赛"];

export default function BracketPage() {
  const r3 = getLatestRound3Run();
  if (!r3) {
    return (
      <div className="p-8 text-center text-gray-500">
        数据未找到。
      </div>
    );
  }

  const bracket = r3.bracket;
  if (!bracket || bracket.r32.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        本轮报告未包含淘汰赛 bracket 数据。
      </div>
    );
  }

  // 把 R32 16 场拆成上半 (A-H 8 场) + 下半 (I-L 8 场)
  // MiroFish bracket.r32 顺序按 FIFA 半区规则: idx 0..7 上半, 8..15 下半
  const r32Top: BracketMatch[] = bracket.r32.slice(0, 8);
  const r32Bot: BracketMatch[] = bracket.r32.slice(8, 16);

  // 列与列对应: r32Top + r32Bot → r16 → qf → sf → final
  const cols: (BracketMatch & { _zone?: "top" | "bot" })[][] = [
    r32Top.map((m) => ({ ...m, _zone: "top" })),
    r32Bot.map((m) => ({ ...m, _zone: "bot" })),
    bracket.r16,
    bracket.qf,
    bracket.sf,
  ];

  // 决赛列 (硬编码 1 场)
  const finalCol: BracketMatch[] = [
    {
      team_a: r3.final.matchup?.split(/\s+vs\s+|\s+v\s+/i)[0]?.trim() || "—",
      team_b: r3.final.matchup?.split(/\s+vs\s+|\s+v\s+/i)[1]?.trim() || "—",
      team_a_win:
        r3.final.tiers?.find((t) => /argentina|阿根/i.test(r3.final.matchup || ""))?.probability ?? 0.5,
      draw: 0.3,
      team_b_win: 0.2,
      score: "1-1 (加时, 4-3 点球)",
      aet_pct: 0.26,
      pen_pct: 0.16,
      winner: "a",
    },
  ];

  // SVG 总尺寸
  // R32 两个半区每个 8 行 = 8 * ROW_H = 416px; 后续列从中点往下汇聚
  const r32TotalH = 8 * ROW_H + 60;          // 单列 R32 总高度
  const totalCols = 6;
  const totalW = totalCols * COL_W + (totalCols - 1) * COL_GAP + 40;
  const totalH = r32TotalH + 40;             // 加点 padding

  // 父-子配对: 第 ci 列的 k 场 → 第 ci+1 列的 floor(k/2) 场
  function parents(colIdx: number, childIdx: number): [number, number] {
    return [childIdx * 2, childIdx * 2 + 1];
  }

  // 第 col 列的 k 场卡片 Y 中心 (相对 SVG top)
  // R32 两个半区: 直接按行号 (col 0 上半, col 1 下半)
  // R16 (col 2): 上半 4 场 (k=0..3) 来自 R32 上半 (k=0..7) 父子配对中点;
  //              下半 4 场 (k=4..7) 来自 R32 下半 (k=0..7) 父子配对中点
  // QF / SF: 全部从上一列父子配对中点
  function cardY(colIdx: number, k: number): number {
    const col = cols[colIdx] ?? finalCol;
    if (colIdx === 0 || colIdx === 1) {
      // R32 上下半: 直接按行号
      return 30 + k * ROW_H + CARD_H / 2;
    }
    // R16 (col 2) k=0..3 → R32 上半 (col 0) 父母; k=4..7 → R32 下半 (col 1) 父母
    let parentCol: number;
    let parentIdx: number;
    if (colIdx === 2) {
      parentCol = k < 4 ? 0 : 1;
      parentIdx = (k % 4) * 2;
    } else {
      parentCol = colIdx - 1;
      parentIdx = k;
    }
    const [l, r] = parents(parentCol, parentIdx);
    const lY = cardY(parentCol, l);
    const rY = cardY(parentCol, r);
    return (lY + rY) / 2;
  }

  // R16/QF/SF 卡片实际高度 = CARD_H_FULL
  function cardHeight(colIdx: number): number {
    return colIdx === 0 || colIdx === 1 ? CARD_H : CARD_H_FULL;
  }

  function cardX(colIdx: number): number {
    if (colIdx === 5) {
      // Final 列在最右
      return 20 + 5 * (COL_W + COL_GAP) - COL_GAP - 20;
    }
    return 20 + colIdx * (COL_W + COL_GAP);
  }

  // 连线: 从 col 列 k 场的右侧 → 子列 floor(k/2) 的左侧
  // 仅在 colIdx < 5 时画; R32→R16 (col 0/1 → col 2) 是灰色虚线 (语义: MiroFish 独立模拟)
  function connectionLines() {
    const paths: { x1: number; y1: number; x2: number; y2: number; key: string; dashed?: boolean }[] = [];
    for (let ci = 0; ci < cols.length; ci++) {
      // R32 上半 (col 0) 和下半 (col 1) 都连到 R16 (col 2), 每列内部按 2 父子配对
      for (let k = 0; k < cols[ci].length; k += 2) {
        const topY = cardY(ci, k);
        const botY = cardY(ci, k + 1);
        const midY = (topY + botY) / 2;
        const x = cardX(ci) + CARD_W;
        const childX = cardX(ci + 1);
        const isR32toR16 = ci < 2;
        const isR32toR16Path = ci === 0 || ci === 1;
        paths.push({
          x1: x, y1: topY, x2: x + 8, y2: topY,
          key: `top-${ci}-${k}`,
          dashed: isR32toR16Path,
        });
        paths.push({
          x1: x + 8, y1: topY, x2: x + 8, y2: botY,
          key: `vbar-${ci}-${k}`,
          dashed: isR32toR16Path,
        });
        paths.push({
          x1: x + 8, y1: botY, x2: x, y2: botY,
          key: `bot-${ci}-${k}`,
          dashed: isR32toR16Path,
        });
        paths.push({
          x1: childX, y1: midY, x2: x + 8, y2: midY,
          key: `hchild-${ci}-${k}`,
          dashed: isR32toR16Path,
        });
      }
    }
    // SF (col 4) → Final (col 5)
    const sfTop = cardY(4, 0);
    const sfBot = cardY(4, 1);
    const finalX = cardX(5);
    const finalY = (sfTop + sfBot) / 2;
    const lastX = cardX(4) + CARD_W;
    paths.push({ x1: lastX, y1: sfTop, x2: lastX + 8, y2: sfTop, key: "sf-top" });
    paths.push({ x1: lastX + 8, y1: sfTop, x2: lastX + 8, y2: sfBot, key: "sf-vbar" });
    paths.push({ x1: lastX + 8, y1: sfBot, x2: lastX, y2: sfBot, key: "sf-bot" });
    paths.push({ x1: finalX, y1: finalY, x2: lastX + 8, y2: finalY, key: "sf-hfinal" });
    return paths;
  }

  const lines = connectionLines();

  // 找冠军 (r3.final.champion) 用于右侧大卡
  const championName = r3.final.champion || finalCol[0].team_a;

  return (
    <div className="space-y-6">
      {/* 顶部标题 */}
      <section className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gradient-to-br from-gray-50 via-white to-gray-50 dark:from-gray-950 dark:via-black dark:to-gray-950 p-6">
        <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">
          2026 世界杯 · 淘汰赛对阵树
        </div>
        <h1 className="text-3xl md:text-4xl font-black tracking-tight">
          32 强 → 16 强 → 1/4 → 半决赛 → 决赛
        </h1>
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 max-w-3xl leading-relaxed">
          树状图按 MiroFish 多智能体模拟的预测路径展开, 胜方按高亮绿显示, 平局走加时/点球以橙色边框标识。
          每张卡片显示两队国名、最可能比分和胜出概率, R32 卡片额外标注组别种子 (如 A1 / I3) 解释对阵来源。
        </p>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-500 leading-relaxed">
          <span className="font-semibold">32 强配对规则</span>: A 组 1 名 vs I 组 3 名 / B 组 1 名 vs J 组 3 名 / ... 上下半区各 8 场, 跨组碰面 — 卡片左边条颜色区分上下半区。
        </p>
        <div className="mt-3 flex flex-wrap gap-3 text-xs">
          <Link href="/" className="px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 hover:bg-gray-200">
            ← 返回首页
          </Link>
          <Link href="/groups" className="px-3 py-1.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
            ⚽ 看 12 组 →
          </Link>
          <Link href="/simulations" className="px-3 py-1.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">
            🔄 多轮漂移 →
          </Link>
        </div>
      </section>

      {/* 图例 */}
      <section className="flex flex-wrap gap-4 text-xs text-gray-600 dark:text-gray-400 px-2">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-emerald-500/80" />
          胜方高亮
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-gray-200 dark:bg-gray-700" />
          未晋级
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded border-l-4 border-l-emerald-500 border-gray-300 bg-white dark:bg-gray-950" />
          上半区 (col 0)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded border-l-4 border-l-orange-500 border-gray-300 bg-white dark:bg-gray-950" />
          下半区 (col 1)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded bg-orange-400/80" />
          平局走加时/点球
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-6 h-0.5 bg-gray-400" />
          实线: 实测延续 (col 2+)
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="24" height="6" className="text-gray-400">
            <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" />
          </svg>
          灰色虚线: MiroFish 独立模拟 (R32→R16)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="px-1 rounded text-[9px] font-mono bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">
            🔁 独立模拟
          </span>
          R16 队伍是 MiroFish 重新模拟 (非 R32 胜方延续)
        </span>
      </section>

      {/* 树状图主体 */}
      <section className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-x-auto">
        <div className="relative" style={{ width: totalW, height: totalH }}>
          {/* 顶部轮次标签 */}
          {ROUND_LABELS.map((label, ci) => (
            <div
              key={label}
              className="absolute top-2 text-xs font-bold uppercase tracking-wider text-gray-500 text-center"
              style={{
                left: ci === 5 ? cardX(5) : cardX(ci),
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
            height={totalH}
          >
            {lines.map((l) => (
              <path
                key={l.key}
                d={`M ${l.x1} ${l.y1} L ${l.x2} ${l.y2}`}
                stroke="currentColor"
                className={l.dashed ? "text-gray-400 dark:text-gray-600 opacity-60" : "text-gray-300 dark:text-gray-700"}
                strokeWidth={l.dashed ? "1" : "1.5"}
                strokeDasharray={l.dashed ? "4 3" : undefined}
                fill="none"
              />
            ))}
          </svg>

          {/* 卡片层 */}
          {cols.map((col, ci) =>
            col.map((m, k) => {
              const h = cardHeight(ci);
              const y = cardY(ci, k) - h / 2;
              const x = cardX(ci);
              return (
                <MatchCard
                  key={`${ci}-${k}`}
                  match={m}
                  x={x}
                  y={y}
                  compact={ci < 2}
                  height={h}
                  zone={m._zone}
                  stage={ci < 2 ? "r32" : ci === 2 ? "r16" : ci === 3 ? "qf" : "sf"}
                  run={r3}
                />
              );
            }),
          )}

          {/* 决赛大卡 + 冠军 (放在 SF 中点) */}
          <FinalChampionCard
            x={cardX(5)}
            y={(cardY(4, 0) + cardY(4, 1)) / 2 - 90}
            finalCol={finalCol}
            champion={championName}
            confidence={r3.final.confidence || 0.22}
          />
        </div>
      </section>

      {/* 3rd place 单独一行 */}
      {bracket.third_place && (
        <section className="rounded-xl border border-orange-200 dark:border-orange-900/40 bg-orange-50/30 dark:bg-orange-950/10 p-4">
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-2 font-bold">
            🥉 季军赛
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <Link
              href={matchHref(bracket.third_place.team_a, bracket.third_place.team_b)}
              className="text-lg font-bold hover:underline cursor-pointer"
            >
              {teamFlag(bracket.third_place.team_a)} {teamNameZh(bracket.third_place.team_a)}
              <span className="mx-2 text-gray-400">对</span>
              {teamFlag(bracket.third_place.team_b)} {teamNameZh(bracket.third_place.team_b)}
            </Link>
            <div className="text-2xl font-black text-orange-600 dark:text-orange-400 font-mono">
              {bracket.third_place.score}
            </div>
            {bracket.third_place.aet && (
              <span className="text-xs px-2 py-1 rounded-full bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300">
                加时赛
              </span>
            )}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            {bracket.third_place.raw}
          </div>
        </section>
      )}

      {/* 决赛三档比分 */}
      {r3.final.tiers && r3.final.tiers.length > 0 && (
        <section>
          <h2 className="text-xl font-bold mb-3">🎯 决赛 — 三档比分概率</h2>
          <div className="grid md:grid-cols-3 gap-3">
            {r3.final.tiers.map((t) => (
              <div
                key={t.tier}
                className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4"
              >
                <div className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                  第 {t.tier} 档
                </div>
                <div className="font-semibold text-base mb-2">
                  {t.label === "90 min" ? "常规 90 分钟"
                    : t.label === "AET" ? "加时赛"
                    : t.label === "Penalties" ? "点球大战"
                    : t.label}
                </div>
                <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
                  {t.probability !== null ? `${(t.probability * 100).toFixed(0)}%` : "—"}
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 leading-relaxed">
                  {t.content}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MatchCard — 单场淘汰赛卡片
// ---------------------------------------------------------------------------
function MatchCard({
  match,
  x,
  y,
  compact,
  height,
  zone,
  stage,
  run,
}: {
  match: BracketMatch;
  x: number;
  y: number;
  compact: boolean;
  height: number;
  zone?: "top" | "bot";
  stage?: "r32" | "r16" | "qf" | "sf";
  run: import("@/lib/types").RunData;
}) {
  const isDraw = match.winner === null;
  const aWins = match.winner === "a";
  const bWins = match.winner === "b";

  // R32 上下半区左边条
  const accentBar =
    zone === "top"
      ? "border-l-4 border-l-emerald-500"
      : zone === "bot"
      ? "border-l-4 border-l-orange-500"
      : "";

  // 组别种子 (R32 用 match 自带的; R16+ 兜底反查 standings)
  const seedA = match.group_a && match.seed_a != null
    ? `${match.group_a}${match.seed_a}`
    : teamSeedLabel(run, match.team_a);
  const seedB = match.group_b && match.seed_b != null
    ? `${match.group_b}${match.seed_b}`
    : teamSeedLabel(run, match.team_b);

  return (
    <div
      className={`absolute rounded-md border ${accentBar} ${
        isDraw
          ? "border-orange-300 dark:border-orange-700 bg-orange-50/40 dark:bg-orange-950/20"
          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950"
      }`}
      style={{
        left: x,
        top: y,
        width: CARD_W,
        height: height,
      }}
    >
      {/* R16 顶部 独立模拟 徽章 (语义: MiroFish 重新模拟, 非 R32 胜方延续) */}
      {stage === "r16" && (
        <div className="absolute -top-2 right-1 px-1 text-[8px] font-mono bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded shadow-sm">
          🔁 独立模拟
        </div>
      )}
      {/* Team A 行 */}
      <div className="flex items-center justify-between px-2 h-[20px]">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`flex items-center gap-1 text-sm truncate hover:underline cursor-pointer ${
            aWins ? "font-bold text-emerald-700 dark:text-emerald-400" : bWins ? "text-gray-400" : ""
          }`}
        >
          <span className="text-base leading-none">{teamFlag(match.team_a)}</span>
          <span className="truncate">{teamNameZh(match.team_a)}</span>
          {seedA && (
            <span className="text-[9px] font-mono text-gray-400 shrink-0 ml-0.5">[{seedA}]</span>
          )}
        </Link>
        <span
          className={`text-xs font-mono shrink-0 ${
            aWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
          }`}
        >
          {Math.round(match.team_a_win * 100)}%
        </span>
      </div>
      {/* Team B 行 */}
      <div className="flex items-center justify-between px-2 h-[20px] border-t border-gray-100 dark:border-gray-800">
        <Link
          href={matchHref(match.team_a, match.team_b)}
          className={`flex items-center gap-1 text-sm truncate hover:underline cursor-pointer ${
            bWins ? "font-bold text-emerald-700 dark:text-emerald-400" : aWins ? "text-gray-400" : ""
          }`}
        >
          <span className="text-base leading-none">{teamFlag(match.team_b)}</span>
          <span className="truncate">{teamNameZh(match.team_b)}</span>
          {seedB && (
            <span className="text-[9px] font-mono text-gray-400 shrink-0 ml-0.5">[{seedB}]</span>
          )}
        </Link>
        <span
          className={`text-xs font-mono shrink-0 ${
            bWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
          }`}
        >
          {Math.round(match.team_b_win * 100)}%
        </span>
      </div>
      {/* 比分 + AET/PEN 行 (compact=false 时显示) */}
      {!compact && (
        <div className="px-2 text-[10px] text-gray-500 flex justify-between items-center h-[16px] mt-0.5">
          <span className="font-mono truncate">
            {match.score}
            {isDraw && match.aet_pct ? ` · 加时 ${Math.round(match.aet_pct * 100)}%` : ""}
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FinalChampionCard — 决赛大卡 + 冠军
// ---------------------------------------------------------------------------
function FinalChampionCard({
  x,
  y,
  finalCol,
  champion,
  confidence,
}: {
  x: number;
  y: number;
  finalCol: BracketMatch[];
  champion: string;
  confidence: number;
}) {
  const m = finalCol[0];
  return (
    <div
      className="absolute rounded-xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-50 via-white to-yellow-50 dark:from-emerald-950/30 dark:via-black dark:to-yellow-950/20 shadow-lg"
      style={{
        left: x,
        top: y,
        width: FINAL_COL_W,
        height: 180,
      }}
    >
      {/* 顶部: 决赛 */}
      <div className="px-3 py-1.5 text-xs uppercase tracking-widest text-emerald-700 dark:text-emerald-400 font-bold border-b border-emerald-500/30">
        🏆 决赛
      </div>
      {/* Team A */}
      <div className="flex items-center justify-between px-3 py-1.5">
        <Link
          href={matchHref(m.team_a, m.team_b)}
          className="flex items-center gap-1.5 text-base font-bold hover:underline cursor-pointer"
        >
          <span className="text-2xl leading-none">{teamFlag(m.team_a)}</span>
          <span>{teamNameZh(m.team_a)}</span>
        </Link>
        <span className="text-xs text-gray-500 font-mono">
          {Math.round(m.team_a_win * 100)}%
        </span>
      </div>
      {/* Team B */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-100 dark:border-gray-800">
        <Link
          href={matchHref(m.team_a, m.team_b)}
          className="flex items-center gap-1.5 text-base hover:underline cursor-pointer"
        >
          <span className="text-2xl leading-none">{teamFlag(m.team_b)}</span>
          <span>{teamNameZh(m.team_b)}</span>
        </Link>
        <span className="text-xs text-gray-500 font-mono">
          {Math.round(m.team_b_win * 100)}%
        </span>
      </div>
      {/* 比分 */}
      <div className="px-3 py-1 text-xs text-gray-600 dark:text-gray-400 font-mono border-t border-gray-100 dark:border-gray-800">
        {m.score}
      </div>
      {/* 冠军徽章 */}
      <div className="px-3 py-1.5 flex items-center justify-between bg-yellow-100/50 dark:bg-yellow-900/20 rounded-b-lg">
        <span className="text-xs text-gray-600 dark:text-gray-400">冠军:</span>
        <Link
          href={matchHref(m.team_a, m.team_b)}
          className="text-base font-black bg-gradient-to-r from-emerald-600 to-yellow-600 bg-clip-text text-transparent hover:underline cursor-pointer"
        >
          {teamFlag(champion)} {teamNameZh(champion)} {Math.round(confidence * 100)}%
        </Link>
      </div>
    </div>
  );
}
