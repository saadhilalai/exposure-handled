"""The bridge's build file keeps Sony's Linux layout for the Pi (it can only be built on the Pi itself, with Sony's
Linux SDK, so this checks the file)."""
import re
from pathlib import Path

CMAKE = (Path(__file__).resolve().parent.parent / "bridge" / "CMakeLists.txt").read_text()


def test_linux_branch_matches_sonys_sample():
    linux = CMAKE.split("    else()\n", 1)[1].split("    endif()", 1)[0]          # the non-Apple branch
    assert 'BUILD_RPATH "$ORIGIN"' in linux                                    # libraries next to the program
    assert "-fsigned-char" in linux and "-fstack-protector-all" in linux
    assert re.search(r'copy_directory "\$\{CRSDK_LIB_DIR\}" \$<TARGET_FILE_DIR:\$\{name\}>', linux)   # incl. CrAdapter


def test_threads_are_linked_explicitly():
    assert "find_package(Threads REQUIRED)" in CMAKE and "Threads::Threads" in CMAKE
