import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MessageComposer } from "@/components/MessageComposer";
import { NetworkError } from "@/lib/api";

describe("MessageComposer", () => {
  it("blocks an empty message", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("Message is required")).toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("sends the trimmed text and clears the box", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "  What is this about?  ");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("What is this about?");
    expect(screen.getByLabelText("Message")).toHaveValue("");
  });

  it("keeps the text and shows the error when sending fails", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new NetworkError("Could not reach the server"));
    render(<MessageComposer onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByLabelText("Message")).toHaveValue("hello");
  });
});
