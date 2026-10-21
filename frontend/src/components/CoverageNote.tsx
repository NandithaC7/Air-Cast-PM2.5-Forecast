import { PROJECT_MIN_HOURS_PER_DAY } from "../config";

export function CoverageNote({ reported }: { reported: number | null | undefined }) {
  const hours = reported ?? PROJECT_MIN_HOURS_PER_DAY;
  return (
    <p className="note">
      Minimum daily coverage rule: a day receives a daily mean only when it has at least {hours} valid hourly PM2.5
      readings. {PROJECT_MIN_HOURS_PER_DAY} is the current setting in Config.scala.{" "}
      {reported != null && reported !== PROJECT_MIN_HOURS_PER_DAY
        ? `The summary endpoint reports ${reported} hours for this response.`
        : "The summary endpoint replaces this number when it returns min_hours_per_day."}
    </p>
  );
}
