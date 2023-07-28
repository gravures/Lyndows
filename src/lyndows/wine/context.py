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

from lyndows.util import EnvMapping, FilePath
from lyndows.wine.dist import Distribution
from lyndows.wine.prefix import Prefix

logger = logging.getLogger(__name__)


class WineContext(EnvMapping):
    __context = set()
    __default = None
    __slots__ = ("_prefix", "_dist")

    def __init__(
        self, dist: FilePath | Distribution, prefix: FilePath | Prefix, **kwargs
    ):
        super().__init__(dist=dist, prefix=prefix)
        self.add_list_separator("WINEDLLOVERRIDES", ";")

        # TODO: Validation of prefix against distribution
        self._dist = dist if isinstance(dist, Distribution) else Distribution(dist)
        self._prefix = prefix if isinstance(prefix, Prefix) else Prefix(prefix)

        self._protected = (
            "WINEDIST",
            "WINELOADER",
            "WINEPREFIX",
            "WINESERVER",
            "WINEARCH",
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
            self.WINEDIST / "lib" / "wine",
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
            if name == "ESYNC":
                env["WINEESYNC"] = int(value)
                if self.is_proton:
                    env["PROTON_NO_ESYNC"] = 1 - int(value)
                del env[name]
            elif name == "FSYNC":
                env["WINEFSYNC"] = int(value)
                if self.is_proton:
                    env["PROTON_NO_FSYNC"] = 1 - int(value)
                del env[name]
            elif name == "LARGE_ADDRESS_AWARE":
                env["WINE_LARGE_ADDRESS_AWARE"] = int(value)
                if self.is_proton:
                    env["PROTON_FORCE_LARGE_ADDRESS_AWARE"] = int(value)
                del env[name]
        return env

    @property
    def dist(self) -> Distribution:
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
    def register(cls, context):
        """Register a WineContext instance with the class.

        Parameters:
            - context (WineContext): The WineContext instance to be registered.

        Raises:
            TypeError: If the argument 'context' is not an instance
            of lyndows.wine.WineContext.
        """
        if isinstance(cls, WineContext):
            cls.__context.add(context)
            cls.__default = context
        else:
            raise TypeError(
                "Argument 'context' should be an instance"
                " of lyndows.wine.WineContext"
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
        if not isinstance(ctx, WineContext):
            raise TypeError(
                "Argument 'ctx' should be an instance of lyndows.wine.WineContext"
            )
        cls.__context.discard(ctx)
        if cls.__default is ctx:
            if cls.__context:
                for x in cls.__context:
                    cls.__default = x
                    break
            else:
                cls.__default = None

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
        dist = Distribution.default()
        if dist is not None:
            if prefix := Prefix.default():
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
            if ctx := cls.default_context():
                cls.register(ctx)
        return cls.__default
