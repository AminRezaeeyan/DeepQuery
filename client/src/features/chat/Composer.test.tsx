import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

const image = new File(["png"], "photo.png", { type: "image/png" });

function renderComposer(onSend = vi.fn()) {
  render(
    <Composer
      options={{ webSearch: false, strictQuotes: false, challenge: false, depth: "Medium", audience: "General" }}
      setOptions={vi.fn()}
      busy={false}
      canAttachImage
      image={image}
      setImage={vi.fn()}
      onPickFiles={vi.fn()}
      onSend={onSend}
      onStop={vi.fn()}
      accept=""
      focusKey={undefined}
      prefill={null}
      onPrefillUsed={vi.fn()}
    />,
  );
  return onSend;
}

describe("Composer", () => {
  it("won't send an image without a question", () => {
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
    const onSend = renderComposer();

    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });

    expect(screen.getByLabelText("Send")).toHaveProperty("disabled", true);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("sends once the image has a question", () => {
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
    const onSend = renderComposer();

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "What is this chart?" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("What is this chart?");
  });
});
