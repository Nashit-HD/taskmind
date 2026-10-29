"""Text handling every request schema shares."""


def strip_text(value: object) -> object:
    """Trim a string before validation, so a whitespace-only value is empty and the length rules
    see the real text. Anything that is not a string is left for Pydantic to reject."""
    return value.strip() if isinstance(value, str) else value
