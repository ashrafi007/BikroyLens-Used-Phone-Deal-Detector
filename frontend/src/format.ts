export function formatPrice(n?: number | null): string {
  if (n === undefined || n === null) return "—";
  return "৳" + Math.round(n).toLocaleString("en-US");
}

export function formatDate(d?: string | null): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return d;
  }
}
