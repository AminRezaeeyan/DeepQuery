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
