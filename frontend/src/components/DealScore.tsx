// The old scheme classified off the 0-100 deal_score number, which is
// 100 - percent-over-fair-price, clipped at 100 for anything at-or-under
// the estimate. That clip is exactly the problem: a listing 1% under fair
// and one 50% under fair both hit the same ceiling and were both labeled
// "Great Deal," which is why the whole site skewed toward that one
// category. Classifying directly off price vs. the fair range instead --
// the same fair_price_min/fair_price_max already shown on screen -- fixes
// that: the range itself splits into Great (lower half, closer to the
// model's central estimate) and Good (upper half), a price under the
// whole range is a Steal, and above it is Above Market. Four real,
// roughly-even buckets instead of one that swallows most of the market.
export interface DealPriceInfo {
  price: number;
  predicted_price?: number | null;
  fair_price_min?: number | null;
  fair_price_max?: number | null;
}

export function dealLabel(listing: DealPriceInfo): { label: string; cls: string } | null {
  const { price, predicted_price, fair_price_min, fair_price_max } = listing;
  if (!predicted_price || fair_price_min == null || fair_price_max == null) return null;

  if (price < fair_price_min) return { label: "Steal", cls: "deal-score--steal" };
  if (price <= predicted_price) return { label: "Great Deal", cls: "deal-score--great" };
  if (price <= fair_price_max) return { label: "Good Deal", cls: "deal-score--good" };
  return { label: "Above Market", cls: "deal-score--poor" };
}

export default function DealScoreBadge({ listing }: { listing: DealPriceInfo & { deal_score?: number | null } }) {
  const deal = dealLabel(listing);
  if (!deal) {
    return <span className="chip">Not yet scored</span>;
  }
  const { label, cls } = deal;
  return (
    <span className={`deal-score ${cls}`}>
      {label}
      {listing.deal_score !== undefined && listing.deal_score !== null ? ` · ${Math.round(listing.deal_score)}` : ""}
    </span>
  );
}
