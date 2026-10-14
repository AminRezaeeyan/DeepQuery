import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PaymentResultPage } from "./PaymentResultPage";
import { ThemeProvider } from "../lib/theme";

afterEach(() => vi.unstubAllGlobals());

function renderAt(url: string) {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/payment/result" element={<PaymentResultPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("PaymentResultPage", () => {
  it("verifies the payment once and shows the new plan", async () => {
    const fetchMock = vi.fn(async (_url: string) => Response.json({ message: "ok", ref_id: "123456", plan: "PRO" }));
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/payment/result?Authority=A1&Status=OK");

    expect(await screen.findByText("You’re on the Pro plan")).toBeTruthy();
    expect(screen.getByText("123456")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/subscriptions/payment/verify/?Authority=A1&Status=OK");
  });

  it("explains a cancelled or failed payment", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(["Payment was canceled by the user."], { status: 400 })));

    renderAt("/payment/result?Authority=A1&Status=NOK");

    expect(await screen.findByText("Payment not completed")).toBeTruthy();
    expect(screen.getByText(/Payment was canceled by the user\./)).toBeTruthy();
  });

  it("handles a link without payment details", async () => {
    vi.stubGlobal("fetch", vi.fn());

    renderAt("/payment/result");

    expect(await screen.findByText("Payment not completed")).toBeTruthy();
  });
});
