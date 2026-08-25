/** Content-safe API contracts exposed by the migration backend. */

export type MigrationRisk = "low" | "medium" | "high";
export type PlanDecision = "approve" | "reject";
export type ValidationStatus = "passed" | "failed" | "timed_out";
export type ReportOutcome = "succeeded" | "rejected" | "failed";

export type WorkflowStatus =
  | "pending"
  | "analyzing"
  | "awaiting_review"
  | "approved"
  | "workspace_ready"
  | "patch_proposed"
  | "patch_applied"
  | "validation_passed"
  | "validation_failed"
  | "finalized"
  | "rejected"
  | "failed";

export interface HumanQuestion {
  readonly key: string;
  readonly prompt: string;
  readonly options: readonly string[];
}

export interface ReviewActionSummary {
  readonly id: string;
  readonly title: string;
  readonly target_file: string;
  readonly risk: MigrationRisk;
  readonly requires_human_input: boolean;
  readonly question_key: string | null;
}

export interface PlanningReview {
  readonly run_id: string;
  readonly actions: readonly ReviewActionSummary[];
  readonly questions: readonly HumanQuestion[];
}

export interface PatchOperationSummary {
  readonly id: string;
  readonly migration_action_id: string;
  readonly api_change_id: string;
  readonly operation_type:
    | "replace_endpoint"
    | "rename_request_key"
    | "rename_response_key"
    | "add_approved_field";
  readonly target_file: string;
}

export interface PatchSummary {
  readonly operations: readonly PatchOperationSummary[];
}

export interface ValidationResult {
  readonly status: ValidationStatus;
  readonly duration_ms: number;
  readonly exit_code: number | null;
  readonly timed_out: boolean;
}

export interface MigrationReport {
  readonly run_id: string;
  readonly outcome: ReportOutcome;
  readonly confirmed_change_ids: readonly string[];
  readonly repository_evidence_ids: readonly string[];
  readonly proposed_action_ids: readonly string[];
  readonly approved_action_ids: readonly string[];
  readonly modified_files: readonly string[];
  readonly validation_status: ValidationStatus | null;
  readonly human_decision: string | null;
  readonly repair_attempt_count: number;
  readonly remaining_uncertainty_codes: readonly string[];
  readonly workspace_cleaned: boolean;
}

export interface MigrationRunRecord {
  readonly run_id: string;
  readonly target_id: string;
  readonly status: WorkflowStatus;
  readonly review: PlanningReview | null;
  readonly patch: PatchSummary | null;
  readonly validation: ValidationResult | null;
  readonly report: MigrationReport | null;
}

export interface HumanPlanDecision {
  readonly decision: PlanDecision;
  readonly approved_action_ids: readonly string[];
  readonly answers: Readonly<Record<string, string>>;
  readonly comment?: string | null;
}

export interface MigrationTargetSummary {
  readonly id: string;
  readonly name: string;
  readonly description: string;
}

export interface MigrationTargetCatalog {
  readonly targets: readonly MigrationTargetSummary[];
}
