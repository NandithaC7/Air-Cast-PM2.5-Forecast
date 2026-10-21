import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AttributionItem, ComparisonRow, CurvePointBlock, RuntimeRow } from "../types";
import { formatMetric } from "../format";
import { StateMessage } from "./StateMessage";

const COLORS = ["#2f4a3c", "#5f7a68", "#7a5a20", "#3d5a80"];

export function ComparisonBars({ rows }: { rows: ComparisonRow[] }) {
  if (!rows.length) {
    return <StateMessage title="Comparison unavailable">No model comparison rows were returned.</StateMessage>;
  }
  const data = rows.map((row) => ({
    name: row.display_name.replace(" ", "\n"),
    Precision: row.precision,
    Recall: row.recall,
    F1: row.f1,
    Accuracy: row.accuracy,
  }));
  return (
    <div className="chart-frame" role="img" aria-label="Grouped bar chart of precision, recall, F1, and accuracy">
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value: number) => formatMetric(value)} />
          <Legend />
          <Bar dataKey="Precision" fill={COLORS[0]} />
          <Bar dataKey="Recall" fill={COLORS[1]} />
          <Bar dataKey="F1" fill={COLORS[2]} />
          <Bar dataKey="Accuracy" fill={COLORS[3]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RuntimeBars({ rows }: { rows: RuntimeRow[] }) {
  if (!rows.length) {
    return <StateMessage title="Runtime unavailable">No runtime measurements were returned.</StateMessage>;
  }
  return (
    <div className="chart-frame" role="img" aria-label="Training and prediction duration by model">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows.map((row) => ({ name: row.display_name, Train: row.train_seconds, Predict: row.predict_seconds }))}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="Train" fill="#2f4a3c" />
          <Bar dataKey="Predict" fill="#7a5a20" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RocChart({ curves, model }: { curves: Record<string, CurvePointBlock>; model: string }) {
  const block = curves[model];
  if (!block?.roc) {
    return <StateMessage title="ROC unavailable">{block?.roc_unavailable_reason ?? "No ROC curve was returned for this model."}</StateMessage>;
  }
  const data = block.roc.false_positive_rate.map((fpr, index) => ({
    fpr,
    tpr: block.roc!.true_positive_rate[index],
    random: fpr,
  }));
  return (
    <div className="chart-frame" role="img" aria-label={`ROC curve for ${model}`}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={{ fontSize: 12 }} />
          <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="tpr" stroke="#2f4a3c" dot={false} name="Model" />
          <Line type="monotone" dataKey="random" stroke="#999" strokeDasharray="4 4" dot={false} name="Random" />
        </LineChart>
      </ResponsiveContainer>
      <p className="meta">
        Score kind: {block.score_kind ?? "not reported"}
        {block.roc.auc != null ? ` · AUC ${formatMetric(block.roc.auc)}` : ""}
      </p>
    </div>
  );
}

export function PrChart({ curves, model }: { curves: Record<string, CurvePointBlock>; model: string }) {
  const block = curves[model];
  if (!block?.pr) {
    return <StateMessage title="PR curve unavailable">{block?.pr_unavailable_reason ?? "No precision-recall curve was returned."}</StateMessage>;
  }
  const data = block.pr.recall.map((recall, index) => ({
    recall,
    precision: block.pr!.precision[index],
    baseline: block.pr!.prevalence,
  }));
  return (
    <div className="chart-frame" role="img" aria-label={`Precision-recall curve for ${model}`}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis dataKey="recall" type="number" domain={[0, 1]} tick={{ fontSize: 12 }} />
          <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="precision" stroke="#2f4a3c" dot={false} name="Precision" />
          <Line type="monotone" dataKey="baseline" stroke="#7a5a20" strokeDasharray="4 4" dot={false} name="Hazard prevalence" />
        </LineChart>
      </ResponsiveContainer>
      <p className="meta">
        Average precision {formatMetric(block.pr.average_precision)}
        {block.pr.prevalence != null ? ` · test prevalence ${formatMetric(block.pr.prevalence)}` : ""}
      </p>
    </div>
  );
}

export function ImportanceBars({ items, kind, note }: { items: AttributionItem[]; kind: string; note?: string }) {
  if (kind === "unavailable" || items.length === 0) {
    return <StateMessage title="Attribution unavailable">{note ?? "This model does not expose a supported importance measure."}</StateMessage>;
  }
  const ranked = [...items].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 12);
  return (
    <div className="chart-frame" role="img" aria-label="Feature attribution">
      {note && <p className="meta">{note}</p>}
      <ResponsiveContainer width="100%" height={Math.max(220, ranked.length * 28)}>
        <BarChart data={ranked} layout="vertical" margin={{ left: 24 }}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="feature" width={150} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="value" fill="#2f4a3c" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendChart({
  points,
}: {
  points: { date: string; daily_mean_pm25: number; exceeds_threshold: number }[];
}) {
  if (!points.length) {
    return <StateMessage title="Trend unavailable">No historical daily series was returned.</StateMessage>;
  }
  return (
    <div className="chart-frame" role="img" aria-label="Historical daily mean PM2.5">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={points}>
          <CartesianGrid stroke="#dddcd4" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="daily_mean_pm25" stroke="#2f4a3c" dot={false} name="Measured daily mean" />
        </LineChart>
      </ResponsiveContainer>
      <p className="meta">Historical observations only. This series is not a forecast.</p>
    </div>
  );
}
