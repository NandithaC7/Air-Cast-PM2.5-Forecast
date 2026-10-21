import type { ConfusionMatrix as Matrix } from "../types";

export function ConfusionMatrix({ matrix }: { matrix: Matrix }) {
  return (
    <div className="table-wrap">
      <table className="matrix">
        <caption>Confusion matrix for the reported evaluation</caption>
        <thead>
          <tr>
            <th scope="col">Actual</th>
            <th scope="col">Predicted no hazard</th>
            <th scope="col">Predicted hazard</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">No hazard</th>
            <td className="num">TN {matrix.tn.toLocaleString("en-IN")}</td>
            <td className="num">FP {matrix.fp.toLocaleString("en-IN")}</td>
          </tr>
          <tr>
            <th scope="row">Hazard</th>
            <td className="num">FN {matrix.fn.toLocaleString("en-IN")}</td>
            <td className="num">TP {matrix.tp.toLocaleString("en-IN")}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function ConfusionTiles({ matrix }: { matrix: Matrix }) {
  const cells = [
    { label: "True negative", value: matrix.tn },
    { label: "False positive", value: matrix.fp },
    { label: "False negative", value: matrix.fn },
    { label: "True positive", value: matrix.tp },
  ];
  return (
    <div className="matrix-tiles" aria-label="Confusion matrix counts">
      {cells.map((cell) => (
        <div key={cell.label}>
          <p>{cell.label}</p>
          <strong>{cell.value.toLocaleString("en-IN")}</strong>
        </div>
      ))}
    </div>
  );
}
