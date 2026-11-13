import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Console } from "../shared/types";

const sample: Console = {
  generated_from: "reports/dev.json", target: 0.01,
  designs: ["Single-shot RAG", "Agent, claims trusted", "Agent, claims checked"],
  ledger: [{ label: "Searches that failed", note: "of 500 RFQs", values: ["98.0%", "74.8%", "0.2%"] }],
  reasons: { "Agent, claims trusted": { "unqualified supplier: trader or distributor": 115 }, "Agent, claims checked": {} },
};
const renderApp = () => render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);
afterEach(() => vi.restoreAllMocks());

describe("console", () => {
  it("shows a skeleton, then the ledger and the reasons", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(sample)));
    renderApp();
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Searches that failed")).toBeTruthy();
    expect(screen.getByText("No search failed.")).toBeTruthy();
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
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...sample, ledger: [], reasons: {} })));
    renderApp();
    expect((await screen.findAllByText(/No run yet/)).length).toBe(2);
  });
});
