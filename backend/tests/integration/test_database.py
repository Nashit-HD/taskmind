from sqlalchemy import Engine, text


def test_the_test_database_answers(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_the_test_database_is_the_test_database(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT current_database()")).scalar_one() == "taskmind_test"
