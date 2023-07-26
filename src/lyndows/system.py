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
import sys
import time
from typing import Callable

import psutil

logger = logging.getLogger(__name__)


def on_windows() -> bool:
    """Check if the current platform is Windows.

    Returns:
        bool: True if the current platform is Windows, False otherwise.
    """
    return sys.platform in ["win32", "cygwin"]


def unix_only(func: Callable) -> Callable:
    """Decorator to restrict function to run only on Unix-like platforms.

    This decorator checks if the function is being executed on a Windows and raises a
    'NotImplementedError', indicating that the method is not available on Windows.

    Args:
        func (Callable): The function to be decorated.

    Returns:
        Callable: The decorated function.

    Raises:
        NotImplementedError: If the decorated function is called on Windows.

    Example:
        >>> @unix_only
        ... def my_unix_function():
        ...     print("This function can only run on Unix-like platforms.")

        >>> my_unix_function()
        This function can only run on Unix-like platforms.

        # If the script is running on Windows, calling the function will raise an error
        NotImplementedError: Method not available on Windows platform
    """
    def inner(*args, **kwargs):
        if on_windows():
            raise NotImplementedError("Method not available on Windows platform")
        return func(*args, **kwargs)
    return inner


#TODO: extend this, check parent, cmdline, pid, etc...
def wait_proc(name, retry=100, idle=0.3):
    i = 0
    process = None
    while True:        
        for p in psutil.process_iter():
            if "cmd.exe" == p.name().lower():
                process = p
                break
        if process:
            break    
        else:
            if i > retry:
                break
            time.sleep(idle)
            i += 1
    return process
