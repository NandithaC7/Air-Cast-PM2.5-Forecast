import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getPipelineStatus, getStations } from "../api/endpoints";
import { useRequest } from "../hooks/useRequest";
import type { PipelineResponse, RequestState, Station, StationsResponse } from "../types";

interface AppDataValue {
  refreshKey: number;
  refresh: () => void;
  selectedStationId: number | null;
  setSelectedStationId: (id: number | null) => void;
  selectedStation: Station | null;
  stations: RequestState<StationsResponse>;
  pipeline: RequestState<PipelineResponse>;
}

const AppDataContext = createContext<AppDataValue | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedStationId, setSelectedStationId] = useState<number | null>(null);
  const stations = useRequest(() => getStations(), [refreshKey]);
  const pipeline = useRequest(() => getPipelineStatus(), [refreshKey]);

  useEffect(() => {
    if (stations.state.status !== "ready") return;
    const list = stations.state.data.stations;
    setSelectedStationId((current) => {
      if (current != null && list.some((station) => station.location_id === current)) return current;
      return list[0]?.location_id ?? null;
    });
  }, [stations.state]);

  const selectedStation =
    stations.state.status === "ready"
      ? stations.state.data.stations.find((station) => station.location_id === selectedStationId) ?? null
      : null;

  const value = useMemo<AppDataValue>(
    () => ({
      refreshKey,
      refresh: () => setRefreshKey((value) => value + 1),
      selectedStationId,
      setSelectedStationId,
      selectedStation,
      stations: stations.state,
      pipeline: pipeline.state,
    }),
    [refreshKey, selectedStationId, selectedStation, stations.state, pipeline.state],
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData(): AppDataValue {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used within AppDataProvider");
  return value;
}
