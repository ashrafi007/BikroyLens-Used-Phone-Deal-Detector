import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { fetchInsights, BRANDS, type InsightsResponse } from "../api";
import ListingCard from "../components/ListingCard";
import { formatPrice, formatDate } from "../format";
import { EmptyState } from "../components/Loading";

export default function Insights() {
  const [brand, setBrand] = useState(BRANDS[0]);
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchInsights({ brand })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [brand]);

  const trendData = (data?.price_trend ?? []).map((t) => ({
    ...t,
    day: formatDate(t.day),
    avg_price: Math.round(t.avg_price),
  }));

  return (
    <div className="page">
      <div className="page__header">
        <h1>Market Insights</h1>
        <p className="page__subtitle">Price trends and breakdowns, computed fresh from every day's data.</p>
      </div>

      <div className="filter-row">
        {BRANDS.map((b) => (
          <button
            key={b}
            className={"filter-pill" + (brand === b ? " filter-pill--active" : "")}
            onClick={() => setBrand(b)}
          >
            {b}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="skeleton" style={{ height: 300, borderRadius: 18 }} />
      ) : !data || data.total_listings === 0 ? (
        <EmptyState message="Not enough data for this brand yet." />
      ) : (
        <>
          <div className="stat-row">
            <div className="stat-tile">
              <div className="stat-tile__value">{data.total_listings}</div>
              <div className="stat-tile__label">Listings tracked</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile__value">{formatPrice(data.median_price)}</div>
              <div className="stat-tile__label">Median price</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile__value">{formatPrice(data.min_price)}</div>
              <div className="stat-tile__label">Lowest price</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile__value">{formatPrice(data.max_price)}</div>
              <div className="stat-tile__label">Highest price</div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card__title">Price trend over time</div>
              {trendData.length > 1 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
                    <XAxis dataKey="day" fontSize={11} stroke="var(--text-muted)" />
                    <YAxis
                      fontSize={11}
                      stroke="var(--text-muted)"
                      tickFormatter={(v) => `${Math.round(v / 1000)}k`}
                    />
                    <Tooltip formatter={(v: number) => formatPrice(v)} />
                    <Line type="monotone" dataKey="avg_price" stroke="var(--accent)" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="muted">Trend needs a few more days of data to draw a meaningful line.</p>
              )}
            </div>

            <div className="card">
              <div className="card__title">Average price by city</div>
              {data.by_city.length > 0 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={data.by_city.map((c) => ({ ...c, avg_price: Math.round(c.avg_price) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
                    <XAxis dataKey="city" fontSize={11} stroke="var(--text-muted)" />
                    <YAxis
                      fontSize={11}
                      stroke="var(--text-muted)"
                      tickFormatter={(v) => `${Math.round(v / 1000)}k`}
                    />
                    <Tooltip formatter={(v: number) => formatPrice(v)} />
                    <Bar dataKey="avg_price" fill="var(--accent)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="muted">No city breakdown available.</p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card__title">By condition</div>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Condition</th>
                    <th>Listings</th>
                    <th>Avg. price</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_condition.map((c) => (
                    <tr key={c.condition_clean}>
                      <td style={{ textTransform: "capitalize" }}>{c.condition_clean || "unknown"}</td>
                      <td>{c.count}</td>
                      <td>{formatPrice(c.avg_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {data.best_deals.length > 0 && (
            <>
              <div className="card__title" style={{ fontSize: 18 }}>
                Best {brand} deals right now
              </div>
              <div className="listing-grid">
                {data.best_deals.map((d) => (
                  <ListingCard key={d.id} listing={d} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
