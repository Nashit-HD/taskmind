from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from tests.integration.conftest import downgrade_to_base, upgrade_to_head

TABLES = {"users", "notes", "chats", "messages"}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_upgrade_to_head_creates_the_four_tables(migrated_engine: Engine) -> None:
    assert _tables(migrated_engine) >= TABLES


def test_downgrade_removes_the_tables_and_upgrade_restores_them(
    migrated_engine: Engine, alembic_config: Config
) -> None:
    downgrade_to_base(migrated_engine, alembic_config)
    assert not TABLES & _tables(migrated_engine)

    upgrade_to_head(migrated_engine, alembic_config)
    assert _tables(migrated_engine) >= TABLES


def test_the_migration_and_the_models_agree(
    migrated_engine: Engine, alembic_config: Config
) -> None:
    """``alembic check`` raises when autogenerate would add anything, so drift fails the suite."""
    with migrated_engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.check(alembic_config)


def test_the_cascades_are_declared_in_the_database(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    chat_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("chats")}
    message_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("messages")}

    assert chat_fks["fk_chats_note_id_notes"]["options"] == {"ondelete": "CASCADE"}
    assert message_fks["fk_messages_chat_id_chats"]["options"] == {"ondelete": "CASCADE"}
