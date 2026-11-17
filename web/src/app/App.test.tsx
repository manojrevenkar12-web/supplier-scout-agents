import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Console } from "../shared/types";

const sample: Console = {
  generated_from: "reports/", target: 0.01, ours: 1,
  designs: ["Agent, keyword checks", "Agent, stance reader + model fallback"],
  ledger: [{ label: "Searches that failed", note: "of 500 RFQs", values: ["22.8%", "0.0%"] }],
  reasons: { "Agent, keyword checks": { "unqualified supplier: trader or distributor": 15 }, "Agent, stance reader + model fallback": {} },
  drift: { designs: ["Agent, keyword checks", "Stance reader v2 + fallback"], ours: 1,
    rows: [{ label: "Cost per search", note: "", values: ["$0.3369", "$0.0017"] }] },
  monitor: [
    { window: "normal week", world: "world", reader: "v1", searches: 500, novel_share: 0.03, confidence_psi: 0,
      fallback_calls_per_search: 0.01, usd_per_search: 0.0017, review_per_search: 2, alerts: [], retrain: false },
    { window: "wording drifted", world: "drift", reader: "v1", searches: 400, novel_share: 0.17, confidence_psi: 0.26,
      fallback_calls_per_search: 3.6, usd_per_search: 0.004, review_per_search: 4,
      alerts: ["novel wording in 17.0% of sentences (limit 6.0%)"], retrain: true },
  ],
  releases: [{ version: "v2", production: true, corpora: ["base.jsonl", "harvested.jsonl"], sentences: 4300,
    accuracy: 0.998, macro_f1: 0.97, ece: 0.001, min_confidence: 0.5, int8_kb: 1163, float32_kb: 4107, parity: 1,
    passed: true, checks: [{ check: "dev: searches that fail", value: 0, limit: "<= 0.01", passed: true }] }],
};
const renderApp = () => render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
afterEach(() => vi.restoreAllMocks());

describe("console", () => {
  it("shows a skeleton, then the ledger, the reasons, the drift and the releases", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(sample)));
    renderApp();
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Searches that failed")).toBeTruthy();
    expect(screen.getByText("No search failed.")).toBeTruthy();
    expect(screen.getByText(/novel wording in 17.0%/)).toBeTruthy(); // the window with alerts opens first
    expect(screen.getByText("in production")).toBeTruthy();
  });
  it("switches between monitor windows", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(sample)));
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /normal week/ }));
    await waitFor(() => expect(screen.getByText(/No check crossed its limit over 500 searches/)).toBeTruthy());
  });
  it("offers a retry when the data does not load", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("", { status: 404 }));
    renderApp();
    expect(await screen.findByRole("alert")).toBeTruthy();
    f.mockResolvedValueOnce(new Response(JSON.stringify(sample)));
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => expect(screen.getByText("Searches that failed")).toBeTruthy());
  });
  it("says what to do when there is no run", async () => {
    const empty = { ...sample, ledger: [], reasons: {}, monitor: [], releases: [], drift: { ...sample.drift, rows: [] } };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(empty)));
    renderApp();
    expect((await screen.findAllByText(/No run yet/)).length).toBe(3);
    expect(screen.getByText(/No monitor run yet/)).toBeTruthy();
    expect(screen.getByText(/No reader in the registry yet/)).toBeTruthy();
  });
});
