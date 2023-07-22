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
import sys
import importlib
from pathlib import Path, PureWindowsPath
import subprocess
import shlex
import time
import logging
import chardet
import copy


logger = logging.getLogger(__name__)


dist_commands = [
    "winecfg", "uninstaller", "regedit", "winetricks",
    "wineconsole", "notepad", "winefile",
    "taskmgr", "control", "msiexec"
]


def on_windows():
    return sys.platform in ["win32", "cygwin"]


def open_guess_encoding(path):
    detector = chardet.universaldetector.UniversalDetector()
    path = get_native_path(path)
    with open(path, "rb") as f:
        for line in f.readlines():
            detector.feed(line)
            if detector.done:
                break
    detector.close()
    return detector.result["encoding"]


def get_native_path(path):
    path = subprocess.check_output(
        ["winepath", "-u", str(path)], encoding="UTF-8", shell=False
    )
    return Path(path.strip()).resolve()


def get_windows_path(path):
    path = subprocess.check_output(
        ["winepath", "-w", str(path)], encoding="UTF-8", shell=False
    )
    return PureWindowsPath(path.strip())


def check_executable(path):
    path = Path(path).expanduser().resolve()
    if not on_windows():
        if str(path.name) in dist_commands:
            return path.name
        path = get_native_path(path)
    
    if all([
        path.is_file(), 
        #FIXME: os.access(path, os.X_OK), 
        path.suffix == ".exe"
    ]):
        return path
    return None


def killall(self, context=None):
    """Kill all processes running inside the wineprefix.
    """
    if context is None:
        context = WineContext.context()
    if not isinstance(context, WineContext):
        raise ValueError()
    subprocess.check_output(
        ["wineboot", "0"], 
        encoding="UTF-8", 
        shell=False, 
        env=dict(WINEPREFIX=context.WINEPREFIX)
    )


proton = None
def import_proton(protonpath):
    global proton
    if not proton:
        sys.path.append(str(protonpath))
        importlib.machinery.SOURCE_SUFFIXES.append("")
        proton = importlib.import_module("proton")
    return proton


class WineContext:
    __context = set()
    __default = None
    __default_dist = None
    __slots__ = ("_dist", "_is_proton", "__dict__")

    def __init__(self, dist=None, prefix=None, **kwargs):
        # Verify dist & prefix
        if not (dist and prefix):
            raise ValueError("dist and prefix arguments are mandatory.")
        dist = Path(dist).expanduser().resolve()
        prefix = Path(prefix).expanduser().resolve()
        if not (dist.exists() and prefix.exists()):
            raise NotADirectoryError(
                "One are all of the required path are not valid directory."
            )
        self.WINEPREFIX = prefix

        # Guess the wine path
        if (dist / "bin").is_dir():
            self.WINEDIST = dist
            self._is_proton = False
        elif (dist / "files").is_dir() and (dist / "proton").is_file():
            self.WINEDIST = dist / "files"
            self._is_proton = True
        elif (dist / "dist").is_dir() and (dist / "proton").is_file():
            self.WINEDIST = dist / "dist"
            self._is_proton = True
        else:
            raise AttributeError("Could not determin a correct Wine Distribution")
        self._dist = dist

        # KWARGS STUFF
        kwargs.pop('WINEDIST', None)
        self.WINELOADER = Path(
            kwargs.get(
                "WINELOADER",
                self.WINEDIST
                / "bin"
                / ("wine64" if (self.WINEDIST / "bin/wine64").exists() else "wine"),
            )
        )
        self.WINESERVER = Path(
            kwargs.get("WINESERVER", self.WINEDIST / "bin/wineserver")
        )
        self.__dict__ |= kwargs

    def copy(self):
        prefix = self.WINEPREFIX.parent if self._is_proton else self.WINEPREFIX
        duply = WineContext(
            self._dist, 
            prefix, 
            WINELOADER=self.WINELOADER, 
            WINESERVER=self.WINESERVER
        )
        for k, v in self.__dict__.items():
            duply.__dict__[k] = copy.copy(v)
        return duply

    def update(self, other):
        if isinstance(other, WineContext):
            other = other.__dict__
        self.__dict__.update(other)

    def get(self, key, default=""):
        return self.__dict__.get(key, default)
    
    def has(self, key):
        return key in self.__dict__

    def start_server(self):
        #FIXME: dont work at all!!
        env = {"WINEPREFIX": self.WINEPREFIX}
        logger.debug(f"start wineserver {self.get_server()} in {self.WINEPREFIX}")
        args = [self.get_server(), "--persistent=10"]
        args = shlex.join(args)
        subprocess.run(args, env=env, shell=True)
        time.sleep(2)

    def get_server(self):
        return self.WINESERVER

    def get_wine(self):
        return self.WINELOADER

    def is_proton(self):
        return self._is_proton

    def get_proton(self):
        return self.WINEDIST.parent / 'proton' if self._is_proton else None

    def get_env(self):
        _env = self._format_env()
        for k, v in _env.items():
            if isinstance(v, list):
                if k == "WINEDLLOVERRIDES":
                    _env["WINEDLLOVERRIDES"] = ";".join([str(p) for p in v])
                else:
                    _env[k] = ":".join([str(p) for p in v])
            else:
                _env[k] = str(v)
        return _env

    def _format_env(self):
        #TODO: more
        _env = dict(self.__dict__)

        if self.get("WINEPATH"):
            _env["WINEPATH"] = self.get("WINEPATH")

        _env["WINEDLLPATH"] = self.get("WINEDLLPATH", []) + [
            self.WINEDIST / "lib64" / "wine",
            self.WINEDIST / "lib" / "wine"
        ]

        if self.get("WINEDLLOVERRIDES"):
            _env["WINEDLLOVERRIDES"] = self.get("WINEDLLOVERRIDES")

        _env["LD_LIBRARY_PATH"] = [
            self.WINEDIST / "lib64/",
            self.WINEDIST / "lib/",
        ] + self.get("LD_LIBRARY_PATH", [])

        _env["PATH"] = self.get("PATH", []) + [
            self.WINEDIST / "bin",
            "/usr/bin",
            "/bin",
        ]

        if "ESYNC" in self.__dict__:
            _env["WINEESYNC"] = self.ESYNC
            if self._is_proton:
                _env["PROTON_NO_ESYNC"] = 1 - int(self.ESYNC)
            del _env["ESYNC"]

        if "FSYNC" in self.__dict__:
            _env["WINEFSYNC"] = self.FSYNC
            if self._is_proton:
                _env["PROTON_NO_FSYNC"] = 1 - int(self.FSYNC)
            del _env["FSYNC"]

        if "LARGE_ADDRESS_AWARE" in self.__dict__:
            _env["WINE_LARGE_ADDRESS_AWARE"] = self.LARGE_ADDRESS_AWARE
            if self._is_proton:
                _env["PROTON_FORCE_LARGE_ADDRESS_AWARE"] = self.LARGE_ADDRESS_AWARE
            del _env["LARGE_ADDRESS_AWARE"]

        _env["TERM"] = self.get("TERM", "xterm")

        # Logs defaults all to none
        _env["WINEDEBUG"] = self.get("WINEDEBUG", "-all,-fixme,-server")
        _env["DXVK_LOG_LEVEL"] = self.get("DXVK_LOG_LEVEL", "none")
        _env["PROTON_LOG"] = self.get("PROTON_LOG", "0")
        return _env

    @classmethod
    def register(cls, ctx):
        if isinstance(ctx, WineContext):
            cls.__context.add(ctx)
            cls.__default = ctx
        else:
            raise TypeError(
                "Argument 'ctx' should be an instance of lyndows.wine.WineContext"
            )

    @classmethod
    def unregister(cls, ctx):
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
    def default_dist(cls):
        if cls.__default_dist:
            return cls.__default_dist

        wine = subprocess.check_output(
            ["whereis", "-b", "wine"], encoding="UTF-8", shell=False
        )
        wine = wine.split(":")
        if wine[1].strip():
            wine = wine[1].split(" ")
            for w in wine:
                w = Path(w).resolve()
                dist = w.parent.parent
                if all(
                    [
                        (dist / "bin").is_dir(),
                        (dist / "lib").is_dir(),
                        (dist / "share").is_dir(),
                        (dist / "bin" / "wine").is_file(),
                        (dist / "bin" / "wineserver").is_file(),
                    ]
                ):
                    cls.__default_dist = dist
                    return dist
        return None

    @classmethod
    def default_context(cls):
        if cls.default_dist():
            prefix = None
            if (Path.home / ".wine64").is_dir():
                prefix = Path.home / ".wine64"
            elif (Path.home / ".wine").is_dir():
                prefix = Path.home / ".wine"
            if prefix:
                return cls(cls.default_dist(), prefix)
        return None

    @classmethod
    def context(cls):
        if cls.__default is None:
            ctx = cls.default_context()
            if ctx:
                cls.register(ctx)
        return cls.__default




class Executable:
    def __init__(self, exe, context=None):
        self.exe = check_executable(exe)
        if self.exe is None:
            raise ValueError(f"{exe} is not a valid executable.")

        if not on_windows():
            self.context = context if context is not None else WineContext.context()
            if self.context is None:
                raise RuntimeError("No valid WineContext was found.")
        else:
            self.context = None
        self._use_proton = False
        self._use_steam = False
        self._proton_mode = 'runinprefix'
        self._prepend_command = None

    def use_proton(self, usage=True, mode='runinprefix'):
        self._use_proton = bool(usage) if self.context.is_proton() else False
        if self._use_proton:
            if self.context.WINEPREFIX.name == "pfx":
                self.context.STEAM_COMPAT_DATA_PATH = self.context.WINEPREFIX.parent
            else:
                self.context.STEAM_COMPAT_DATA_PATH = self.context.WINEPREFIX
            #NOTE: proton expect 'wine' and append '64' after, so reset it as simply 'wine'
            self.context.WINELOADER = self.context.WINELOADER.with_name('wine')
            if mode in ('runinprefix', 'run'):
                self._proton_mode = mode    

    def use_steam(self, usage=True):     
        self._use_steam = bool(usage)       

    def prepend_command(self, command=None):
        #TODO: verify command
        self._prepend_command = command

    def get_path(self, path):
        return get_windows_path(path) if self.context else path

    def get_exe(self):
        return self.exe

    def get_env(self):
        return self.context.get_env() if self.context else {}

    def get_wine(self):
        return self.context.get_wine() if self.context else None

    def get_command(self):
        # [<command>, [<wine> | <proton>, [<runinprefix> | <run>]], <steam.exe>, <exe>]
        cmd = []
        if self.context:
            if self._prepend_command:
                cmd.append(str(self._prepend_command))
            if not self._use_proton:
                cmd.append(str(self.context.get_wine()))
            else:
                cmd.append(str(self.context.get_proton()))
                cmd.append(self._proton_mode)
            if self._use_steam and not self._use_proton:
                cmd.append('c:\\windows\\system32\\steam.exe')
        cmd.append(str(self.exe))
        return cmd
    
    # def _proton_init(self):
    #     import_proton(self.context.WINEDIST)
    #     _proton = proton.Proton(str(self.context.WINEDIST))
    #     _proton.cleanup_legacy_dist()
    #     proton.g_proton = _proton

    #     # set environement variables
    #     tmp_env = dict(os.environ)  # save env for restore later
    #     os.environ |= self.context.get_env()

    #     proton.CompatData(str(self.context.WINEPREFIX.removesuffix("/pfx")))
    #     _session = proton.Session()
    #     _session.init_wine()

    #     if _proton.missing_default_prefix():
    #         _proton.make_default_prefix()
    #     _session.init_session(False)

    #     self.context.__dict__ |= _session.env
    #     os.environ = tmp_env
    #     self.context.WINELOADER = Path(_proton.wine64_bin)

    def __repr__(self):
        return str(self.exe)

    def __str__(self):
        return self.__repr__()

    def __contains__(self, substr):
        return substr in self.__repr__()

    def __iter__(self):
        return iter(self.__repr__().split())
