// Same 0-100 scale the backend computes: 100 - ((price - predicted) / predicted * 100),
// clipped 0-100. Bucketed into 4 labels purely for the badge's color/text —
// the underlying number is what's actually meaningful, shown alongside it.
export function dealScoreLabel(score: number): { label: string; cls: string } {
  if (score >= 80) return { label: "Great Deal", cls: "deal-score--great" };
  if (score >= 55) return { label: "Good Deal", cls: "deal-score--good" };
  if (score >= 30) return { label: "Fair Price", cls: "deal-score--fair" };
  return { label: "Above Market", cls: "deal-score--poor" };
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
