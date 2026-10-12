import logging
import subprocess
from unittest.mock import patch

import pytest

from tinfoilhat.desktop import desktop_app


@pytest.fixture
def client(tmp_path):
    return desktop_app(tmp_path).test_client()


def test_status_does_not_probe_hardware(client):
    with patch("tinfoilhat.diagnostics.subprocess.run") as run:
        data = client.get("/admin/diagnostics").get_json()
    run.assert_not_called()
    assert data["hackrf"] is None
    assert all(item["available"] for item in data["dependencies"])
    assert b"Diagnostics" in client.get("/admin").data


@pytest.mark.parametrize(
    "out,code,available",
    [
        ("HackRF One\nSerial number: 123", 0, True),
        ("No HackRF boards found.", 1, False),
        ("HackRF One", 1, False),
    ],
)
def test_hardware_result_and_cached_status(client, out, code, available):
    with (
        patch("tinfoilhat.diagnostics.shutil.which", return_value="/tools/hackrf_info"),
        patch(
            "tinfoilhat.diagnostics.subprocess.run", return_value=subprocess.CompletedProcess([], code, out, "")
        ) as run,
    ):
        result = client.post("/admin/diagnostics/hackrf").get_json()
        assert result["available"] is available
        assert result["exit_code"] == code
        assert out in result["output"]
        assert client.get("/admin/diagnostics").get_json()["hackrf"] == result
    assert run.call_count == 1
    assert run.call_args.kwargs["timeout"] == 5


def test_missing_tools(client):
    with (
        patch("tinfoilhat.diagnostics.shutil.which", return_value=None),
        patch("tinfoilhat.diagnostics.subprocess.run") as run,
    ):
        result = client.post("/admin/diagnostics/hackrf").get_json()
    run.assert_not_called()
    assert not result["available"]
    assert "missing" in result["message"]


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("hackrf_info", 5), OSError("missing DLL")])
def test_tool_failures_are_reported(client, error):
    with (
        patch("tinfoilhat.diagnostics.shutil.which", return_value="/tools/hackrf_info"),
        patch("tinfoilhat.diagnostics.subprocess.run", side_effect=error),
    ):
        response = client.post("/admin/diagnostics/hackrf")
    assert response.status_code == 200
    assert not response.get_json()["available"]
    assert response.get_json()["advice"]


def test_bounded_log_download(client, tmp_path):
    (tmp_path / "desktop.log").write_text("old line\n" * 12000 + "latest scanner error\n")
    response = client.get("/admin/diagnostics/logs")
    assert len(response.data) <= 65536
    assert response.data.endswith(b"latest scanner error\n")
    assert "attachment" in response.headers["Content-Disposition"]


def test_scanner_messages_captured_without_desktop_file(client, tmp_path):
    client.application.config.pop("DESKTOP_LOG")
    logging.getLogger("tinfoilhat.scanner").warning("USB detection failed")
    assert b"USB detection failed" in client.get("/admin/diagnostics/logs").data
