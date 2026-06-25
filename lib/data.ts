// Data loader — reads MiroFish run JSON from /data/runs/ at build time.
// Build-time: Next.js bundles the JSON into the serverless function.

import fs from "fs";
import path from "path";
import type { RunData, MeihuaPred, BracketMatch } from "./types";

const DATA_DIR = path.join(process.cwd(), "data", "runs");
const REAL_DIR = path.join(process.cwd(), "data", "real");
const MEIHUA_DIR = path.join(process.cwd(), "data", "meihua");

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

// ---------------------------------------------------------------------------
// 博彩赔率 (DraftKings via ESPN, 2026-06-24 起): 仅赛前盘 (state=post 的 event ESPN 不再返 odds)
// ---------------------------------------------------------------------------
export type OddsBlock = {
  home_odds_american: string;
  draw_odds_american: string;
  away_odds_american: string;
  home_prob_raw: number;
  draw_prob_raw: number;
  away_prob_raw: number;
  overround: number;
  home_prob_norm: number;
  draw_prob_norm: number;
  away_prob_norm: number;
  over_under: number | null;
  provider: string;
};

export type OddsMatch = {
  group: string;
  team_a: string;
  team_b: string;
  date: string | null;
  kickoff_utc: string | null;
  is_played: boolean;
  odds: OddsBlock;
};

export type OddsData = {
  fetched_at: string;
  source: string;
  window: string;
  match_count: number;
  pre_count: number;
  post_count: number;
  matches: OddsMatch[];
} | null;

export function loadOdds(): OddsData {
  const fp = path.join(REAL_DIR, "wc_2026_odds.json");
  if (!fs.existsSync(fp)) return null;
  try {
    return JSON.parse(fs.readFileSync(fp, "utf-8")) as OddsData;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// 波胆赔率 (Flashscore 抓 DraftKings/Bet365/Pinnacle 等 6 家最佳赔率, 2026-06-24 起)
// 文件: data/real/wc_2026_correct_score.json
// ---------------------------------------------------------------------------
export type CorrectScoreEntry = {
  home: number;
  away: number;
  odds_decimal: number;
  odds_american: string;
  prob_norm: number;
  n_bookmakers: number;
  prev_decimal: number;
};

export type CorrectScoreBlock = {
  provider: string;
  scores: CorrectScoreEntry[];
};

export type CorrectScoreMatch = {
  group: string | null;
  team_a: string;
  team_b: string;
  date: string | null;
  kickoff_utc: string | null;
  is_played: boolean | null;
  source_url?: string;
  correct_score: CorrectScoreBlock;
};

export type CorrectScoreData = {
  fetched_at: string;
  source: string;
  scraper?: string;
  match_count: number;
  matches: CorrectScoreMatch[];
} | null;

export function loadCorrectScores(): CorrectScoreData {
  const fp = path.join(REAL_DIR, "wc_2026_correct_score.json");
  if (!fs.existsSync(fp)) return null;
  try {
    return JSON.parse(fs.readFileSync(fp, "utf-8")) as CorrectScoreData;
  } catch {
    return null;
  }
}

// 给 (group, team_a, team_b) 查 correct_score (跟 lookupOdds 同语义: 不分主客)
export type CorrectScoreLookup = { match: CorrectScoreMatch; cs: CorrectScoreBlock } | null;
export function lookupCorrectScore(
  cs: CorrectScoreData,
  group: string | null | undefined,
  team_a: string,
  team_b: string,
): CorrectScoreLookup {
  if (!cs) return null;
  const a = canonTeam(team_a);
  const b = canonTeam(team_b);
  const wantKey = [a, b].sort().join("|");
  for (const m of cs.matches) {
    if (group && m.group && m.group !== group) continue;
    const ma = canonTeam(m.team_a);
    const mb = canonTeam(m.team_b);
    const k = [ma, mb].sort().join("|");
    if (k === wantKey) return { match: m, cs: m.correct_score };
  }
  return null;
}

// 取 top N 最高概率的比分 (返回 [{home, away, prob, odds_american}, ...])
export function topCorrectScores(
  cs: CorrectScoreBlock | null | undefined,
  n = 5,
): CorrectScoreEntry[] {
  if (!cs || !cs.scores) return [];
  return [...cs.scores]
    .sort((x, y) => y.prob_norm - x.prob_norm)
    .slice(0, n);
}

// 给 (group, team_a, team_b) 排序无关查 odds (跟 playedKeyForMatch 同语义)。
// 返回 {match, odds} 或 null — PlayedVsPredicted 直接渲染。
export type OddsLookup = { match: OddsMatch; odds: OddsBlock } | null;
export function lookupOdds(
  odds: OddsData,
  group: string,
  team_a: string,
  team_b: string,
): OddsLookup {
  if (!odds) return null;
  const a = canonTeam(team_a);
  const b = canonTeam(team_b);
  const wantKey = [a, b].sort().join("|");
  for (const m of odds.matches) {
    if (m.group !== group) continue;
    const ma = canonTeam(m.team_a);
    const mb = canonTeam(m.team_b);
    const k = [ma, mb].sort().join("|");
    if (k === wantKey) return { match: m, odds: m.odds };
  }
  return null;
}

// 美国式赔数 → 中文 "主/平/客" 标签: 直接返原串 (-185 / +300 / +600)
export function fmtAmericanOdds(s: string | null | undefined): string {
  if (!s) return "—";
  return s.startsWith("+") || s.startsWith("-") ? s : `+${s}`;
}

// Build a lookup key from (group, team_a, team_b) regardless of who is home/away.
// Used by /bracket and /groups to colour matches that have already been played.
export type PlayedKey = string; // "{group}|{team_a_canonical}|{team_b_canonical}"
function canon(t: string): string {
  return t.trim().toLowerCase();
}
// 把 FIFA 三字代码 (MEX/CZE) 归一化成 MiroFish 用的全称 (Mexico/Czech Republic),
// 让 playedKeyForMatch 在 R4 三字代码 + R3 全称场景下都能查到。
const CODE_TO_TEAM_CANON: Record<string, string> = {
  mex: "mexico", kor: "south korea", cze: "czech republic", rsa: "south africa",
  sui: "switzerland", qat: "qatar", bih: "bosnia", can: "canada",
  bra: "brazil", mar: "morocco", sco: "scotland", hai: "haiti",
  usa: "usa", par: "paraguay", aus: "australia", tur: "turkey",
  ger: "germany", ecu: "ecuador", civ: "ivory coast", cuw: "curaçao",
  ned: "netherlands", swe: "sweden", jpn: "japan", tun: "tunisia",
  bel: "belgium", irn: "iran", egy: "egypt", nzl: "new zealand",
  esp: "spain", uru: "uruguay", ksa: "saudi arabia", cpv: "cape verde",
  fra: "france", nor: "norway", sen: "senegal", irq: "iraq",
  arg: "argentina", alg: "algeria", aut: "austria", jor: "jordan",
  por: "portugal", col: "colombia", cod: "dr congo", uzb: "uzbekistan",
  eng: "england", cro: "croatia", gha: "ghana", pan: "panama",
};
function canonTeam(t: string): string {
  const c = canon(t);
  return CODE_TO_TEAM_CANON[c] || c;
}
export function playedKeyForMatch(group: string, team_a: string, team_b: string): PlayedKey {
  const a = canonTeam(team_a);
  const b = canonTeam(team_b);
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
  // baseline (run_a18431af48fd) and whose file has both `final` and `groups`.
  //
  // 2026-06-25 update: pick newest by created_at, no bracket fallback.
  // Previously we preferred runs with bracket.r32 > 0, but that locks us to
  // R9 d1f74f (which has 134-fallback bracket) instead of newer R10 905a0
  // which has 16 fresh MD2/MD3 group matches but no bracket yet.
  // Bracket is rendered with 134 fallback at runtime anyway, so any run works.
  const all = listRuns().filter(
    (r) => r.run_id !== "run_a18431af48fd" && r.final && r.groups,
  );
  if (all.length === 0) return null;
  return all[0];
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

// ---------------------------------------------------------------------------
// 组别+排名反查 (用来给 R32 卡显示 "A1" / "I3" 这种种子标识)
// ---------------------------------------------------------------------------
// 优先: match 自带的 group_a/seed_a
// 兜底: 反查 groups[letter].standings (R3 旧 run 没有 group 字段, 用 standings)
export function buildGroupIndex(
  run: RunData
): Map<string, { group: string; rank: number }> {
  const idx = new Map<string, { group: string; rank: number }>();
  const bracket = run.bracket;
  if (bracket) {
    for (const stage of ["r32", "r16", "qf", "sf"] as const) {
      for (const m of bracket[stage] || []) {
        if (m.group_a && m.seed_a != null) {
          idx.set(m.team_a, { group: m.group_a, rank: m.seed_a });
        }
        if (m.group_b && m.seed_b != null) {
          idx.set(m.team_b, { group: m.group_b, rank: m.seed_b });
        }
      }
    }
  }
  // 兜底: 从小组赛积分榜拿 (R3 旧 run 没补字段)
  // 注意: Standing 类型只有 team/points/note; rank 在 R3 JSON 里 position = rank, R4 JSON 里也 position
  for (const [letter, g] of Object.entries(run.groups || {})) {
    g.standings.forEach((s, i) => {
      if (!idx.has(s.team)) {
        idx.set(s.team, { group: letter, rank: i + 1 });
      }
    });
  }
  return idx;
}

// 返回 "A1" / "I3" 这种组+排名短码, 查不到返空串
export function teamSeedLabel(run: RunData, team: string): string {
  const info = buildGroupIndex(run).get(team);
  return info ? `${info.group}${info.rank}` : "";
}

// ---------------------------------------------------------------------------
// 梅花易数 (2026-06-20): 从 data/meihua/run_<id>_meihua.json 读卦象 + 注入到 BracketMatch
// ---------------------------------------------------------------------------
type MeihuaIndexKey = string;  // "{match_num}|{team_a}|{team_b}"
function meihuaKey(matchNum: number, teamA: string, teamB: string): MeihuaIndexKey {
  return `${matchNum}|${canonTeam(teamA)}|${canonTeam(teamB)}`;
}

export function loadMeihua(runId: string): Map<MeihuaIndexKey, MeihuaPred> {
  // 2026-06-20 修: runId 已经含 "run_" 前缀 (如 "run_ea1419a0e22f"),
  // 不要再拼 "run_", 实际文件名是 "run_<id>_meihua.json" = 双重 run_ 错
  const safeId = runId.startsWith("run_") ? runId : `run_${runId}`;
  const fp = path.join(MEIHUA_DIR, `${safeId}_meihua.json`);
  const idx = new Map<MeihuaIndexKey, MeihuaPred>();
  if (!fs.existsSync(fp)) return idx;
  try {
    const raw = JSON.parse(fs.readFileSync(fp, "utf-8")) as {
      matches: Array<{
        stage: string;
        match_num?: number;
        matchday?: number;
        team_a: string;
        team_b: string;
        meihua: MeihuaPred | null;
      }>;
    };
    for (const m of raw.matches) {
      if (!m.meihua) continue;
      // group 阶段用 matchday, 淘汰赛用 match_num (R32=73..88, R16=89..96, QF=97..100, SF=101..102, Final=103)
      let num = m.match_num;
      if (!num && typeof m.matchday === "number") {
        // group stage: 用一个固定起点 (1000+) 避开与淘汰赛冲突
        num = 1000 + m.matchday;
      }
      if (!num) continue;
      const key = meihuaKey(num, m.team_a, m.team_b);
      idx.set(key, m.meihua);
    }
  } catch {
    // ignore — meihua optional
  }
  return idx;
}

// 把 loadMeihua 结果按 (stage, match_num) 注入到 run.bracket 各 stage 的每场 match 上
export function injectMeihua(run: RunData): RunData {
  const idx = loadMeihua(run.run_id);
  if (idx.size === 0) return run;
  const bracket = run.bracket;
  if (!bracket) return run;

  const applyToStage = (stage: "r32" | "r16" | "qf" | "sf", startMatchNum: number) => {
    bracket[stage] = (bracket[stage] || []).map((m: BracketMatch, i: number) => {
      const matchNum = startMatchNum + i;
      const key = meihuaKey(matchNum, m.team_a, m.team_b);
      let meihua = idx.get(key);
      // 兜底: 顺序不匹配时按 (team_a, team_b) 反向查
      if (!meihua) {
        const reverseKey = meihuaKey(matchNum, m.team_b, m.team_a);
        meihua = idx.get(reverseKey);
      }
      return meihua ? { ...m, meihua } : m;
    });
  };

  applyToStage("r32", 73);
  applyToStage("r16", 89);
  applyToStage("qf", 97);
  applyToStage("sf", 101);
  // Final (match 103): 单场, 从 idx 找含 team_a/b 的 final 卦象
  const finalPred = Array.from(idx.entries()).find(([k]) => k.startsWith("103|"));
  if (finalPred && run.final?.matchup) {
    // 注意: bracket.final 字段在 Bracket 类型里是 third_place, 没有 final match 字段;
    // Final 卦象放到 final.meta.meihua 给 /report 页读 (暂不在 /bracket 显示)
    (run.final as any).meihua = finalPred[1];
  }

  return { ...run, bracket };
}
