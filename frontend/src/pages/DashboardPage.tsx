import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { getMetrics, getOverview, getSummary, postPrediction } from "../api/endpoints";
import { BarChart } from "../components/BarChart";
import { ConfusionTiles } from "../components/ConfusionMatrix";
import { FieldList } from "../components/FieldList";
import { ForecastControls } from "../components/ForecastControls";
import { IngestionPanel } from "../components/IngestionPanel";
import { SeriesChart } from "../components/SeriesChart";
import { EndpointState, StateMessage, stationIdle } from "../components/StateMessage";
import { PROJECT_THRESHOLD_UG_M3 } from "../config";
import { useAppData } from "../context/AppData";
import {
  addCalendarDay,
  formatConcentration,
  formatCount,
  formatElapsed,
  formatMetric,
  formatPercent,
  formatWhen,
  hazardLabel,
  modelDisplayName,
} from "../format";
import { useRequest } from "../hooks/useRequest";
import type { PredictV1Response, RequestState, Station, SummaryResponse } from "../types";

const PROBABILITY_MODEL = "random_forest";

function toErrorState(error: unknown): RequestState<PredictV1Response> {
  if (error instanceof ApiError) {
    if (error.kind === "not_configured") return { status: "not_configured", message: error.message };
    if (error.kind === "not_connected") return { status: "not_connected", message: error.message };
    return { status: "error", message: error.message };
  }
  return { status: "error", message: "The request failed before a response could be read." };
}

function probabilityHeadline(forecast: PredictV1Response | null, requested: boolean): string {
  if (!requested) return "—";
  if (!forecast) return "—";
  if (!forecast.available) return "Unavailable";
  if (forecast.probability_supported && forecast.probability != null) return formatPercent(forecast.probability);
  return "Probability not reported";
}

export function DashboardPage() {
  const { selectedStationId, selectedStation, refreshKey, stations } = useAppData();
  const enabled = selectedStationId != null;
  const overview = useRequest(() => getOverview(), [refreshKey]);
  const summary = useRequest(
    () => getSummary({ station_id: selectedStationId as number }),
    [selectedStationId, refreshKey],
    enabled,
  );
  const metrics = useRequest(
    () => getMetrics(selectedStationId as number),
    [selectedStationId, refreshKey],
    enabled,
  );
  const compareIds =
    stations.status === "ready" ? stations.data.stations.slice(0, 8).map((station) => station.location_id) : [];
  const comparison = useRequest(
    async () => {
      const list: Station[] = stations.status === "ready" ? stations.data.stations.slice(0, 8) : [];
      return Promise.all(
        list.map(async (station) => {
          const payload = await getSummary({ station_id: station.location_id });
          return {
            label: station.name,
            value: payload.latest_daily_mean?.pm25_daily_mean ?? null,
          };
        }),
      );
    },
    [compareIds.join(","), refreshKey],
    compareIds.length >= 2,
  );

  const summaryData: SummaryResponse | null = summary.state.status === "ready" ? summary.state.data : null;
  const minTarget = summaryData?.first_feature_date ? addCalendarDay(summaryData.first_feature_date) : null;
  const maxTarget = summaryData?.latest_feature_date
    ? addCalendarDay(summaryData.latest_feature_date)
    : summaryData?.latest_daily_mean?.date
      ? addCalendarDay(summaryData.latest_daily_mean.date)
      : null;

  const [targetDate, setTargetDate] = useState("");
  const [forecast, setForecast] = useState<RequestState<PredictV1Response>>({ status: "idle" });
  const [validation, setValidation] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Dashboard · AirCast India";
  }, []);

  useEffect(() => {
    setForecast({ status: "idle" });
    setValidation(null);
    setTargetDate(maxTarget ?? "");
  }, [selectedStationId, maxTarget]);

  const observation = summaryData?.latest_observation;
  const freshness = summaryData?.freshness;
  const forecastData = forecast.status === "ready" ? forecast.data : null;
  const requested = forecast.status !== "idle";
  const hazardTone =
    forecastData?.available && forecastData.hazard_class === "hazard" ? "tile-warn" : "tile-sage";

  const checkProbability = () => {
    setValidation(null);
    if (selectedStationId == null) {
      setValidation("Select a monitoring station before requesting a forecast.");
      return;
    }
    if (!targetDate) {
      setValidation("Choose a forecast target date.");
      return;
    }
    if (!minTarget || !maxTarget) {
      setValidation("This station has no labelled feature rows, so a next-day class cannot be requested.");
      return;
    }
    if (targetDate < minTarget || targetDate > maxTarget) {
      setValidation(
        `Choose a date between ${minTarget} and ${maxTarget}. Those are the next calendar days after this station's labelled feature rows.`,
      );
      return;
    }
    setForecast({ status: "loading" });
    postPrediction({ model_name: PROBABILITY_MODEL, station_id: selectedStationId, target_date: targetDate }).then(
      (data) => setForecast({ status: "ready", data }),
      (error: unknown) => setForecast(toErrorState(error)),
    );
  };

  const compareItems = useMemo(() => (comparison.state.status === "ready" ? comparison.state.data : []), [comparison.state]);
  const metricsData = metrics.state.status === "ready" ? metrics.state.data : null;
  const showEval = metricsData?.available && metricsData.test != null;

  const overviewData = overview.state.status === "ready" ? overview.state.data : null;

  return (
    <div className="bento">
      <section className="tile tile-wide">
        <div className="tile-head">
          <h2>Dataset coverage</h2>
          <span className="kind kind-measured">Measured</span>
        </div>
        <EndpointState state={overview.state} endpoint="GET /api/v1/overview">
          {overviewData && (
            <FieldList
              items={[
                { label: "Monitoring stations", value: formatCount(overviewData.stations) },
                { label: "Valid hourly observations", value: formatCount(overviewData.valid_hourly_observations) },
                { label: "Labelled station-days", value: formatCount(overviewData.labelled_station_days) },
                { label: "Hazard / non-hazard", value: `${formatCount(overviewData.hazard_positive)} / ${formatCount(overviewData.hazard_negative)}` },
                { label: "Feature date range", value: `${overviewData.first_feature_date} to ${overviewData.last_feature_date}` },
                { label: "Configured threshold", value: `${overviewData.hazard_threshold_ug_m3} µg/m³` },
                { label: "Latest observation date", value: overviewData.latest_observation_date ?? "—" },
                { label: "Preferred model", value: overviewData.preferred_display_name ?? "Not selected yet" },
              ]}
            />
          )}
        </EndpointState>
      </section>
      <section className="tile">
        <div className="tile-head">
          <h2>Current PM2.5</h2>
          <span className="kind kind-measured">Measured</span>
        </div>
        <EndpointState state={summary.state} endpoint="GET /api/summary" idle={stationIdle(stations, "GET /api/summary")}>
          {summaryData && (
            <>
              <p className="metric-value">
                {observation ? formatConcentration(observation.pm25, observation.unit ?? summaryData.unit) : "—"}
              </p>
              <p className="tile-detail">
                {observation
                  ? `${formatWhen(observation.timestamp)}. ${
                      freshness?.latest_observation_at ? formatElapsed(freshness.latest_observation_at) : "Freshness not reported."
                    }`
                  : "No observation was returned for the selected station."}
              </p>
            </>
          )}
        </EndpointState>
      </section>

      <section className={`tile ${hazardTone}`}>
        <div className="tile-head">
          <h2>Tomorrow&apos;s probability</h2>
          <span className="kind kind-predicted">Predicted</span>
        </div>
        <p className="metric-value">{probabilityHeadline(forecastData, requested)}</p>
        <p className="tile-detail">
          {!requested && "Choose a date below and press Request tomorrow's probability."}
          {forecast.status === "loading" && "Scoring this station with Random Forest…"}
          {forecast.status === "ready" && forecastData && !forecastData.available && (forecastData.reason ?? "Model not available.")}
          {forecast.status === "ready" &&
            forecastData?.available &&
            `${forecastData.hazard_class ? hazardLabel(forecastData.hazard_class) : "Class not reported"} · target ${formatWhen(forecastData.target_date)} · ${modelDisplayName(forecastData.model?.name)}`}
          {(forecast.status === "error" || forecast.status === "not_connected" || forecast.status === "not_configured") &&
            forecast.message}
        </p>
      </section>

      <section className="tile">
        <div className="tile-head">
          <h2>Selected station</h2>
        </div>
        <p className="metric-value" style={{ fontSize: "1.35rem" }}>
          {selectedStation?.name ?? "Choose station"}
        </p>
        <p className="tile-detail">
          {selectedStation
            ? [
                selectedStation.city,
                selectedStation.provider,
                `sensor ${selectedStation.location_id}`,
                freshness?.latest_observation_at ? `latest ${formatWhen(freshness.latest_observation_at)}` : null,
              ]
                .filter(Boolean)
                .join(" · ")
            : "The station list is returned by GET /api/stations. Names and coordinates are not invented."}
        </p>
      </section>

      <section className="tile">
        <div className="tile-head">
          <h2>Hazard threshold</h2>
        </div>
        <p className="metric-value">{PROJECT_THRESHOLD_UG_M3} µg/m³</p>
        <p className="tile-detail">
          Configured project setting in Config.scala and config.py, not an automatically verified official standard.
          {summaryData?.threshold_ug_m3 != null ? ` The API reports ${formatConcentration(summaryData.threshold_ug_m3, "ug/m3")}.` : ""}
        </p>
      </section>

      <section className="tile tile-wide">
        <div className="tile-head">
          <h2>Tomorrow&apos;s forecast</h2>
          <span className="kind kind-predicted">Predicted</span>
        </div>
        <ForecastControls
          targetDate={targetDate}
          minDate={minTarget}
          maxDate={maxTarget}
          onTargetDate={setTargetDate}
          onSubmit={checkProbability}
          busy={forecast.status === "loading"}
          submitLabel="Request tomorrow's probability"
        />
        {validation && (
          <StateMessage tone="warning" title="Date not supported">
            {validation}
          </StateMessage>
        )}
      </section>

      <IngestionPanel />

      <section className="tile tile-wide">
        <div className="tile-head">
          <h2>PM2.5 trends and model insights</h2>
        </div>
        <p className="tile-detail">
          Measured daily means sit below the bento overview. Predicted probabilities are not drawn on the concentration
          chart.
        </p>
        <h3 className="subhead">Historical daily mean</h3>
        <EndpointState state={summary.state} endpoint="GET /api/summary" idle={stationIdle(stations, "GET /api/summary")}>
          {summaryData && (
            <SeriesChart
              ariaLabel="Measured daily mean PM2.5 with the configured hazard threshold"
              emptyMessage="No measured daily means were returned for this station."
              threshold={summaryData.threshold_ug_m3 ?? PROJECT_THRESHOLD_UG_M3}
              thresholdLabel="Configured threshold"
              points={summaryData.daily_series.map((point) => ({
                label: point.date,
                value: point.pm25_daily_mean,
              }))}
            />
          )}
        </EndpointState>

        <h3 className="subhead">Station comparison</h3>
        {compareIds.length < 2 ? (
          <StateMessage title="Comparison not available">
            A comparison chart is drawn only when GET /api/stations returns at least two stations and each has a summary.
          </StateMessage>
        ) : (
          <EndpointState state={comparison.state} endpoint="GET /api/summary">
            <BarChart
              ariaLabel="Latest measured daily mean PM2.5 by station"
              emptyMessage="Stations were returned, but no latest daily means were included."
              items={compareItems}
            />
          </EndpointState>
        )}

        <h3 className="subhead">Model evaluation</h3>
        <EndpointState state={metrics.state} endpoint="GET /api/model/metrics" idle={stationIdle(stations, "GET /api/model/metrics")}>
          {metricsData && !showEval && (
            <StateMessage title="Evaluation pending">
              {metricsData.reason ?? "Confusion-matrix and precision/recall/F1 tiles appear when GET /api/model/metrics returns them."}
            </StateMessage>
          )}
          {showEval && metricsData.test && (
            <>
              <p className="tile-detail">
                {modelDisplayName(metricsData.model?.name)} · precision {formatMetric(metricsData.test.precision)} · recall{" "}
                {formatMetric(metricsData.test.recall)} · F1 {formatMetric(metricsData.test.f1)}
              </p>
              {metricsData.test.confusion ? (
                <ConfusionTiles matrix={metricsData.test.confusion} />
              ) : (
                <p className="meta">The confusion matrix was not included.</p>
              )}
            </>
          )}
        </EndpointState>
      </section>
    </div>
  );
}
