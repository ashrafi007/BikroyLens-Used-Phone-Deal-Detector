import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchStats, fetchDeals, BRANDS, CITIES, type StatsResponse, type Listing } from "../api";
import StatTile from "../components/StatTile";
import ListingCard from "../components/ListingCard";
import { GridSkeleton } from "../components/Loading";

export default function Home() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [deals, setDeals] = useState<Listing[] | null>(null);
  const [brand, setBrand] = useState("");
  const [city, setCity] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
    fetchDeals(6).then(setDeals).catch(() => setDeals([]));
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (brand) params.set("brand", brand);
    if (city) params.set("city", city);
    if (query) params.set("model", query);
    navigate(`/search?${params.toString()}`);
  }

  return (
    <div className="page">
      <section className="hero">
        <span className="hero__eyebrow">Bikroy.com · Real-time data</span>
        <h1>Know a fair price before you buy — or sell.</h1>
        <p>
          BikroyLens scrapes used-phone listings across Dhaka, Chattogram, and Rajshahi every day, then
          uses a machine learning model to estimate what each phone should actually cost — so you can spot
          a real deal instead of guessing.
        </p>

        <form className="search-bar" onSubmit={handleSearch}>
          <select value={brand} onChange={(e) => setBrand(e.target.value)}>
            <option value="">Any brand</option>
            {BRANDS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <select value={city} onChange={(e) => setCity(e.target.value)}>
            <option value="">Any city</option>
            {CITIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search a model, e.g. Galaxy S24"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn btn--primary" type="submit">
            Search
          </button>
        </form>
      </section>

      {stats && (
        <div className="stat-row">
          <StatTile value={stats.total_unique_listings.toLocaleString()} label="Listings tracked" />
          <StatTile value={stats.total_scrape_days} label="Days of data collected" />
          <StatTile value={stats.brands.length} label="Brands covered" />
          <StatTile value={stats.avg_deal_score ?? "—"} label="Avg. deal score" />
        </div>
      )}

      <div className="card__header-row">
        <h2 className="card__title" style={{ fontSize: 18 }}>
          🔥 Best deals right now
        </h2>
        <a href="/deals" className="btn btn--sm" onClick={(e) => { e.preventDefault(); navigate("/deals"); }}>
          See all deals →
        </a>
      </div>

      {deals === null ? (
        <GridSkeleton count={6} />
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
