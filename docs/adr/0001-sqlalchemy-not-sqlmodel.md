# SQLAlchemy 2.0, not SQLModel

The official FastAPI skill recommends SQLModel, but we use plain SQLAlchemy 2.0 (synchronous, psycopg 3) with separate Pydantic request and response schemas. The assignment requires separate schemas anyway, so SQLModel's one-class-for-both saves little, and Alembic autogenerate works more smoothly with plain SQLAlchemy. Don't "fix" this by switching to SQLModel.
