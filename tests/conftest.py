import pytest

from urbancart import cleaning


@pytest.fixture(scope="session")
def built():
    con, dq = cleaning.build_warehouse()  # in-memory, from data/
    yield con, dq
    con.close()


@pytest.fixture(scope="session")
def con(built):
    return built[0]


@pytest.fixture(scope="session")
def dq(built):
    return built[1].set_index("issue")
