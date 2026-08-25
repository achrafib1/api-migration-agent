"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiClientError,
  getHealth,
  getMigrationTargets,
  reviewMigration,
  startMigration,
} from "@/lib/api-client";
import type {
  HumanPlanDecision,
  MigrationRunRecord,
  MigrationTargetSummary,
  ReviewActionSummary,
} from "@/lib/migration-types";

type BusyAction = "start" | "approve" | "reject" | null;
type BackendStatus = "checking" | "online" | "offline";

const WORKFLOW_STAGES = [
  "Analyze specifications",
  "Map repository impact",
  "Human review",
  "Apply approved patch",
  "Validate & report",
] as const;

function riskLabel(action: ReviewActionSummary): string {
  return `${action.risk.charAt(0).toUpperCase()}${action.risk.slice(1)} risk`;
}

function readError(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : "The operation failed safely. No changes were applied.";
}

/** Interactive human-review surface for the trusted AtlasPay workflow. */
export function MigrationConsole() {
  const [run, setRun] = useState<MigrationRunRecord | null>(null);
  const [selectedActionIds, setSelectedActionIds] = useState<Set<string>>(new Set());
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [targets, setTargets] = useState<readonly MigrationTargetSummary[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([getHealth(controller.signal), getMigrationTargets(controller.signal)])
      .then(([, catalog]) => {
        setTargets(catalog.targets);
        setSelectedTargetId(catalog.targets[0]?.id ?? "");
        setBackendStatus(catalog.targets.length > 0 ? "online" : "offline");
      })
      .catch(() => setBackendStatus("offline"));
    return () => controller.abort();
  }, []);

  const review = run?.review ?? null;
  const activeTarget = targets.find((target) => target.id === run?.target_id);
  const allActionsSelected = useMemo(
    () =>
      review !== null &&
      review.actions.length > 0 &&
      review.actions.every((action) => selectedActionIds.has(action.id)),
    [review, selectedActionIds],
  );
  const allQuestionsAnswered =
    review?.questions.every((question) => Boolean(answers[question.key])) ?? true;

  async function handleStart(): Promise<void> {
    setBusyAction("start");
    setError(null);
    try {
      const nextRun = await startMigration(selectedTargetId);
      setRun(nextRun);
      setSelectedActionIds(new Set(nextRun.review?.actions.map((action) => action.id)));
      setAnswers({});
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusyAction(null);
    }
  }

  function toggleAction(actionId: string): void {
    setSelectedActionIds((current) => {
      const next = new Set(current);
      if (next.has(actionId)) next.delete(actionId);
      else next.add(actionId);
      return next;
    });
  }

  async function submitDecision(decision: "approve" | "reject"): Promise<void> {
    if (!run || !review) return;
    setBusyAction(decision);
    setError(null);

    const payload: HumanPlanDecision = {
      decision,
      approved_action_ids:
        decision === "approve" ? Array.from(selectedActionIds) : [],
      answers: decision === "approve" ? answers : {},
      comment: null,
    };

    try {
      setRun(await reviewMigration(run.run_id, payload));
    } catch (caught) {
      setError(readError(caught));
    } finally {
      setBusyAction(null);
    }
  }

  const isReviewing = run?.status === "awaiting_review" && review !== null;
  const isComplete = run?.report !== null && run?.report !== undefined;

  return (
    <section className="console" aria-labelledby="workspace-title">
      <div className="console-topline">
        <div>
          <p className="eyebrow">Migration workspace</p>
          <h2 id="workspace-title">AtlasPay API upgrade</h2>
        </div>
        <div className={`system-state system-state-${backendStatus}`} role="status">
          <span aria-hidden="true" />
          {backendStatus === "checking"
            ? "Checking backend"
            : backendStatus === "online"
              ? "Backend ready"
              : "Backend offline"}
        </div>
      </div>

      <div className="stage-grid" aria-label="Migration stages">
        {WORKFLOW_STAGES.map((stage, index) => (
          <div className="stage" key={stage}>
            <span className="stage-number">0{index + 1}</span>
            <span>{stage}</span>
          </div>
        ))}
      </div>

      {error ? (
        <div className="notice notice-error" role="alert">
          <strong>Request stopped</strong>
          <span>{error}</span>
        </div>
      ) : null}

      {!run ? (
        <div className="empty-state">
          <div className="empty-mark" aria-hidden="true">A</div>
          <div>
            <p className="eyebrow">Ready for deterministic analysis</p>
            <h3>Review a real migration from evidence to validation.</h3>
            <p>
              Select a server-approved target. The MVP compares its registered OpenAPI
              specifications, maps verified changes, and pauses before creating a temporary copy.
            </p>
            <label className="target-select">
              <span>Migration target</span>
              <select
                disabled={backendStatus !== "online" || targets.length === 0}
                onChange={(event) => setSelectedTargetId(event.target.value)}
                value={selectedTargetId}
              >
                {targets.map((target) => (
                  <option key={target.id} value={target.id}>{target.name}</option>
                ))}
              </select>
              <small>{targets.find((target) => target.id === selectedTargetId)?.description}</small>
            </label>
            <small className="scope-note">Trusted demonstration repository only · User repository intake is not enabled</small>
          </div>
          <button className="button button-primary" disabled={busyAction !== null || backendStatus !== "online" || !selectedTargetId} onClick={handleStart}>
            {busyAction === "start" ? "Analyzing…" : "Start migration analysis"}
            <span aria-hidden="true">→</span>
          </button>
        </div>
      ) : null}

      {isReviewing ? (
        <div className="review-layout">
          <div className="review-main">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Human approval required</p>
                <h3>Review the proposed migration plan</h3>
              </div>
              <span className="run-id">Run {run.run_id.slice(0, 8)}</span>
            </div>
            <p className="supporting-copy">
              Select only the evidence-backed actions you authorize. Nothing is applied
              until you approve this exact set.
            </p>

            <div className="action-list">
              {review.actions.map((action) => (
                <label className="action-card" key={action.id}>
                  <input
                    checked={selectedActionIds.has(action.id)}
                    onChange={() => toggleAction(action.id)}
                    type="checkbox"
                  />
                  <span className="custom-check" aria-hidden="true">✓</span>
                  <span className="action-content">
                    <span className="action-row">
                      <strong>{action.title}</strong>
                      <span className={`risk risk-${action.risk}`}>{riskLabel(action)}</span>
                    </span>
                    <code>{action.target_file}</code>
                    <small>Evidence-backed action · {action.id}</small>
                  </span>
                </label>
              ))}
            </div>

            {review.questions.length > 0 ? (
              <div className="questions">
                <h4>Required business decisions</h4>
                {review.questions.map((question) => (
                  <fieldset key={question.key}>
                    <legend>{question.prompt}</legend>
                    <div className="option-row">
                      {question.options.map((option) => (
                        <label key={option}>
                          <input
                            checked={answers[question.key] === option}
                            name={question.key}
                            onChange={() => setAnswers((current) => ({ ...current, [question.key]: option }))}
                            type="radio"
                          />
                          <span>{option}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>
            ) : null}
          </div>

          <aside className="review-summary">
            <p className="eyebrow">Approval summary</p>
            <div className="summary-metric">
              <strong>{selectedActionIds.size}</strong>
              <span>of {review.actions.length} actions selected</span>
            </div>
            <dl>
              <div><dt>Repository</dt><dd>{activeTarget?.name ?? run.target_id}</dd></div>
              <div><dt>Patch target</dt><dd>Temporary workspace</dd></div>
              <div><dt>Validation</dt><dd>Fixed pytest command</dd></div>
              <div><dt>Repair limit</dt><dd>One attempt</dd></div>
            </dl>
            <button
              className="button button-primary button-full"
              disabled={!allActionsSelected || !allQuestionsAnswered || busyAction !== null}
              onClick={() => void submitDecision("approve")}
            >
              {busyAction === "approve" ? "Applying & validating…" : "Approve selected plan"}
            </button>
            <button
              className="button button-quiet button-full"
              disabled={busyAction !== null}
              onClick={() => void submitDecision("reject")}
            >
              {busyAction === "reject" ? "Rejecting…" : "Reject migration"}
            </button>
            {!allActionsSelected ? <small>Select every proposed action to approve this MVP plan.</small> : null}
          </aside>
        </div>
      ) : null}

      {isComplete && run.report ? (
        <div className="report-view">
          <div className={`outcome outcome-${run.report.outcome}`}>
            <div className="outcome-icon" aria-hidden="true">
              {run.report.outcome === "succeeded" ? "✓" : run.report.outcome === "rejected" ? "—" : "!"}
            </div>
            <div>
              <p className="eyebrow">Migration finalized</p>
              <h3>{run.report.outcome === "succeeded" ? "Validation passed" : `Run ${run.report.outcome}`}</h3>
              <p>The isolated workspace was {run.report.workspace_cleaned ? "cleaned successfully" : "retained for investigation"}.</p>
            </div>
          </div>
          <div className="metric-grid">
            <article><span>Migration target</span><strong className="metric-word">{activeTarget?.name ?? run.target_id}</strong></article>
            <article><span>Confirmed changes</span><strong>{run.report.confirmed_change_ids.length}</strong></article>
            <article><span>Approved actions</span><strong>{run.report.approved_action_ids.length}</strong></article>
            <article><span>Modified files</span><strong>{run.report.modified_files.length}</strong></article>
            <article><span>Validation</span><strong className="metric-word">{run.report.validation_status ?? "Not run"}</strong></article>
          </div>
          {run.report.modified_files.length > 0 ? (
            <div className="file-list">
              <p className="eyebrow">Modified in temporary workspace</p>
              {run.report.modified_files.map((file) => <code key={file}>{file}</code>)}
            </div>
          ) : null}
          <button className="button button-secondary" onClick={() => void handleStart()} disabled={busyAction !== null}>
            Run analysis again
          </button>
        </div>
      ) : null}
    </section>
  );
}
