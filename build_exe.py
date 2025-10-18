"""Utility script to build the standalone CN Upload Results executable.

Usage:
    python build_exe.py [--clean]

This wraps PyInstaller using the bundled ``cn_upload_results.spec`` so the resulting
``CNUploadResults.exe`` includes Python, dependencies, Qt libraries, and the `.env`
configuration file. After running the script, the executable will be available under
``dist/CNUploadResults``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_pyinstaller(*, clean: bool) -> None:
    """Invoke PyInstaller with the project specification file."""

    repo_root = Path(__file__).parent.resolve()
    spec_path = repo_root / "cn_upload_results.spec"
    build_dir = repo_root / "build"
    dist_dir = repo_root / "dist"

    if not spec_path.exists():
        raise FileNotFoundError(f"No spec file found at {spec_path}")

    if clean:
        for path in (build_dir, dist_dir):
            if path.exists():
                shutil.rmtree(path)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path),
    ]

    env = os.environ.copy()
    env.setdefault("PYI_SPEC_PATH", str(spec_path))

    subprocess.run(command, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CN Upload Results executable.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previous build artifacts before creating the new executable.",
    )
    args = parser.parse_args()

    run_pyinstaller(clean=args.clean)


if __name__ == "__main__":
    main()
