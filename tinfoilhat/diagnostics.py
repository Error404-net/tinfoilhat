"""Bounded application logs and explicit, read-only hardware diagnostics."""

import logging
import platform
import shutil
import subprocess
import threading
from collections import deque
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify

bp = Blueprint("diagnostics", __name__)
logger = logging.getLogger(__name__)


class RecentLogs(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.lines = deque(maxlen=300)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        self.lines.append(self.format(record)[-4096:])

    def read(self):
        with self.lock:
            return "\n".join(self.lines)


recent_logs = RecentLogs()


def init_diagnostics(app):
    root = logging.getLogger()
    if recent_logs not in root.handlers:
        root.addHandler(recent_logs)
    app.extensions["hackrf_diagnostics"] = {"lock": threading.Lock(), "result": None}
    app.register_blueprint(bp)


def read_logs():
    path = current_app.config.get("DESKTOP_LOG")
    if path:
        try:
            with Path(path).open("rb") as stream:
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(max(0, size - 65536))
                data = stream.read(65536)
            text = data.decode("utf-8", errors="replace")
            if size > 65536:
                text = text.partition("\n")[2]
            return text
        except OSError as error:
            return f"Unable to read desktop log: {error}\n" + recent_logs.read()
    return recent_logs.read()


@bp.get("/admin/diagnostics")
def status():
    packages = ["Flask", "numpy"]
    if current_app.config.get("DESKTOP_MODE"):
        packages += ["pywebview", "waitress", "platformdirs"]
    dependencies = []
    for name in packages:
        try:
            dependencies.append({"name": name, "version": version(name), "available": True})
        except PackageNotFoundError:
            dependencies.append({"name": name, "version": None, "available": False})
    return jsonify(
        python=platform.python_version(),
        platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
        dependencies=dependencies,
        tools={name: shutil.which(name) for name in ("hackrf_info", "hackrf_transfer")},
        hackrf=current_app.extensions["hackrf_diagnostics"]["result"],
        log_path=current_app.config.get("DESKTOP_LOG"),
        logs=read_logs(),
    )


@bp.post("/admin/diagnostics/hackrf")
def check_hackrf():
    state = current_app.extensions["hackrf_diagnostics"]
    if not state["lock"].acquire(blocking=False):
        return jsonify(error="A HackRF check is already running."), 409
    try:
        executable = shutil.which("hackrf_info")
        result = {"checked_at": datetime.now(UTC).isoformat(), "available": False, "output": ""}
        if not executable:
            result.update(
                message="HackRF tools are missing.",
                advice="Reinstall the desktop application to restore its bundled HackRF tools. "
                "For a web installation, install HackRF tools and add them to PATH.",
            )
        else:
            try:
                process = subprocess.run(
                    [executable],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                result["output"] = (process.stdout + "\n" + process.stderr).strip()[-16384:]
                result["exit_code"] = process.returncode
                result["available"] = process.returncode == 0 and "HackRF One" in process.stdout
                result["message"] = "HackRF One detected." if result["available"] else "HackRF One is unavailable."
                result["advice"] = (
                    "The device can be opened. This check does not perform an RF measurement."
                    if result["available"]
                    else "Check the USB cable and port, reconnect the device, and close other SDR applications. "
                    "On Windows, confirm the HackRF device uses a compatible WinUSB driver. "
                    "A missing DLL error indicates the application should be reinstalled."
                )
            except subprocess.TimeoutExpired:
                result.update(
                    message="HackRF check timed out.",
                    advice="The device may be busy. " "Close other SDR applications and reconnect the USB device.",
                )
            except OSError as error:
                result.update(
                    message="HackRF tools could not start.",
                    output=str(error),
                    advice="Reinstall the application to repair missing tools or DLL dependencies.",
                )
        state["result"] = result
        logger.info("%s %s", result["message"], result["output"])
        return jsonify(result)
    finally:
        state["lock"].release()


@bp.get("/admin/diagnostics/logs")
def download_logs():
    return Response(
        read_logs(),
        mimetype="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="tinfoilhat-diagnostics.log"',
            "Cache-Control": "no-store",
        },
    )
