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
from pathlib import Path

from lyndows.util import (
    EnvMapping,
    FilePath,
    assert_data_dir,
    assert_dir,
    assert_file,
    assert_library,
    assert_type,
)

logger = logging.getLogger(__name__)


class SteamHelper(EnvMapping):
    __slots__ = ()

    def __init__(self, steambase: FilePath, gameid: int, winedist: FilePath):
        super().__init__(steambase=steambase, gameid=gameid)
        self.add_list_separator("VK_LOADER_LAYERS_ENABLE", ",")
        self.add_list_separator("VK_ADD_LAYER_PATH", ":")

        steambase = Path(steambase)

        assert_dir(steambase)
        assert_dir(steambase / "steamapps" / "compatdata" / str(gameid))

        winedist = Path(winedist)
        assert_dir(winedist)

        self.SteamGameId = gameid
        self.SteamAppId = gameid
        self.STEAM_COMPAT_CLIENT_INSTALL_PATH = steambase
        self.MEDIACONV_AUDIO_DUMP_FILE = (
            f"{steambase}/steamapps/shadercache/{gameid}/fozmediav1/audiov2.foz"
        )
        self.MEDIACONV_AUDIO_TRANSCODED_FILE = (
            f"{steambase}/steamapps/shadercache/{gameid}/transcoded_audio.foz"
        )
        self.MEDIACONV_VIDEO_DUMP_FILE = (
            f"{steambase}/steamapps/shadercache/{gameid}/fozmediav1/video.foz"
        )
        self.MEDIACONV_VIDEO_TRANSCODED_FILE = (
            f"{steambase}/steamapps/shadercache/{gameid}/transcoded_video.foz"
        )
        self.LD_LIBRARY_PATH = [
            "/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu",
            "/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu/aliases",
            "/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu",
            "/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu/aliases",
        ]
        self.WINEDLLOVERRIDES = ["steam.exe=b"]

        # gstreamer-1.0
        self.WINE_GST_REGISTRY_DIR = list(
            (steambase / "steamapps" / "compatdata" / str(gameid)).glob(
                "**/gstreamer-1.0"
            )
        )[0]
        self.GST_PLUGIN_SYSTEM_PATH_1_0 = list(winedist.glob("**/gstreamer-1.0"))

        # steam vulkan implicit layers
        self.XDG_DATA_DIRS = [Path.home() / ".local" / "share"]

        # share = self.assert_dir(Path.home() / '.local' / 'share')
        # self.VK_ADD_LAYER_PATH = [
        #     self.assert_dir(share / 'vulkan' / 'implicit_layer.d')
        # ]
        # self.VK_LOADER_LAYERS_ENABLE = [
        #     'VK_LAYER_VALVE_steam_fossilize_64',
        #     'VK_LAYER_VALVE_steam_overlay_64'
        # ]


class SystemHelper(EnvMapping):
    __slots__ = ()

    def __init__(
        self,
        esync: bool = True,
        fsync: bool = False,
        large_adress_aware: bool = True,
        term: str = "xterm",
    ):
        super().__init__(
            esync=esync, fsync=fsync, large_adress_aware=large_adress_aware, term=term
        )
        self.ESYNC = esync
        self.FSYNC = fsync
        self.LARGE_ADDRESS_AWARE = large_adress_aware
        self.XTERM = term
        self.XDG_DATA_DIRS = os.environ.get("XDG_DATA_DIRS", "").split(":")
        self.XDG_RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR")
        self.HOME = os.environ.get("HOME")


class VkBasaltHelper(EnvMapping):
    __slots__ = ()

    def __init__(self, vkbasalt: FilePath, config_file: FilePath | None = None):
        super().__init__(vkbasalt=vkbasalt)
        vkbasaltlibs = assert_library(Path(vkbasalt), "libvkbasalt")
        self.LD_LIBRARY_PATH = [lib.parent for lib in vkbasaltlibs]

        # for vulkan implicit layers
        self.XDG_DATA_DIRS = [assert_data_dir(vkbasaltlibs[0])]
        self.ENABLE_VKBASALT = 1

        # share = self.assert_data_dir(vkbasalt[0])
        # self.VK_ADD_LAYER_PATH = [
        #     self.assert_dir(share / 'vulkan' / 'implicit_layer.d')
        # ]
        # self.VK_LOADER_LAYERS_ENABLE = ['VK_LAYER_VKBASALT_post_processing']

        if config_file:
            assert_file(Path(config_file))
            self.VKBASALT_CONFIG_FILE = config_file


class LibStrangleHelper(EnvMapping):
    __slots__ = ()

    def __init__(self, libstrangle: FilePath):
        super().__init__(libstrangle=libstrangle)
        libstranglelibs = assert_library(Path(libstrangle), "libstrangle")
        self.LD_LIBRARY_PATH = [lib.parent for lib in libstranglelibs]

        # for vulkan implicit layers
        self.XDG_DATA_DIRS = [assert_data_dir(libstranglelibs[0])]
        self.ENABLE_VK_LAYER_TORKEL104_libstrangle = 1

        # share = self.assert_data_dir(libstrangle[0])
        # self.VK_ADD_LAYER_PATH = [
        #     self.assert_dir(share / 'vulkan' / 'implicit_layer.d')
        # ]
        # self.VK_LOADER_LAYERS_ENABLE = ['VK_LAYER_TORKEL104_libstrangle']


class MesaHelper(EnvMapping):
    __slots__ = ()

    def __init__(
        self,
        mesalib: FilePath | None = None,
        libdrm: FilePath | None = None,
        vkdriver: list | None = None,
    ) -> None:
        super().__init__(mesalib=mesalib, libdrm=libdrm, vkdriver=vkdriver)

        if mesalib:
            mesalibs = assert_library(Path(mesalib), "mesa")
            self.LD_LIBRARY_PATH = [lib.parent for lib in mesalibs]
            self.EGL_DRIVERS_PATH = self.LD_LIBRARY_PATH
            self.LIBGL_DRIVERS_PATH = self.LD_LIBRARY_PATH
            # for graphic pipeline vulkan extension
            self.ANV_GPL = "true"

            # for vulkan implicit and explicit layers
            self.XDG_DATA_DIRS = [assert_data_dir(mesalibs[0])]

            # share = self.assert_data_dir(mesalib[0])
            # self.VK_ADD_LAYER_PATH = [
            #     self.assert_dir(share / 'vulkan' / 'explicit_layer.d'),
            #     self.assert_dir(share / 'vulkan' / 'implicit_layer.d')
            # ]
            # self.VK_LOADER_LAYERS_ENABLE = [
            #     'VK_LAYER_MESA_device_select', 'VK_LAYER_MESA_overlay'
            # ]

        if libdrm:
            libdrm = Path(libdrm)
            libdrms = assert_library(Path(libdrm), "libdrm")
            self.LD_LIBRARY_PATH = [lib.parent for lib in libdrms]

        if vkdriver and mesalib:
            assert_type(vkdriver, list)
            # The VK_ICD_FILENAMES environment variable is a list
            # of Driver Manifest files, containing the full path
            # to the driver JSON Manifest file.
            # VK_ICD_FILENAMES will only contain a full pathname
            # to one info file for a single driver.
            for driver in vkdriver:
                if icd := list(Path(mesalib).glob(f"**/{driver}_icd.*.json")):
                    self.VK_ICD_FILENAMES = icd
                else:
                    raise ValueError(f"No icd file found for driver {driver}")


def get_dxvk_version(dist: FilePath) -> str:
    version = Path(dist) / "files" / "lib64" / "wine" / "dxvk" / "version"
    with version.open("rU") as f:
        return f.readline().split("dxvk")[1].strip()[2:-1]


# class DXVK_Helper(Context):
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
