from verified_agent.api import _env_flag


def test_env_flag_treats_zero_as_false(monkeypatch):
    monkeypatch.setenv("USE_DOCKER", "0")
    assert _env_flag("USE_DOCKER") is False


def test_env_flag_accepts_true_values(monkeypatch):
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("USE_DOCKER", value)
        assert _env_flag("USE_DOCKER") is True
