# Copyright (c) 2023 - Gilles Coissac
# See end of file for extended copyright information
"""|
==================================
Pathlib standard library extension
==================================

This module provides an extension to the standard pathlib library, offering support
for working with Windows filesystem paths on both Windows and POSIX systems with Wine.
This module extends and enhances the functionality of the standard pathlib library
to provide better support for working with Windows paths on different platforms.
The :class:`UPath` class dynamically determines whether to create a :class:`UPosixPath`,
:class:`UWindowsPath`, or :class:`UWinePath` object based on the platform and input.
:class:`UPosixPath` and :class:`UWindowsPath` are designed for use on POSIX and Windows
systems respectively. :class:`UWinePath` is designed for use on POSIX systems with Wine
support for handling Windows paths.

|

.. inheritance-diagram:: lyndows.path.UPosixPath lyndows.path.UWindowsPath lyndows.path.UWinePath
   :parts: -1
.. centered:: The lyndows.path class hierarchy
|

.. seealso::
    For more information, refer to the official Python documentation for `pathlib
    <https://docs.python.org/3/library/pathlib.html>`_ and related modules.
"""

from __future__ import annotations

import logging
import re
from pathlib import (
    Path,
    PurePath,
    PurePosixPath,
    PureWindowsPath,
    _posix_flavour,  # type: ignore
    _windows_flavour,  # type: ignore
    _WindowsFlavour,  # type: ignore
)
from types import FunctionType, GeneratorType
from typing import Any, Union

import psutil

from lyndows.util import FilePath, is_flagexec, is_win32exec, on_windows
from lyndows.wine.context import WineContext
from lyndows.wine.prefix import Prefix

logger = logging.getLogger(__name__)

__all__ = [
    "UPath",
    "UPosixPath",
    "UWindowsPath",
    "UWinePath",
    "split_drive",
    "is_windows_path",
]


def split_drive(path: FilePath) -> tuple[str, str]:
    """Split a file path into its drive part and the rest of the path.

    Args:
        path (str|Path): The file path to split.

    Returns:
        tuple[str, str]: A tuple containing the drive and the rest of the path.
    """
    path = str(path)
    if match := re.search(r"^\w:[/\\]", path):
        return (path[: match.end() - 1], path[match.end() - 1 :])
    else:
        return ("", path)


def is_windows_path(path: FilePath) -> bool:
    """Check if the given path is a Windows path.

    Args:
        path (FilePath): The path to check.

    Returns:
        bool: True if the path is an instance of PureWindowsPath or if
        the path starts with a drive letter. Otherwise, on windows if
        the path is not a PurePosixPath always return True.

    Note:
        As a consequence, on Posix system, paasing relative paths will always
        return False, except if the path is an instance of a PureWindowsPath or one
        of its subclasses.
    """
    #  'file:///home/user/etc' will not match
    return (
        isinstance(path, (PureWindowsPath))
        or (split_drive(path)[0] != "")
        or (on_windows() and not isinstance(path, PurePath))
    )


class _WineFlavour(_WindowsFlavour):
    is_supported = not on_windows()


_wine_flavour = _WineFlavour()


class UMeta(type):
    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any
    ) -> UMeta:
        namespace = cls.__prepare_api__(bases, namespace, **kwargs)
        return type.__new__(cls, name, bases, namespace)

    @classmethod
    def __prepare_api__(
        cls, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        api = kwargs.pop("api", None)
        if api is None:
            return namespace

        namespace["__upath_api__"] = {}  # type: ignore
        _bases = [b.__dict__ for b in api]
        _bases.append(namespace)
        for base in _bases:
            for name in base:
                if type(base[name]) in (
                    FunctionType,
                    staticmethod,
                    classmethod,
                    property,
                ):
                    namespace["__upath_api__"][name] = base[name]
        return namespace


class UPath(Path, metaclass=UMeta):
    """Path class offering support for Wine filesystem.

    Extends :class:`Path` standard library class and represents a filesystem
    path whith actual I/O methods. On Posix systems,
    from the parts given to the constructor, try to guess the underlying
    filesystem type returning either a :class:`UPosixPath` or a :class:`UWinePath`
    object. On Windows always returns a :class:`UWindowsPath` object.
    You can also instantiate either one of these classes directly if it's
    supported by your system.
    """

    __slots__ = ("_winepfx", "_context", "_drive_mapping", "_mount_points", "_posix_path")
    __upath_api__: dict[str, Any] = {}
    _sys_mount_points = {
        part.mountpoint: part.device for part in psutil.disk_partitions()
    }

    def __new__(cls, *args: Any, **kwargs: Any):
        if cls is UPath:
            if on_windows():
                cls = UWindowsPath
            elif args and is_windows_path(args[0]):
                cls = UWinePath
            else:
                cls = UPosixPath

        self = cls._from_parts(args)  # type: ignore
        if not self._flavour.is_supported:
            raise NotImplementedError(
                "cannot instantiate %r on your system" % (cls.__name__,)
            )
        self._new_winepfx()
        self._posix_path = None
        return self

    def _new_winepfx(self, context: WineContext | None = None) -> None:
        self._winepfx: Prefix | None = None
        if on_windows():
            self._context = None
            return
        if context := WineContext.context():
            self._context = context
            self._winepfx = context.prefix
            self._drive_mapping: dict[str, str] = {}
            self._mount_points: dict[str, str] = {}
            self._update_drive_mapping()
        else:
            raise EnvironmentError("No WineContext was found")

    def _update_drive_mapping(self) -> None:
        if not self._winepfx:
            return
        self._drive_mapping.clear()
        self._mount_points.clear()
        devices = self._winepfx.pfx / "dosdevices"
        for mnt in self._sys_mount_points:
            self._mount_points[mnt] = ""
        for dev in devices.iterdir():
            if len(dev.name) == 2 and dev.name.endswith(":") and dev.is_symlink:
                mnt = dev.readlink()
                mnt = str(mnt) if mnt.is_absolute() else str((devices / mnt).resolve())
                self._drive_mapping[dev.name] = mnt
                if mnt in self._sys_mount_points:
                    self._mount_points[mnt] = dev.name

    def _map_parts(self) -> tuple[str, UPath]:
        mnt = self.mount_point()
        drive = self._mount_points.get(str(mnt), "")
        path = self.expanduser().absolute()
        path = path.relative_to(mnt) if drive else path
        drive = drive or self._mount_points.get("/", "")
        return drive, path

    def mount_point(self) -> UPath:
        """Returns the mount point of the current path.

        Returns:
           :class:`UPath`: The mount point of the current path.
        """

        path = self.expanduser().absolute()
        while not path.is_mount():
            path = path.parent
        return path

    def as_native(self) -> UPath:
        """Convert the current path to a native UPath object.

        Returns:
            :class:`UPath`: Returns either a :class:`UPosixPath` or a :class:`UWindowsPath`.
        """

        return self

    def as_windows(self) -> UPath:
        """Convert the current path to a windows UPath object.

        Returns:
            :class:`UPath`: Returns either a :class:`UWinePath` or a :class:`UWindowsPath`.
        """
        return self


UFilePath = Union[str, UPath]


class UPosixPath(UPath, Path, PurePosixPath):
    """:class:`UPath` subclass for non-Windows systems.

    On a POSIX system, instantiating an :class:`UPosixPath` should return this object.
    This class requires a valid Wine instalation on the system, otherwise
    an :class:`EnvironmentError` will be raised.
    The main purpose of this class is with the help of the :meth:`as_windows` method
    to provide an :class:`UWinePath` version of this path for further usage within the Wine
    runtime environment.
    :class:`UPosixPath` is a subclass of the :class:`Path` class and therfore inherits of all
    of its methods.
    """

    __slots__ = ()
    _flavour = _posix_flavour

    def as_windows(self) -> UWinePath:
        """Convert the current path as a :class:`UWinePath` object.

        Returns:
           :class:`UWinePath`: Returns a :class:`UWinePath` representing the current path.
        """
        drive, path = self._map_parts()
        return UWinePath(f"{drive}/{path}")


class UWindowsPath(UPath, Path, PureWindowsPath):
    __slots__ = ()
    _flavour = _windows_flavour


def _path_generator(generator):
    def wrapper():
        for x in generator:
            if isinstance(x, UPosixPath):
                yield UPath(x).as_windows()
            else:
                yield x

    return wrapper()


def _path_wrapper(func, instance):
    def wrapper(*args, **kwargs):
        res = func(instance._posix_path, *args, **kwargs)
        if isinstance(res, GeneratorType):
            return _path_generator(res)
        return UPath(res).as_windows() if type(res) is UPosixPath else res

    return wrapper


class UWinePath(UPath, Path, PureWindowsPath, api=(PurePath, UPath)):
    """An :class:`UPath` subclass offering support for Wine filesystem.

    Represent a windows filesystem path on Posix platforms with
    Wine support. This class internally delegates I/O operations
    to an :class:`UPosixPath` equivalent of this path.
    """

    __slots__ = ()
    _flavour = _wine_flavour

    def __init__(self, *args: FilePath, **kwargs: Any) -> None:
        super().__init__()
        self._posix_path = self.as_native()

    def __getattribute__(self, attr: str) -> Any:
        cls = object.__getattribute__(self, "__class__")
        _attr = Path.__dict__.get(attr, None)

        if attr in cls.__upath_api__:
            return cls.__upath_api__[attr].__get__(self, cls)
        elif _attr is None or not isinstance(_attr, FunctionType):
            return object.__getattribute__(self, attr)

        # @wraps(_attr)
        # def _wrapped(*args, **kwargs):  # type: ignore
        #     res = _attr(self._posix_path, *args, **kwargs)
        #     return UPath(res).as_windows() if type(res) is UPosixPath else res

        return _path_wrapper(_attr, self)

    @classmethod
    def home(cls) -> UWinePath:
        """Return a new path pointing to the user's home directory
        as an :class:`UWinePath` object.

        Returns:
            :class:`UWinePath`: A new :class:`UWinePath` object pointing to the home directory.
        """
        return UPosixPath(Path.home()).as_windows()

    def absolute(self) -> UWinePath:
        """Returns a new :class:`UWinePath` object that represents the absolute
        path of the current Path object.

        Returns:
            :class:`UWinePath`: A new :class:`UWinePath` object that is absolute.
        """
        return (
            self
            if self.is_absolute()
            else self.__class__.__new__(
                self.__class__, self._mount_points.get("/", ""), Path.cwd(), self
            )
        )

    def as_native(self) -> UPosixPath:
        """Converts the current path object as a :class:`UPosixPath` object.

        Returns:
            :class:`UPosixPath`: A :class:`UPosixPath` object representing the converted path.
        """
        path = self.absolute()
        return UPosixPath(
            self._drive_mapping.get(path.drive, "/"),
            path.relative_to(PureWindowsPath(path.anchor)),
        )


# Copyright (c) 2023 - Gilles Coissac
#
# This file is part of Lyndows library.
#
# Lyndows is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# Lyndows is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Lyndows. If not, see <https://www.gnu.org/licenses/>
