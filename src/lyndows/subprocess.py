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
import subprocess
from enum import Enum
from pathlib import Path

from psutil import Popen

from lyndows.util import FilePath, is_flagexec, is_win32exec, on_windows
from lyndows.wine.context import WineContext

logger = logging.getLogger(__name__)


def command(*args, **kwargs):
    cp = subprocess.run(
        args, encoding="UTF-8", shell=False, capture_output=True, text=True, **kwargs
    )
    return cp.stdout + cp.stderr


class Program:
    __slots__ = (
        "_exe",
        "_use_proton",
        "_use_steam",
        "_proton_mode",
        "_prepend_command",
        "_context",
    )

    def __init__(self, exe: FilePath, context: WineContext | None = None) -> None:
        if on_windows():
            self._context = None
            self._exe = exe if is_win32exec(exe) else None
        elif not is_win32exec(exe) and is_flagexec(exe):
            self._context = None
            self._exe = Path(exe).expanduser().resolve()
        else:
            self._context = context if context is not None else WineContext.context()
            if self._context is None:
                raise RuntimeError("No valid WineContext was found.")
            self._exe = self._context.prefix.get_native_path(exe)
            self._exe = self._context.dist.check_executable(self._exe)
        if self._exe is None:
            raise ValueError(f"{exe} is not a valid executable.")

        self._use_proton = False
        self._use_steam = False
        self._proton_mode = "runinprefix"
        self._prepend_command = None

    def use_proton(self, usage: bool = True, mode: str = "runinprefix") -> None:
        if self._context:
            self._use_proton = usage if self._context.is_proton else False
            if self._use_proton:
                self._context.STEAM_COMPAT_DATA_PATH = self._context.prefix.root
                # NOTE: proton expect 'wine' and append '64' after,
                # so reset it as simply 'wine', ugly but....
                self._context.__dict__[
                    "WINELOADER"
                ] = f"{self._context.dist.winedist}/bin/wine"
                if mode in {"runinprefix", "run"}:
                    self._proton_mode = mode

    def use_steam(self, usage: bool = True) -> None:
        if self._context:
            self._use_steam = usage

    def prepend_command(self, command: FilePath | None = None) -> None:
        # TODO: verify command
        self._prepend_command = command

    def get_path(self, path):
        return self._context.prefix.get_windows_path(path) if self._context else path

    @property
    def exe(self) -> Path:
        return self._exe  # type: ignore

    @property
    def context(self) -> WineContext | None:
        return self._context

    @property
    def env(self) -> dict[str, str]:
        return self._context.env if self._context else {}

    @property
    def wine(self) -> Path | None:
        return self._context.dist.loader if self._context else None

    @property
    def command(self) -> list:
        # [<command>, [<wine> | <proton>, [<runinprefix> | <run>]], <steam.exe>, <exe>]
        cmd = []
        if self._context:
            if not self._use_proton:
                cmd.append(str(self._context.dist.loader))
            else:
                cmd.extend((str(self._context.dist.proton), self._proton_mode))
            if self._use_steam and not self._use_proton:
                cmd.append("c:\\windows\\system32\\steam.exe")
        if self._prepend_command:
            cmd.insert(0, str(self._prepend_command))
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


##
# External process handling
class Process:
    __slots__ = ("_program", "_process", "_arguments", "_state", "_env", "_exit_code")

    class STATE(Enum):
        NOT_STARTED = 0
        RUNNING = 1
        STOPPED = 2

    def __init__(self, program, *args, env=None):
        self._program = program if isinstance(program, Program) else Program(program)
        self.set_arguments(*args)
        self._env = env or {}
        self._process = None
        self._exit_code = None
        self._state = Process.STATE.NOT_STARTED

    def set_arguments(self, *args):
        self._arguments = []
        self.add_arguments(*args)

    def add_arguments(self, *args):
        for tup in args:
            if not (isinstance(tup, tuple) and len(tup) < 3):
                raise TypeError(f"args should be tuples('opt', [<value>]):\n {args}")
            tmp = []
            for e in tup:
                if isinstance(e, Path):
                    e = self._program.get_path(e)
                tmp.append(str(e))
            self._arguments += tmp

    def get_arguments(self):
        return self._arguments

    def compile_args(self):
        return shlex.join(self._program.command + self._arguments)

    def run(self, isolation=False, text=True, **kwargs) -> subprocess.CompletedProcess:
        if self._process is not None or self._state != Process.STATE.NOT_STARTED:
            raise RuntimeError("This Process has already been started.")

        args = self.compile_args()
        for arg in ("args", "env", "text", "shell"):
            kwargs.pop(arg, None)

        _env = {}
        if not isolation:
            _env |= os.environ
        _env |= self._program.env
        _env |= self._env

        codec = "UTF-8" if text else None

        cp = subprocess.run(
            args,
            env=_env,
            capture_output=True,
            text=text,
            encoding=codec,
            check=False,
            shell=True,
            **kwargs,
        )
        self._state = Process.STATE.STOPPED
        self._exit_code = cp.returncode
        return cp

    def popen(self, isolation=False, text=True, **kwargs) -> None:
        if self._process is not None:
            raise RuntimeError("This Process is already running.")
        elif self._state == Process.STATE.STOPPED:
            raise RuntimeError("This Process has now stopped.")

        args = self._program.command + self._arguments
        for arg in ("args", "env", "text", "shell", "executable"):
            kwargs.pop(arg, None)

        _env = {}
        if not isolation:
            _env |= os.environ
        _env |= self._program.env
        _env |= self._env

        codec = "UTF-8" if text else None

        try:
            self._process = Popen(
                args, env=_env, text=text, encoding=codec, shell=False, **kwargs
            )
        except subprocess.CalledProcessError as e:
            self._process = None
            self._state = Process.STATE.STOPPED
            raise e
        else:
            self._state = Process.STATE.RUNNING

    def is_running(self) -> bool:
        """Returns if the process is running.

        Return whether the current process is running in the current
        process list. This is reliable also in case the process is gone
        and its PID reused by another process.
        """
        return self._process.is_running() if self._process else False

    def suspend(self) -> None:
        """Suspend the process.

        Suspend process execution with SIGSTOP signal preemptively
        checking whether PID has been reused.
        """
        return self._process.suspend() if self._process else None

    def resume(self) -> None:
        """Resume the process.

        Suspend process execution with SIGSTOP signal preemptively
        and checking whether PID has been reused.
        """
        return self._process.resume() if self._process else None

    def terminate(self) -> None:
        """Terminate the process.

        Terminate the process with SIGTERM signal preemptively
        checking whether PID has been reused.
        """
        return self._process.terminate() if self._process else None

    def kill(self) -> None:
        """Kill the process.

        Terminate the process with SIGTERM signal preemptively
        checking whether PID has been reused.
        """
        return self._process.kill() if self._process else None

    def wait(self, timeout=None) -> bool | None:
        """Wait for the process to terminate.

        On all platforms return True if the process has terminated
        without error or False otherwise. If the procees does
        not exist return None immediately. The exit code of
        the process could be retriewed with the property exit_code.
        """
        if self._process is not None:
            self._exit_code = self._process.wait(timeout)
            if self._exit_code is None:
                self._state = Process.STATE.STOPPED
                return None
            elif on_windows():
                return self._exit_code == 0
            else:
                return self._exit_code >= 0
        return None

    @property
    def exit_code(self) -> int | None:
        """Return the exit code of the process.

        The returned code meaning is depending on
        the platform. Return None if the process does not
        exist or has not terminated yet.
        """
        return self._exit_code


class BaseHook:
    def __init__(self, context: WineContext | None = None):
        self.context = context

    def __enter__(self) -> BaseHook:
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
        return False


class Launcher:
    def __init__(
        self,
        context: WineContext | None,
        exe: FilePath,
        *args: list,
        use_proton: bool = False,
        proton_mode: str = "runinprefix",
        use_steam: bool = False,
        hook: BaseHook | None = None,
        isolation: bool = False,
        textmode: bool = True,
        prepend_command: FilePath | None = None,
    ):
        WineContext.register(context)
        self.exe = Program(exe, context)
        self.exe.use_proton(use_proton, mode=proton_mode)
        self.exe.use_steam(use_steam)
        self.exe.prepend_command(prepend_command)
        self.process = Process(self.exe)
        self.process.set_arguments(*args)
        self.hook = hook if hook is not None else BaseHook()
        self.isolation = isolation
        self.textmode = textmode

    def run(self, nowait: bool = False) -> None:
        with self.hook:
            if not nowait:
                cp = self.process.run(self.isolation, self.textmode)
                print(cp.stderr)
                print(cp.stdout)
            else:
                self.process.popen(self.isolation, self.textmode)

    def get_command(self) -> str:
        return self.process.compile_args()

    def finished(self) -> bool:
        # sourcery skip: boolean-if-exp-identity, remove-unnecessary-cast
        return False if self.process.poll() is None else True  # type: ignore
