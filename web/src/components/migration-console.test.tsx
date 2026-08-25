// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MigrationRunRecord } from "@/lib/migration-types";

import { MigrationConsole } from "./migration-console";

const { getHealthMock, getMigrationTargetsMock, startMigrationMock, reviewMigrationMock } = vi.hoisted(() => ({
  getHealthMock: vi.fn(),
  getMigrationTargetsMock: vi.fn(),
  startMigrationMock: vi.fn(),
  reviewMigrationMock: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  ApiClientError: class ApiClientError extends Error {},
  getHealth: getHealthMock,
  getMigrationTargets: getMigrationTargetsMock,
  startMigration: startMigrationMock,
  reviewMigration: reviewMigrationMock,
}));

const REVIEW_RUN: MigrationRunRecord = {
  run_id: "run-ui-test",
  target_id: "atlaspay",
  status: "awaiting_review",
  review: {
    run_id: "run-ui-test",
    actions: [{
      id: "ACTION-0123456789AB",
      title: "Replace the retired endpoint",
      target_file: "atlaspay/client.py",
      risk: "medium",
      requires_human_input: true,
      question_key: "account_tier",
    }],
    questions: [{
      key: "account_tier",
      prompt: "Which account tier should be sent?",
      options: ["standard", "premium"],
    }],
  },
  patch: null,
  validation: null,
  report: null,
};

const FINAL_RUN: MigrationRunRecord = {
  run_id: "run-ui-test",
  target_id: "atlaspay",
  status: "finalized",
  review: null,
  patch: { operations: [] },
  validation: { status: "passed", duration_ms: 140, exit_code: 0, timed_out: false },
  report: {
    run_id: "run-ui-test",
    outcome: "succeeded",
    confirmed_change_ids: ["CHANGE-0123456789AB"],
    repository_evidence_ids: ["EVIDENCE-1"],
    proposed_action_ids: ["ACTION-0123456789AB"],
    approved_action_ids: ["ACTION-0123456789AB"],
    modified_files: ["atlaspay/client.py"],
    validation_status: "passed",
    human_decision: "approve",
    repair_attempt_count: 0,
    remaining_uncertainty_codes: [],
    workspace_cleaned: true,
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("MigrationConsole", () => {
  it("keeps analysis disabled when the backend is unavailable", async () => {
    getHealthMock.mockRejectedValue(new Error("offline"));
    getMigrationTargetsMock.mockRejectedValue(new Error("offline"));
    render(<MigrationConsole />);

    expect(await screen.findByText("Backend offline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start migration analysis/i })).toBeDisabled();
    expect(screen.getByText(/trusted demonstration repository only/i)).toBeInTheDocument();
  });

  it("starts analysis and presents the human review plan", async () => {
    getHealthMock.mockResolvedValue({ status: "ok" });
    getMigrationTargetsMock.mockResolvedValue({
      targets: [{ id: "atlaspay", name: "AtlasPay Python client", description: "Trusted fixture." }],
    });
    startMigrationMock.mockResolvedValue(REVIEW_RUN);
    const user = userEvent.setup();
    render(<MigrationConsole />);

    await screen.findByText("Backend ready");
    await user.click(screen.getByRole("button", { name: /start migration analysis/i }));

    expect(await screen.findByRole("heading", { name: /review the proposed migration plan/i })).toBeInTheDocument();
    expect(startMigrationMock).toHaveBeenCalledWith("atlaspay");
    expect(screen.getByText("Replace the retired endpoint")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve selected plan/i })).toBeDisabled();
  });

  it("submits only the explicit answer and approved action", async () => {
    getHealthMock.mockResolvedValue({ status: "ok" });
    getMigrationTargetsMock.mockResolvedValue({
      targets: [{ id: "atlaspay", name: "AtlasPay Python client", description: "Trusted fixture." }],
    });
    startMigrationMock.mockResolvedValue(REVIEW_RUN);
    reviewMigrationMock.mockResolvedValue(FINAL_RUN);
    const user = userEvent.setup();
    render(<MigrationConsole />);

    await screen.findByText("Backend ready");
    await user.click(screen.getByRole("button", { name: /start migration analysis/i }));
    await user.click(await screen.findByRole("radio", { name: "standard" }));
    await user.click(screen.getByRole("button", { name: /approve selected plan/i }));

    await waitFor(() => expect(reviewMigrationMock).toHaveBeenCalledWith(
      "run-ui-test",
      {
        decision: "approve",
        approved_action_ids: ["ACTION-0123456789AB"],
        answers: { account_tier: "standard" },
        comment: null,
      },
    ));
    expect(await screen.findByRole("heading", { name: "Validation passed" })).toBeInTheDocument();
    expect(screen.getByText("atlaspay/client.py")).toBeInTheDocument();
  });

  it("rejects without approving actions or forwarding answers", async () => {
    getHealthMock.mockResolvedValue({ status: "ok" });
    getMigrationTargetsMock.mockResolvedValue({
      targets: [{ id: "atlaspay", name: "AtlasPay Python client", description: "Trusted fixture." }],
    });
    startMigrationMock.mockResolvedValue(REVIEW_RUN);
    reviewMigrationMock.mockResolvedValue({
      ...FINAL_RUN,
      report: { ...FINAL_RUN.report!, outcome: "rejected", validation_status: null, human_decision: "reject" },
    });
    const user = userEvent.setup();
    render(<MigrationConsole />);

    await screen.findByText("Backend ready");
    await user.click(screen.getByRole("button", { name: /start migration analysis/i }));
    await user.click(await screen.findByRole("button", { name: /reject migration/i }));

    await waitFor(() => expect(reviewMigrationMock).toHaveBeenCalledWith(
      "run-ui-test",
      { decision: "reject", approved_action_ids: [], answers: {}, comment: null },
    ));
    expect(await screen.findByRole("heading", { name: "Run rejected" })).toBeInTheDocument();
  });
});
