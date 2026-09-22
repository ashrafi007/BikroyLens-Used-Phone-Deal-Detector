import { useEffect, useState } from "react";
import { fetchDeals, type Listing } from "../api";
import ListingCard from "../components/ListingCard";
import { GridSkeleton, EmptyState } from "../components/Loading";

export default function Deals() {
  const [deals, setDeals] = useState<Listing[] | null>(null);

  useEffect(() => {
    fetchDeals(60).then(setDeals).catch(() => setDeals([]));
  }, []);

  return (
    <div className="page">
      <div className="page__header">
        <h1>🔥 Best Deals Right Now</h1>
        <p className="page__subtitle">
          Listings priced furthest below their predicted fair value — flagged suspicious listings are
          excluded automatically.
        </p>
      </div>

      {deals === null ? (
        <GridSkeleton count={9} />
      ) : deals.length === 0 ? (
        <EmptyState message="No deals available right now — check back after the next scrape." />
      ) : (
        <div className="listing-grid">
          {deals.map((d) => (
            <ListingCard key={d.id} listing={d} />
          ))}
        </div>
      )}
    </div>
  );
}
