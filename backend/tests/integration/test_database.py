from sqlalchemy import Engine, text


def test_the_test_database_answers(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_the_suite_is_connected_to_a_test_database(engine: Engine) -> None:
    """The rule, not the name: whatever TEST_DATABASE_URL names, it must be a *_test database."""
    with engine.connect() as connection:
        name = connection.execute(text("SELECT current_database()")).scalar_one()

    assert name.endswith("_test")
