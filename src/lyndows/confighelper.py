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
import os
from pathlib import Path
from typing import Any

from lyndows.fileutil import FilePath


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
        
    def dump(self) -> str:
        """Generates a string representation of the environment variables.

        Returns:
            str: A string containing key-value pairs of the context's environment.
        """
        dump = ""
        for k, v in self.env.items():
            dump += f"{k} = {v}\n"
        return dump
    
    def assert_file(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
                                    
    def assert_dir(self, path: Path) -> None:
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {path}")
        
    def assert_list(self, obj: Any) -> None:
        if not isinstance(obj, list):
            raise ValueError(f"{obj} is not a list")


class MesaHelper(BaseHelper):
    __slots__ = ()

    def __init__(
        self, 
        mesalib: FilePath=None, 
        libdrm: FilePath=None,
        vkdriver: list=None
    ) -> None:
        super().__init__()

        _mesalib = Path(mesalib)

        if mesalib:
            mesalib = _mesalib
            self.assert_dir(mesalib)
            try:
                mesalib = list(mesalib.glob("**/*mesa*.so"))[0].parent
            except IndexError:
                raise ValueError(f"No mesa library found in prefix {mesalib}")
            else:
                self.LD_LIBRARY_PATH = [mesalib]
                self.EGL_DRIVERS_PATH = mesalib
                self.LIBGL_DRIVERS_PATH = mesalib
                # for vulkan implicit and explicit layers
                self.XDG_DATA_DIRS = os.environ.get('XDG_DATA_DIRS').split(':')
                self.XDG_DATA_DIRS = [mesalib / 'share']
            
        if libdrm:
            libdrm = Path(libdrm) 
            self.assert_dir(libdrm)
            try:
                libdrm = list(libdrm.glob("**/*libdrm*.so"))[0].parent
            except IndexError:
                raise ValueError(f"No libdrm library found in prefix {libdrm}")
            else:
                self.LD_LIBRARY_PATH = [libdrm]
            
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

        # general variables
        self.MESA_NO_ERROR = 1
        self.MESA_DEBUG = 'silent'
        self.INTEL_PRECISE_TRIG = 0



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