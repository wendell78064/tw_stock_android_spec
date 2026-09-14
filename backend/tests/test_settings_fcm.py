from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_monitoring_user_id_absent_is_none():
    assert Settings().fcm_monitoring_user_id is None


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_monitoring_user_id_blank_is_none(value):
    assert Settings(fcm_monitoring_user_id=value).fcm_monitoring_user_id is None


def test_monitoring_user_id_valid_uuid_is_parsed():
    value = "12345678-1234-4234-8234-123456789abc"
    assert Settings(fcm_monitoring_user_id=value).fcm_monitoring_user_id == UUID(value)


def test_monitoring_user_id_malformed_nonempty_is_rejected():
    with pytest.raises(ValidationError):
        Settings(fcm_monitoring_user_id="not-a-uuid")


def test_fcm_disabled_with_blank_monitoring_user_id_loads():
    settings = Settings(fcm_enabled=False, fcm_monitoring_user_id=" ")
    assert settings.fcm_enabled is False
    assert settings.fcm_monitoring_user_id is None


def test_monitoring_user_id_normalization_does_not_change_fcm_settings():
    settings = Settings(
        fcm_enabled=True,
        fcm_project_id="project",
        fcm_credentials_file="/app/config/firebase-service-account.json",
        fcm_monitoring_user_id="",
    )
    assert settings.fcm_enabled is True
    assert settings.fcm_project_id == "project"
    assert settings.fcm_credentials_file == "/app/config/firebase-service-account.json"
    assert settings.fcm_monitoring_user_id is None
