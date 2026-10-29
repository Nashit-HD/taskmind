from app.assistant import EchoAssistant, NoteContext, Turn, get_assistant


def test_the_echo_quotes_the_question_and_names_the_note() -> None:
    reply = EchoAssistant().reply(
        NoteContext(title="Plan", content="Ship it"), [Turn("user", "earlier")], "When?"
    )

    assert "When?" in reply
    assert "Plan" in reply
    assert "Ship it" not in reply


def test_the_default_assistant_is_the_echo() -> None:
    assert isinstance(get_assistant(), EchoAssistant)
