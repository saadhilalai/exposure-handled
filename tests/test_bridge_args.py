"""The bridge's start-up switches and its kill-switch file (bridge/src/bridge_args.hpp), built without the Sony SDK
and run without any camera."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_bridge_args_and_lock_file(tmp_path):
    cxx = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
    if not cxx:
        pytest.skip("no C++ compiler")
    exe = tmp_path / "test_bridge_args"
    subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "bridge" / "src"),
                    str(ROOT / "bridge" / "tests" / "test_bridge_args.cpp"), "-o", str(exe)], check=True, timeout=120)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    out = subprocess.run([str(exe), str(scratch)], capture_output=True, text=True, timeout=10)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "all passed" in out.stdout
