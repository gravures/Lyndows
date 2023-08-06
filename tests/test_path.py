import pytest
from lyndows.path import UPurePosixPath


class TestUPurePosixPath:
    def test_expanduser_with_tilde(self):
        path = UPurePosixPath("~/case")
        expanded_path = path.expanduser()
        assert expanded_path == UPurePosixPath("/home/username/case")

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
        expected_result = UPurePosixPath("/current/working/directory").joinpath(path)
        assert path.absolute() == expected_result

    def test_is_absolute(self):
        # Test when the path is absolute
        path = UPurePosixPath("/home/user/test")
        assert path.is_absolute()

        # Test when the path is relative
        path = UPurePosixPath("test")
        assert path.is_absolute()

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

    # def test_mount_point(self):
    #     # Test getting the mount points on the system
    #     mount_point = UPurePosixPath.mount_point()
    #     expected_mount_point = [UPurePosixPath("/"), UPurePosixPath("/mnt")]
    #     self.assertEqual(mount_point, expected_mount_point)

    def test_as_windows(self):
        # Test converting a POSIX path to a Windows path
        path = UPurePosixPath("/home/user/test")
        windows_path = path.as_windows()
        assert str(windows_path) == "\\home\\user\\test"
