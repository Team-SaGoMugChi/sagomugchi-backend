from app.core.config import Settings, get_settings
from app.services.counsel_context import resolve


def test_dummy_counsel_context_is_opt_in():
    assert Settings(_env_file=None).counsel_dummy_context is False


def test_missing_context_stays_missing_by_default(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "false")
    get_settings.cache_clear()

    context = resolve()

    assert context.emotions is None
    assert context.signals is None
    assert context.diary_summary is None
    assert context.recent_themes is None
    assert context.used_dummy is False


def test_dummy_context_can_be_enabled_for_local_ui_work(monkeypatch):
    monkeypatch.setenv("COUNSEL_DUMMY_CONTEXT", "true")
    get_settings.cache_clear()

    context = resolve()

    assert context.emotions
    assert context.signals
    assert context.diary_summary
    assert context.recent_themes
    assert context.used_dummy is True
