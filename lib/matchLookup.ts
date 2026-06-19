// Cross-run match lookup + calibration engine.
// Loads 3 MiroFish run files (R3 旧 / R3 新 / R4), finds the match
// across group stage and bracket stage using sorted-pair key (home/away
// 顺序无关), then applies the fav+2pp / draw-3pp / underdog+1pp
// calibration used by /tmp/recalibrate.js (MEX vs KOR baseline).
//
// 校准权重来源: 4 场已比赛 Brier 评分 — favorite 端微加, 平局端微减,
// underdog 端微加。详见 /tmp/recalibrate.js:118-127。

import fs from "fs";
import path from "path";
import type { RunData, BracketMatch } from "./types";
import { teamNameZh } from "./data";

const RUN_FILES = {
  r3_old: "run_b37f734df790",
  r3_new: "run_d7c8d02bf376",
  r4:     "run_e667e173bb3f",
} as const;

type RunKey = keyof typeof RUN_FILES;

export type Stage = "group" | "r32" | "r16" | "qf" | "sf" | "final";

export type FoundMatch = {
  run: RunKey;
  stage: Stage;
  group?: string;
  matchday?: number;
  // MiroFish 写入时 team_a / team_b 的顺序 (跟 URL 可能不同)
  mirofish_team_a: string;
  mirofish_team_b: string;
  // 永远是 [a胜%, 平局%, b胜%], 跟 URL 顺序一致 (a = 传入 crossValidate 的第一个参数)
  team_a_win: number;
  draw: number;
  team_b_win: number;
  modal_score: string;
};

export type CrossValidation = {
  team_a: string;
  team_b: string;
  round_found: Record<RunKey, boolean>;
  matches: FoundMatch[];
  // 校准后 (跟 URL 顺序一致)
  calibrated: { a_win: number; draw: number; b_win: number; modal: string };
  // 最可能比分按出现频次排
  ranked_scores: { score: string; count: number }[];
  notes: string[];
};

function canonPair(a: string, b: string): string {
  return [a.trim().toLowerCase(), b.trim().toLowerCase()].sort().join("|");
}

export function loadAllRuns(): Record<RunKey, RunData> {
  const out = {} as Record<RunKey, RunData>;
  for (const [k, id] of Object.entries(RUN_FILES) as [RunKey, string][]) {
    const fp = path.join(process.cwd(), "data", "runs", `${id}.json`);
    if (!fs.existsSync(fp)) {
      throw new Error(`[matchLookup] 找不到 run 文件: ${fp}`);
    }
    out[k] = JSON.parse(fs.readFileSync(fp, "utf-8")) as RunData;
  }
  return out;
}

function runIdToKey(runId: string): RunKey {
  for (const [k, id] of Object.entries(RUN_FILES) as [RunKey, string][]) {
    if (id === runId) return k;
  }
  // 兜底: 不在已知 3 个里就当作 r4
  return "r4";
}

function searchInRun(run: RunData, runKey: RunKey, a: string, b: string): FoundMatch[] {
  const key = canonPair(a, b);
  const hits: FoundMatch[] = [];
  const aLower = a.trim().toLowerCase();

  // 小组赛
  for (const [letter, g] of Object.entries(run.groups)) {
    if (!g.matches) continue;
    for (const m of g.matches) {
      if (canonPair(m.team_a, m.team_b) === key) {
        // MiroFish 的 team_a 是不是 URL 的 team_a?
        const mirofishAIsUrlA = m.team_a.trim().toLowerCase() === aLower;
        hits.push({
          run: runKey,
          stage: "group",
          group: letter,
          matchday: m.matchday,
          mirofish_team_a: m.team_a,
          mirofish_team_b: m.team_b,
          team_a_win: mirofishAIsUrlA ? m.team_a_win : m.team_b_win,
          draw: m.draw,
          team_b_win: mirofishAIsUrlA ? m.team_b_win : m.team_a_win,
          modal_score: m.most_likely_score?.raw || "—",
        });
        break;
      }
    }
  }
  // 淘汰赛
  for (const stage of ["r32", "r16", "qf", "sf"] as const) {
    const arr = (run.bracket as any)?.[stage] as BracketMatch[] | undefined;
    if (!arr) continue;
    for (const m of arr) {
      if (canonPair(m.team_a, m.team_b) === key) {
        const mirofishAIsUrlA = m.team_a.trim().toLowerCase() === aLower;
        hits.push({
          run: runKey,
          stage,
          mirofish_team_a: m.team_a,
          mirofish_team_b: m.team_b,
          team_a_win: mirofishAIsUrlA ? m.team_a_win : m.team_b_win,
          draw: m.draw,
          team_b_win: mirofishAIsUrlA ? m.team_b_win : m.team_a_win,
          modal_score: m.score || "—",
        });
        break;
      }
    }
  }
  return hits;
}

export function crossValidate(a: string, b: string): CrossValidation {
  const runs = loadAllRuns();
  const r3o = searchInRun(runs.r3_old, "r3_old", a, b);
  const r3n = searchInRun(runs.r3_new, "r3_new", a, b);
  const r4  = searchInRun(runs.r4,     "r4",     a, b);
  // 优先保留 R3 新 > R4 > R3 旧 的"主"信息做 stage/group/matchday 推断
  const matches = [...r3n, ...r4, ...r3o];
  const notes: string[] = [];
  if (!r3o.length) notes.push("R3 旧未模拟这场 (赛程跳过或 D 组等)");
  if (!r3n.length) notes.push("R3 新未模拟这场");
  if (!r4.length)  notes.push("R4 未模拟这场 (赛程跳过)");

  const found = matches.length;
  if (found === 0) {
    return {
      team_a: a, team_b: b,
      round_found: { r3_old: !!r3o.length, r3_new: !!r3n.length, r4: !!r4.length },
      matches: [],
      calibrated: { a_win: 0, draw: 0, b_win: 0, modal: "—" },
      ranked_scores: [],
      notes: [...notes, "三轮都没模拟到这场, 无预测"],
    };
  }

  // 简单平均 (校准前)
  let sumA = 0, sumD = 0, sumB = 0;
  for (const m of matches) { sumA += m.team_a_win; sumD += m.draw; sumB += m.team_b_win; }
  const avgA = sumA / found, avgD = sumD / found, avgB = sumB / found;

  // 校准: avgA >= avgB 表示 a 是 MiroFish 偏好的队
  const aIsFav = avgA >= avgB;
  let calA = avgA + 0.02;
  let calD = Math.max(0, avgD - 0.03);
  let calB = avgB + 0.01;
  const total = calA + calD + calB;
  calA /= total; calD /= total; calB /= total;
  const aWin = aIsFav ? calA : calB;
  const bWin = aIsFav ? calB : calA;

  // 最可能比分按出现频次排
  const scoreCounts = new Map<string, number>();
  for (const m of matches) {
    if (m.modal_score && m.modal_score !== "—") {
      scoreCounts.set(m.modal_score, (scoreCounts.get(m.modal_score) || 0) + 1);
    }
  }
  const ranked = [...scoreCounts.entries()]
    .sort((x, y) => y[1] - x[1])
    .map(([score, count]) => ({ score, count }));
  // modal 兜底: 1-1 (MiroFish 通用默认)
  const modal = ranked[0]?.score || "1-1";

  // 备注
  if (found === 1) notes.push("⚠️ 单轮信号 — 置信度低于 2 轮交叉, 校准风险大");
  if (found === 2) notes.push("✅ 2 轮交叉验证");
  if (found === 3) notes.push("✅ 3 轮交叉验证 (R3 旧 + R3 新 + R4)");
  notes.push(aIsFav
    ? `${teamNameZh(a)} 被校准为热门 (+2pp), ${teamNameZh(b)} 冷门 (+1pp)`
    : `${teamNameZh(b)} 被校准为热门 (+2pp), ${teamNameZh(a)} 冷门 (+1pp)`);

  return {
    team_a: a, team_b: b,
    round_found: { r3_old: !!r3o.length, r3_new: !!r3n.length, r4: !!r4.length },
    matches,
    calibrated: { a_win: aWin, draw: calD, b_win: bWin, modal },
    ranked_scores: ranked,
    notes,
  };
}

// 给 match 详情页用的"本组其他比赛"查找 (R3 新为锚, R3 新覆盖最全)
export function findRelatedMatchesInGroup(a: string, b: string, limit = 2) {
  const runs = loadAllRuns();
  for (const k of ["r3_new", "r4", "r3_old"] as RunKey[]) {
    const r = runs[k];
    for (const [letter, g] of Object.entries(r.groups)) {
      const hasAB = g.matches?.some(
        (m) => canonPair(m.team_a, m.team_b) === canonPair(a, b),
      );
      if (!hasAB) continue;
      // 同组其他比赛 (排除 a vs b 自己)
      const others = (g.matches || [])
        .filter((m) => canonPair(m.team_a, m.team_b) !== canonPair(a, b))
        .slice(0, limit);
      return { run: k, group: letter, others };
    }
  }
  return null;
}
