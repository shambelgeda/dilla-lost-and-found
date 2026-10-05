from app.config import settings
from app.main import app


def test_settings_use_case_sensitive_configuration():
    assert settings.model_config.get("case_sensitive") is True


def test_fastapi_uses_no_deprecated_startup_hook():
    assert app.router.on_startup == []
    assert app.router.on_shutdown == []
