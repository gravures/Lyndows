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
import os
import struct
from pathlib import Path, PureWindowsPath
from typing import Union

import chardet

from lyndows.system import unix_only

logger = logging.getLogger(__name__)

FilePath = Union[str, Path]


#TODO: check this again...
def is_windows_path(path: FilePath) -> bool:
    return Path(path).drive or issubclass(path.__class__, PureWindowsPath)


def is_flagexec(path: FilePath) -> bool:
    """Check if a file at the given path has the executable permission set.

    Checks if the path corresponds to an existing file and if it has the
    executable permission set.

    Args:
        path (Union[str, Path]): The file path to check for executable permission.

    Returns:
        bool: True if the file has the executable permission, False otherwise.
              If the file does not exist or is not a regular file, the function 
              returns False.
    """
    path = Path(path).resolve()
    return path.is_file() and os.access(path, os.X_OK)


def is_win32exec(path: FilePath) -> bool:
    """Check if a file has an extension associated with executable files on Windows.

    The function checks if the file has a suffix (extension) that matches any of the
    Windows executable extensions commonly found on Windows platforms. The extensions 
    considered as Windows executable files are: 'COM', 'EXE', 'BAT', 'CMD', 'VBS', 
    'VBE', 'JS', 'JSE', 'WSF', 'WSH', 'MSC'. The comparison of the suffix is 
    case-insensitive (capitalized) to handle different cases.

    Args:
        path (Union[str, Path]): The file path to check for the Windows 
        executable extension.

    Returns:
        bool: True if the file has a Windows executable extension, False otherwise.
              If the file does not exist or is not a regular file, the function 
              returns False
    """
    path = Path(path).resolve()
    if path.is_file():
        if path.suffix.capitalize() in (
            'COM', 'EXE', 'BAT', 'CMD', 'VBS', 'VBE', 
            'JS', 'JSE', 'WSF', 'WSH', 'MSC'
        ):
            return True
    return False


def open_guess_encoding(path: FilePath) -> str | None:
    """Open a file and guess its character encoding.

    Reads a file from the specified path and tries to guess 
    its character encoding.

    Args:
        path (FilePath): The path to the file to be analyzed.str

    Returns:
        str or None: The guessed character encoding as a string if successful,
        None if the encoding cannot be determined.

    Example:
        >>> file_path = "/path/to/file.txt"
        >>> open_guess_encoding(file_path)
        'utf-8'

    Note:
        - The function assumes the file is in binary mode ("rb") for detection.
        - For larger files, the function reads the content line by line to minimize 
          the memory usage.
        - The 'get_native_path' function is called to convert the path 
          to a native format.
          See 'get_native_path' function docstring for more details.
    """
    detector = chardet.universaldetector.UniversalDetector()
    with open(path, "rb") as f:
        for line in f.readlines():
            detector.feed(line)
            if detector.done:
                break
    detector.close()
    return detector.result["encoding"]


@unix_only
def mount_point(path: FilePath) -> Path:
    """Find the mount point (root) of the filesystem containing the given path.

    Takes a file path and traverses up the directory tree until it finds 
    the mount point (root) of the filesystem containing the path.

    Args:
        path (Union[str, Path]): The file path for which to find the mount point.

    Returns:
        Path: The mount point (root) of the filesystem containing the given path.

    Raises:
        ValueError: If the input path is a Windows filesystem path 
        (for Windows-specific paths).
        NotImplementedError: If called from Winodws platform.

    Example:
        >>> mount_point("/home/user/documents/file.txt")
        PosixPath('/')

        >>> mount_point("/mnt/data/photos/image.jpg")
        PosixPath('/mnt')

        >>> mount_point("C:\\projects\\code\\script.py")
        WindowsPath('C:/')
    """
    path = Path(path).expanduser().absolute()
    if is_windows_path(path):
        raise ValueError("path should not be a Windows filesystem path")
    while not path.is_mount():
        path = path.parent
    return path
        

def get_pe_version(file: FilePath) -> str | None:
    """Extract the version information from a Portable Executable (PE) file.

    Reads the specified Portable Executable (PE) file and extracts its version 
    information using the Windows-specific 'VS_VERSION_INFO' structure. 
    The function returns the version information as a string in the format 
    'Major.Minor.Patch.Build' if available.

    Args:
        file (str): The path to the Portable Executable (PE) file.

    Returns:
        str or None: The version information of the PE file if available, 
        None otherwise.

    Raises:
        FileNotFoundError: If the input 'file' does not exist or is not a file.

    Example:
        >>> pe_file_path = "C:\\path\\to\\app.exe"
        >>> get_pe_version(pe_file_path)
        '1.2.3.4'

    Note:
        - The function reads the entire file into memory, so it may not be suitable 
        for large binaries.
        - The function returns None if the 'VS_VERSION_INFO' structure is not found 
        or if an error occurs.
    """
    if Path(file).is_file():
        # http://windowssdk.msdn.microsoft.com/en-us/library/ms646997.aspx
        sig = struct.pack("32s", u"VS_VERSION_INFO".encode("utf-16-le"))
        version = None

        #NOTE: there is a pefile module available on pypi
        #      https://github.com/erocarrera/pefile

        # This pulls the whole file into memory, 
        # so not very feasible for large binaries.
        with Path(file).open('rb') as f:
            data = f.read()
            offset = data.find(sig)
            if offset != -1:
                data = data[offset + 32 : offset + 32 + (13*4)]
                version_struct = struct.unpack("13I", data)
                ver_ms, ver_ls = version_struct[4], version_struct[5]
                version = "%d.%d.%d.%d" % (
                    ver_ls & 0x0000ffff, (ver_ms & 0xffff0000) >> 16,
                    ver_ms & 0x0000ffff, (ver_ls & 0xffff0000) >> 16
                )
    else:
        raise FileNotFoundError()
    return version