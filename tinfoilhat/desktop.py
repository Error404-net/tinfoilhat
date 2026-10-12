"""Native desktop window backed by a private local Flask/Waitress server."""

import argparse
import ctypes
import json
import logging
import os
import secrets
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from platformdirs import user_data_path
from waitress import create_server, wasyncore

from tinfoilhat.app import create_app


def prepare_hackrf():
    """Prefer the bundled tools without requiring a global PATH change."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    tools = bundle_root / "hackrf"
    if tools.is_dir():
        os.environ["PATH"] = str(tools) + os.pathsep + os.environ.get("PATH", "")


def desktop_app(data_dir):
    """Use stable user storage across launches and installer updates."""
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / "session.key"
    try:
        with key_path.open("x", encoding="utf-8") as key_file:
            key_path.chmod(0o600)
            key_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return create_app(
        {
            "DATABASE": str(data_dir / "tinfoilhat.sqlite"),
            "UPLOAD_FOLDER": str(data_dir / "uploads"),
            "SECRET_KEY": key_path.read_text(encoding="utf-8"),
            "DESKTOP_MODE": True,
            "DESKTOP_LOG": str(data_dir / "desktop.log"),
        },
        instance_path=str(data_dir),
    )


class DesktopServer:
    """Own the listener, worker threads, and startup/shutdown lifecycle."""

    def __init__(self, app):
        self.socket_map = {}
        self.server = create_server(
            app, host="127.0.0.1", port=0, threads=8, map=self.socket_map, asyncore_loop_timeout=0.1
        )
        self.url = f"http://127.0.0.1:{self.server.effective_port}"
        self.thread = threading.Thread(target=self.server.run, name="desktop-http", daemon=True)

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with urlopen(self.url + "/leaderboard", timeout=1) as response:
                    data = json.load(response)
                if "leaderboard" in data and "contestants" in data:
                    return
            except (URLError, TimeoutError):
                pass
            if not self.thread.is_alive():
                break
            time.sleep(0.05)
        self.close()
        raise RuntimeError("The application server did not become ready.")

    def close(self):
        self.server.task_dispatcher.shutdown(timeout=3)
        wasyncore.close_all(self.socket_map)
        if self.thread.is_alive():
            self.thread.join(timeout=3)


class DesktopWindowAPI:
    """Only expose known display pages and controls for this native window."""

    def __init__(self, displays):
        self._displays = displays
        self._window = None
        self._fullscreen = False

    def open_display(self, path):
        return self._displays.open_display(path)

    def toggle_fullscreen(self):
        self._window.toggle_fullscreen()
        self._fullscreen = not self._fullscreen
        return self._fullscreen

    def get_fullscreen(self):
        return self._fullscreen


class DisplayWindows:
    def __init__(self, server_url):
        self._server_url = server_url
        self._windows = []

    def open_display(self, path):
        titles = {"/billboard": "RF Billboard", "/design-billboard": "Vote Showcase"}
        if path not in titles:
            raise ValueError("Unknown display screen.")
        import webview

        api = DesktopWindowAPI(self)
        window = webview.create_window(
            "Tinfoil Hat — " + titles[path],
            self._server_url + path,
            js_api=api,
            width=1280,
            height=900,
            resizable=True,
        )
        api._window = window
        self._windows.append(window)

        def forget_window():
            if window in self._windows:
                self._windows.remove(window)

        window.events.closed += forget_window
        return True


def smoke_check(server):
    """Validate packaged templates, assets, database writes, and readback."""
    from urllib.parse import urlencode
    from urllib.request import Request

    with urlopen(server.url, timeout=20) as response:
        if b"Tinfoil Hat Competition" not in response.read():
            raise RuntimeError("The packaged home page did not render.")
    for asset in ("jquery.min.js", "select2.min.js", "select2.min.css", "chart.umd.min.js"):
        with urlopen(server.url + "/static/vendor/" + asset, timeout=5) as response:
            if not response.read():
                raise RuntimeError(f"Missing packaged asset: {asset}")
    request = Request(
        server.url + "/contestants",
        data=urlencode({"name": "Desktop packaging smoke test"}).encode(),
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    with urlopen(request, timeout=5) as response:
        if json.load(response)["status"] != "success":
            raise RuntimeError("Contestant registration failed.")
    with urlopen(server.url + "/leaderboard", timeout=5) as response:
        if not any(c["name"] == "Desktop packaging smoke test" for c in json.load(response)["contestants"]):
            raise RuntimeError("Registered contestant was not persisted.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tinfoil Hat Competition desktop application")
    parser.add_argument("--data-dir", type=Path, help="Override the application data directory")
    parser.add_argument("--smoke-test", action="store_true", help="Validate packaging without opening a window")
    parser.add_argument("--gui-smoke-test", action="store_true", help="Validate the native window, then exit")
    parser.add_argument("--smoke-report", type=Path, help="Write a report only after smoke validation succeeds")
    args = parser.parse_args(argv)
    smoke = args.smoke_test or args.gui_smoke_test
    # Smoke runs never mutate the user's competition data.
    temporary = tempfile.TemporaryDirectory(prefix="tinfoilhat-smoke-", ignore_cleanup_errors=True) if smoke else None
    data_dir = Path(temporary.name) if temporary else (args.data_dir or user_data_path("TinfoilHat", appauthor=False))
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "desktop.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, force=True)
    # A --windowed executable has no stdout/stderr. The scanner currently uses print.
    log_stream = None
    if sys.stdout is None or sys.stderr is None:
        log_stream = log_path.open("a", encoding="utf-8")
        sys.stdout = sys.stderr = log_stream
    server = None
    try:
        prepare_hackrf()
        app = desktop_app(data_dir)
        server = DesktopServer(app)
        server.start()
        if smoke:
            smoke_check(server)
        if not args.smoke_test:
            import webview

            displays = DisplayWindows(server.url)
            window_api = DesktopWindowAPI(displays)
            window = webview.create_window(
                "Tinfoil Hat Competition", server.url, width=1280, height=900, js_api=window_api
            )
            window_api._window = window
            gui_errors = []

            def check_window():
                try:
                    if not window.events.loaded.wait(timeout=30):
                        raise RuntimeError("The desktop window did not load.")
                    title = window.evaluate_js("document.title")
                    if "Tinfoil Hat" not in title:
                        raise RuntimeError(f"Unexpected desktop page title: {title}")
                    if not window.evaluate_js(
                        "typeof window.Chart === 'function' && typeof window.jQuery?.fn?.select2 === 'function'"
                    ):
                        raise RuntimeError("The desktop browser dependencies did not load.")

                    def wait_for_page(path):
                        deadline = time.monotonic() + 20
                        while time.monotonic() < deadline:
                            try:
                                if window.evaluate_js(
                                    f"location.pathname === {json.dumps(path)} && document.readyState === 'complete'"
                                ):
                                    return
                            except Exception:
                                # WebView can reject script execution during a document transition.
                                pass
                            time.sleep(0.1)
                        raise RuntimeError(f"Desktop navigation did not reach {path}.")

                    for path in ("/vote", "/billboard", "/design-billboard"):
                        window.load_url(server.url + path)
                        wait_for_page(path)
                        if not window.evaluate_js("""(() => {
                            const button = document.getElementById('back-to-admin');
                            if (!button || new URL(button.href).pathname !== '/admin') return false;
                            const rect = button.getBoundingClientRect();
                            return rect.width >= 44 && rect.height >= 44 && rect.top >= 0 &&
                                rect.bottom <= innerHeight &&
                                Boolean(document.elementFromPoint(rect.x + rect.width / 2,
                                    rect.y + rect.height / 2)?.closest('#back-to-admin'));
                        })()"""):
                            raise RuntimeError(f"The Back to Admin button is not usable on {path}.")
                        window.evaluate_js("document.getElementById('back-to-admin').click()")
                        wait_for_page("/admin")
                    window.resize(360, 640)
                    window.load_url(server.url + "/vote")
                    wait_for_page("/vote")
                    window.evaluate_js("""document.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Backspace', bubbles: true, cancelable: true
                    }))""")
                    wait_for_page("/admin")
                    window.resize(1280, 900)
                    window.evaluate_js("document.querySelector('[aria-controls=diagnostics]').click()")
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if window.evaluate_js(
                            "document.getElementById('diagnostics-message').textContent === 'Diagnostics updated.'"
                        ):
                            break
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("Admin diagnostics did not load in the desktop window.")
                    if not window.evaluate_js(
                        "document.getElementById('diagnostics-status').textContent.includes('hackrf_info:') && "
                        "document.getElementById('diagnostics-status').textContent.includes('pywebview:')"
                    ):
                        raise RuntimeError("Admin diagnostics did not display desktop dependencies and HackRF tools.")
                    window.evaluate_js("document.getElementById('diagnostics-check').click()")
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if window.evaluate_js(
                            "document.getElementById('diagnostics-message').textContent === 'Diagnostics updated.' && "
                            "document.getElementById('diagnostics-device').textContent.includes('Checked:')"
                        ):
                            break
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("The Admin HackRF check did not finish in the desktop window.")
                    for path in ("/billboard", "/design-billboard"):
                        window.evaluate_js(f"document.querySelector('a[href={json.dumps(path)}]').click()")
                        deadline = time.monotonic() + 20
                        while not displays._windows and time.monotonic() < deadline:
                            time.sleep(0.1)
                        if not displays._windows:
                            raise RuntimeError(f"Clicking {path} did not open a separate native window.")
                        child = displays._windows[-1]
                        try:
                            if not child.events.loaded.wait(timeout=30):
                                raise RuntimeError("The display window did not load.")
                            if not child.evaluate_js(f"location.pathname === {json.dumps(path)}"):
                                raise RuntimeError("The display window opened the wrong page.")
                            wait_for_page("/admin")
                            child.move(80, 80)
                            child.evaluate_js("document.getElementById('display-fullscreen').click()")
                            deadline = time.monotonic() + 10
                            while time.monotonic() < deadline:
                                if child.evaluate_js(
                                    "document.getElementById('display-fullscreen')"
                                    ".getAttribute('aria-pressed') === 'true'"
                                ):
                                    break
                                time.sleep(0.1)
                            else:
                                raise RuntimeError("The display fullscreen button did not work.")
                            child.evaluate_js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
                            deadline = time.monotonic() + 10
                            while time.monotonic() < deadline:
                                if child.evaluate_js(
                                    "document.getElementById('display-fullscreen')"
                                    ".getAttribute('aria-pressed') === 'false'"
                                ):
                                    break
                                time.sleep(0.1)
                            else:
                                raise RuntimeError("The display window did not exit fullscreen.")
                        finally:
                            child.destroy()
                            displays._windows.clear()
                except Exception as error:
                    gui_errors.append(error)
                finally:
                    for child in displays._windows:
                        child.destroy()
                    window.destroy()

            webview.start(
                func=check_window if args.gui_smoke_test else None,
                gui="edgechromium" if sys.platform == "win32" else None,
                storage_path=str(data_dir / "webview"),
                private_mode=False,
                icon=str(Path(app.root_path) / "static" / "img" / "tinfoil-wizard-hat.png"),
            )
            if gui_errors:
                raise gui_errors[0]
        if args.smoke_report:
            args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
            args.smoke_report.write_text(
                json.dumps({"status": "passed", "native_window": args.gui_smoke_test}), encoding="utf-8"
            )
        return 0
    except Exception as error:
        logging.exception("Desktop startup failed")
        if args.smoke_report:
            args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
            args.smoke_report.write_text(json.dumps({"status": "failed", "error": str(error)}), encoding="utf-8")
        if sys.platform == "win32" and not smoke:
            ctypes.windll.user32.MessageBoxW(
                None,
                f"Tinfoil Hat could not start: {error}\n\nDetails: {log_path}\n"
                "Try reinstalling to repair the WebView2 runtime.",
                "Tinfoil Hat Competition",
                0x10,
            )
        return 1
    finally:
        if server:
            server.close()
        logging.shutdown()
        if log_stream:
            log_stream.close()
            sys.stdout = sys.stderr = None
        if temporary:
            temporary.cleanup()
