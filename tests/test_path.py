import subprocess
from pathlib import Path

import pytest
from lyndows.path import UPurePosixPath, UPureWindowsPath


def winepath(path: str, mode: str) -> str:
    return subprocess.check_output(
        ["winepath", f"-{mode}", str(path)], encoding="UTF-8", shell=False  # type: ignore
    ).strip()


class TestUPurePosixPath:
    def test_expanduser_with_tilde(self):
        path = UPurePosixPath("~/case")
        expanded_path = path.expanduser()
        expected_result = UPurePosixPath(Path.home() / "case")
        assert expanded_path == expected_result

    def test_expanduser_without_tilde(self):
        path = UPurePosixPath("path/to/file")
        expanded_path = path.expanduser()
        assert expanded_path == UPurePosixPath("path/to/file")

    def test_absolute(self):
        # Test when the path is already absolute
        path = UPurePosixPath("/home/user/test")
        assert path.absolute() == path

        # Test when the path is relative
        path = UPurePosixPath("test")
        expected_result = UPurePosixPath(Path.cwd() / path)
        assert path.absolute() == expected_result

    def test_is_absolute(self):
        # Test when the path is absolute
        path = UPurePosixPath("/home/user/test")
        assert path.is_absolute()

        # Test when the path is relative
        path = UPurePosixPath("test")
        assert not path.is_absolute()

    def test_joinpath(self):
        # Test joining a path with a string
        path = UPurePosixPath("/home/user")
        joined_path = path.joinpath("test")
        assert str(joined_path) == "/home/user/test"

        # Test joining a path with another path
        path1 = UPurePosixPath("/home/user")
        path2 = UPurePosixPath("test")
        joined_path = path1.joinpath(path2)
        assert str(joined_path) == "/home/user/test"

    def test_is_mount(self):
        # Test when the path is a mount point
        path = UPurePosixPath("/")
        assert path.is_mount()

        # Test when the path is not a mount point
        path = UPurePosixPath("/home/user/test")
        assert not path.is_mount()

    def test_mount_point(self):
        # Test getting the mount points on the system
        raise AssertionError()

    def test_as_windows(self):
        # Test converting a POSIX path to a Windows path
        _str = "/home/user/test"
        _wstr = winepath(_str, "w")
        path = UPurePosixPath(_str)
        windows_path = path.as_windows()
        assert UPureWindowsPath(_wstr) == windows_path
        # assert str(windows_path) == _wstr
