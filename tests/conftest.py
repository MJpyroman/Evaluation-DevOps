import pytest

import app as app_module


@pytest.fixture
def client():
    return app_module.app.test_client()
