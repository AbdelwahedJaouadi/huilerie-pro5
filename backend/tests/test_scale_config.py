import pytest
from pydantic import ValidationError

from models.schemas import AppSettings, ScaleConfig


def test_scale_profile_defaults_to_disabled_and_does_not_assume_connection():
    config = ScaleConfig()
    assert config.enabled is False
    assert config.connection_type == "serial"
    assert config.protocol == ""
    assert config.serial_port == ""


def test_serial_scale_requires_port_and_explicit_protocol_when_enabled():
    with pytest.raises(ValidationError, match="scale_serial_port_required"):
        ScaleConfig(enabled=True, protocol="vendor-v1")
    with pytest.raises(ValidationError, match="scale_protocol_required"):
        ScaleConfig(enabled=True, serial_port="/dev/ttyUSB0")


def test_ethernet_scale_requires_host_port_and_protocol_when_enabled():
    with pytest.raises(ValidationError, match="scale_ethernet_host_and_port_required"):
        ScaleConfig(enabled=True, connection_type="ethernet", host="192.168.1.20", protocol="vendor-v1")
    config = ScaleConfig(
        enabled=True, connection_type="ethernet", host="192.168.1.20",
        port=4001, protocol="vendor-v1",
    )
    assert config.port == 4001


def test_usb_scale_requires_explicit_protocol_when_enabled():
    with pytest.raises(ValidationError, match="scale_protocol_required"):
        ScaleConfig(enabled=True, connection_type="usb")
    config = ScaleConfig(enabled=True, connection_type="usb", protocol="vendor-usb-v2")
    assert config.connection_type == "usb"


def test_app_settings_supply_default_scale_profile_for_legacy_database_records():
    settings = AppSettings(price_per_kg=0)
    assert settings.scale_config.enabled is False
    assert settings.scale_config.unit == "kg"
    assert settings.scale_config.decimal_places == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"baud_rate": 0},
        {"decimal_places": 4},
        {"stable_readings": 0},
        {"port": 65536},
    ],
)
def test_scale_profile_rejects_out_of_range_transport_and_precision_values(payload):
    with pytest.raises(ValidationError):
        ScaleConfig(**payload)
