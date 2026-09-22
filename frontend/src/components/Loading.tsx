export function CardSkeleton() {
  return <div className="skeleton" style={{ height: 160, borderRadius: 18 }} />;
}

export function GridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="listing-grid">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function EmptyState({ icon = "🔍", message }: { icon?: string; message: string }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">{icon}</div>
      <p>{message}</p>
    </div>
  );
}
