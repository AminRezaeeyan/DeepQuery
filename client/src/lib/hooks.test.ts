import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useWhenVisible } from "./hooks";

type Callback = (entries: { isIntersecting: boolean }[]) => void;
let observers: { callback: Callback; disconnect: () => void }[] = [];

class FakeObserver {
  callback: Callback;
  disconnect = vi.fn();
  constructor(callback: Callback) {
    this.callback = callback;
    observers.push(this);
  }
  observe() {}
}

afterEach(() => {
  observers = [];
  vi.unstubAllGlobals();
});

describe("useWhenVisible", () => {
  it("calls back when the marker comes into view, and re-arms after loading", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    const ref = { current: document.createElement("div") };
    const onVisible = vi.fn();

    const { rerender } = renderHook(({ enabled }) => useWhenVisible(ref, enabled, onVisible), { initialProps: { enabled: true } });
    observers.at(-1)!.callback([{ isIntersecting: false }]);
    expect(onVisible).not.toHaveBeenCalled();

    observers.at(-1)!.callback([{ isIntersecting: true }]);
    expect(onVisible).toHaveBeenCalledTimes(1);

    // While a page loads the hook is disabled; enabling again watches afresh.
    rerender({ enabled: false });
    expect(observers.at(-1)!.disconnect).toHaveBeenCalled();
    const before = observers.length;
    rerender({ enabled: true });
    expect(observers.length).toBe(before + 1);
  });

  it("does nothing while disabled", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    renderHook(() => useWhenVisible({ current: document.createElement("div") }, false, vi.fn()));

    expect(observers).toHaveLength(0);
  });
});
