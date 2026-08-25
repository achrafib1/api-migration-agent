import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  getHealth,
  getMigrationTargets,
  getApiBaseUrl,
  reviewMigration,
  startMigration,
} from "./api-client";

const AWAITING_REVIEW_RESPONSE = {
  run_id: "run-test-001",
  target_id: "atlaspay",
  status: "awaiting_review",
  review: { run_id: "run-test-001", actions: [], questions: [] },
  patch: null,
  validation: null,
  report: null,
} as const;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("migration API client", () => {
  it("accepts only the minimal operational health response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    ));
    await expect(getHealth()).resolves.toEqual({ status: "ok" });
  });

  it("rejects health payloads that are not operational", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", provider: "unexpected" }), { status: 200 }),
    ));
    await expect(getHealth()).resolves.toEqual({ status: "ok" });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "degraded" }), { status: 200 }),
    ));
    await expect(getHealth()).rejects.toThrow("invalid health response");
  });

  it("uses the safe local backend URL by default", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("rejects public API URLs that contain credentials", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://user:replace-me-locally@example.test");
    expect(() => getApiBaseUrl()).toThrow(ApiClientError);
  });

  it("starts a run and validates the minimum response envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(AWAITING_REVIEW_RESPONSE), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(startMigration("atlaspay")).resolves.toEqual(AWAITING_REVIEW_RESPONSE);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/migrations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ target_id: "atlaspay" }),
      }),
    );
  });

  it("loads content-safe selectable migration targets", async () => {
    const catalog = {
      targets: [{ id: "atlaspay", name: "AtlasPay", description: "Trusted fixture." }],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(catalog), { status: 200 }),
    ));

    await expect(getMigrationTargets()).resolves.toEqual(catalog);
  });

  it("encodes the run identifier and sends a structured review decision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(AWAITING_REVIEW_RESPONSE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await reviewMigration("run/unsafe-segment", {
      decision: "reject",
      approved_action_ids: [],
      answers: {},
      comment: null,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/migrations/run%2Funsafe-segment/review",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          decision: "reject",
          approved_action_ids: [],
          answers: {},
          comment: null,
        }),
      }),
    );
  });

  it("does not expose arbitrary backend error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "sensitive-internal-canary" }), {
          status: 500,
        }),
      ),
    );

    const error = await startMigration("atlaspay").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiClientError);
    expect(String(error)).not.toContain("sensitive-internal-canary");
  });

  it("rejects malformed success payloads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "finalized" }), { status: 200 })),
    );

    await expect(startMigration("atlaspay")).rejects.toThrow(
      "The migration service returned an invalid response.",
    );
  });
});
