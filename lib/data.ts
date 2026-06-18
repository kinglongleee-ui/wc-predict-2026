// Data loader — reads MiroFish run JSON from /data/runs/ at build time.
// Build-time: Next.js bundles the JSON into the serverless function.

import fs from "fs";
import path from "path";
import type { RunData } from "./types";

const DATA_DIR = path.join(process.cwd(), "data", "runs");

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
  // Round 3 is the canonical detailed report (run_b37f734df790 was the latest)
  return loadRun("run_b37f734df790");
}

export function getRound2Run(): RunData | null {
  return loadRun("run_a18431af48fd");
}

export function listGroupLetters(): string[] {
  return "ABCDEFGHIJKL".split("");
}

export function formatPct(n: number, digits = 0): string {
  return `${(n * 100).toFixed(digits)}%`;
}

export function teamFlag(team: string): string {
  // Approximate country code → emoji flag (most common WC teams)
  const map: Record<string, string> = {
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
  return map[team] || "🏳️";
}
