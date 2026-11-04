import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NoteForm } from "@/components/NoteForm";
import { ApiError } from "@/lib/api";

describe("NoteForm", () => {
  it("blocks a blank title and does not submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Title"), "   ");
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(screen.getByText("Title is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("blocks a title over 200 characters", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.click(screen.getByLabelText("Title"));
    await user.paste("x".repeat(201));
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(screen.getByText("Title must be at most 200 characters")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the trimmed title and the content, then clears for the next note", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Title"), "  Groceries ");
    await user.type(screen.getByLabelText("Content"), "milk");
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(onSubmit).toHaveBeenCalledWith({ title: "Groceries", content: "milk" });
    expect(screen.getByLabelText("Title")).toHaveValue("");
    expect(screen.getByLabelText("Content")).toHaveValue("");
  });

  it("keeps the values and shows the error when saving fails", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(403, "Not the author"));
    render(
      <NoteForm
        initial={{ title: "Old", content: "text" }}
        submitLabel="Save"
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Not the author");
    expect(screen.getByLabelText("Title")).toHaveValue("Old");
  });
});
