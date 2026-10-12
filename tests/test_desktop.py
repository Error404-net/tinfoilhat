"""Exercise desktop storage, real HTTP lifecycle, and writable packaged uploads."""

import io
import json
import sqlite3
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import urlopen

import pytest

pytest.importorskip("waitress")
pytest.importorskip("platformdirs")

from tinfoilhat.desktop import DesktopServer, DesktopWindowAPI, DisplayWindows, desktop_app


def test_competition_survives_restart(tmp_path):
    app = desktop_app(tmp_path)
    client = app.test_client()
    assert client.post("/contestants", data={"name": "Persistent entrant"}).status_code == 302
    secret = app.config["SECRET_KEY"]
    restarted = desktop_app(tmp_path)
    assert restarted.config["SECRET_KEY"] == secret
    assert any(
        c["name"] == "Persistent entrant" for c in restarted.test_client().get("/leaderboard").json["contestants"]
    )


def test_photo_is_stored_and_served_outside_package(tmp_path):
    app = desktop_app(tmp_path)
    client = app.test_client()
    photo = b"test photo bytes"
    response = client.post(
        "/contestants",
        data={"name": "Photographed entrant", "photo": (io.BytesIO(photo), "hat.png")},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200
    stored_photo = next((tmp_path / "uploads").glob("*.png"))
    assert stored_photo.read_bytes() == photo
    assert client.get("/static/uploads/" + stored_photo.name).data == photo
    assert client.get("/static/uploads/../session.key").status_code == 404


def test_empty_database_initializes_and_partial_database_is_preserved(tmp_path):
    (tmp_path / "tinfoilhat.sqlite").touch()
    assert desktop_app(tmp_path).test_client().get("/leaderboard").status_code == 200
    partial = tmp_path / "partial"
    partial.mkdir()
    with sqlite3.connect(partial / "tinfoilhat.sqlite") as db:
        db.execute("CREATE TABLE contestant (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO contestant(name) VALUES ('Do not erase')")
    with pytest.raises(sqlite3.OperationalError):
        desktop_app(partial)
    with sqlite3.connect(partial / "tinfoilhat.sqlite") as db:
        assert db.execute("SELECT name FROM contestant").fetchone()[0] == "Do not erase"


def test_real_server_readiness_and_shutdown(tmp_path):
    server = DesktopServer(desktop_app(tmp_path))
    try:
        server.start()
        assert server.url.startswith("http://127.0.0.1:")
        with urlopen(server.url + "/leaderboard", timeout=2) as response:
            assert json.load(response)["contestants"] == []
    finally:
        server.close()
    assert not server.thread.is_alive()
    with pytest.raises(URLError):
        urlopen(server.url + "/leaderboard", timeout=1)


def test_desktop_kiosk_links_stay_in_application_window(tmp_path):
    app = desktop_app(tmp_path)
    response = app.test_client().get("/admin")
    assert response.status_code == 200
    assert b'href="/vote" target="_self"' in response.data
    assert b'href="/billboard" target="_self"' in response.data
    assert b'href="/design-billboard" target="_self"' in response.data
    assert b"js/desktop-navigation.js" in response.data


def test_display_windows_only_open_known_local_pages():
    displays = DisplayWindows("http://127.0.0.1:12345")
    with patch("webview.create_window") as create:
        with pytest.raises(ValueError):
            displays.open_display("https://example.com")
        create.assert_not_called()
        assert displays.open_display("/billboard")
        assert create.call_args.args[1] == "http://127.0.0.1:12345/billboard"
        assert create.call_args.kwargs["resizable"]
        api = create.call_args.kwargs["js_api"]
        api.toggle_fullscreen()
        create.return_value.toggle_fullscreen.assert_called_once()


def test_native_fullscreen_targets_own_window():
    api = DesktopWindowAPI(MagicMock())
    api._window = MagicMock()
    assert api.toggle_fullscreen()
    api._window.toggle_fullscreen.assert_called_once()
