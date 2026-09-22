export default function StatTile({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__value">{value}</div>
      <div className="stat-tile__label">{label}</div>
    </div>
  );
}
