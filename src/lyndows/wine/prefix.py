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

import os
from collections import OrderedDict
from pathlib import Path, PosixPath, PureWindowsPath

import psutil

from lyndows.util import FilePath, is_windows_path, mount_point


class Prefix:
    _known_places = OrderedDict()
    __slots__ = (
        "_root",
        "_pfx",
        "_win_version",
        "_dll_overrides",
        "_arch",
        "_drive_mapping",
        "_sys_mount_points",
    )

    def __init__(self, root: FilePath) -> None:
        self._root = Path(root).expanduser().resolve()
        if not self._root.is_dir():
            raise NotADirectoryError("root is not a valid directory.")

        if Prefix.validate(self._root):
            self._pfx = self._root
        elif Prefix.validate(self._root / "pfx"):
            self._pfx = self._root / "pfx"
        else:
            raise AttributeError(f"Invalid Wine Prefix for {self._root}")
        self._drive_mapping = {}
        self._update_drive_mapping()
        self._sys_mount_points = {}

    @property
    def root(self):
        return self._root

    @property
    def pfx(self):
        return self._pfx

    @property
    def arch(self):
        return self._arch

    @property
    def win_version(self):
        return self._win_version

    @property
    def dll_overrides(self):
        return self._dll_overrides

    @classmethod
    def validate(cls, path: FilePath) -> bool:
        path = Path(path).absolute()
        if not path.is_dir():
            return False
        for _dir in ("dosdevices", "drive_c"):
            if not (path / _dir).is_dir():
                return False
        return all(
            (path / file).is_file()
            for file in (
                "system.reg",
                "user.reg",
                "userdef.reg",
                ".update-timestamp",
            )
        )

    # FIXME:resolve ../drive_c
    def _update_drive_mapping(self):
        devices = self._pfx / "dosdevices"
        for dev in devices.iterdir():
            if len(dev.name) == 2 and dev.name.endswith(":") and dev.is_symlink:
                self._drive_mapping[str(dev.readlink())] = dev.name

        self._sys_mount_points = {
            part.mountpoint: part.device for part in psutil.disk_partitions()
        }
        for mnt in self._sys_mount_points:
            self._sys_mount_points[mnt] = self._drive_mapping.get(mnt)  # type: ignore

    def get_windows_path(self, path: FilePath) -> PureWindowsPath:
        """Convert a Windows path to a native path format.

        Takes a native path and converts it to the Windows
        path format for later use in the Windows environnement.

        Args:
            path (FilePath): The native path to be converted.

        Returns:
            pathlib.PureWindowsPath: The Windows path equivalent
            of the given native path.
        """
        if is_windows_path(path):
            return PureWindowsPath(path)
        mnt = mount_point(path)
        drive = self._sys_mount_points.get(str(mnt))
        path = Path(path).expanduser().absolute()
        if drive:
            path = path.relative_to(mnt)
        else:
            drive = self._sys_mount_points.get("/")
        return PureWindowsPath(f"{drive}/{path}")

    def get_native_path(self, path: FilePath) -> Path:
        """Convert a Windows path to a native path format.

        Takes a Windows path and converts it to native path format.

        Args:
            path (FilePath): The Windows path to be converted.

        Returns:
            pathlib.PosixPath: The native path equivalent
            of the given Windows path.
        """
        if not is_windows_path(path):
            return PosixPath(path)
        path = Path(path).absolute()
        anchor = next(
            (mnt for mnt, drv in self._drive_mapping.items() if drv == path.drive),
            "/",
        )
        # FIXME: drive letter not found case
        return Path(anchor) / path.relative_to(Path(path.anchor))

    @staticmethod
    def _look_for() -> None:
        home = str(Path.home())
        envp = os.environ.get("WINEPREFIX", "")
        paths = {envp} if envp else set()
        paths.add(f"{home}/.wine")
        paths.add(f"{home}/.wine64")
        for p in paths:
            if Path(p).is_dir():
                Prefix._known_places[p] = None

    # TODO: Prefixes are kinda linked to a Dist,
    #      we should have a way to figured this out.
    #      and proton Dist hae a default prefix
    #      in their directory...
    @staticmethod
    def default() -> Prefix | None:
        if len(Prefix._known_places) == 0:
            Prefix._look_for()
        for place, state in Prefix._known_places.items():
            if state is False:
                continue
            elif isinstance(state, Prefix):
                return state
            else:
                try:
                    Prefix._known_places[place] = Prefix(place)
                except (NotADirectoryError, AttributeError):
                    Prefix._known_places[place] = False
                    continue
                else:
                    return Prefix._known_places[place]
        return None
