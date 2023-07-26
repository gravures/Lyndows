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

import copy
import logging
import os
from pathlib import Path
from typing import Any

from lyndows.fileutil import FilePath

logger = logging.getLogger(__name__)


class BaseHelper():
    __slots__ = ("_lock", "_protected", "_kwargs", "__dict__")
    
    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs
        self._protected = []
        self._lock = True

    def get(self, key: str, default: Any="") -> Any: 
        """Retrieve the value associated with key

        Retrieve the value associated with the given key 
        from the object's dictionary.

        Parameters:
            key (str): The key to retrieve the value for.
            default (Any, optional): The default value to return 
            if the key is not found. Defaults to an empty string.

        Returns:
            Any: The value associated with the key if found, 
            otherwise the default value.
        """
        return self.__dict__.get(key, default)
    
    def has(self, key: str) -> bool:
        """Check if the given key exists in the object's attributes.

        Parameters:
            key (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key in self.__dict__
    
    def copy(self) -> BaseHelper:
        """Creates a deep copy of this object.

        Returns:
            BaseHelper: A new BaseHelper object that is a deep 
            copy of the original object.
        """
        duply = self.__class__(**self._kwargs) 
        for k, v in self.__dict__.items():
            duply.__dict__[k] = copy.copy(v)
        return duply
    
    def update(
        self, other: BaseHelper | dict[str, Any], clear: list[str]=None
    ) -> None:
        """Update this BaseHelper object.

        Update the BaseHelper object with the values from another 
        BaseHelper object or a dictionary.

        Parameters:
            other (BaseHelper | dict[str, Any]): The object or dictionary 
            containing the values to update the BaseHelper object with.
            clear (list[str], optional): A list of names to set as empty lists 
            in the WineContext object. Defaults to an empty list.

        Raises:
            ValueError: If the 'empty' parameter is not a list.
        """
        clear = clear or []
        self.assert_list(clear)
        if isinstance(other, BaseHelper):
            other = other.__dict__
        for key, value in other.items():
            if key not in self._protected:
                if (key in clear) and (isinstance(self.__dict__[key], list)):
                    self.__dict__[key] = []
                self.__setattr__(key, value)

    def unset(self, name: str) -> None:
        """Unset an attribute.

        Unsets a given attribute `name` from the WineContext object.

        Parameters:
            name (str): The name of the attribute to unset.
        """
        if name not in self._protected:
            del self.__dict__[name]

    def __setattr__(self, name: str, value: Any) -> None:
        # __slots__ case
        for cls in self.__class__.__mro__:
            if cls is not object:
                if name in cls.__slots__:
                    object.__setattr__(self, name, value)
                    return
        # protected attributes
        if name in self._protected and self._lock:
            raise AttributeError(
                f"{name} is a protected variable and can't "
                f"be set by assignement."
            )
        # normal attributes
        elif isinstance(value, list):
            self._append_list(name, value)
        else:
            self.__dict__[name] = value

    def _append_list(self, key, values_list):
        if key in self.__dict__:
            logger.debug(f"KEY: {key} - VALUES: {values_list}")
            self.__dict__[key] += values_list
        else:
            self.__dict__[key] = values_list

    def env_hook(self, env: dict) -> dict:
        return env

    @property
    def env(self) -> dict[str, str]:
        """Returns this BaseHelper as environment variables.

        Returns: 
            dict[str, str]: A dictionary containing the environment 
            variables.
        """
        hook = self.env_hook(dict(self.__dict__))
        _env = dict()
        for k, v in hook.items():
            if isinstance(v, list):
                _env[k] = ":".join([str(p) for p in v])
            elif isinstance(v, bool):
                _env[k] = str(int(v))
            elif str(v)=='' or v is None:
                continue 
            else:
                _env[k] = str(v)
        return _env
        
    def dump(self) -> None:
        """Print a string representation of the environment variables.
        """
        dump = ""
        for k, v in self.env.items():
            dump += f"{k} = {v}\n"
        print(dump)
    
    def assert_file(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
                                    
    def assert_dir(self, path: Path) -> None:
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")
        
    def assert_list(self, obj: Any) -> None:
        if not isinstance(obj, list):
            raise ValueError(f"{obj} is not a list")
        
    def assert_library(self, libprefix: Path, libname: str) -> list[Path]:
        self.assert_dir(libprefix)
        try:
            libprefix = [lib.parent for lib in libprefix.glob(f"**/*{libname}*.so")]
        except IndexError:
            raise ValueError(f"No {libname} library found in prefix {libprefix}")
        else:            
            return libprefix
        
    def assert_data_dir(self, libprefix: Path) -> Path:
        while libprefix != Path('/'):
            if (libprefix / 'share').is_dir():
                return (libprefix / 'share')
            libprefix = libprefix.parent  
        raise ValueError(f"do not found data dir for prefix {libprefix}")


class SteamHelper(BaseHelper):
    __slots__ = ()

    def __init__(self, steambase: FilePath, gameid: int, winedist: FilePath):
        super().__init__(steambase=steambase, gameid=gameid)
        steambase = Path(steambase)
        self.assert_dir(steambase)
        self.assert_dir(steambase / 'steamapps' / 'compatdata' / str(gameid))
        winedist = Path(winedist)
        self.assert_dir(winedist)

        self.SteamGameId = gameid
        self.SteamAppId = gameid
        self.STEAM_COMPAT_CLIENT_INSTALL_PATH = steambase
        self.MEDIACONV_AUDIO_DUMP_FILE = (
            f"{steambase}/steamapps/shadercache/{gameid}/fozmediav1/audiov2.foz"
        )
        self.MEDIACONV_AUDIO_TRANSCODED_FILE= (
            f"{steambase}/steamapps/shadercache/{gameid}/transcoded_audio.foz"
        )
        self.MEDIACONV_VIDEO_DUMP_FILE= (
            f"{steambase}/steamapps/shadercache/{gameid}/fozmediav1/video.foz"
        )
        self.MEDIACONV_VIDEO_TRANSCODED_FILE= (
            f"{steambase}/steamapps/shadercache/{gameid}/transcoded_video.foz" 
        )
        self.LD_LIBRARY_PATH = [
            "/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu",
            "/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu/aliases",
            "/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu",
            "/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu/aliases"
        ]
        self.WINEDLLOVERRIDES = ["steam.exe=b"]

        # gstreamer-1.0
        self.WINE_GST_REGISTRY_DIR = list(
            (steambase / 'steamapps' / 'compatdata'/ 
             str(gameid)).glob('**/gstreamer-1.0')
        )[0]
        self.GST_PLUGIN_SYSTEM_PATH_1_0 = list(winedist.glob("**/gstreamer-1.0"))
        
        # steam vulkan implicit layers
        self.XDG_DATA_DIRS = [Path.home() / '.local' / 'share']


class SystemHelper(BaseHelper):
    __slots__ = ()

    def __init__(
        self, 
        esync: bool=True,
        fsync: bool=False,
        large_adress_aware: bool=True,
        term: str="xterm",
    ):
        super().__init__(
            esync=esync, fsync=fsync, large_adress_aware=large_adress_aware, term=term
        )
        self.ESYNC = esync
        self.FSYNC = fsync
        self.LARGE_ADDRESS_AWARE = large_adress_aware
        self.XTERM = term
        self.XDG_DATA_DIRS = os.environ.get('XDG_DATA_DIRS').split(':')
        self.XDG_RUNTIME_DIR = os.environ.get('XDG_RUNTIME_DIR')
        self.HOME = os.environ.get('HOME')


class VkBasaltHelper(BaseHelper):
    __slots__ = ()

    def __init__(self, vkbasalt: FilePath, config_file: FilePath=None):
        super().__init__(vkbasalt=vkbasalt)
        vkbasalt = self.assert_library(Path(vkbasalt), 'libvkbasalt')
        self.LD_LIBRARY_PATH = vkbasalt
        # for vulkan implicit layers
        self.XDG_DATA_DIRS = [self.assert_data_dir(vkbasalt[0])]
        #
        self.ENABLE_VKBASALT = 1

        if config_file:
            self.assert_file(Path(config_file))
            self.VKBASALT_CONFIG_FILE = config_file


class LibStrangleHelper(BaseHelper):
    __slots__ = ()

    def __init__(self, libstrangle: FilePath):
        super().__init__(libstrangle=libstrangle)
        libstrangle = self.assert_library(Path(libstrangle), 'libstrangle')
        self.LD_LIBRARY_PATH = libstrangle
        # for vulkan implicit layers
        self.XDG_DATA_DIRS = [self.assert_data_dir(libstrangle[0])]
        # obviously
        self.ENABLE_VK_LAYER_TORKEL104_libstrangle = 1


class MesaHelper(BaseHelper):
    __slots__ = ()

    def __init__(
        self, 
        mesalib: FilePath=None, 
        libdrm: FilePath=None,
        vkdriver: list=None
    ) -> None:
        super().__init__(mesalib=mesalib, libdrm=libdrm, vkdriver=vkdriver)

        _mesalib = Path(mesalib)
        if mesalib:
            mesalib = _mesalib
            mesalib = self.assert_library(mesalib, 'mesa')
            self.LD_LIBRARY_PATH = mesalib
            self.EGL_DRIVERS_PATH = mesalib[0]
            self.LIBGL_DRIVERS_PATH = mesalib[0]
            # for graphic pipeline vulkan extension
            self.ANV_GPL = 'true'
            # for vulkan implicit and explicit layers
            self.XDG_DATA_DIRS = [self.assert_data_dir(mesalib[0])]
            
        if libdrm:
            libdrm = Path(libdrm) 
            libdrm = self.assert_library(libdrm, 'libdrm')
            self.LD_LIBRARY_PATH = libdrm
            
        if vkdriver and mesalib:
            self.assert_list(vkdriver)
            # The VK_ICD_FILENAMES environment variable is a list 
            # of Driver Manifest files, containing the full path 
            # to the driver JSON Manifest file.
            # VK_ICD_FILENAMES will only contain a full pathname 
            # to one info file for a single driver.
            for driver in vkdriver:
                icd = list(_mesalib.glob(f"**/{driver}_icd.*.json"))
                if not icd:
                    raise ValueError(f"No icd file found for driver {driver}")
                self.VK_ICD_FILENAMES = icd


def get_dxvk_version(dist: FilePath) -> str:
    version = Path(dist) / 'files' / 'lib64' / 'wine' / 'dxvk' / 'version'
    with version.open('rU') as f:
        return f.readline().split('dxvk')[1].strip()[2:-1]
    

# class DXVK_Helper(BaseHelper):
#     __slots__ = ()
#     def __init__(self) -> None:
#         self.DXVK_STATE_CACHE = "disable"  # disable|reset
#         self.DXVK_STATE_CACHE_PATH= f"{SHADER_CACHE}/DXVK_state_cache"
#         self.DXVK_ASYNC = 1
#         self.DXVK_HUD = "fps,compiler,version,devinfo,pipelines,scale=.42"
#         self.DXVK_CONFIG_FILE = f"{HOME}/.steam/SKYRIM/conf/dxvk.conf"
#         self.DXVK_LOG_PATH = f"{HOME}/.steam/SKYRIM/Logs"
#         self.DXVK_LOG_LEVEL = "none"


# def get_driver_diagnostic(mesa_lib, vk_driver, lib_drm=None):
#     mesa = get_mesa_conf(mesa_lib, vk_driver, lib_drm)
#     data_dir = os.environ.get('XDG_DATA_DIRS', '').split(':')
#     data_dir.insert(0, '/usr/local/share')  # libstrangle, vkbasalt
#     data_dir.insert(0, '/opt/mesa-22.3/share')  # implicit explicit mesa vkLayers
#     data_dir.insert(0, '/home/gilles/.local/share')  # steam layer
    
#     context = wine.WineContext(
#         dist = get_dist('GE-Proton8-6'),
#         prefix = get_prefix('GE-Proton8-6'),
#         # **common, 
#         **mesa, 
#         # **DRIVER
#         XDG_DATA_DIRS = data_dir
#     )
#     env = context.get_env()
#     sysld = os.environ.get('LD_LIBRARY_PATH', '')
#     vkld = '/usr/local/lib/x86_64-linux-gnu:/usr/local/lib/libstrangle/lib64'
#     mld = ':'.join(mesa['LD_LIBRARY_PATH'])
#     env['LD_LIBRARY_PATH'] = f"{vkld}:{mld}"
#     env['DISPLAY'] = os.environ.get('DISPLAY')
#     env['XDG_RUNTIME_DIR'] = os.environ.get('XDG_RUNTIME_DIR')
#     env['ANV_GPL'] = '1'

#     #
#     diagnostic = command('vulkaninfo', env=env)
#     vkloader = command('grep', 'Vulkan Instance Version', input=diagnostic)
#     deviceName = command('grep', 'deviceName', input=diagnostic)
#     deviceType = command('grep', 'deviceType', input=diagnostic)
#     driverName = command('grep', 'driverName', input=diagnostic)
#     driverInfo = command('grep', 'driverInfo', input=diagnostic)
#     conformanceVersion = command('grep', 'conformanceVersion', input=diagnostic)
#     vklayer = command('grep', 'VK_LAYER', input=diagnostic)

#     # vk extension stuff
#     vkext = command('grep', 'VK_EXT_', input=diagnostic)
#     vkext = vkext.splitlines()
#     dxvk2_ext_required = (
#         'VK_EXT_robustness2', 'VK_EXT_transform_feedback', 
#         'VK_EXT_graphics_pipeline_library', 'VK_EXT_shader_module_identifier', 
#         'VK_EXT_extended_dynamic_state3'
#     )

#     dxvk_ext = {}
#     for e in vkext:
#         e = e.split(':')
#         dxvk_ext[e[0].strip()] = e[1].strip()
#     dext = ""
#     for e in dxvk2_ext_required:
#         dext += f"{e} : {dxvk_ext.get(e, 'not available')}\n"

#     # dxvk version
#     d3d9_version = get_pe_version(
#         Path(get_dist('GE-Proton8-6')) 
#         / 'files' / 'lib64' / 'wine' / 'dxvk' / 'd3d9.dll'
#     )
#     dxvk_version = get_dxvk_version(get_dist('GE-Proton8-6'))

#     return (
#         f"{vkloader}{deviceName}{deviceType}{driverName}{driverInfo}"
#         f"{conformanceVersion}\n{vklayer}\n{dext}\ndxvk version : {dxvk_version}\n" 
#         f"d3d9 dll version : {d3d9_version}"
#     )
