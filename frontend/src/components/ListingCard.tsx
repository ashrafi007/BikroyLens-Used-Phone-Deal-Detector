import { Link } from "react-router-dom";
import type { Listing } from "../api";
import DealScoreBadge from "./DealScore";
import { formatPrice } from "../format";

export default function ListingCard({ listing }: { listing: Listing }) {
  return (
    <Link to={`/listing/${listing.id}`} className="card card--hover listing-card">
      <div className="listing-card__top">
        <p className="listing-card__title">{listing.raw_title}</p>
        {listing.is_suspicious && <span className="suspicious-flag">⚠ Check</span>}
      </div>

      <div className="listing-card__meta">
        {listing.city && <span className="chip">{listing.city}</span>}
        {listing.condition_clean && <span className="chip">{listing.condition_clean}</span>}
        {listing.storage && <span className="chip">{listing.storage}</span>}
      </div>

      <div className="listing-card__price">{formatPrice(listing.price)}</div>
      {listing.fair_price_min && listing.fair_price_max && (
        <div className="listing-card__fair">
          Fair range: {formatPrice(listing.fair_price_min)} – {formatPrice(listing.fair_price_max)}
        </div>
      )}

      <DealScoreBadge score={listing.deal_score} />
    </Link>
  );
}
