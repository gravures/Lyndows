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

import logging
from pathlib import Path

from lyndows.confighelper import BaseHelper
from lyndows.dist import Dist, Prefix
from lyndows.fileutil import FilePath, is_win32exec
from lyndows.system import on_windows

logger = logging.getLogger(__name__)


class WineContext(BaseHelper):
    __context = set()
    __default = None
    __slots__ = ("_prefix", "_dist")

    def __init__(self, dist: FilePath, prefix: FilePath, **kwargs) -> None:
        super().__init__(dist=dist, prefix=prefix)

        self._dist = Dist(dist)
        self._prefix = Prefix(prefix)

        self._protected = (
            'WINEDIST', 'WINELOADER', 'WINEPREFIX', 'WINESERVER', 'WINEARCH'
        )

        # base environement variables
        self._lock = False
        self.WINEDIST = self.dist.winedist
        self.WINELOADER = self.dist.loader
        self.WINEPREFIX = self.prefix.pfx
        self.WINESERVER = self.dist.server
        self.WINEARCH = ""
        self._lock = True

        # some default
        self.WINEPATH = ""
        self.WINEDLLPATH = [
            self.WINEDIST / "lib64" / "wine",
            self.WINEDIST / "lib" / "wine"
        ]
        self.WINEDLLOVERRIDES = []
        self.PATH = [self.WINEDIST / "bin", "/usr/bin", "/bin"]
        self.LD_LIBRARY_PATH = [self.WINEDIST / "lib64", self.WINEDIST / "lib"]
        self.TERM = "xterm"
        self.WINEDEBUG = "-all,-fixme,-server"

        # now merge dict
        self.update(kwargs)

    def env_hook(self, env: dict) -> dict:
        proxy = dict(env)
        for name, value in proxy.items():
            if name == 'ESYNC':
                env["WINEESYNC"] = int(value)
                if self.is_proton:
                    env["PROTON_NO_ESYNC"] = 1 - int(value)
                del env[name]
            elif name == 'FSYNC':
                env["WINEFSYNC"] = int(value)
                if self.is_proton:
                    env["PROTON_NO_FSYNC"] = 1 - int(value)
                del env[name]
            elif name == 'LARGE_ADDRESS_AWARE':
                env["WINE_LARGE_ADDRESS_AWARE"] = int(value)
                if self.is_proton:
                    env["PROTON_FORCE_LARGE_ADDRESS_AWARE"] = int(value)
                del env[name]
            elif name == "WINEDLLOVERRIDES":
                env["WINEDLLOVERRIDES"] = ";".join([str(p) for p in value])
        return env

    @property
    def dist(self) -> Dist:
        """Returns the wine dist associated with this context.""" 
        return self._dist
    
    @property
    def prefix(self) -> Prefix:   
        """Returns the prefix associated with this context."""     
        return self._prefix 
    
    @property
    def is_proton(self) -> bool:
        """Returns whether the wine dist associated
        with this context is a proton one.
        """
        return self.dist.is_proton
    
    @classmethod
    def register(cls, ctx):
        """Register a WineContext instance with the class.

        Parameters:
            - ctx (WineContext): The WineContext instance to be registered.

        Raises:
            TypeError: If the argument 'ctx' is not an instance 
            of lyndows.wine.WineContext.
        """
        if isinstance(ctx, WineContext):
            cls.__context.add(ctx)
            cls.__default = ctx
        else:
            raise TypeError(
                "Argument 'ctx' should be an instance of lyndows.wine.WineContext"
            )

    @classmethod
    def unregister(cls, ctx):
        """Unregisters a WineContext from the class.

        Parameters:
            ctx (WineContext): The WineContext instance to unregister.

        Raises:
            TypeError: If the 'ctx' argument is not an instance 
            of lyndows.wine.WineContext.
        """
        if isinstance(ctx, WineContext):
            cls.__context.discard(ctx)
            if cls.__default is ctx:
                if cls.__context:
                    for x in cls.__context:
                        cls.__default = x
                        break
                else:
                    cls.__default = None
        else:
            raise TypeError(
                "Argument 'ctx' should be an instance of lyndows.wine.WineContext"
            )

    @classmethod
    def default_context(cls) -> WineContext | None:
        """Returns a default context object.

        This class method tries to instantiate a WineContext with a default winedist 
        found on the systemas returned by Dist.default() and a default prefix as 
        returned by Prefix.default(). This will succed only if Dist.default() and
        Prefix.default() are both None

        Returns: 
            WineContext | None: An instance of a WineContext or `None` if it's failed.
        """
        dist = Dist.default()
        if dist is not None:
            prefix = Prefix.default()
            if prefix:
                return cls(dist, prefix)
        return None

    @classmethod
    def context(cls) -> WineContext | None:
        """Get the default registred context.

        The default registred context is the last one that has been registred. 
        If there is no such context this method will call the `default_context` 
        method trying to get a context representing the default wine distribution
        for this system associated to a default wine prefix (eg: ~/.wine)

        Returns:
            WineContext | None: The default context if successful, `None` otherwise.
        """
        if cls.__default is None:
            ctx = cls.default_context()
            if ctx:
                cls.register(ctx)
        return cls.__default


class Session():
    def __init__(self) -> None:
        pass


class Executable():
    __slots__ = (
        '_exe', '_use_proton', '_use_steam', '_proton_mode', 
        '_prepend_command', 'context'
    )

    def __init__(self, exe: FilePath, context: WineContext=None) -> None:
        _exe = exe
        if not on_windows():
            self.context = context if context is not None else WineContext.context()
            if self.context is None:
                raise RuntimeError("No valid WineContext was found.")
            exe = self.context.prefix.get_native_path(exe)
            logger.debug(f"exe: {exe}")
            exe = self.context.dist.check_executable(exe)
        else:
            self.context = None
            exe = exe if is_win32exec(exe) else None
        if exe is None:
            raise ValueError(f"{_exe} is not a valid executable.")

        self._exe = exe
        self._use_proton = False
        self._use_steam = False
        self._proton_mode = 'runinprefix'
        self._prepend_command = None

    def use_proton(self, usage: bool=True, mode: str='runinprefix') -> None:
        self._use_proton = bool(usage) if self.context.is_proton else False
        if self._use_proton:
            self.context.STEAM_COMPAT_DATA_PATH = self.context.prefix.root
            #NOTE: proton expect 'wine' and append '64' after, 
            # so reset it as simply 'wine', ugly but....
            self.context.__dict__['WINELOADER'] = (
                f"{self.context.dist.winedist}/bin/wine"
            )
            if mode in ('runinprefix', 'run'):
                self._proton_mode = mode    

    def use_steam(self, usage: bool=True) -> None:     
        self._use_steam = bool(usage)       

    def prepend_command(self, command: FilePath=None) -> None:
        #TODO: verify command
        self._prepend_command = command

    def get_path(self, path):
        return self.context.prefix.get_windows_path(path) if self.context else path

    @property
    def exe(self) -> Path:
        return self._exe

    @property
    def env(self) -> dict[str:str]:
        return self.context.env if self.context else {}

    @property
    def wine(self) -> Path | None:
        return self.context.dist.loader if self.context else None

    @property
    def command(self) -> list:
        # [<command>, [<wine> | <proton>, [<runinprefix> | <run>]], <steam.exe>, <exe>]
        cmd = []
        if self.context:
            if self._prepend_command:
                cmd.append(str(self._prepend_command))
            if not self._use_proton:
                cmd.append(str(self.context.dist.loader))
            else:
                cmd.append(str(self.context.dist.proton))
                cmd.append(self._proton_mode)
            if self._use_steam and not self._use_proton:
                cmd.append('c:\\windows\\system32\\steam.exe')
        cmd.append(str(self._exe))
        return cmd
    
    def __repr__(self):
        return str(self._exe)

    def __str__(self):
        return self.__repr__()

    def __contains__(self, substr):
        return substr in self.__repr__()

    def __iter__(self):
        return iter(self.__repr__().split())
