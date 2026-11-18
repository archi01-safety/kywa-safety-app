"""Package the generated public files for a manual Netlify deployment."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {
    "_headers", "_redirects", "index.html", "style.css", "app.mjs",
    "controller.mjs", "config.json", "assets/icon.png",
}
NETLIFY_CONFIG = b"""[build]
  command = "test -s site/index.html && test -s site/_redirects"
  publish = "site"
"""


def package(organization):
    if not re.fullmatch("[a-z]{3,8}", organization):
        raise ValueError("Specify an institution ID with --org")
    dist = ROOT / "dist"
    build = json.loads((dist / f"{organization}.manifest.json").read_text(encoding="utf-8"))
    if build["organization"] != organization:
        raise ValueError("Build manifest belongs to another institution")
    rows = {row["path"]: row for row in build["files"]}
    if set(rows) != PUBLIC_FILES or len(build["files"]) != len(PUBLIC_FILES):
        raise ValueError("Unexpected public file list")

    # Logged-in uploads run framework detection. Specify the prebuilt output explicitly.
    entries = {"netlify.toml": NETLIFY_CONFIG}
    for name, row in sorted(rows.items()):
        data = (dist / organization / PurePosixPath(name)).read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"Rebuild before packaging: {name} changed")
        entries[f"site/{name}"] = data
    artifacts = ROOT.parent / "artifacts"
    artifacts.mkdir(exist_ok=True)
    archive = artifacts / f"{organization}-entry-static.zip"
    with zipfile.ZipFile(archive, "w") as package_file:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            package_file.writestr(info, data)

    manifest = {
        **build,
        "sourceCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "archive": archive.name,
        "archiveBytes": archive.stat().st_size,
        "archiveSha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "publishDirectory": "site",
    }
    archive.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in ("archive", "archiveBytes", "archiveSha256")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    package(parser.parse_args().org)
