
import { useEffect, useState } from "react";
import { loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiBivariateRow, ApiCovarianceMatrix, ApiPage, ApiPairPlan, ApiResearchRun } from "../contracts";
import { useResource } from "../hooks/use-resource";

function metric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}

function covarianceColor(value: number, extent: number): string {
  if (extent === 0) return "#f1f5f9";
  const intensity = Math.min(1, Math.abs(value) / extent);
  const lightness = 96 - intensity * 42;
  return value >= 0 ? `hsl(152 58% ${lightness}%)` : `hsl(8 74% ${lightness}%)`;
}

export function BivariateStatisticsPage() {
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);
  const [run, setRun] = useState<ApiResearchRun | null>(null);
  const [results, setResults] = useState<ApiPage<ApiBivariateRow> | null>(null);
  const [covarianceMatrix, setCovarianceMatrix] = useState<ApiCovarianceMatrix | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setResults(null);
      setCovarianceMatrix(null);
      setMessage("");
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    let timeoutId: number | undefined;
    async function pollBivariateRun() {
      try {
        const current = await requestJson<ApiResearchRun>(`/api/bivariate-statistics/runs/${activeRunId}`);
        if (cancelled) return;
        setRun(current);
        if (current.status === "running") {
          setMessage(`${current.completed.toLocaleString()} of ${current.total.toLocaleString()} pair statistics computed.`);
          timeoutId = window.setTimeout(() => void pollBivariateRun(), 750);
          return;
        }
        if (current.status === "failed") {
          setMessage("Bivariate computation failed. Please try again.");
          return;
        }
        const [page, matrix] = await Promise.all([
          requestJson<ApiPage<ApiBivariateRow>>(`/api/bivariate-statistics/runs/${current.run_id}/results?limit=50&offset=0`),
          requestJson<ApiCovarianceMatrix>(`/api/bivariate-statistics/runs/${current.run_id}/covariance-matrix`),
        ]);
        if (cancelled) return;
        setResults(page);
        setCovarianceMatrix(matrix);
        setMessage(`${page.total.toLocaleString()} pair statistics computed.`);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not retrieve bivariate computation status.");
      }
    }
    void pollBivariateRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [run?.run_id, run?.status]);

  if (workflow.status === "loading" || workflow.status === "idle") return <LoadingState label="Loading bivariate statistics" />;
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const selectionId = workflow.data.stages.univariate_filter.univariate_filter_selection_id;
  if (!selectionId) {
    return <Panel title="Bivariate Statistics"><p>Complete univariate statistics and select at least two ISINs first.</p></Panel>;
  }

  async function compute() {
    setMessage("Planning bivariate statistics…");
    try {
      const nextPlan = await postJson<ApiPairPlan>("/api/bivariate-statistics/plan", { univariate_filter_selection_id: selectionId });
      if (!nextPlan.allowed) {
        setMessage(`Pair count exceeds the ${nextPlan.pair_limit} limit or has fewer than two selected ISINs.`);
        return;
      }
      setMessage("Computing bivariate statistics…");
      const nextRun = await postJson<ApiResearchRun>("/api/bivariate-statistics/runs", { univariate_filter_selection_id: selectionId });
      setRun(nextRun);
      if (nextRun.status === "complete") {
        const [page, matrix] = await Promise.all([
          requestJson<ApiPage<ApiBivariateRow>>(`/api/bivariate-statistics/runs/${nextRun.run_id}/results?limit=50&offset=0`),
          requestJson<ApiCovarianceMatrix>(`/api/bivariate-statistics/runs/${nextRun.run_id}/covariance-matrix`),
        ]);
        setResults(page);
        setCovarianceMatrix(matrix);
        setMessage(`${page.total.toLocaleString()} pair statistics computed.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Bivariate computation failed.");
    }
  }

  const covarianceRows = results?.items.filter((row) => row.covariance != null) ?? [];
  const averageCovariance = covarianceRows.length === 0
    ? null
    : covarianceRows.reduce((total, row) => total + (row.covariance ?? 0), 0) / covarianceRows.length;
  const positiveCovarianceCount = covarianceRows.filter((row) => (row.covariance ?? 0) > 0).length;
  const covarianceExtent = Math.max(
    0,
    ...(covarianceMatrix?.values.flat().map((value) => Math.abs(value)) ?? []),
  );

  return (
    <Panel title="Bivariate Statistics">
      <div className="quote-fetch quote-fetch--panel bivariate-compute">
        <label htmlFor="bivariate-progress">Bivariate statistics progress</label>
        <progress id="bivariate-progress" max={100} value={run?.percent ?? 0} />
        <p className="status-line" aria-live="polite">{message || "Compute statistics for the ISINs selected in univariate statistics."}</p>
        <div className="quote-fetch__action">
          <Button type="button" variant="primary" disabled={run?.status === "running"} onClick={() => void compute()}>
            {run?.status === "running" ? "Computing…" : "Compute Bivariate Statistics"}
          </Button>
        </div>
      </div>
      <section className="bivariate-statistic" aria-labelledby="covariance-title">
        <div className="bivariate-statistic__facts">
          <h3 id="covariance-title">Covariance</h3>
          <p>Joint variation of return series for every pair in the filtered ISIN universe.</p>
          <dl>
            <div><dt>Pairs analysed</dt><dd>{covarianceRows.length.toLocaleString()}</dd></div>
            <div><dt>Average covariance</dt><dd>{averageCovariance === null ? "—" : metric(averageCovariance)}</dd></div>
            <div><dt>Positive covariance</dt><dd>{covarianceRows.length === 0 ? "—" : `${((positiveCovarianceCount / covarianceRows.length) * 100).toFixed(1)}%`}</dd></div>
          </dl>
        </div>
        <div className="bivariate-statistic__results">
          {covarianceMatrix === null ? <p className="status-line">Compute bivariate statistics to populate the daily log-return covariance matrix.</p> : covarianceMatrix.labels.length > 0 ? <>
            <p className="bivariate-statistic__matrix-caption">Daily log-return covariance matrix · {covarianceMatrix.observation_count.toLocaleString()} shared observations</p>
            <table className="covariance-matrix">
              <thead><tr><th scope="col">ISIN</th>{covarianceMatrix.labels.map((label) => <th scope="col" key={label.isin} title={label.isin}>{label.label}</th>)}</tr></thead>
              <tbody>{covarianceMatrix.labels.map((label, rowIndex) => <tr key={label.isin}><th scope="row" title={label.isin}>{label.label}</th>{covarianceMatrix.values[rowIndex].map((value, columnIndex) => <td key={`${label.isin}:${covarianceMatrix.labels[columnIndex].isin}`} title={`Covariance: ${metric(value)}`} style={{ backgroundColor: covarianceColor(value, covarianceExtent) }}>{metric(value)}</td>)}</tr>)}</tbody>
            </table>
            <p className="covariance-matrix__legend"><span className="covariance-matrix__legend-negative" /> Negative <span className="covariance-matrix__legend-neutral" /> Near zero <span className="covariance-matrix__legend-positive" /> Positive</p>
            <p className="univariate-equation">Cov(Rᵢ, Rⱼ) = 𝔼[(Rᵢ − μᵢ)(Rⱼ − μⱼ)]</p>
            <p className="univariate-notation">Rᵢ, Rⱼ: paired returns · μ: mean return · 𝔼: expected value</p>
          </> : <p className="status-line">No common log-return observations are available.</p>}
        </div>
      </section>
    </Panel>
  );
}
