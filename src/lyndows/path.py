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
    PureWindowsPath,
    WindowsPath,
    _posix_flavour,  # type: ignore
    _windows_flavour,  # type: ignore
    _WindowsFlavour,  # type: ignore
)
from types import FunctionType
from typing import Any, Mapping, Union, no_type_check

import psutil

from lyndows.util import is_flagexec, is_win32exec, on_windows
from lyndows.wine.context import WineContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FilePath = Union[str, PurePath]


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


class UMeta(type):
    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any
    ) -> UMeta:
        if name == "UPosixPath":
            bases = (UPath, Path, UPurePosixPath)
        elif name == "UWindowsPath":
            bases = (UPath, Path, UPureWindowsPath)
            namespace = cls.__prepare_api__(
                (PurePath, UPurePath, UPureWindowsPath, UPath), namespace
            )
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
        if self.callby == "UPurePath":
            if on_windows():
                return PurePath(*args, **kwds)
            elif args and is_windows_path(args[0]):
                return UPureWindowsPath(*args, **kwds)
            else:
                return UPurePosixPath(*args, **kwds)
        elif self.callby == "UPath":
            if on_windows():
                return Path(*args, **kwds)
            elif args and is_windows_path(args[0]):
                return UWindowsPath(*args, **kwds)
            else:
                return UPosixPath(*args, **kwds)
        return super().__call__(*args, **kwds)


class _WineFlavour(_WindowsFlavour):
    is_supported = not on_windows()


_wine_flavour = _WineFlavour()


class UPurePath(PurePath, metaclass=UMeta):
    """PurePath offering support for Wine filesystem.

    Extends PurePath standard library and represents a filesystem
    path which don't imply any actual filesystem I/O. On Posix systems,
    from the parts given to the constructor, try to guess the underlying
    filesystem type returning either a UPurePosixPath or a UPureWindowsPath
    object. On Windows always returns a PurePath object.
    You can also instantiate either of these classes directly, regardless
    of the nature of the path or the os system.
    """

    __slots__ = ("_context", "_drive_mapping", "_mount_points")
    _sys_mount_points = {
        part.mountpoint: part.device for part in psutil.disk_partitions()
    }

    def _new_context(self) -> None:
        if on_windows():
            self._context = None
            return
        self._context = WineContext.context()
        if self._context is None:
            raise EnvironmentError("Wine context not found")
        self._drive_mapping: dict[str, str] = {}
        self._mount_points: dict[str, str] = {}
        self._update_drive_mapping()

    def _update_drive_mapping(self) -> None:
        if not self._context:
            return
        # FIXME:resolve ../drive_c
        self._drive_mapping.clear()
        self._mount_points.clear()
        devices = self._context.prefix.pfx / "dosdevices"
        for mnt in self._sys_mount_points:
            self._mount_points[mnt] = ""
        for dev in devices.iterdir():
            if len(dev.name) == 2 and dev.name.endswith(":") and dev.is_symlink:
                mnt = str(dev.readlink())
                self._drive_mapping[dev.name] = mnt
                if mnt in self._sys_mount_points:
                    self._mount_points[mnt] = dev.name

    def as_native(self) -> UPurePath | PurePath:
        return self

    def as_windows(self) -> UPurePath | PurePath:
        return self


UFilePath = Union[str, UPurePath]


class UPurePosixPath(UPurePath):
    __slots__ = ()
    _flavour = _posix_flavour

    def __new__(cls, *args: FilePath) -> UPurePosixPath:
        self: UPurePosixPath = UPurePosixPath._from_parts(args)  # type: ignore
        self._new_context()
        return self

    def expanduser(self) -> UPurePosixPath:
        # TODO: './~/case'
        if self.parts and self.parts[0] == "~":
            return self.__class__.__new__(self.__class__, Path.home(), *self.parts[1:])
        return self

    def absolute(self) -> UPurePosixPath:
        return (
            self
            if self.is_absolute()
            else self.__class__.__new__(self.__class__, Path.cwd(), self)
        )

    def is_mount(self) -> bool:
        return str(self.expanduser()) in self._sys_mount_points

    def mount_point(self) -> UPurePosixPath:
        path = self.expanduser().absolute()
        while not path.is_mount():
            path = path.parent
        return path

    def _map_parts(self) -> tuple[str, UPurePosixPath]:
        mnt = self.mount_point()
        drive = self._mount_points.get(str(mnt), "")
        path = self.expanduser().absolute()
        path = path.relative_to(mnt) if drive else path
        drive = drive or self._mount_points.get("/", "")
        return drive, path

    def as_windows(self) -> UPurePath | PurePath:
        if on_windows():
            return PureWindowsPath(self)
        drive, path = self._map_parts()
        return UPureWindowsPath(f"{drive}/{path}")


class UPureWindowsPath(UPurePath):
    __slots__ = ()
    _flavour = _windows_flavour

    def __new__(cls, *args: FilePath) -> UPureWindowsPath:
        self: UPureWindowsPath = UPureWindowsPath._from_parts(args)  # type: ignore
        self._new_context()
        return self

    def __getattribute__(self, attr: str) -> Any:
        # for UWindowsPath
        return object.__getattribute__(self, attr)

    def absolute(self) -> UPureWindowsPath:
        return (
            self
            if self.is_absolute()
            else self.__class__.__new__(
                self.__class__, self._mount_points.get("/", ""), Path.cwd(), self
            )
        )

    def as_native(self) -> UPurePath:
        if on_windows():
            return self
        path = self.absolute()
        return UPurePath(
            self._drive_mapping.get(path.drive, "/"),
            path.relative_to(PureWindowsPath(path.anchor)),
        )


class UPath(UPurePath):
    __slots__ = ()


class UPosixPath(UPath):
    __slots__ = ()
    _flavour = _posix_flavour

    def __new__(cls, *args: FilePath, **kwargs: Any) -> UPosixPath:
        self: UPosixPath = UPosixPath._from_parts(args)  # type: ignore
        self._new_context()
        return self

    def as_windows(self) -> UWindowsPath:
        drive, path = self._map_parts()  # type: ignore
        return UWindowsPath(f"{drive}/{path}")


class UWindowsPath(UPath):
    __slots__ = ("_uwdrive", "_posix_path", "__dict__")
    __upath_api__: dict[str, Any] = {}
    _flavour = _wine_flavour

    @no_type_check
    def __new__(cls, *args: FilePath, **kwargs: Any) -> UWindowsPath:
        self: UWindowsPath = UWindowsPath._from_parts(args)  # type: ignore
        self._new_context()
        self.__dict__["_flavour"] = _wine_flavour
        self._uwdrive, path = split_drive(self) if args else ("", args[0])
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
    def home(cls) -> UWindowsPath:
        return UPosixPath(Path.home()).as_windows()

    def as_native(self) -> UPosixPath:
        path = self.absolute()
        return UPosixPath(
            self._drive_mapping.get(path.drive, "/"),
            path.relative_to(PureWindowsPath(path.anchor)),
        )
