import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchListing, type Listing } from "../api";
import DealScoreBadge, { dealLabel } from "../components/DealScore";
import { formatPrice } from "../format";

export default function ListingDetail() {
  const { id } = useParams();
  const [listing, setListing] = useState<Listing | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetchListing(Number(id))
      .then(setListing)
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) {
    return (
      <div className="page">
        <div className="empty-state">
          <div className="empty-state__icon">😕</div>
          <p>Listing not found — it may have been removed from Bikroy.</p>
          <Link to="/search" className="btn btn--primary" style={{ marginTop: 12 }}>
            Back to search
          </Link>
        </div>
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="page">
        <div className="skeleton" style={{ height: 320, borderRadius: 18 }} />
      </div>
    );
  }

  const priceGapPct =
    listing.predicted_price && listing.predicted_price > 0
      ? Math.round(((listing.predicted_price - listing.price) / listing.predicted_price) * 100)
      : null;

  const deal = dealLabel(listing);

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <div className="page__header">
        <h1>{listing.raw_title}</h1>
        <p className="page__subtitle">
          {listing.city} · {listing.condition_clean} · {listing.storage}
        </p>
      </div>

      {listing.is_suspicious && (
        <div className="card" style={{ borderColor: "var(--status-bad)", background: "rgba(220,76,76,0.06)" }}>
          <strong>⚠ Flagged as potentially suspicious</strong>
          <p className="muted" style={{ marginTop: 6, marginBottom: 0, fontSize: 13.5 }}>
            The title mentions "box open" and the price sits in the top 20% of its price tier — worth
            double-checking the actual condition before buying.
          </p>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <div className="card__title">Asking Price</div>
          <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: "-0.02em" }}>
            {formatPrice(listing.price)}
          </div>
          {deal && (
            <div style={{ marginTop: 12 }}>
              <DealScoreBadge listing={listing} />
            </div>
          )}
        </div>

        <div className="card">
          <div className="card__title">BikroyLens Fair Price Estimate</div>
          {listing.predicted_price ? (
            <>
              <div style={{ fontSize: 22, fontWeight: 800 }}>{formatPrice(listing.predicted_price)}</div>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                Fair range: {formatPrice(listing.fair_price_min)} – {formatPrice(listing.fair_price_max)}
              </div>
              {priceGapPct !== null && (
                <p className="prose prose--muted" style={{ marginTop: 10, marginBottom: 0 }}>
                  This listing is priced{" "}
                  <strong style={{ color: priceGapPct > 0 ? "var(--status-good)" : "var(--status-bad)" }}>
                    {Math.abs(priceGapPct)}% {priceGapPct > 0 ? "below" : "above"}
                  </strong>{" "}
                  our model's fair price estimate for a phone with these exact specs.
                </p>
              )}
            </>
          ) : (
            <p className="muted">Not yet scored — this listing is too new or missing key details.</p>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card__title">Listing Details</div>
        <table className="table">
          <tbody>
            <tr>
              <td className="muted">Brand</td>
              <td>{listing.brand || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Model</td>
              <td>{listing.model || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Storage</td>
              <td>{listing.storage || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Condition</td>
              <td>{listing.condition_clean || listing.condition_raw || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Location</td>
              <td>{listing.location || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Posted</td>
              <td>{listing.posted_date || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Seller type</td>
              <td>{listing.seller_type || "—"}</td>
            </tr>
            <tr>
              <td className="muted">Photos</td>
              <td>{listing.photo_count ?? "—"}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <a href={listing.url} target="_blank" rel="noreferrer" className="btn btn--primary">
        View original listing on Bikroy ↗
      </a>
    </div>
  );
}
