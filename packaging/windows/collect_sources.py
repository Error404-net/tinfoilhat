"""Include checksum-verified corresponding sources and recipes for GPL/LGPL tools."""

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml


def collect_sources(licenses):
    for record_path in (licenses / "package-records").glob("*.json"):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if "GPL" not in record.get("license", "").upper():
            continue
        directory = licenses / f"{record['name']}-{record['version']}-{record['build']}"
        recipe_path = directory / "recipe" / "meta.yaml"
        if not recipe_path.is_file():
            recipe_path = directory / "recipe" / "recipe.yaml"
        if not recipe_path.is_file():
            raise RuntimeError(f"Missing source recipe for {record['name']}")
        text = recipe_path.read_text(encoding="utf-8")
        recipe = yaml.safe_load(text)
        # Rattler recipes use simple context substitutions instead of rendered meta.yaml.
        for name, value in recipe.get("context", {}).items():
            if isinstance(value, (str, int, float)):
                text = re.sub(r"\$\{\{\s*" + re.escape(name) + r"\s*\}\}", str(value), text)
        recipe = yaml.safe_load(text)
        sources = recipe.get("source", [])
        sources = sources if isinstance(sources, list) else [sources]
        if not sources:
            raise RuntimeError(f"Missing corresponding source for {record['name']}")
        for source in sources:
            urls = source.get("url", [])
            urls = urls if isinstance(urls, list) else [urls]
            checksum = source.get("sha256")
            if not urls or not checksum or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
                raise RuntimeError(f"No verifiable source archive for {record['name']}")
            errors = []
            for url in urls:
                # Some upstream recipes retain old HTTP links; require the TLS equivalent.
                url = re.sub(r"^http://", "https://", url)
                if not url.startswith("https://") or "${{" in url:
                    continue
                try:
                    with urlopen(url, timeout=60) as response:
                        content = response.read()
                    if hashlib.sha256(content).hexdigest() != checksum.lower():
                        raise RuntimeError(f"Source checksum mismatch for {url}")
                    target = directory / "source" / Path(urlparse(url).path).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    print(f"Included verified source for {record['name']}")
                    break
                except Exception as error:
                    errors.append(str(error))
            else:
                raise RuntimeError(f"Cannot fetch source for {record['name']}: {errors}")


if __name__ == "__main__":
    collect_sources(Path(sys.argv[1]))
