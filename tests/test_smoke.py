"""Smoke tests: the package imports, and the free suite stays offline."""



def test_import_app():
    import app  # noqa: F401


def test_free_suite_never_constructs_real_client(monkeypatch):
    # Even if a developer has a key exported for the paid tests, none of the free
    # tests build the real client: every agent test injects a FakeLLMClient and
    # the web tests inject a fake runner. This asserts the seam exists — calling
    # the real client requires an explicit key AND an explicit AnthropicLLMClient,
    # neither of which the free tests use.
    from app.agents.client import build_default_client

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # empty -> treated as absent
    assert build_default_client() is None


def test_build_default_client_without_key_returns_none(monkeypatch):
    from app.agents.client import build_default_client

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert build_default_client() is None
