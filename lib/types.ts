// Types for MiroFish run data — see scripts/parse-report.py output

export type Score = {
  raw: string;
  home: number | null;
  away: number | null;
  aet: boolean;
  pens: boolean;
};

export type TopScore = {
  home: number;
  away: number;
  prob: number;     // 0-1 (e.g. 0.247 for 24.7%)
  pct?: number;     // optional pre-formatted display value (e.g. 24.7)
};

export type Match = {
  stage: string;
  matchday: number;
  team_a: string;
  team_b: string;
  team_a_win: number;
  draw: number;
  team_b_win: number;
  most_likely_score: Score;
  // Top 3 most likely exact scores with probabilities. New in A+B (2026-06-19):
  // populated from MiroFish's prompt-anchored output when available, falling
  // back to scripts/elo_poisson.py's independent-Poisson baseline.
  top_3_scores?: TopScore[];
};

export type Standing = {
  team: string;
  points: number;
  note: string | null;
};

export type Group = {
  letter: string;
  teams: string[];
  matches: Match[];
  standings: Standing[];
};

export type Signal = {
  signal: string;
  direction: "positive" | "negative" | "mixed";
  strength: number;
};

export type Verdict = {
  prediction: string;
  confidence: number;
  key_dynamics: string[];
  signals: Signal[];
};

export type FinalTier = {
  tier: number;
  label: string;
  content: string;
  probability: number | null;
};

export type Final = {
  matchup: string | null;
  tiers: FinalTier[];
  combined_text: string | null;
  champion: string | null;
  confidence: number | null;
};

export type BestThird = {
  rank: number;
  team: string;
  group: string;
  points: number;
  goal_difference: number;
  reason: string;
};

export type UpsetRisk = {
  rank: number;
  match: string;
  stage: string;
  upset_probability: number;
  rationale: string;
};

export type TopAgent = {
  agent_id: number;
  agent_name: string;
  total_actions: number;
  twitter_actions: number;
  reddit_actions: number;
};

export type Summary = {
  rounds: number;
  node_count: number;
  edge_count: number;
  total_actions: number;
  top_agents: TopAgent[];
};

export type RunData = {
  run_id: string;
  created_at: string;
  verdict: Verdict;
  summary?: Summary;
  groups: Record<string, Group>;
  best_thirds: BestThird[];
  bracket?: Bracket;
  final: Final;
  upset_risks: UpsetRisk[];
  report_markdown: string;
  champion_table?: Record<string, number>;
  round?: number;
  format?: string;
};

export type MeihuaPred = {
  trigram_upper: string;        // 上卦 (e.g. "离")
  trigram_lower: string;        // 下卦 (e.g. "坤")
  changing_line: number;        // 动爻 1-6
  host_trigram: string;         // 体卦 (主队)
  guest_trigram: string;        // 用卦 (客队)
  host_element: string;         // 金/木/水/火/土
  guest_element: string;
  five_element_relation:        // 体用生克关系
    | "体生用" | "用生体" | "体克用" | "用克体" | "比和";
  base_score: { home: number; away: number };  // 中心分
  top_3_scores: TopScore[];     // 与 MiroFish top_3_scores 同 schema (3 个候选)
  predicted_winner: "a" | "b" | null;
  kickoff_utc_used: string;
  // 4 段文本 (2026-06-22): M3 LLM 生成, 模板 fallback
  basic?: string;                // 基础信息
  hexagram_interpretation?: string;  // 卦象解读
  score_hint?: string;           // 卦数附会
  reality_check?: string;        // 客观现实
  llm_narrative?: string | null;  // M3 4 段合并 markdown
  template_fallback?: string;    // 模板版 4 段合并 markdown (永久兜底)
};

export type BracketMatch = {
  bracket_idx?: number;       // 0-based position within the round
  team_a: string;
  team_b: string;
  // 组别种子 (parse 阶段从 MiroFish 报告的 (A1)/(1A) 后缀提取; 老 run 缺字段时 buildGroupIndex() 反查 standings)
  group_a?: string;           // "A" / "I" — R32 才有; R16/QF/SF 通常没 (跨组)
  seed_a?: number;            // 1 / 2 / 3
  group_b?: string;
  seed_b?: number;
  team_a_win: number;
  draw: number;
  team_b_win: number;
  score: string;
  aet_pct: number | null;
  pen_pct: number | null;
  winner: "a" | "b" | null;
  // A+B (2026-06-19): same top-3 score list as group matches. Drives the
  // new "Top-1 exact score" + "Top-3 score" hit metrics on the homepage.
  top_3_scores?: TopScore[];
  // 梅花易数 (2026-06-20): 时间起卦 + 五行生克 + 体用推分
  meihua?: MeihuaPred;
};

export type ThirdPlace = {
  team_a: string;
  team_b: string;
  score: string;
  raw: string;
  aet: boolean;
} | null;

export type Bracket = {
  r32: BracketMatch[];
  r16: BracketMatch[];
  qf: BracketMatch[];
  sf: BracketMatch[];
  third_place: ThirdPlace;
};
