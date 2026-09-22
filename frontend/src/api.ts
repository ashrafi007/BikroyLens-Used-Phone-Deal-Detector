import axios from "axios";

// Local dev talks to the FastAPI server on :8000 directly. In production
// this gets replaced with the deployed Render URL via an env var.
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export const api = axios.create({ baseURL: API_BASE });

export interface Listing {
  id: number;
  url: string;
  raw_title: string;
  price: number;
  condition_raw?: string;
  condition_clean?: string;
  location?: string;
  city?: string;
  posted_date?: string;
  photo_count?: number;
  seller_type?: string;
  brand?: string;
  model?: string;
  storage?: string;
  price_tier?: string;
  is_suspicious: boolean;
  predicted_price?: number;
  fair_price_min?: number;
  fair_price_max?: number;
  deal_score?: number;
}

export interface SearchResponse {
  total: number;
  fair_price_min?: number;
  fair_price_max?: number;
  median_price?: number;
  listings: Listing[];
}

export interface StatsResponse {
  total_unique_listings: number;
  total_scrape_days: number;
  last_scraped?: string;
  brands: { brand: string; count: number }[];
  cities: { city: string; count: number }[];
  avg_deal_score?: number;
}

export interface InsightsResponse {
  brand?: string;
  model?: string;
  total_listings: number;
  avg_price?: number;
  median_price?: number;
  min_price?: number;
  max_price?: number;
  by_city: { city: string; count: number; avg_price: number }[];
  by_condition: { condition_clean: string; count: number; avg_price: number }[];
  price_trend: { day: string; avg_price: number; count: number }[];
  best_deals: Listing[];
}

export interface SearchParams {
  brand?: string;
  model?: string;
  city?: string;
  condition?: string;
  min_price?: number;
  max_price?: number;
  sort?: "deal_score" | "price" | "newest";
  limit?: number;
  offset?: number;
}

export const fetchStats = () => api.get<StatsResponse>("/api/stats").then((r) => r.data);

export const fetchSearch = (params: SearchParams) =>
  api.get<SearchResponse>("/api/search", { params }).then((r) => r.data);

export const fetchDeals = (limit = 20) =>
  api.get<Listing[]>("/api/deals", { params: { limit } }).then((r) => r.data);

export const fetchListing = (id: number) =>
  api.get<Listing>(`/api/listings/${id}`).then((r) => r.data);

export const fetchInsights = (params: { brand?: string; model?: string }) =>
  api.get<InsightsResponse>("/api/insights", { params }).then((r) => r.data);

export const BRANDS = ["Apple", "Samsung", "Xiaomi", "OnePlus", "Nothing Phone"];
export const CITIES = ["Dhaka", "Chattogram", "Rajshahi"];
