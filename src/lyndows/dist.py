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
# pylint: disable='no-member'
from __future__ import annotations

import importlib
import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path, PosixPath, PureWindowsPath

import psutil

from lyndows.fileutil import (
    FilePath,
    is_flagexec,
    is_win32exec,
    is_windows_path,
    mount_point,
)

logger = logging.getLogger(__name__)


class Dist():
    _known_places = OrderedDict()
    commands = [
        "winecfg", "uninstaller", "regedit", "winetricks",
        "wineconsole", "notepad", "winefile",
        "taskmgr", "control", "msiexec"
    ]
    __slots__ = (
        "_root", "_is_proton", "_version", "_winedist", "_proton_module"
    )

    def __init__(self, root: FilePath) -> None:
        self._root = Path(root).expanduser().resolve()
        if not self._root.is_dir():
            raise NotADirectoryError("root is not a valid directory.")
        
        self._is_proton = False
        self._proton_module = None
                
        if self._check_proton():
            if Dist.validate(self._root / 'dist'):  
                # old proton version
                self._winedist = self._root / 'dist'
            elif Dist.validate(self._root / 'files'):
                self._winedist = self._root / 'files'
            else:
                raise AttributeError(f"Invalid Wine Distribution for {self._root}")
            self._is_proton = True
            self._proton_module = None
        elif Dist.validate(self._root): 
            self._winedist = self._root
        else:
            raise AttributeError(f"Invalid Wine Distribution for {self._root}")

    @classmethod
    def validate(cls, path: FilePath) -> bool:
        path = Path(path).absolute()
        if not path.is_dir():
            return False
        for _dir in ('bin', 'lib', 'lib64', 'share'):
            if not (path / _dir).is_dir():
                return False
        for _bin in (
            'wine', 'wine64', 'wineserver', 
            'wine-preloader', 'wine64-preloader'
        ):
            if not is_flagexec(path / 'bin' / _bin):
                return False            
        return True

    def _check_proton(self) -> bool:
        return is_flagexec(self._root / 'proton') 
    
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
    def proton(self) -> Path:
        return self._root / 'proton' if self._is_proton else None
    
    @property
    def server(self) -> Path:
        return self._winedist / 'bin' / 'wineserver'
    
    @property
    def loader(self) -> Path:               
        return self._winedist / 'bin' / 'wine64'
    
    def import_proton(self):
        if self._is_proton:
            if not self._proton_module:
                sys.path.append(str(self.get_proton()))
                importlib.machinery.SOURCE_SUFFIXES.append("")
                self._proton_module = importlib.import_module("proton")
        return self._proton_module
    
    @staticmethod
    def check_executable(path: FilePath) -> Path | None:
        if is_windows_path(path):
            raise ValueError("path should be a native posix path")
        if path.name in Dist.commands:
            return path.name
        path = Path(path).resolve()
        if is_win32exec(path):
            return path
        return None
    
    @staticmethod
    def _look_for() -> None:
        home = str(Path.home())
        paths = {
            '/usr/bin', 
            '/usr/local/bin', 
            '/opt/bin',
            f"{home}/.local/bin"
        }        
        envp = os.environ.get('PATH', '').split(':')

        # look for wine in usual paths
        for p in envp:
            paths.add(p)
        for p in paths:
            w = Path(p) / 'wine'
            if is_flagexec(w):
                Dist._known_places[str(w.resolve().parent.parent)] = None

        #NOTE: should we add those? 
        # look for proton usual depots
        for depot in (
            f"{home}/.steam/steam/compatibilitytools.d",
            f"{home}/.steam/steam/steamapps/common/Proton"
        ):
            depot = Path(depot)
            print(depot)
            if depot.is_dir():
                for d in depot.iterdir():
                    d.resolve()
                    Dist._known_places[str(d)] = None

    @staticmethod
    def default() -> Dist | None:
        if len(Dist._known_places) == 0:
            Dist._look_for()
        for place, state in Dist._known_places.items():
            if state is False:
                continue
            elif isinstance(state, Dist):
                return state
            else:
                try:
                    Dist._known_places[place] = Dist(place)
                except (NotADirectoryError, AttributeError):
                    Dist._known_places[place] = False
                    continue
                else:
                    return Dist._known_places[place]
        return None
                
    
# def start_server(self):
#     #FIXME: dont work at all!!
#     env = {"WINEPREFIX": self.WINEPREFIX}
#     logger.debug(f"start wineserver {self.get_server()} in {self.WINEPREFIX}")
#     args = [self.get_server(), "--persistent=10"]
#     args = shlex.join(args)
#     subprocess.run(args, env=env, shell=True)
#     time.sleep(2)
    

class Prefix():
    _known_places = OrderedDict()
    __slots__ = (
        "_root", "_pfx", "_win_version", "_dll_overrides", 
        "_arch", "_drive_mapping", "_sys_mount_points"
    )

    def __init__(self, root: FilePath) -> None:
        self._root = Path(root).expanduser().resolve()
        if not self._root.is_dir():
            raise NotADirectoryError("root is not a valid directory.")
        
        if not Prefix.validate(self._root):
            if Prefix.validate(self._root / 'pfx'):
                self._pfx = self._root / 'pfx'
            else:
                raise AttributeError(
                    f"Invalid Wine Prefix for {self._root}"
                )
        else:
            self._pfx = self._root
        self._drive_mapping = dict()
        self._update_drive_mapping()

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
        for _dir in ('dosdevices', 'drive_c'):
            if not (path / _dir).is_dir():
                return False
        for file in (
            'system.reg', 'user.reg', 'userdef.reg', '.update-timestamp'
        ):
            if not (path / file).is_file():
                return False            
        return True
    
    #FIXME:resolve ../drive_c
    def _update_drive_mapping(self):
        devices = self._pfx / 'dosdevices'
        for dev in devices.iterdir():
            if len(dev.name)==2 and dev.name.endswith(':') and dev.is_symlink:
                self._drive_mapping[str(dev.readlink())] = dev.name

        self._sys_mount_points = {
            part.mountpoint: part.device for part in psutil.disk_partitions()
        }
        for mnt, dev in self._sys_mount_points.items():
            self._sys_mount_points[mnt] = self._drive_mapping.get(mnt)


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
            drive = self._sys_mount_points.get('/')
        return PureWindowsPath(f"{drive}/{path}")
    
    def get_native_path(self, path: FilePath) -> PosixPath:
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
        anchor = '/'
        for mnt, drv in self._drive_mapping.items():
            if drv == path.drive:
                anchor = mnt 
                break
        #FIXME: drive letter not found case
        return Path(anchor) / path.relative_to(Path(path.anchor))
    
    @staticmethod
    def _look_for() -> None:
        home = str(Path.home())
        envp = os.environ.get('WINEPREFIX', '')
        paths = {envp} if envp else {}
        paths.add(f"{home}/.wine")
        paths.add(f"{home}/.wine64")
        for p in paths:
            if Path(p).is_dir():
                Prefix._known_places[p] = None

    #TODO: Prefixes are kinda linked to a Dist,
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
        