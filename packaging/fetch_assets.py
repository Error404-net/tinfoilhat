"""Fetch versioned UI dependencies with TLS and fixed SHA-256 verification."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

ASSETS = {
    "jquery-LICENSE.txt": (
        "https://cdn.jsdelivr.net/npm/jquery@3.7.1/LICENSE.txt",
        "d4db9ebe6f29f5168eac45ad713f055623ac5d0dcd5ba92da23d650ae012020d",
    ),
    "chart-LICENSE.md": (
        "https://cdn.jsdelivr.net/npm/chart.js@4.3.0/LICENSE.md",
        "5a0877ad6d818529be4f33009d0942cdf7e2ed7656156f4aba7308459a546030",
    ),
    "select2-LICENSE.md": (
        "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/LICENSE.md",
        "4ee0cbc51370afde358652a0f977972053729ed578b6a42f5e2a037d114f0b39",
    ),
    "chart.umd.min.js": (
        "https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js",
        "87899805686b553e6ff3c8bfed71f38dca31ac0c295f52fe5ef5f318a85c9b61",
    ),
    "jquery.min.js": (
        "https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js",
        "fc9a93dd241f6b045cbff0481cf4e1901becd0e12fb45166a8f17f95823f0b1a",
    ),
    "select2.min.js": (
        "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js",
        "f7244fff610595b944f76bf3080d74e3af42b5dd234f8f079e698cc39ac966b0",
    ),
    "select2.min.css": (
        "https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css",
        "cda4a81c187015d95ed2c71f1841540b08203cdec5fa2a7d5d1825a3c2166f8c",
    ),
}


def fetch_assets(destination=None):
    destination = destination or Path(__file__).resolve().parents[1] / "tinfoilhat" / "static" / "vendor"
    destination.mkdir(parents=True, exist_ok=True)
    for filename, (url, expected_hash) in ASSETS.items():
        target = destination / filename
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected_hash:
            continue
        with urlopen(url, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise RuntimeError(f"SHA-256 verification failed for {filename}")
        target.write_bytes(content)
        print(f"Verified {filename}")


if __name__ == "__main__":
    fetch_assets()
