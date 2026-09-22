from pathlib import Path

import pytest

from app.core.config import Settings, load_settings, redact_mapping


def test_demo_mode_cannot_enable_ssh_or_ncc() -> None:
    with pytest.raises(ValueError, match="demo mode"):
        Settings(demo_mode=True, enable_ssh=True).validate_safety()

    with pytest.raises(ValueError, match="demo mode"):
        Settings(demo_mode=True, enable_ncc=True, enable_ssh=True).validate_safety()


def test_production_cannot_skip_tls_verification() -> None:
    with pytest.raises(ValueError, match="insecure TLS"):
        Settings(environment="production", tls_mode="insecure_skip_verify").validate_safety()


def test_redaction_hides_secret_values() -> None:
    values = {
        "CAO_PC_PASSWORD": "secret",
        "Authorization": "Bearer abc",
        "CAO_PC_URL": "https://example.invalid",
    }

    assert redact_mapping(values) == {
        "CAO_PC_PASSWORD": "***REDACTED***",
        "Authorization": "***REDACTED***",
        "CAO_PC_URL": "https://example.invalid",
    }


def test_load_settings_from_local_env(tmp_path: Path) -> None:
    env_file = tmp_path / "local.env"
    env_file.write_text(
        "\n".join(
            [
                "CAO_ENVIRONMENT=lab",
                "CAO_DEMO_MODE=false",
                "CAO_PC_URL=https://192.0.2.205:9440/",
                "CAO_PC_USERNAME=admin",
                "CAO_PC_PASSWORD=secret",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.environment == "lab"
    assert settings.demo_mode is False
    assert settings.pc_url == "https://192.0.2.205:9440/"
    assert settings.redacted()["pc_password"] == "***REDACTED***"
