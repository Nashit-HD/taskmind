"""SQLAlchemy models.

Importing this package imports every model, which registers every table on ``Base.metadata``.
Alembic's ``env.py`` imports it for that reason: a model missing here is a table Alembic cannot
see, and ``alembic check`` would report the drift.
"""

from app.models.chat import Chat
from app.models.message import Message, MessageRole
from app.models.note import Note
from app.models.user import User

__all__ = ["Chat", "Message", "MessageRole", "Note", "User"]
