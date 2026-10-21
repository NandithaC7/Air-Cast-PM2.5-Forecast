import { formatNumber } from "../format";

export interface BarItem {
  label: string;
  value: number | null;
}

export function BarChart({
  items,
  ariaLabel,
  emptyMessage,
}: {
  items: BarItem[];
  ariaLabel: string;
  emptyMessage: string;
}) {
  const measured = items.filter((item) => item.value != null && Number.isFinite(item.value));
  if (measured.length === 0) {
    return (
      <div className="chart-empty">
        <p>{emptyMessage}</p>
      </div>
    );
  }
  const max = Math.max(...measured.map((item) => item.value as number), 1);
  return (
    <figure className="bars" aria-label={ariaLabel}>
      {items.map((item) => {
        const width = item.value == null ? 0 : Math.max(4, (item.value / max) * 100);
        return (
          <div key={item.label} className="bar-row">
            <span className="bar-label">{item.label}</span>
            <span className="bar-track">
              {item.value == null ? (
                <i className="bar-missing">Not reported</i>
              ) : (
                <i className="bar-fill" style={{ width: `${width}%` }} />
              )}
            </span>
            <span className="bar-value">{item.value == null ? "—" : formatNumber(item.value, 1)}</span>
          </div>
        );
      })}
      <figcaption>Latest measured daily mean PM2.5 (µg/m³) for stations returned by the API.</figcaption>
    </figure>
  );
}
