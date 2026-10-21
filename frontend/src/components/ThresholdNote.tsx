import { PROJECT_THRESHOLD_UG_M3 } from "../config";
import { formatConcentration } from "../format";

export function ThresholdNote({ reported }: { reported: number | null | undefined }) {
  return (
    <p className="note">
      Configured hazard threshold: {PROJECT_THRESHOLD_UG_M3} µg/m³. This is the project setting in
      aircast-pyspark/config.py and Config.scala. It is a project configuration rather than an automatically verified
      official standard.
      {reported == null
        ? " The API has not reported a threshold."
        : ` The API reports ${formatConcentration(reported, "ug/m3")} as the threshold in use.`}
    </p>
  );
}
