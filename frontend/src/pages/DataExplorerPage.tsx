import { useEffect, useState } from "react";
import { getObservations, getSummary } from "../api/endpoints";
import { CoverageNote } from "../components/CoverageNote";
import { FieldList } from "../components/FieldList";
import { Pagination } from "../components/Pagination";
import { SeriesChart } from "../components/SeriesChart";
import { EndpointState, StateMessage, stationIdle } from "../components/StateMessage";
import { ThresholdNote } from "../components/ThresholdNote";
import { PROJECT_MIN_HOURS_PER_DAY, PROJECT_THRESHOLD_UG_M3 } from "../config";
import { useAppData } from "../context/AppData";
import { exceedsLabel, formatCount, formatNumber, formatWhen, isMicrogramUnit } from "../format";
import { useRequest } from "../hooks/useRequest";

const PAGE_SIZE = 50;

function rangeError(from: string, to: string): string | null {
  if (!from || !to) return null;
  if (from > to) return "The start date is after the end date.";
  const days = (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000;
  if (days > 366) return "Choose a range of 366 days or fewer so the daily series stays bounded.";
  return null;
}

export function DataExplorerPage() {
  const { selectedStationId, selectedStation, refreshKey, stations } = useAppData();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const filterKey = `${selectedStationId ?? ""}|${from}|${to}`;
  const [seenFilter, setSeenFilter] = useState(filterKey);
  if (filterKey !== seenFilter) {
    setSeenFilter(filterKey);
    setPage(1);
  }

  const invalid = rangeError(from, to);
  const enabled = selectedStationId != null && invalid == null;

  const summary = useRequest(
    () => getSummary({ station_id: selectedStationId as number, from, to }),
    [selectedStationId, from, to, refreshKey],
    enabled,
  );
  const observations = useRequest(
    () =>
      getObservations({
        station_id: selectedStationId as number,
        from,
        to,
        page,
        page_size: PAGE_SIZE,
      }),
    [selectedStationId, from, to, page, refreshKey],
    enabled,
  );

  useEffect(() => {
    document.title = "Data Explorer · AirCast India";
  }, []);

  const hold = (endpoint: string) =>
    invalid ? (
      <StateMessage tone="warning" title="Date range">
        {invalid} {endpoint} is not sent until the range is valid.
      </StateMessage>
    ) : (
      stationIdle(stations, endpoint)
    );

  const summaryData = summary.state.status === "ready" ? summary.state.data : null;
  const table = observations.state.status === "ready" ? observations.state.data : null;
  const threshold = summaryData?.threshold_ug_m3 ?? null;
  const minHours = summaryData?.min_hours_per_day ?? PROJECT_MIN_HOURS_PER_DAY;
  const quality = summaryData?.quality;

  return (
    <div>
      <header className="page-head">
        <h1>Data Explorer</h1>
        <p className="lede">
          Inspect measured hourly PM2.5, the daily means built from those hours, and the coverage rule used before a day
          can train or score the forecast.
        </p>
      </header>

      <div className="toolbar">
        <label className="field">
          <span>From</span>
          <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </label>
        <label className="field">
          <span>To</span>
          <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </label>
      </div>
      <p className="meta">Leave the dates empty to request the backend&apos;s default window. Hourly rows are requested {PAGE_SIZE} at a time.</p>
      {invalid && (
        <StateMessage tone="warning" title="Date range">
          {invalid}
        </StateMessage>
      )}

      <section className="tile">
        <div className="section-head">
          <h2>Coverage</h2>
          <p>Valid, invalid, and missing-hour figures are shown only when the summary includes them.</p>
        </div>
        <EndpointState state={summary.state} endpoint="GET /api/summary" idle={hold("GET /api/summary")}>
          {summaryData &&
            (quality ? (
              <FieldList
                items={[
                  { label: "Valid readings", value: formatCount(quality.valid_readings) },
                  { label: "Invalid readings", value: formatCount(quality.invalid_readings) },
                  { label: "Missing hours", value: formatCount(quality.missing_hours) },
                  { label: "Expected hours", value: formatCount(quality.expected_hours) },
                  { label: "Latest timestamp", value: formatWhen(quality.latest_timestamp) },
                  {
                    label: "Coverage window",
                    value: `${formatWhen(summaryData.freshness?.coverage_start)} to ${formatWhen(summaryData.freshness?.coverage_end)}`,
                  },
                ]}
              />
            ) : (
              <p className="meta">This summary did not include a quality object.</p>
            ))}
        </EndpointState>
        {quality?.missing_hour_timestamps && quality.missing_hour_timestamps.length > 0 && (
          <div className="missing-list">
            <h3>Reported missing hours</h3>
            <ul>
              {quality.missing_hour_timestamps.slice(0, 12).map((stamp) => (
                <li key={stamp}>{formatWhen(stamp)}</li>
              ))}
            </ul>
            {quality.missing_hour_timestamps.length > 12 && (
              <p className="meta">
                {quality.missing_hour_timestamps.length.toLocaleString("en-IN")} timestamps were listed
                {quality.missing_hours != null ? ` out of ${formatCount(quality.missing_hours)} missing hours` : ""}.
              </p>
            )}
          </div>
        )}
        <CoverageNote reported={summaryData?.min_hours_per_day} />
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Daily mean PM2.5</h2>
          <p>Each point is a measured daily mean. The threshold line is the hazard configuration, not a prediction.</p>
        </div>
        <EndpointState state={summary.state} endpoint="GET /api/summary" idle={hold("GET /api/summary")}>
          {summaryData && (
            <>
              <SeriesChart
                ariaLabel="Measured daily mean PM2.5 and the configured threshold"
                emptyMessage="No daily means were returned for this station and date range."
                threshold={threshold ?? PROJECT_THRESHOLD_UG_M3}
                thresholdLabel={threshold == null ? "Project configuration threshold" : "API threshold"}
                points={summaryData.daily_series.map((point) => ({ label: point.date, value: point.pm25_daily_mean }))}
              />
              {summaryData.daily_series.length > 0 && (
                <div className="table-wrap table-limit">
                  <table>
                    <caption>Daily means and the valid hourly readings that contribute to each one</caption>
                    <thead>
                      <tr>
                        <th scope="col">Date</th>
                        <th scope="col">Daily mean (µg/m³)</th>
                        <th scope="col">Valid hours</th>
                        <th scope="col">Coverage rule</th>
                        <th scope="col">Measured exceedance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summaryData.daily_series.map((point) => (
                        <tr key={point.date}>
                          <td>{point.date}</td>
                          <td className="num">{formatNumber(point.pm25_daily_mean, 1)}</td>
                          <td className="num">{formatCount(point.valid_hours)}</td>
                          <td>
                            {point.valid_hours == null
                              ? "—"
                              : point.valid_hours >= minHours
                                ? `Meets ${minHours} h`
                                : `Below ${minHours} h`}
                          </td>
                          <td>{exceedsLabel(point.exceeds)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </EndpointState>
        <ThresholdNote reported={threshold} />
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Hourly observations</h2>
          <p>Measured PM2.5 rows for the selected station. The table requests one page from the API and does not load the full archive into the browser.</p>
        </div>
        <EndpointState state={observations.state} endpoint="GET /api/observations" idle={hold("GET /api/observations")}>
          {table && table.items.length === 0 && (
            <StateMessage title="No observations">
              The API returned no hourly rows for this station and date range.
            </StateMessage>
          )}
          {table && table.items.length > 0 && (
            <>
              <SeriesChart
                ariaLabel="Hourly PM2.5 on the current results page"
                emptyMessage="This page of hourly observations has no PM2.5 values."
                threshold={threshold ?? PROJECT_THRESHOLD_UG_M3}
                thresholdLabel="Configured threshold"
                points={table.items.map((row) => ({
                  label: row.timestamp,
                  value: row.pm25,
                }))}
              />
              <div className="table-wrap">
                <table>
                  <caption>
                    Hourly PM2.5 observations, page {table.page}, {table.page_size} rows per page
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Timestamp</th>
                      <th scope="col">Station</th>
                      <th scope="col">PM2.5 (µg/m³)</th>
                      <th scope="col">Unit</th>
                      <th scope="col">Valid</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.items.map((row) => {
                      const unit = row.unit ?? table.unit;
                      return (
                        <tr key={`${row.location_id}-${row.timestamp}`}>
                          <td>{formatWhen(row.timestamp)}</td>
                          <td>{row.station_name ?? selectedStation?.name ?? String(row.location_id)}</td>
                          <td className="num">
                            {formatNumber(row.pm25, 1)}
                            {unit && !isMicrogramUnit(unit) ? ` (${unit})` : ""}
                          </td>
                          <td>{unit && isMicrogramUnit(unit) ? "µg/m³" : unit ?? "Not reported"}</td>
                          <td>{row.valid == null ? "Not reported" : row.valid ? "Valid" : "Invalid"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={table.page_size} total={table.total} onPage={setPage} />
            </>
          )}
        </EndpointState>
      </section>
    </div>
  );
}
