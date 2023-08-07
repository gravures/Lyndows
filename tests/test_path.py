import subprocess
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest
from lyndows.path import UPath, UPosixPath, UWindowsPath, UWinePath
from lyndows.util import on_windows


def winepath(path: str, mode: str) -> str:
    return subprocess.check_output(
        ["winepath", f"-{mode}", str(path)], encoding="UTF-8", shell=False  # type: ignore
    ).strip()


class TestUPath:
    def test_new(self):
        if on_windows:
            assert isinstance(UPath("/home/user/test"), UWindowsPath)
        else:
            assert isinstance(UPath("/home/user/test"), UPosixPath)
            assert isinstance(UPath("c:/home/user/test"), UWinePath)


class TestUWindowsPath:
    def test_new(self):
        if not on_windows():
            with pytest.raises(NotImplementedError):
                UPosixPath("/home/user/test")
            return
        path = UPosixPath("/home/user/test")
        assert path.__class__.__mro__ == (
            UWindowsPath,
            UPath,
            Path,
            PureWindowsPath,
            PurePath,
            object,
        )


class TestUWinePath:
    def test_new(self):
        if on_windows():
            with pytest.raises(NotImplementedError):
                UPosixPath("/home/user/test")
            return
        path = UWinePath("/home/user/test")
        assert path.__class__.__mro__ == (
            UWinePath,
            UPath,
            Path,
            PureWindowsPath,
            PurePath,
            object,
        )


class TestUPosixPath:
    def test_new(self):
        if on_windows():
            with pytest.raises(NotImplementedError):
                UPosixPath("/home/user/test")
            return
        path = UPosixPath("/home/user/test")
        assert path.__class__.__mro__ == (
            UWinePath,
            UPath,
            Path,
            PurePosixPath,
            PurePath,
            object,
        )

    def test_expanduser_with_tilde(self):
        path = UPosixPath("~/case")
        expanded_path = path.expanduser()
        expected_result = UPosixPath(Path.home() / "case")
        assert expanded_path == expected_result

    def test_expanduser_without_tilde(self):
        path = UPosixPath("path/to/file")
        expanded_path = path.expanduser()
        assert expanded_path == UPosixPath("path/to/file")

    def test_absolute(self):
        # Test when the path is already absolute
        path = UPosixPath("/home/user/test")
        assert path.absolute() == path

        # Test when the path is relative
        path = UPosixPath("test")
        expected_result = UPosixPath(Path.cwd() / path)
        assert path.absolute() == expected_result

    def test_is_absolute(self):
        # Test when the path is absolute
        path = UPosixPath("/home/user/test")
        assert path.is_absolute()

        # Test when the path is relative
        path = UPosixPath("test")
        assert not path.is_absolute()

    def test_joinpath(self):
        # Test joining a path with a string
        path = UPosixPath("/home/user")
        joined_path = path.joinpath("test")
        assert str(joined_path) == "/home/user/test"

        # Test joining a path with another path
        path1 = UPosixPath("/home/user")
        path2 = UPosixPath("test")
        joined_path = path1.joinpath(path2)
        assert str(joined_path) == "/home/user/test"

    def test_is_mount(self):
        # Test when the path is a mount point
        path = UPosixPath("/")
        assert path.is_mount()

        # Test when the path is not a mount point
        path = UPosixPath("/home/user/test")
        assert not path.is_mount()

    def test_mount_point(self):
        # Test getting the mount points on the system
        raise AssertionError()

    def test_as_windows(self):
        # Test converting a POSIX path to a Windows path
        _str = "/home/user/test"
        _wstr = winepath(_str, "w")
        path = UPosixPath(_str)
        windows_path = path.as_windows()
        assert UWinePath(_wstr) == windows_path
        # assert str(windows_path) == _wstr
