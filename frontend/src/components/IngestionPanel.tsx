import { INGESTION_FLOW } from "../config";
import { useAppData } from "../context/AppData";
import { formatCount, formatWhen, pipelineStatusLabel, statusTone } from "../format";
import type { PipelineStage } from "../types";
import { IconRadio } from "./Icons";
import { EndpointState } from "./StateMessage";

function pickIngestion(stages: PipelineStage[]): PipelineStage | undefined {
  return stages.find((stage) => stage.id === "ingestion") ?? stages.find((stage) => stage.id === "openaq_api");
}

export function IngestionPanel() {
  const { pipeline } = useAppData();
  const stages = pipeline.status === "ready" ? pipeline.data.stages : [];
  const byId = new Map(stages.map((stage) => [stage.id, stage]));
  const ingest = pickIngestion(stages);
  const pending = pipeline.status !== "ready";

  return (
    <section className="tile tile-wide">
      <div className="section-head">
        <h2>Live data ingestion</h2>
        <p>OpenAQ fetch status from GET /api/pipeline/status. This is not a simulated feed.</p>
      </div>
      <div className="ingest-hero">
        <span className="ingest-mark">
          <IconRadio />
        </span>
        <div>
          <p className="ingest-title">OpenAQ → AirCast</p>
          <p className="tile-detail">
            Latest successful fetch {formatWhen(ingest?.last_success_at)} · records {formatCount(ingest?.records)}
          </p>
        </div>
        <p className={`status-chip tone-${statusTone(pending ? "neutral" : ingest?.status ?? "not_reported")}`}>
          {pending
            ? pipeline.status === "loading"
              ? "Checking"
              : pipeline.status === "not_connected"
                ? "Not connected"
                : "Awaiting API"
            : pipelineStatusLabel(ingest?.status)}
        </p>
      </div>
      <EndpointState state={pipeline} endpoint="GET /api/pipeline/status">
        {pipeline.status === "ready" && (
          <p className="meta">Status document generated at {formatWhen(pipeline.data.generated_at)}.</p>
        )}
      </EndpointState>
      <ol className="flow">
        {INGESTION_FLOW.map((item, index) => {
          const stage = byId.get(item.id);
          const status = pending ? (pipeline.status === "loading" ? "loading" : "awaiting_backend") : stage?.status ?? "not_reported";
          return (
            <li key={item.id}>
              {index > 0 && <span className="flow-arrow" aria-hidden="true" />}
              <span className="flow-name">{item.title}</span>
              <span className={`flow-status tone-${statusTone(pending ? "neutral" : status)}`}>{pipelineStatusLabel(status)}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
