import type {
  HumanPlanDecision,
  MigrationRunRecord,
  MigrationTargetCatalog,
} from "@/lib/migration-types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export interface HealthStatus {
  readonly status: "ok";
}

/** A sanitized client error that never exposes an arbitrary backend response. */
export class ApiClientError extends Error {
  public readonly status: number | null;

  public constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

/** Resolve the public, non-secret backend URL and reject unsafe URL shapes. */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;

  try {
    const url = new URL(configured);
    if (!(["http:", "https:"] as const).includes(url.protocol as "http:" | "https:")) {
      throw new TypeError("Unsupported protocol");
    }
    if (url.username || url.password) {
      throw new TypeError("Credentials are not allowed in the API URL");
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    throw new ApiClientError("The public backend URL is not configured correctly.");
  }
}

const WORKFLOW_STATUSES = new Set([
  "pending", "analyzing", "awaiting_review", "approved", "workspace_ready",
  "patch_proposed", "patch_applied", "validation_passed", "validation_failed",
  "finalized", "rejected", "failed",
]);
const RISKS = new Set(["low", "medium", "high"]);
const VALIDATION_STATUSES = new Set(["passed", "failed", "timed_out"]);
const REPORT_OUTCOMES = new Set(["succeeded", "rejected", "failed"]);
const OPERATION_TYPES = new Set([
  "replace_endpoint", "rename_request_key", "rename_response_key", "add_approved_field",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isReview(value: unknown): boolean {
  if (!isRecord(value) || typeof value.run_id !== "string" || !Array.isArray(value.actions) || !Array.isArray(value.questions)) return false;
  return value.actions.every((item) => isRecord(item)
    && typeof item.id === "string"
    && typeof item.title === "string"
    && typeof item.target_file === "string"
    && typeof item.risk === "string" && RISKS.has(item.risk)
    && typeof item.requires_human_input === "boolean"
    && (item.question_key === null || typeof item.question_key === "string"))
    && value.questions.every((item) => isRecord(item)
      && typeof item.key === "string"
      && typeof item.prompt === "string"
      && isStringArray(item.options));
}

function isPatch(value: unknown): boolean {
  return isRecord(value) && Array.isArray(value.operations) && value.operations.every((item) =>
    isRecord(item)
    && typeof item.id === "string"
    && typeof item.migration_action_id === "string"
    && typeof item.api_change_id === "string"
    && typeof item.operation_type === "string" && OPERATION_TYPES.has(item.operation_type)
    && typeof item.target_file === "string");
}

function isValidation(value: unknown): boolean {
  return isRecord(value)
    && typeof value.status === "string" && VALIDATION_STATUSES.has(value.status)
    && typeof value.duration_ms === "number" && value.duration_ms >= 0
    && (value.exit_code === null || typeof value.exit_code === "number")
    && typeof value.timed_out === "boolean";
}

function isReport(value: unknown): boolean {
  return isRecord(value)
    && typeof value.run_id === "string"
    && typeof value.outcome === "string" && REPORT_OUTCOMES.has(value.outcome)
    && isStringArray(value.confirmed_change_ids)
    && isStringArray(value.repository_evidence_ids)
    && isStringArray(value.proposed_action_ids)
    && isStringArray(value.approved_action_ids)
    && isStringArray(value.modified_files)
    && (value.validation_status === null || (typeof value.validation_status === "string" && VALIDATION_STATUSES.has(value.validation_status)))
    && (value.human_decision === null || typeof value.human_decision === "string")
    && typeof value.repair_attempt_count === "number"
    && isStringArray(value.remaining_uncertainty_codes)
    && typeof value.workspace_cleaned === "boolean";
}

function isMigrationRunRecord(value: unknown): value is MigrationRunRecord {
  if (!isRecord(value)) return false;
  return typeof value.run_id === "string"
    && typeof value.target_id === "string"
    && typeof value.status === "string" && WORKFLOW_STATUSES.has(value.status)
    && (value.review === null || isReview(value.review))
    && (value.patch === null || isPatch(value.patch))
    && (value.validation === null || isValidation(value.validation))
    && (value.report === null || isReport(value.report));
}

function isTargetCatalog(value: unknown): value is MigrationTargetCatalog {
  return isRecord(value) && Array.isArray(value.targets) && value.targets.every((target) =>
    isRecord(target)
    && typeof target.id === "string"
    && typeof target.name === "string"
    && typeof target.description === "string");
}

/** Check backend readiness without exposing provider or configuration details. */
export async function getHealth(signal?: AbortSignal): Promise<HealthStatus> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/health`, {
      method: "GET",
      signal: signal ?? null,
    });
  } catch {
    throw new ApiClientError("The migration service is offline.");
  }

  if (!response.ok) {
    throw new ApiClientError("The migration service is not ready.", response.status);
  }
  const payload: unknown = await response.json();
  if (!isRecord(payload) || payload.status !== "ok") {
    throw new ApiClientError("The migration service returned an invalid health response.");
  }
  return { status: "ok" };
}

/** List server-approved migration targets without receiving private paths. */
export async function getMigrationTargets(
  signal?: AbortSignal,
): Promise<MigrationTargetCatalog> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/migrations/targets`, {
      method: "GET",
      signal: signal ?? null,
    });
  } catch {
    throw new ApiClientError("The migration target catalog is unavailable.");
  }
  if (!response.ok) {
    throw new ApiClientError("The migration target catalog could not be loaded.", response.status);
  }
  const payload: unknown = await response.json();
  if (!isTargetCatalog(payload)) {
    throw new ApiClientError("The migration service returned an invalid target catalog.");
  }
  return payload;
}

async function requestMigration(
  path: string,
  init: RequestInit,
): Promise<MigrationRunRecord> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiClientError(
      "The migration service is unavailable. Confirm that the backend is running.",
    );
  }

  if (!response.ok) {
    throw new ApiClientError(
      "The migration service could not complete this request.",
      response.status,
    );
  }

  const payload: unknown = await response.json();
  if (!isMigrationRunRecord(payload)) {
    throw new ApiClientError("The migration service returned an invalid response.");
  }
  return payload;
}

/** Start the trusted, bundled AtlasPay migration workflow. */
export function startMigration(
  targetId: string,
  signal?: AbortSignal,
): Promise<MigrationRunRecord> {
  return requestMigration("/api/v1/migrations", {
    method: "POST",
    body: JSON.stringify({ target_id: targetId }),
    signal: signal ?? null,
  });
}

/** Submit an explicit human approval or rejection for a paused run. */
export function reviewMigration(
  runId: string,
  decision: HumanPlanDecision,
  signal?: AbortSignal,
): Promise<MigrationRunRecord> {
  return requestMigration(`/api/v1/migrations/${encodeURIComponent(runId)}/review`, {
    method: "POST",
    body: JSON.stringify(decision),
    signal: signal ?? null,
  });
}

/** Retrieve the latest content-safe snapshot for a known migration run. */
export function getMigration(
  runId: string,
  signal?: AbortSignal,
): Promise<MigrationRunRecord> {
  return requestMigration(`/api/v1/migrations/${encodeURIComponent(runId)}`, {
    method: "GET",
    signal: signal ?? null,
  });
}
