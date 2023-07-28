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

import importlib
import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path

from lyndows.util import (
    FilePath,
    is_flagexec,
    is_win32exec,
    is_windows_path,
)

logger = logging.getLogger(__name__)


class Distribution:
    _known_places = OrderedDict()
    commands = [
        "winecfg",
        "uninstaller",
        "regedit",
        "winetricks",
        "wineconsole",
        "notepad",
        "winefile",
        "taskmgr",
        "control",
        "msiexec",
    ]
    __slots__ = ("_root", "_is_proton", "_version", "_winedist", "_proton_module")

    def __init__(self, root: FilePath) -> None:
        self._root = Path(root).expanduser().resolve()
        if not self._root.is_dir():
            raise NotADirectoryError("root is not a valid directory.")

        self._is_proton = False
        self._proton_module = None

        if self._check_proton():
            if Distribution.validate(self._root / "dist"):
                # old proton version
                self._winedist = self._root / "dist"
            elif Distribution.validate(self._root / "files"):
                self._winedist = self._root / "files"
            else:
                raise AttributeError(f"Invalid Wine Distribution for {self._root}")
            self._is_proton = True
            self._proton_module = None
        elif Distribution.validate(self._root):
            self._winedist = self._root
        else:
            raise AttributeError(f"Invalid Wine Distribution for {self._root}")

    @classmethod
    def validate(cls, path: FilePath) -> bool:
        path = Path(path).absolute()

        required_dirs = ("bin", "lib", "lib64", "share")
        for _dir in required_dirs:
            if not (path / _dir).is_dir():
                return False
        required_bins = (
            "wine",
            "wine64",
            "wineserver",
            "wine-preloader",
            "wine64-preloader",
        )
        return all((is_flagexec(path / "bin" / _bin) for _bin in required_bins))

    def _check_proton(self) -> bool:
        return is_flagexec(self._root / "proton")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def winedist(self) -> Path:
        return self._winedist

    @property
    def is_proton(self) -> bool:
        return self._is_proton

    @property
    def proton(self) -> Path | None:
        return self._root / "proton" if self._is_proton else None

    @property
    def server(self) -> Path:
        return self._winedist / "bin" / "wineserver"

    @property
    def loader(self) -> Path:
        return self._winedist / "bin" / "wine64"

    def import_proton(self):
        if self._is_proton and not self._proton_module:
            sys.path.append(str(self.proton))
            importlib.machinery.SOURCE_SUFFIXES.append("")  # type: ignore
            self._proton_module = importlib.import_module("proton")
        return self._proton_module

    @staticmethod
    def check_executable(path: FilePath) -> FilePath | None:
        path = Path(path)
        if is_windows_path(path):
            raise ValueError("path should be a native posix path")
        if path.name in Distribution.commands:
            return path.name
        path = Path(path).resolve()
        return path if is_win32exec(path) else None

    @staticmethod
    def _look_for() -> None:
        home = str(Path.home())
        paths = {"/usr/bin", "/usr/local/bin", "/opt/bin", f"{home}/.local/bin"}
        envp = os.environ.get("PATH", "").split(":")

        # look for wine in usual paths
        for p in envp:
            paths.add(p)
        for p in paths:
            w = Path(p) / "wine"
            if is_flagexec(w):
                Distribution._known_places[str(w.resolve().parent.parent)] = None

        # NOTE: should we add those?
        # look for proton usual depots
        for depot in (
            f"{home}/.steam/steam/compatibilitytools.d",
            f"{home}/.steam/steam/steamapps/common/Proton",
        ):
            depot = Path(depot)
            print(depot)
            if depot.is_dir():
                for d in depot.iterdir():
                    d.resolve()
                    Distribution._known_places[str(d)] = None

    @staticmethod
    def default() -> Distribution | None:
        if len(Distribution._known_places) == 0:
            Distribution._look_for()
        for place, state in Distribution._known_places.items():
            if state is False:
                continue
            elif isinstance(state, Distribution):
                return state
            else:
                try:
                    Distribution._known_places[place] = Distribution(place)
                except (NotADirectoryError, AttributeError):
                    Distribution._known_places[place] = False
                    continue
                else:
                    return Distribution._known_places[place]
        return None


# def start_server(self):
#     #FIXME: dont work at all!!
#     env = {"WINEPREFIX": self.WINEPREFIX}
#     logger.debug(f"start wineserver {self.get_server()} in {self.WINEPREFIX}")
#     args = [self.get_server(), "--persistent=10"]
#     args = shlex.join(args)
#     subprocess.run(args, env=env, shell=True)
#     time.sleep(2)


# def killall(self, context=None):
#     """Kill all processes running inside the wineprefix.
#     """
#     if context is None:
#         context = WineContext.context()
#     if not isinstance(context, WineContext):
#         raise ValueError()
#     subprocess.check_output(
#         ["wineboot", "0"],
#         encoding="UTF-8",
#         shell=False,
#         env=dict(WINEPREFIX=context.WINEPREFIX)
#     )
