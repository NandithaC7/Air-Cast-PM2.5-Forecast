export function ForecastControls({
  targetDate,
  minDate,
  maxDate,
  onTargetDate,
  onSubmit,
  busy,
  submitLabel = "Request next-day class",
}: {
  targetDate: string;
  minDate: string | null;
  maxDate: string | null;
  onTargetDate: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  submitLabel?: string;
}) {
  return (
    <form
      className="forecast-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label className="field grow">
        <span>Forecast target date</span>
        <input
          type="date"
          value={targetDate}
          min={minDate ?? undefined}
          max={maxDate ?? undefined}
          onChange={(event) => onTargetDate(event.target.value)}
        />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? "Requesting" : submitLabel}
      </button>
    </form>
  );
}
