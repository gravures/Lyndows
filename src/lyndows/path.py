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
import re
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
from typing import Any, Mapping, Union

import psutil

from lyndows.util import FilePath, is_flagexec, is_win32exec, on_windows
from lyndows.wine.context import WineContext
from lyndows.wine.prefix import Prefix

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def split_drive(path: FilePath) -> tuple[str, str]:
    path = str(path)
    if match := re.search(r"^\w:[/\\]", path):
        return path[: match.end() - 1], path[match.end() - 1 :]
    else:
        return "", path


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
        if name == "UPosixPath":
            bases = (UPath, Path, PurePosixPath)
        elif name == "UWindowsPath":
            bases = (UPath, Path, PureWindowsPath)
        elif name == "UWinePath":
            bases = (UPath, Path, PureWindowsPath)
            namespace = cls.__prepare_api__((PurePath, UPath), namespace)
        return type.__new__(cls, name, bases, namespace, **kwargs)

    def __init__(
        self,
        name: str,
        bases: tuple[type, ...],
        namespace: Mapping[str, object],
        **kwargs: Any,
    ) -> None:
        self.callby = name

    @classmethod
    def __prepare_api__(
        cls, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> dict[str, Any]:
        _bases = [b.__dict__ for b in bases]
        _bases.append(namespace)  # type: ignore
        for base in _bases:
            for name in base:
                if type(base[name]) in (
                    FunctionType,
                    staticmethod,
                    classmethod,
                    property,
                ):
                    namespace["__upath_api__"][name] = base[name]  # type: ignore
        return namespace

    @classmethod
    def __prepare__(
        cls, name: str, bases: tuple[type, ...], /, **kwargs: Any
    ) -> Mapping[str, object]:
        return super().__prepare__(name, bases, **kwargs)

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        if self.callby == "UPath":
            if on_windows():
                return UWindowsPath(*args, **kwds)
            elif args and is_windows_path(args[0]):
                return UWinePath(*args, **kwds)
            else:
                return UPosixPath(*args, **kwds)
        return super().__call__(*args, **kwds)


class UPath(Path, metaclass=UMeta):
    """PurePath offering support for Wine filesystem.

    Extends PurePath standard library and represents a filesystem
    path which don't imply any actual filesystem I/O. On Posix systems,
    from the parts given to the constructor, try to guess the underlying
    filesystem type returning either a UPurePosixPath or a UPureWindowsPath
    object. On Windows always returns a PurePath object.
    You can also instantiate either of these classes directly, regardless
    of the nature of the path or the os system.
    """

    __slots__ = ("_winepfx", "_drive_mapping", "_mount_points")
    _sys_mount_points = {
        part.mountpoint: part.device for part in psutil.disk_partitions()
    }

    @classmethod
    def _from_parts(cls, args):
        self = super()._from_parts(args)  # type: ignore
        if not self._flavour.is_supported:
            raise NotImplementedError(
                "cannot instantiate %r on your system" % (cls.__name__,)
            )
        return self

    def _new_winepfx(self) -> None:
        self._winepfx: Prefix | None = None
        if on_windows():
            return
        if context := WineContext.context():
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

    def mount_point(self) -> UPath:
        path = self.expanduser().absolute()
        while not path.is_mount():
            path = path.parent
        return path

    def as_native(self) -> UPath:
        return self

    def as_windows(self) -> UPath:
        return self


UFilePath = Union[str, UPath]


class UPosixPath(UPath):
    __slots__ = ()
    _flavour = _posix_flavour

    def __new__(cls, *args: FilePath, **kwargs: Any) -> UPosixPath:
        self: UPosixPath = UPosixPath._from_parts(args)
        self._new_winepfx()
        return self

    def _map_parts(self) -> tuple[str, UPosixPath]:
        mnt = self.mount_point()
        drive = self._mount_points.get(str(mnt), "")
        path = self.expanduser().absolute()
        path = path.relative_to(mnt) if drive else path
        drive = drive or self._mount_points.get("/", "")
        return drive, path  # type: ignore

    def as_windows(self) -> UWinePath:
        drive, path = self._map_parts()  # type: ignore
        return UWinePath(f"{drive}/{path}")


class UWindowsPath(UPath):
    __slots__ = ()
    _flavour = _windows_flavour

    def __new__(cls, *args: FilePath, **kwargs: Any) -> UWindowsPath:
        self: UWindowsPath = UWindowsPath._from_parts(args)
        return self


class UWinePath(UPath):
    __slots__ = ("_uwdrive", "_posix_path", "__dict__")
    __upath_api__: dict[str, Any] = {}
    _flavour = _wine_flavour

    def __new__(cls, *args: FilePath, **kwargs: Any) -> UWinePath:
        self: UWinePath = UWinePath._from_parts(args)
        self._new_winepfx()
        self.__dict__["_flavour"] = _wine_flavour
        self._uwdrive, path = split_drive(self) if args else ("", args[0])
        self._posix_path = self.as_native()
        return self

    def __getattr__(self, attr: str) -> Any:
        if attr in self.__slots__:
            return None
        raise AttributeError(attr)

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
        return UPosixPath(Path.home()).as_windows()

    def absolute(self) -> UWinePath:
        return (
            self
            if self.is_absolute()
            else self.__class__.__new__(
                self.__class__, self._mount_points.get("/", ""), Path.cwd(), self
            )
        )

    def as_native(self) -> UPosixPath:
        path = self.absolute()
        return UPosixPath(
            self._drive_mapping.get(path.drive, "/"),
            path.relative_to(PureWindowsPath(path.anchor)),
        )
