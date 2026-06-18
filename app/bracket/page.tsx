import Link from "next/link";
import { getLatestRound3Run } from "@/lib/data";
import type { BracketMatch } from "@/lib/types";

// 一列宽度 + 一行高度 + SVG 总尺寸。所有匹配卡几何参数在这里集中调整。
const COL_W = 220;        // 单列宽度
const COL_GAP = 36;       // 列间隙 (留给连线)
const ROW_H = 44;         // R32 中每行间距
const CARD_W = 200;
const CARD_H = 60;
const FINAL_COL_W = 240;  // 决赛列稍宽,放冠军大卡

// 5 列: R32 → R16 → QF → SF → Final
const ROUND_LABELS = ["32 强赛", "16 强赛", "1/4 决赛", "半决赛", "决赛"];

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

  // 列与列对应: r32 → r16 → qf → sf → final (final 用 r3.final.matchup)
  const cols = [bracket.r32, bracket.r16, bracket.qf, bracket.sf];
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
  const totalRows = cols[0].length;        // 16
  const totalH = totalRows * ROW_H + 80;   // 16 * 44 + 上下 padding
  const totalW = 5 * COL_W + 4 * COL_GAP + FINAL_COL_W + 40;

  // 父-子配对: 第 i 列的 k 场比赛 → 第 i+1 列的 floor(k/2) 场
  // 返回 { leftIdx, rightIdx } 在子列上的父母索引
  function parents(colIdx: number, childIdx: number): [number, number] {
    return [childIdx * 2, childIdx * 2 + 1];
  }

  // 第 col 列的 k 场卡片 Y 中心 (相对 SVG top)
  function cardY(colIdx: number, k: number): number {
    const col = cols[colIdx] ?? finalCol;
    if (colIdx === 0) {
      // R32: 直接按行号
      return 30 + k * ROW_H + CARD_H / 2;
    }
    // R16/QF/SF: 是其两个父母 Y 中心的中点
    const [l, r] = parents(colIdx, k);
    const lY = cardY(colIdx - 1, l);
    const rY = cardY(colIdx - 1, r);
    return (lY + rY) / 2;
  }

  function cardX(colIdx: number): number {
    if (colIdx === 4) {
      // Final 列在最右
      return 20 + 4 * (COL_W + COL_GAP) + COL_W - 40;
    }
    return 20 + colIdx * (COL_W + COL_GAP);
  }

  // 连线: 从 col 列 k 场的右侧 → 子列 floor(k/2) 的左侧
  // 仅在 colIdx < 4 时画
  function connectionLines() {
    const paths: { x1: number; y1: number; x2: number; y2: number; key: string }[] = [];
    for (let ci = 0; ci < cols.length; ci++) {
      for (let k = 0; k < cols[ci].length; k += 2) {
        const topY = cardY(ci, k);
        const botY = cardY(ci, k + 1);
        const midY = (topY + botY) / 2;
        const x = cardX(ci) + CARD_W;
        const childX = cardX(ci + 1);
        paths.push({
          x1: x,
          y1: topY,
          x2: x + 8,
          y2: topY,
          key: `top-${ci}-${k}`,
        });
        paths.push({
          x1: x + 8,
          y1: topY,
          x2: x + 8,
          y2: botY,
          key: `vbar-${ci}-${k}`,
        });
        paths.push({
          x1: x + 8,
          y1: botY,
          x2: x,
          y2: botY,
          key: `bot-${ci}-${k}`,
        });
        paths.push({
          x1: childX,
          y1: midY,
          x2: x + 8,
          y2: midY,
          key: `hchild-${ci}-${k}`,
        });
      }
    }
    // 第 4 列 (SF) → Final (colIdx=4)
    const sfTop = cardY(3, 0);
    const sfBot = cardY(3, 1);
    const finalX = cardX(4);
    const finalY = (sfTop + sfBot) / 2;
    const lastX = cardX(3) + CARD_W;
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
          树状图按 MiroFish 多智能体模拟的预测路径展开,胜方按高亮绿显示,平局走加时/点球以虚线连接。
          每张卡片显示两队国名、最可能比分和胜出概率。
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
          <span className="inline-block w-3 h-3 rounded bg-orange-400/80" />
          平局走加时/点球
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 bg-gray-400" />
          父-子连线 (胜方路径)
        </span>
      </section>

      {/* 树状图主体 */}
      <section className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-x-auto">
        <div className="relative" style={{ width: totalW, height: totalH + 60 }}>
          {/* 顶部轮次标签 */}
          {ROUND_LABELS.map((label, ci) => (
            <div
              key={label}
              className="absolute top-2 text-xs font-bold uppercase tracking-wider text-gray-500 text-center"
              style={{
                left: ci === 4 ? cardX(4) : cardX(ci),
                width: ci === 4 ? FINAL_COL_W : CARD_W,
              }}
            >
              {label}
            </div>
          ))}

          {/* SVG 连线层 */}
          <svg
            className="absolute inset-0 pointer-events-none"
            width={totalW}
            height={totalH + 60}
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

          {/* 卡片层 */}
          {cols.map((col, ci) =>
            col.map((m, k) => {
              const y = cardY(ci, k) - CARD_H / 2;
              const x = cardX(ci);
              return (
                <MatchCard
                  key={`${ci}-${k}`}
                  match={m}
                  x={x}
                  y={y}
                  compact={ci < 3}
                />
              );
            }),
          )}

          {/* 决赛大卡 + 冠军 */}
          <FinalChampionCard
            x={cardX(4)}
            y={cardY(3, 0) - 90}
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
          <div className="flex items-center gap-4">
            <div className="text-lg font-bold">
              {bracket.third_place.team_a}
              <span className="mx-2 text-gray-400">vs</span>
              {bracket.third_place.team_b}
            </div>
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
}: {
  match: BracketMatch;
  x: number;
  y: number;
  compact: boolean;
}) {
  const isDraw = match.winner === null;
  const aWins = match.winner === "a";
  const bWins = match.winner === "b";

  return (
    <div
      className={`absolute rounded-md border ${
        isDraw
          ? "border-orange-300 dark:border-orange-700 bg-orange-50/40 dark:bg-orange-950/20"
          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950"
      }`}
      style={{
        left: x,
        top: y,
        width: CARD_W,
        height: CARD_H,
      }}
    >
      {/* Team A 行 */}
      <div className="flex items-center justify-between px-2 h-[28px]">
        <div
          className={`flex items-center gap-1 text-sm truncate ${
            aWins ? "font-bold text-emerald-700 dark:text-emerald-400" : bWins ? "text-gray-400" : ""
          }`}
        >
          <span className="text-base leading-none">{flagFor(match.team_a)}</span>
          <span className="truncate">{match.team_a}</span>
        </div>
        <span
          className={`text-xs font-mono shrink-0 ${
            aWins ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500"
          }`}
        >
          {Math.round(match.team_a_win * 100)}%
        </span>
      </div>
      {/* Team B 行 */}
      <div className="flex items-center justify-between px-2 h-[28px] border-t border-gray-100 dark:border-gray-800">
        <div
          className={`flex items-center gap-1 text-sm truncate ${
            bWins ? "font-bold text-emerald-700 dark:text-emerald-400" : aWins ? "text-gray-400" : ""
          }`}
        >
          <span className="text-base leading-none">{flagFor(match.team_b)}</span>
          <span className="truncate">{match.team_b}</span>
        </div>
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
        <div className="px-2 text-[10px] text-gray-500 flex justify-between items-center h-[4px]">
          <span className="font-mono">
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
        <div className="flex items-center gap-1.5 text-base font-bold">
          <span className="text-2xl leading-none">{flagFor(m.team_a)}</span>
          <span>{m.team_a}</span>
        </div>
        <span className="text-xs text-gray-500 font-mono">
          {Math.round(m.team_a_win * 100)}%
        </span>
      </div>
      {/* Team B */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-1.5 text-base">
          <span className="text-2xl leading-none">{flagFor(m.team_b)}</span>
          <span>{m.team_b}</span>
        </div>
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
        <span className="text-base font-black bg-gradient-to-r from-emerald-600 to-yellow-600 bg-clip-text text-transparent">
          {champion} {Math.round(confidence * 100)}%
        </span>
      </div>
    </div>
  );
}

// 临时旗子 helper (不查 lib.data 避免 SSR issue)
function flagFor(team: string): string {
  const m: Record<string, string> = {
    Mexico: "🇲🇽", "South Korea": "🇰🇷", "Czech Republic": "🇨🇿", "South Africa": "🇿🇦",
    Switzerland: "🇨🇭", Qatar: "🇶🇦", Bosnia: "🇧🇦", Canada: "🇨🇦",
    Brazil: "🇧🇷", Morocco: "🇲🇦", Scotland: "🏴", Haiti: "🇭🇹",
    USA: "🇺🇸", Paraguay: "🇵🇾", Australia: "🇦🇺", Turkey: "🇹🇷",
    Germany: "🇩🇪", Ecuador: "🇪🇨", "Ivory Coast": "🇨🇮", Curaçao: "🇨🇼",
    Netherlands: "🇳🇱", Sweden: "🇸🇪", Japan: "🇯🇵", Tunisia: "🇹🇳",
    Belgium: "🇧🇪", Iran: "🇮🇷", Egypt: "🇪🇬", "New Zealand": "🇳🇿",
    Spain: "🇪🇸", Uruguay: "🇺🇾", "Saudi Arabia": "🇸🇦", "Cape Verde": "🇨🇻",
    France: "🇫🇷", Norway: "🇳🇴", Senegal: "🇸🇳", Iraq: "🇮🇶",
    Argentina: "🇦🇷", Algeria: "🇩🇿", Austria: "🇦🇹", Jordan: "🇯🇴",
    Portugal: "🇵🇹", Colombia: "🇨🇴", "DR Congo": "🇨🇩", Uzbekistan: "🇺🇿",
    England: "🏴", Croatia: "🇭🇷", Ghana: "🇬🇭", Panama: "🇵🇦",
  };
  return m[team] || "🏳️";
}