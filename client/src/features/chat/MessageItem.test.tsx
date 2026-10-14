import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessageItem } from "./MessageItem";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("MessageItem", () => {
  it("loads a saved chat image with the user's token", async () => {
    localStorage.setItem("dq-access", "token-123");
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response("png", { headers: { "Content-Type": "image/png" } }));
    vi.stubGlobal("fetch", fetchMock);
    URL.createObjectURL = vi.fn(() => "blob:image");
    URL.revokeObjectURL = vi.fn();

    render(
      <MessageItem
        status=""
        message={{ uuid: "m1", role: "user", content: "What is this?", image: "/api/messages/m1/image/", created_at: "2026-01-01T00:00:00Z" }}
      />,
    );

    await waitFor(() => expect(screen.getByAltText("Attached image")).toHaveProperty("src", "blob:image"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/messages/m1/image/");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-123");
  });
});

describe("research steps", () => {
  const steps = [
    { id: 1, tool: "search_documents", status: "done" as const, summary: 'Searched documents for "speed" · 6 passages' },
    { id: 2, tool: "read_document", status: "done" as const, summary: "Read refined.pdf, p. 6" },
  ];

  it("fold into one line once the answer is in, and open on click", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<MessageItem status="" message={{ uuid: "a1", role: "assistant", content: "Answer.", image: null, created_at: "2026-01-01T00:00:00Z", trace: steps }} />);

    const toggle = screen.getByText("Researched in 2 steps");
    expect(screen.queryByText("Read refined.pdf, p. 6")).toBeNull();
    fireEvent.click(toggle);
    expect(screen.getByText("Read refined.pdf, p. 6")).toBeTruthy();
  });

  it("show live while the agent works, instead of a generic status", () => {
    const live = [steps[0], { id: 2, tool: "read_document", status: "running" as const, summary: "Reading refined.pdf, p. 6" }];
    render(<MessageItem status="Thinking" message={{ uuid: "a1", role: "assistant", content: "", image: null, created_at: "2026-01-01T00:00:00Z", streaming: true, trace: live }} />);

    expect(screen.getByText("Reading refined.pdf, p. 6")).toBeTruthy();
    expect(screen.queryByText("Thinking")).toBeNull();
  });
});
