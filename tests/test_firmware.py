"""Unit tests for firmware lookup helpers."""

from unittest.mock import Mock, patch

from py_netgear_plus import NetgearSwitchConnector
from py_netgear_plus.firmware import get_latest_firmware_info, is_update_available
from py_netgear_plus.models import GS105Ev2

SITEMAP_XML = """\
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://kb.netgear.com/000064372/GS105Ev2-Firmware-Version-1-6-0-11</loc>
    <lastmod>2025-10-17</lastmod>
  </url>
  <url>
    <loc>https://kb.netgear.com/000070626/GS105Ev2-Firmware-Version-1-6-0-24</loc>
    <lastmod>2026-04-01</lastmod>
  </url>
  <url>
    <loc>https://kb.netgear.com/000070622/GS108Ev4-Firmware-Version-1-0-1-13</loc>
    <lastmod>2026-04-01</lastmod>
  </url>
</urlset>
"""

ARTICLE_HTML = """\
<html>
  <body>
    <h1>GS105Ev2 Firmware Version 1.6.0.24</h1>
    <p>Security Fixes:</p>
    <ul><li>Fixes security vulnerabilities.</li></ul>
    <p>Download Link:
      <a href="https://www.downloads.netgear.com/files/GDC/GS105EV2/GS105Ev2_V1.6.0.24.zip">
        firmware
      </a>
    </p>
    <p>Firmware Update Instructions:</p>
  </body>
</html>
"""


def test_is_update_available() -> None:
    """Test firmware version comparison."""
    assert is_update_available("V1.6.0.15", "1.6.0.24") is True
    assert is_update_available("V1.6.0.24", "1.6.0.24") is False
    assert is_update_available(None, "1.6.0.24") is False


@patch("py_netgear_plus.firmware.requests.get")
def test_get_latest_firmware_info(mock_get: Mock) -> None:
    """Test lookup of latest firmware from KB sitemap and article."""
    mock_get.side_effect = [
        Mock(status_code=200, text=SITEMAP_XML, raise_for_status=Mock()),
        Mock(status_code=200, text=ARTICLE_HTML, raise_for_status=Mock()),
    ]

    result = get_latest_firmware_info("GS105Ev2", "V1.6.0.15")

    assert result == {
        "model_name": "GS105Ev2",
        "installed_version": "1.6.0.15",
        "installed_version_raw": "V1.6.0.15",
        "latest_version": "1.6.0.24",
        "update_available": True,
        "release_url": "https://kb.netgear.com/000070626/GS105Ev2-Firmware-Version-1-6-0-24",
        "download_url": "https://www.downloads.netgear.com/files/GDC/GS105EV2/GS105Ev2_V1.6.0.24.zip",
        "release_date": "2026-04-01",
        "release_title": "GS105Ev2 Firmware Version 1.6.0.24",
        "release_summary": "Security Fixes: Fixes security vulnerabilities.",
    }


@patch("py_netgear_plus.get_latest_firmware_info")
def test_connector_get_firmware_update_info(
    mock_get_latest_firmware_info: Mock,
) -> None:
    """Test connector firmware lookup uses cached switch metadata."""
    connector = NetgearSwitchConnector(host="192.168.0.1", password="password")
    connector._set_instance_attributes_by_model(GS105Ev2())
    connector._loaded_switch_metadata = {"switch_firmware": "V1.6.0.15"}
    mock_get_latest_firmware_info.return_value = {"latest_version": "1.6.0.24"}

    result = connector.get_firmware_update_info()

    assert result == {"latest_version": "1.6.0.24"}
    mock_get_latest_firmware_info.assert_called_once_with(
        "GS105Ev2", "V1.6.0.15"
    )
