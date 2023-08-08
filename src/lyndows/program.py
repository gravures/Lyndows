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
import shlex
from pathlib import (
    Path,
    PurePath,
    _posix_flavour,  # type: ignore
    _windows_flavour,  # type: ignore
)
from typing import Any, Sequence, Type

import psutil

from lyndows.path import (
    UPath,
    UPosixPath,
    UWindowsPath,
    UWinePath,
    is_windows_path,
)
from lyndows.util import FilePath, is_win32exec, on_windows

logger = logging.getLogger(__name__)

Arguments = Sequence[tuple[str, ...]] | None


class Program(UPath):
    __slots__ = ("_arguments", "_prepend_command", "_env")

    def __new__(cls, *parts: Any, args: Arguments = None, **kwargs: Any):
        if cls is Program:
            winexe = is_win32exec(Path(*parts))
            cls = WineProgram if not on_windows() and winexe else NativeProgram

        self = super().__new__(cls, *parts, **kwargs)
        self._prepend_command = None
        if args:
            self.set_arguments(*args)
        else:
            self._arguments = []
        self._env = {}
        return self

    def _transform_path_argument(self, path: FilePath) -> FilePath:
        raise NotImplementedError()

    def _command(self) -> list[str]:
        cmd = [str(self)]
        if self._prepend_command:
            cmd.insert(0, str(self._prepend_command))
        return cmd

    def prepend_command(self, command: FilePath | None = None) -> None:
        # TODO: verify command
        self._prepend_command = command

    def add_arguments(self, *args: tuple[str, ...]) -> None:
        for tup in args:
            if not (isinstance(tup, tuple) and len(tup) < 3):
                raise TypeError(f"args should be tuples('opt', [<value>]):\n {args}")
            tmp = []
            for e in tup:
                if isinstance(e, Path):
                    e = self._transform_path_argument(e)
                tmp.append(str(e))
            self._arguments += tmp

    def set_arguments(self, *args: tuple[str, ...]) -> None:
        self._arguments = []
        self.add_arguments(*args)

    def compile_arguments(self) -> str:
        return shlex.join([str(a) for a in self._command()] + self._arguments)

    def open(
        self,
        isolation: bool = False,
        cwd: FilePath | None = None,
        encoding: str = "utf-8",
        text=None,
    ) -> psutil.Process:
        args = self._command() + self._arguments

        _env = {}
        if not isolation:
            _env |= os.environ
        if self._context:
            _env |= self._context.env
        _env |= self._env

        return psutil.Popen(
            args, cwd=cwd, env=_env, text=text, encoding=encoding, shell=False
        )

    def __fspath__(self) -> str:
        return self.compile_arguments()


_Native: Type[UWindowsPath] | Type[UPosixPath] = (
    UWindowsPath if on_windows() else UPosixPath
)


class NativeProgram(Program, _Native):  # type: ignore
    __slots__ = ()
    _flavour = _windows_flavour if on_windows() else _posix_flavour

    def _transform_path_argument(self, path: FilePath) -> FilePath:
        return path


class WineProgram(Program, UWinePath, api=(PurePath, UPath, UWinePath)):
    __slots__ = (
        "_use_proton",
        "_use_steam",
        "_proton_runmode",
    )

    def __new__(cls, *parts: Any, args: Arguments = None, **kwargs: Any):
        self = super().__new__(cls, *parts, args=args, **kwargs)
        self._use_proton = False
        self._use_steam = False
        self._proton_runmode = "runinprefix"
        return self

    def _transform_path_argument(self, path: FilePath) -> FilePath:
        return path if is_windows_path(path) else UPosixPath(path).as_windows()

    def _command(self) -> list[str]:
        # [<command>, [<wine> | <proton>, [<runinprefix> | <run>]], <steam.exe>, <exe>]
        cmd = super()._command()
        xcmd = []
        if not self._use_proton:
            xcmd.append(str(self._context.dist.loader))  # type: ignore
        else:
            xcmd.extend((str(self._context.dist.proton), self._proton_runmode))  # type: ignore
        if self._use_steam and not self._use_proton:
            xcmd.append("c:\\windows\\system32\\steam.exe")
        if self._prepend_command:
            xcmd.insert(0, str(self._prepend_command))
        return xcmd + cmd

    def use_proton(self, usage: bool = True, mode: str = "runinprefix") -> None:
        self._use_proton = usage if self._context.is_proton else False  # type: ignore
        if self._use_proton:
            self._context.STEAM_COMPAT_DATA_PATH = self._context.prefix.root  # type: ignore
            # NOTE: proton expect 'wine' and append '64' after,
            # so reset it as simply 'wine', ugly but....
            self._context.__dict__[
                "WINELOADER"
            ] = f"{self._context.dist.winedist}/bin/wine"
            if mode in {"runinprefix", "run"}:
                self._proton_mode = mode

    def use_steam(self, usage: bool = True) -> None:
        self._use_steam = usage
