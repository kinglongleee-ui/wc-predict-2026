// URL helper for per-match prediction routes.
// MiroFish team names can contain spaces and "&" (e.g. "South Korea",
// "Bosnia & Herzegovina") — encodeURIComponent handles both.
//
// Usage: <Link href={matchHref("USA", "Australia")}>...</Link>
// → renders to /match/USA/Australia (Next.js decodes params back).

export function matchHref(a: string, b: string): string {
  return `/match/${encodeURIComponent(a)}/${encodeURIComponent(b)}`;
}
