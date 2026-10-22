"""
Downloads a portable (no-install, no-admin-rights-needed) Eclipse Temurin
JDK 17 into .tools/, for PySpark to use. Only needed on a machine with no
system Java already on PATH — spark/session.py automatically falls back
to this bundled JDK if JAVA_HOME isn't already set.

Run:
    python scripts/setup_java.py
"""

import platform
import shutil
import urllib.request
import zipfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / ".tools"
ZIP_PATH = TOOLS_DIR / "jdk17.zip"

ADOPTIUM_URLS = {
    "windows": "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk",
    "linux": "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk",
    "darwin": "https://api.adoptium.net/v3/binary/latest/17/ga/mac/x64/jdk/hotspot/normal/eclipse?project=jdk",
}


def main():
    system = platform.system().lower()
    if system not in ADOPTIUM_URLS:
        raise SystemExit(f"Unsupported OS: {system}. Install a JDK 17 manually and set JAVA_HOME.")

    if any(TOOLS_DIR.glob("jdk-*")):
        print(f"A JDK already exists under {TOOLS_DIR}, skipping download.")
        return

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading Eclipse Temurin JDK 17 (~180MB)...")
    urllib.request.urlretrieve(ADOPTIUM_URLS[system], ZIP_PATH)

    print("Extracting...")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(TOOLS_DIR)
    ZIP_PATH.unlink()

    jdk_dirs = list(TOOLS_DIR.glob("jdk-*"))
    print(f"Done. JDK available at: {jdk_dirs[0] if jdk_dirs else TOOLS_DIR}")


if __name__ == "__main__":
    main()
