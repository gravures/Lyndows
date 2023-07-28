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

from Xlib.display import Display

from lyndows.subprocess import command


def get_display_server():
    # echo $XDG_SESSION_TYPE
    # echo $DISPLAY
    # echo $WAYLAND_DISPLAY
    # seesion = loginctl
    return command("loginctl", "show-session", "3", "-p", "Type")


def get_screen_name():
    screen = Display().screen()
    return screen.name


def get_display_name():
    return Display().get_display_name()


def get_display_res():
    screen = Display().screen()
    return (screen.width_in_pixels, screen.height_in_pixels)


def set_display_res(xres: int, yres: int) -> None:
    command("xrandr", "-s", f"{xres}x{yres}")


def set_display_scale(scale: int) -> None:
    # xrandr --output "<output>" --set "scaling mode" "<scaling mode>"
    out = Display().get_display_name()
    out = "eDP-1"
    command(
        "xrandr",
        "--output",
        out,
        "--scale",
        f"{scale}x{scale}",
    )
