#!/usr/bin/env python3
"""Build the NET KIT single-file executable: dist/netkit.pyz.

Cross-platform (no shell, no make needed). Used by both `make build` and CI so
there is one build path. zipapp requires the package to sit UNDER the archive
source root (so the generated top-level __main__.py can import it); we stage a
parent dir and zip that, rather than zipping the package directly (which would
collide with the package's own __main__.py).
"""
import shutil
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build_stage"
DIST = ROOT / "dist"
OUT = DIST / "netkit.pyz"


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    DIST.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "netkit", STAGE / "netkit",
                    ignore=shutil.ignore_patterns("__pycache__"))
    zipapp.create_archive(STAGE, target=OUT, main="netkit.server:main",
                          interpreter="/usr/bin/env python3")
    shutil.rmtree(STAGE)
    try:
        OUT.chmod(0o755)
    except OSError:
        pass
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
