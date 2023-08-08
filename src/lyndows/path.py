# -*- coding: utf-8 -*-
#
#       Copyright (c) Gilles Coissac 2020 <info@gillescoissac.fr>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#
from __future__ import annotations

import logging
import os
import re
import shlex
from functools import wraps
from pathlib import (
    Path,
    PurePath,
    PurePosixPath,
    PureWindowsPath,
    WindowsPath,
    _posix_flavour,  # type: ignore
    _windows_flavour,  # type: ignore
    _WindowsFlavour,  # type: ignore
)
from types import FunctionType
from typing import Any, Mapping, Sequence, Type, Union

import psutil

from lyndows.util import FilePath, is_flagexec, is_win32exec, on_windows
from lyndows.wine.context import WineContext
from lyndows.wine.prefix import Prefix

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def split_drive(path: FilePath) -> tuple[str, str]:
    path = str(path)
    if match := re.search(r"^\w:[/\\]", path):
        return (path[: match.end() - 1], path[match.end() - 1 :])
    else:
        return ("", path)


def is_windows_path(path: FilePath) -> bool:
    # NOTE: * 'file:///home/user/etc' will not match
    #       * relative paths never match
    return isinstance(path, (PureWindowsPath, WindowsPath)) or split_drive(path)[0] != ""


class _WineFlavour(_WindowsFlavour):
    is_supported = not on_windows()


_wine_flavour = _WineFlavour()


class UMeta(type):
    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any
    ) -> UMeta:
        return type.__new__(cls, name, bases, namespace)

    def __init__(
        self,
        name: str,
        bases: tuple[type, ...],
        namespace: Mapping[str, object],
        **kwargs: Any,
    ) -> None:
        self.callby = name

    @classmethod
    def __prepare__(
        cls, name: str, bases: tuple[type, ...], /, **kwargs: Any
    ) -> Mapping[str, object]:
        api = kwargs.pop("api", None)
        namespace = super().__prepare__(name, bases, **kwargs)
        if api is None:
            return namespace

        _bases = [b.__dict__ for b in api]
        namespace["__upath_api__"] = {}  # type: ignore
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

    Extends pathlib.Path standard library class and represents a filesystem
    path whith actual I/O methods. On Posix systems,
    from the parts given to the constructor, try to guess the underlying
    filesystem type returning either a UPosixPath or a UWinePath
    object. On Windows always returns a UWindowsPath object.
    You can also instantiate either of these classes directly if supported
    by your system.
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
        # FIXME:resolve ../drive_c
        self._drive_mapping.clear()
        self._mount_points.clear()
        devices = self._winepfx.pfx / "dosdevices"
        for mnt in self._sys_mount_points:
            self._mount_points[mnt] = ""
        for dev in devices.iterdir():
            if len(dev.name) == 2 and dev.name.endswith(":") and dev.is_symlink:
                mnt = str(dev.readlink())
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
           UPath: The mount point of the current path.
        """

        path = self.expanduser().absolute()
        while not path.is_mount():
            path = path.parent
        return path

    def as_native(self) -> UPath:
        """Convert the current path to a native UPath object.

        Returns:
            UPath: Returns either a UPosixPath or a UWindowsPath.
        """

        return self

    def as_windows(self) -> UPath:
        """Convert the current path to a windows UPath object.

        Returns:
            UPath: Returns either a UWinePath or a UWindowsPath.
        """
        return self


UFilePath = Union[str, UPath]


class UPosixPath(UPath, Path, PurePosixPath):
    __slots__ = ()
    _flavour = _posix_flavour

    def as_windows(self) -> UWinePath:
        """Convert the current path as a UWinePath object.

        Returns:
            UWinePath: Returns a UWinePath representing the current path.
        """
        drive, path = self._map_parts()
        return UWinePath(f"{drive}/{path}")


class UWindowsPath(UPath, Path, PureWindowsPath):
    __slots__ = ()
    _flavour = _windows_flavour


class UWinePath(UPath, Path, PureWindowsPath, api=(PurePath, UPath)):
    """An UPath class offering support for Wine filesystem.

    Represent a windows filesystem path on Posix platforms with
    Wine support. This class internally delegates I/O operations
    to an UPosixPath equivalent of this path
    """

    __slots__ = ()
    _flavour = _wine_flavour

    def __new__(cls, *args: FilePath, **kwargs: Any):
        self = super().__new__(cls, *args, **kwargs)
        self._posix_path = self.as_native()
        return self

    def __getattribute__(self, attr: str) -> Any:
        cls = object.__getattribute__(self, "__class__")
        _attr = Path.__dict__.get(attr, None)

        if attr in cls.__upath_api__:
            return cls.__upath_api__[attr].__get__(self, cls)
        elif _attr is None or not isinstance(_attr, FunctionType):
            return object.__getattribute__(self, attr)

        @wraps(_attr)
        def _wrapped(*args, **kwargs):  # type: ignore
            return _attr(self._posix_path, *args, **kwargs)

        return _wrapped

    @classmethod
    def home(cls) -> UWinePath:
        """Return a new path pointing to the user's home directory
        as a WinePath.

        Returns:
            UWinePath: A new UWinePath object pointing to the home directory.
        """
        return UPosixPath(Path.home()).as_windows()

    def absolute(self) -> UWinePath:
        """Returns a new UWinePath object that represents the absolute
        path of the current UWinePath object.

        Returns:
            UWinePath: A new UWinePath object that represents the absolute path.
        """
        return (
            self
            if self.is_absolute()
            else self.__class__.__new__(
                self.__class__, self._mount_points.get("/", ""), Path.cwd(), self
            )
        )

    def as_native(self) -> UPosixPath:
        """Converts the current path object as a UPosixPath.

        Returns:
            UPosixPath: A UPosixPath object representing the converted path.
        """

        path = self.absolute()
        return UPosixPath(
            self._drive_mapping.get(path.drive, "/"),
            path.relative_to(PureWindowsPath(path.anchor)),
        )
