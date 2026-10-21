import { useAppData } from "../context/AppData";

export function StationSelect({ compact = false }: { compact?: boolean }) {
  const { stations, selectedStationId, setSelectedStationId } = useAppData();
  const ready = stations.status === "ready";
  const list = ready ? stations.data.stations : [];
  const disabled = !ready || list.length === 0;

  let placeholder = "Loading stations";
  if (stations.status === "not_configured") placeholder = "Awaiting backend";
  else if (stations.status === "not_connected") placeholder = "Stations not connected";
  else if (stations.status === "error") placeholder = "Stations unavailable";
  else if (ready && list.length === 0) placeholder = "No stations returned";

  return (
    <label className={compact ? "field field-compact" : "field"}>
      <span>{compact ? "Selected station" : "Monitoring station"}</span>
      <select
        value={selectedStationId ?? ""}
        disabled={disabled}
        onChange={(event) => {
          const next = Number(event.target.value);
          setSelectedStationId(Number.isInteger(next) ? next : null);
        }}
      >
        {disabled && <option value="">{placeholder}</option>}
        {list.map((station) => (
          <option key={station.location_id} value={station.location_id}>
            {station.name} ({station.location_id})
          </option>
        ))}
      </select>
    </label>
  );
}
