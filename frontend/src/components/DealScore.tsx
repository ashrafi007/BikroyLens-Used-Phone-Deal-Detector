// Same 0-100 scale the backend computes: 100 - ((price - predicted) / predicted * 100),
// clipped 0-100 -- so every point below 100 means "priced this many percent
// above our fair-price estimate," and 100 itself means at-or-under it (the
// formula can't go higher, it's clipped there). Thresholds are chosen in
// those same percent-over-fair terms, not just picked to look evenly
// spaced 0-100: a 20%-over-priced phone (score 80) used to read as "Great
// Deal" under the old 80/55/30 cutoffs, which was backwards -- being
// meaningfully overpriced should never look great. >=100 is the only value
// that actually means "at or under our estimate," so that's the real
// dividing line for "Great Deal."
export function dealScoreLabel(score: number): { label: string; cls: string } {
  if (score >= 100) return { label: "Great Deal", cls: "deal-score--great" }; // at or under fair price
  if (score >= 90) return { label: "Good Deal", cls: "deal-score--good" }; // up to 10% over
  if (score >= 75) return { label: "Fair Price", cls: "deal-score--fair" }; // 10-25% over
  return { label: "Above Market", cls: "deal-score--poor" }; // more than 25% over
}

export default function DealScoreBadge({ score }: { score?: number }) {
  if (score === undefined || score === null) {
    return <span className="chip">Not yet scored</span>;
  }
  const { label, cls } = dealScoreLabel(score);
  return (
    <span className={`deal-score ${cls}`}>
      {label} · {Math.round(score)}
    </span>
  );
}
