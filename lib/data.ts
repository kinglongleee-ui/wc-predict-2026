// Data loader — reads MiroFish run JSON from /data/runs/ at build time.
// Build-time: Next.js bundles the JSON into the serverless function.

import fs from "fs";
import path from "path";
import type { RunData } from "./types";

const DATA_DIR = path.join(process.cwd(), "data", "runs");
const REAL_DIR = path.join(process.cwd(), "data", "real");

export type RealMatch = {
  group: string;
  team_a: string;
  score_a: number;
  team_b: string;
  score_b: number;
  date: string | null;
  source_wiki_page: string;
};

export type RealResults = {
  fetched_at: string;
  source: string;
  match_count: number;
  matches: RealMatch[];
} | null;

export function loadRealResults(): RealResults {
  const fp = path.join(REAL_DIR, "wc_2026_results.json");
  if (!fs.existsSync(fp)) return null;
  try {
    return JSON.parse(fs.readFileSync(fp, "utf-8")) as RealResults;
  } catch {
    return null;
  }
}

// Build a lookup key from (group, team_a, team_b) regardless of who is home/away.
// Used by /bracket and /groups to colour matches that have already been played.
export type PlayedKey = string; // "{group}|{team_a_canonical}|{team_b_canonical}"
function canon(t: string): string {
  return t.trim().toLowerCase();
}
export function playedKeyForMatch(group: string, team_a: string, team_b: string): PlayedKey {
  const a = canon(team_a);
  const b = canon(team_b);
  // 用 (sorted pair) 让 home/away 顺序无关
  return `${group}|${[a, b].sort().join("|")}`;
}
export function buildPlayedIndex(real: RealResults): Map<PlayedKey, RealMatch> {
  const m = new Map<PlayedKey, RealMatch>();
  if (!real) return m;
  for (const r of real.matches) {
    const key = playedKeyForMatch(r.group, r.team_a, r.team_b);
    m.set(key, r);
  }
  return m;
}

// 判断模拟里的预测结果是否跟真实结果"对得上" (是否预测对了胜平负)
export type MatchPrediction = {
  team_a_win: number;
  draw: number;
  team_b_win: number;
};
export function predictOutcome(p: MatchPrediction): "a" | "draw" | "b" {
  const arr = [
    { k: "a" as const, v: p.team_a_win },
    { k: "draw" as const, v: p.draw },
    { k: "b" as const, v: p.team_b_win },
  ];
  arr.sort((x, y) => y.v - x.v);
  return arr[0].k;
}
export function realOutcome(r: RealMatch): "a" | "draw" | "b" {
  if (r.score_a > r.score_b) return "a";
  if (r.score_a < r.score_b) return "b";
  return "draw";
}

export function listRuns(): RunData[] {
  if (!fs.existsSync(DATA_DIR)) return [];
  const files = fs.readdirSync(DATA_DIR).filter((f) => f.endsWith(".json"));
  return files
    .map((f) => loadRun(f.replace(".json", "")))
    .filter((r): r is RunData => r !== null)
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
}

export function loadRun(runId: string): RunData | null {
  const filePath = path.join(DATA_DIR, `${runId}.json`);
  if (!fs.existsSync(filePath)) return null;
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as RunData;
  } catch {
    return null;
  }
}

export function getLatestRound3Run(): RunData | null {
  // Round 3 is the canonical detailed report. Cron updates this daily; we
  // pick the most recently created run whose id is NOT the pinned Round 2
  // baseline (run_a18431af48fd) and whose file is large enough to be a full
  // Round 3 (>20 KB; Round 2's parsed JSON is ~13 KB).
  //
  // IMPORTANT: prefer runs whose `bracket` field is populated (= parse-report.py
  // successfully extracted the R32 table). Newer runs whose report.md uses a
  // Chinese heading variant ("## 4. 32 强赛") may parse without a bracket —
  // we fall back to the latest run WITH bracket so the tree / BracketMini
  // pages still render. See scripts/parse-report.py for the regex TODO.
  const all = listRuns().filter(
    (r) => r.run_id !== "run_a18431af48fd" && r.final && r.groups,
  );
  if (all.length === 0) return null;
  const withBracket = all.find(
    (r) => r.bracket && r.bracket.r32 && r.bracket.r32.length >= 16,
  );
  return withBracket || all[0];
}

export function getRound2Run(): RunData | null {
  return loadRun("run_a18431af48fd");
}

export function getSecondLatestRound3Run(): RunData | null {
  // Used by /simulations to show "previous round" for drift comparison.
  const all = listRuns().filter(
    (r) => r.run_id !== "run_a18431af48fd" && r.final && r.groups,
  );
  if (all.length < 2) return null;
  return all[1];
}

export function listGroupLetters(): string[] {
  return "ABCDEFGHIJKL".split("");
}

export function formatPct(n: number, digits = 0): string {
  return `${(n * 100).toFixed(digits)}%`;
}

const FLAG_MAP: Record<string, string> = {
  "Mexico": "🇲🇽", "South Korea": "🇰🇷", "Czech Republic": "🇨🇿", "South Africa": "🇿🇦",
  "Switzerland": "🇨🇭", "Qatar": "🇶🇦", "Bosnia": "🇧🇦", "Bosnia & Herzegovina": "🇧🇦", "Canada": "🇨🇦",
  "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Haiti": "🇭🇹",
  "USA": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Turkey": "🇹🇷",
  "Germany": "🇩🇪", "Ecuador": "🇪🇨", "Ivory Coast": "🇨🇮", "Curaçao": "🇨🇼",
  "Netherlands": "🇳🇱", "Sweden": "🇸🇪", "Japan": "🇯🇵", "Tunisia": "🇹🇳",
  "Belgium": "🇧🇪", "Iran": "🇮🇷", "Egypt": "🇪🇬", "New Zealand": "🇳🇿",
  "Spain": "🇪🇸", "Uruguay": "🇺🇾", "Saudi Arabia": "🇸🇦", "Cape Verde": "🇨🇻",
  "France": "🇫🇷", "Norway": "🇳🇴", "Senegal": "🇸🇳", "Iraq": "🇮🇶",
  "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
  "Portugal": "🇵🇹", "Colombia": "🇨🇴", "DR Congo": "🇨🇩", "Uzbekistan": "🇺🇿",
  "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
};

// Build a lowercase index for case-insensitive lookups
const FLAG_INDEX = Object.entries(FLAG_MAP).map(([k, v]) => [k.toLowerCase(), v] as [string, string]);

export function teamFlag(team: string): string {
  const key = team.trim();
  if (FLAG_MAP[key]) return FLAG_MAP[key];
  const lower = key.toLowerCase();
  for (const [k, v] of FLAG_INDEX) {
    if (k === lower) return v;
  }
  return "🏳️";
}

// Normalize a "champion" string like "FRANCE — confidence 64%." into "France"
export function normalizeChampion(raw: string | null | undefined): string {
  if (!raw) return "—";
  return raw
    .replace(/\s*—\s*confidence.*$/i, "")
    .replace(/[.。,，]+$/, "")
    .trim()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

// ---------------------------------------------------------------------------
// 全站零英文: 球队 / 阶段 / 信号方向 / 冠军档位的中文映射
// ---------------------------------------------------------------------------

const TEAM_ZH: Record<string, string> = {
  // 全称
  "Mexico": "墨西哥", "South Korea": "韩国", "Czech Republic": "捷克", "South Africa": "南非",
  "Switzerland": "瑞士", "Qatar": "卡塔尔", "Bosnia": "波黑", "Bosnia & Herzegovina": "波黑",
  "Canada": "加拿大", "Brazil": "巴西", "Morocco": "摩洛哥", "Scotland": "苏格兰", "Haiti": "海地",
  "USA": "美国", "Paraguay": "巴拉圭", "Australia": "澳大利亚", "Turkey": "土耳其",
  "Germany": "德国", "Ecuador": "厄瓜多尔", "Ivory Coast": "科特迪瓦", "Curaçao": "库拉索",
  "Netherlands": "荷兰", "Sweden": "瑞典", "Japan": "日本", "Tunisia": "突尼斯",
  "Belgium": "比利时", "Iran": "伊朗", "Egypt": "埃及", "New Zealand": "新西兰",
  "Spain": "西班牙", "Uruguay": "乌拉圭", "Saudi Arabia": "沙特", "Cape Verde": "佛得角",
  "France": "法国", "Norway": "挪威", "Senegal": "塞内加尔", "Iraq": "伊拉克",
  "Argentina": "阿根廷", "Algeria": "阿尔及利亚", "Austria": "奥地利", "Jordan": "约旦",
  "Portugal": "葡萄牙", "Colombia": "哥伦比亚", "DR Congo": "刚果(金)", "Uzbekistan": "乌兹别克斯坦",
  "England": "英格兰", "Croatia": "克罗地亚", "Ghana": "加纳", "Panama": "巴拿马",
  // 三字代码 (MiroFish 在 upset/match 里也用)
  "ARG": "阿根廷", "BEL": "比利时", "BRA": "巴西", "CIV": "科特迪瓦",
  "ENG": "英格兰", "FRA": "法国", "GER": "德国", "MEX": "墨西哥",
  "NED": "荷兰", "POR": "葡萄牙", "SUI": "瑞士", "URU": "乌拉圭",
};

export function teamNameZh(raw: string | null | undefined): string {
  if (!raw) return "—";
  const trimmed = raw.trim();
  if (TEAM_ZH[trimmed]) return TEAM_ZH[trimmed];
  // 容错: 大小写不敏感
  for (const [k, v] of Object.entries(TEAM_ZH)) {
    if (k.toLowerCase() === trimmed.toLowerCase()) return v;
  }
  return trimmed; // 找不到就原样返回 (避免静默丢数据)
}

const DIRECTION_ZH: Record<string, string> = {
  positive: "利好",
  negative: "利空",
  mixed: "混合",
};

export function directionZh(d: string | null | undefined): string {
  if (!d) return "—";
  return DIRECTION_ZH[d] || d;
}

export function stageZh(stage: string | null | undefined): string {
  if (!stage) return "—";
  const s = stage.trim();
  // 形如 "Group A" → "A 组"
  const groupMatch = s.match(/^Group\s+([A-L])$/i);
  if (groupMatch) return `${groupMatch[1].toUpperCase()} 组`;
  if (/^group$/i.test(s)) return "小组赛";
  const map: Record<string, string> = {
    "R16": "16 强赛",
    "Round of 16": "16 强赛",
    "QF": "1/4 决赛",
    "Quarterfinal": "1/4 决赛",
    "Quarter-final": "1/4 决赛",
    "SF": "半决赛",
    "Semifinal": "半决赛",
    "Semi-final": "半决赛",
    "Final": "决赛",
  };
  return map[s] || map[s.toUpperCase()] || s;
}

const TIER_LABEL_ZH: Record<string, string> = {
  "90 minutes result": "常规 90 分钟",
  "90 min": "常规 90 分钟",
  "After Extra Time": "加时赛",
  "Extra Time": "加时赛",
  "AET": "加时赛",
  "Penalties": "点球大战",
  "On Penalties": "点球大战",
  "PSO": "点球大战",
};

export function tierLabelZh(label: string | null | undefined): string {
  if (!label) return "—";
  return TIER_LABEL_ZH[label] || TIER_LABEL_ZH[label.trim()] || label;
}

// 把 "France vs Spain" 渲染成 "法国 对 西班牙"
export function matchupZh(matchup: string | null | undefined): string {
  if (!matchup) return "—";
  return matchup
    .split(/\s+vs\s+|\s+v\s+/i)
    .map((t) => teamNameZh(t.trim()))
    .join(" 对 ");
}
