import type { ReactNode } from "react";
import type { RequestState } from "../types";

export function stationIdle(stations: RequestState<unknown>, endpoint: string): ReactNode {
  if (stations.status === "loading") {
    return <StateMessage title="Loading">Waiting for GET /api/stations before calling {endpoint}.</StateMessage>;
  }
  if (stations.status === "not_configured") {
    return (
      <StateMessage title="Awaiting backend">
        {endpoint} runs after the API base URL is set and a station list is returned. No values are simulated.
      </StateMessage>
    );
  }
  if (stations.status === "not_connected") {
    return (
      <StateMessage tone="warning" title="Not connected">
        {stations.message} {endpoint} stays idle until the station list loads.
      </StateMessage>
    );
  }
  if (stations.status === "error") {
    return (
      <StateMessage tone="error" title="API error">
        {stations.message}
      </StateMessage>
    );
  }
  return (
    <StateMessage title="No station available">
      GET /api/stations did not return a station, so {endpoint} was not called.
    </StateMessage>
  );
}

export function StateMessage({
  tone = "neutral",
  title,
  children,
}: {
  tone?: "neutral" | "warning" | "error";
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={`state state-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <p className="state-title">{title}</p>
      {children && <div className="state-body">{children}</div>}
    </div>
  );
}

export function EndpointState({
  state,
  endpoint,
  idle,
  children,
}: {
  state: RequestState<unknown>;
  endpoint: string;
  idle?: ReactNode;
  children: ReactNode;
}) {
  if (state.status === "idle") {
    return (
      idle ?? (
        <StateMessage title="Waiting for a station">
          This block calls {endpoint} after a monitoring station is available.
        </StateMessage>
      )
    );
  }
  if (state.status === "loading") {
    return <StateMessage title="Loading">Requesting {endpoint}.</StateMessage>;
  }
  if (state.status === "not_configured") {
    return (
      <StateMessage title="Awaiting backend">
        {state.message} This block calls {endpoint}. No values are simulated.
      </StateMessage>
    );
  }
  if (state.status === "not_connected") {
    return (
      <StateMessage tone="warning" title="Not connected">
        {state.message} Endpoint: {endpoint}.
      </StateMessage>
    );
  }
  if (state.status === "error") {
    return (
      <StateMessage tone="error" title="API error">
        {state.message}
      </StateMessage>
    );
  }
  return children;
}
