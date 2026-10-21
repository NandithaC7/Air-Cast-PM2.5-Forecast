import { formatConcentration, formatNumber } from "../format";
import { IconChart } from "./Icons";

export interface ChartPoint {
  label: string;
  value: number | null;
}

const WIDTH = 640;
const HEIGHT = 228;
const PAD = { left: 52, right: 16, top: 16, bottom: 36 };

export function SeriesChart({
  points,
  threshold,
  thresholdLabel,
  ariaLabel,
  emptyMessage,
}: {
  points: ChartPoint[];
  threshold: number | null;
  thresholdLabel: string;
  ariaLabel: string;
  emptyMessage: string;
}) {
  const measured = points.filter((point) => point.value != null && Number.isFinite(point.value));
  if (measured.length === 0) {
    return (
      <div className="chart-empty">
        <IconChart />
        <p>{emptyMessage}</p>
        {threshold != null && (
          <p className="chart-empty-note">
            {thresholdLabel}: {formatConcentration(threshold, "ug/m3")}. No measured line is drawn.
          </p>
        )}
      </div>
    );
  }

  const values = measured.map((point) => point.value as number);
  const domainValues = threshold == null ? values : [...values, threshold];
  let min = Math.min(...domainValues, 0);
  let max = Math.max(...domainValues);
  if (min === max) max = min + 1;
  const pad = (max - min) * 0.08;
  min -= pad;
  max += pad;

  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const xAt = (index: number) =>
    PAD.left + (points.length === 1 ? innerW / 2 : (index / (points.length - 1)) * innerW);
  const yAt = (value: number) => PAD.top + ((max - value) / (max - min)) * innerH;

  let path = "";
  let drawing = false;
  points.forEach((point, index) => {
    if (point.value == null || !Number.isFinite(point.value)) {
      drawing = false;
      return;
    }
    const command = drawing ? "L" : "M";
    path += `${command}${xAt(index).toFixed(1)},${yAt(point.value).toFixed(1)} `;
    drawing = true;
  });

  const ticks = [0, 1, 2, 3].map((step) => min + ((max - min) * step) / 3);
  const labelIndexes = points.length <= 2 ? points.map((_, index) => index) : [0, Math.floor((points.length - 1) / 2), points.length - 1];
  const last = measured[measured.length - 1];

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={ariaLabel}>
        <title>{ariaLabel}</title>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={yAt(tick)} y2={yAt(tick)} />
            <text className="tick" x={PAD.left - 8} y={yAt(tick) + 4} textAnchor="end">
              {formatNumber(tick, 0)}
            </text>
          </g>
        ))}
        {threshold != null && (
          <line
            className="threshold"
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={yAt(threshold)}
            y2={yAt(threshold)}
          />
        )}
        <path className="series" d={path.trim()} />
        {points.length <= 90 &&
          points.map((point, index) =>
            point.value == null ? null : (
              <circle key={`${point.label}-${index}`} className="point" cx={xAt(index)} cy={yAt(point.value)} r={2.5}>
                <title>
                  {point.label}: {formatConcentration(point.value, "ug/m3")}
                </title>
              </circle>
            ),
          )}
        {labelIndexes.map((index) => (
          <text key={points[index].label + index} className="tick" x={xAt(index)} y={HEIGHT - 10} textAnchor="middle">
            {points[index].label.slice(0, 10)}
          </text>
        ))}
      </svg>
      <figcaption className="legend">
        <span>
          <i className="swatch swatch-series" /> Measured PM2.5 (µg/m³)
        </span>
        <span>
          <i className="swatch swatch-threshold" /> {thresholdLabel}
          {threshold == null ? "" : `: ${formatConcentration(threshold, "ug/m3")}`}
        </span>
        <span>
          {measured.length} measured points. Latest {last.label}: {formatConcentration(last.value, "ug/m3")}.
        </span>
      </figcaption>
    </figure>
  );
}
