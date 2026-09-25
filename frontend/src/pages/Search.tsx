import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { fetchSearch, BRANDS, CITIES, type Listing, type SearchResponse } from "../api";
import DealScoreBadge from "../components/DealScore";
import { formatPrice } from "../format";
import { EmptyState } from "../components/Loading";

const CONDITIONS = ["used", "mint", "refurbished", "good"];
const columnHelper = createColumnHelper<Listing>();

const columns = [
  columnHelper.accessor("raw_title", {
    header: "Listing",
    cell: (info) => (
      <Link to={`/listing/${info.row.original.id}`} style={{ fontWeight: 600 }}>
        {info.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("city", { header: "City", cell: (info) => info.getValue() || "—" }),
  columnHelper.accessor("condition_clean", { header: "Condition", cell: (info) => info.getValue() || "—" }),
  columnHelper.accessor("price", { header: "Price", cell: (info) => formatPrice(info.getValue()) }),
  columnHelper.accessor("deal_score", {
    header: "Deal Score",
    cell: (info) => <DealScoreBadge listing={info.row.original} />,
  }),
];

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<SearchResponse | null>(null);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [loading, setLoading] = useState(true);

  const brand = searchParams.get("brand") || "";
  const city = searchParams.get("city") || "";
  const condition = searchParams.get("condition") || "";
  const model = searchParams.get("model") || "";
  const minPrice = searchParams.get("min_price") || "";
  const maxPrice = searchParams.get("max_price") || "";

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  useEffect(() => {
    setLoading(true);
    fetchSearch({
      brand: brand || undefined,
      city: city || undefined,
      condition: condition || undefined,
      model: model || undefined,
      min_price: minPrice ? Number(minPrice) : undefined,
      max_price: maxPrice ? Number(maxPrice) : undefined,
      sort: "deal_score",
      limit: 100,
    })
      .then(setData)
      .catch(() => setData({ total: 0, listings: [] }))
      .finally(() => setLoading(false));
  }, [brand, city, condition, model, minPrice, maxPrice]);

  const table = useReactTable({
    data: data?.listings ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="page">
      <div className="page__header">
        <h1>Search Listings</h1>
        <p className="page__subtitle">
          {data ? `${data.total.toLocaleString()} listings match your filters` : "Loading…"}
        </p>
      </div>

      <div className="card">
        <div className="filter-row" style={{ marginBottom: 12 }}>
          <span className="muted" style={{ fontSize: 12.5, alignSelf: "center", marginRight: 4 }}>
            Brand:
          </span>
          <button
            className={"filter-pill" + (!brand ? " filter-pill--active" : "")}
            onClick={() => updateParam("brand", "")}
          >
            All
          </button>
          {BRANDS.map((b) => (
            <button
              key={b}
              className={"filter-pill" + (brand === b ? " filter-pill--active" : "")}
              onClick={() => updateParam("brand", b)}
            >
              {b}
            </button>
          ))}
        </div>

        <div className="filter-row" style={{ marginBottom: 12 }}>
          <span className="muted" style={{ fontSize: 12.5, alignSelf: "center", marginRight: 4 }}>
            City:
          </span>
          <button
            className={"filter-pill" + (!city ? " filter-pill--active" : "")}
            onClick={() => updateParam("city", "")}
          >
            All
          </button>
          {CITIES.map((c) => (
            <button
              key={c}
              className={"filter-pill" + (city === c ? " filter-pill--active" : "")}
              onClick={() => updateParam("city", c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="filter-row" style={{ marginBottom: 14 }}>
          <span className="muted" style={{ fontSize: 12.5, alignSelf: "center", marginRight: 4 }}>
            Condition:
          </span>
          <button
            className={"filter-pill" + (!condition ? " filter-pill--active" : "")}
            onClick={() => updateParam("condition", "")}
          >
            All
          </button>
          {CONDITIONS.map((c) => (
            <button
              key={c}
              className={"filter-pill" + (condition === c ? " filter-pill--active" : "")}
              onClick={() => updateParam("condition", c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="form-row" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input
            type="number"
            placeholder="Min price (৳)"
            defaultValue={minPrice}
            onBlur={(e) => updateParam("min_price", e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: 9,
              border: "1px solid var(--card-border)",
              fontSize: 13,
              width: 140,
            }}
          />
          <input
            type="number"
            placeholder="Max price (৳)"
            defaultValue={maxPrice}
            onBlur={(e) => updateParam("max_price", e.target.value)}
            style={{
              padding: "9px 12px",
              borderRadius: 9,
              border: "1px solid var(--card-border)",
              fontSize: 13,
              width: 140,
            }}
          />
        </div>
      </div>

      {data && data.fair_price_min !== undefined && data.fair_price_min !== null && (
        <div className="card">
          <div className="card__title">Fair price range for this search</div>
          <div style={{ fontSize: 22, fontWeight: 800 }}>
            {formatPrice(data.fair_price_min)} – {formatPrice(data.fair_price_max)}
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            Median asking price: {formatPrice(data.median_price)}
          </div>
        </div>
      )}

      <div className="card">
        {loading ? (
          <p className="muted">Loading listings…</p>
        ) : !data || data.listings.length === 0 ? (
          <EmptyState message="No listings match these filters. Try widening your search." />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th key={header.id} onClick={header.column.getToggleSortingHandler()}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{ asc: " ↑", desc: " ↓" }[header.column.getIsSorted() as string] ?? ""}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
