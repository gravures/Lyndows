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
import struct
import sys
from pathlib import Path, PureWindowsPath
from typing import IO, Any, Iterator, Sequence, Union

import chardet

from lyndows.system import unix_only

logger = logging.getLogger(__name__)
FilePath = Union[str, Path]  # Type Aliasing


# TODO: check this again...
def is_windows_path(path: FilePath) -> bool:
    return Path(path).drive != "" or issubclass(path.__class__, PureWindowsPath)


def is_flagexec(path: FilePath) -> bool:
    """Check if a file has the executable permission set.

    Checks if the path corresponds to an existing file
    and if this file has the executable permission set.

    Args:
        path (Union[str, Path]): The file path to check
        for executable permission.

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
    return bool(
        path.is_file()
        and path.suffix.upper()
        in (
            ".COM",
            ".EXE",
            ".BAT",
            ".CMD",
            ".VBS",
            ".VBE",
            ".JS",
            ".JSE",
            ".WSF",
            ".WSH",
            ".MSC",
        )
    )


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
        for line in f:
            detector.feed(line)
            if detector.done:
                break
    detector.close()
    return detector.result["encoding"] if detector.result else None


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
    if not Path(file).is_file():
        raise FileNotFoundError()

    # http://windowssdk.msdn.microsoft.com/en-us/library/ms646997.aspx
    sig = struct.pack("32s", "VS_VERSION_INFO".encode("utf-16-le"))
    version = None

    # NOTE: there is a pefile module available on pypi
    #      https://github.com/erocarrera/pefile

    # This pulls the whole file into memory,
    # so not very feasible for large binaries.
    with Path(file).open("rb") as f:
        data = f.read()
        offset = data.find(sig)
        if offset != -1:
            data = data[offset + 32 : offset + 32 + (13 * 4)]
            version_struct = struct.unpack("13I", data)
            ver_ms, ver_ls = version_struct[4], version_struct[5]
            version = "%d.%d.%d.%d" % (
                ver_ls & 0x0000FFFF,
                (ver_ms & 0xFFFF0000) >> 16,
                ver_ms & 0x0000FFFF,
                (ver_ls & 0xFFFF0000) >> 16,
            )
    return version


def assert_type(obj: Any, cls: type) -> Any:
    if not isinstance(obj, cls):
        raise ValueError(f"{obj} is not of type {cls}")
    return obj


def assert_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def assert_dir(path: Path) -> Path:
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")
    return path


def assert_library(root: Path, libname: str) -> list[Path]:
    assert_dir(root)
    try:
        libraries = list(root.glob(f"**/*{libname}*.so"))
    except IndexError as e:
        raise ValueError(f"No {libname} library found under {root}") from e
    else:
        return libraries


def assert_data_dir(library: Path) -> Path:
    libdir = assert_file(library).parent
    while libdir != Path("/"):
        if (libdir / "share").is_dir():
            return libdir / "share"
        libdir = libdir.parent
    raise ValueError(f"do not found data dir for library {library}")


def assert_windows_path(path: Path) -> Path:
    if not is_windows_path(path):
        raise ValueError(f"{path} is not a windows path")
    return path


def format_bytes(
    nbytes: int, unit: str | None = None, suffix: str = "b", space: bool = True
) -> str:
    """Format bytes size.

    Scale bytes to its proper byte format.
    e.g: 1253656678 => '1.17GB'

    Args:
        nbytes (int): bytes size to format.
        unit (str | None): unit to convert bytes,
        if None unit will be search for best fit.
        suffix (str): Letter added just after the
        main unit letter (Mb, Kb, etc).Defaults to "b".
        space (bool): add space before the unit letter.
        Defaults to True.

    Returns:
        str: formated string.
    """
    units = ["B", "K", "M", "G", "T", "P", "E", "Z"]
    factor = 1024
    space = " " if space else ""  # type: ignore

    if unit:
        if unit not in units:
            raise ValueError(f"unit {unit} shold be one of {units}")
        res = nbytes if unit == "B" else nbytes / factor ** (units.index(unit))
        return f"{res:.2f}{space}{unit}{suffix}"
    else:
        units[0] = ""
        for unit in units:
            if nbytes < factor:
                return f"{nbytes:.2f}{space}{unit}{suffix}"
            nbytes /= factor  # type: ignore
    return f"{nbytes:.2f}{space}Y{suffix}"


def unique(seq: Sequence[Any], lifo: bool = False) -> list:
    """Returns a list of unique items from seq.

    Generate a list of unique elements from the input Sequence.
    By default first element will be kept at their index removing
    further duplicate occurrences. Setting lifo to True will inverse
    this behavior.

    Args:
        iter (Sequence[Any]): The input Sequence.
        lifo (bool, optional): If True, return the unique elements
        in Last-In-First-Out order. Defaults to False.

    Returns:
        list: A new list containing only unique elements.
    """
    unique = []
    _lst = list(seq[::-1]) if lifo else list(seq)
    for v in _lst:
        if v not in unique:
            unique.append(v)
    return unique[::-1] if lifo else unique


class EnvMapping:
    __slots__ = ("_lock", "_protected", "_kwargs", "__dict__")
    __list_separator = {}

    def __init__(self, **kwargs) -> None:
        self._kwargs = kwargs
        self._protected = []
        self._lock = True

    def add_list_separator(self, attribute: str, separator: str) -> None:
        if not isinstance(separator, str) and len(separator) != 1:
            raise TypeError("Separator must be a single character")
        EnvMapping.__list_separator[attribute] = separator

    def get(self, key: str, default: Any = "") -> Any:
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

    def copy(self) -> EnvMapping:
        """Creates a deep copy of this object.

        Returns:
            EnvMapping: A new EnvMapping object that is a deep
            copy of the original object.
        """
        duply = self.__class__(**self._kwargs)
        for k, v in self.__dict__.items():
            duply.__dict__[k] = copy.copy(v)
        return duply

    def update(
        self, other: EnvMapping | dict[str, Any], clear: list[str] | None = None
    ) -> None:
        """Update this EnvMapping object.

        Update the EnvMapping object with the values from another
        EnvMapping object or a dictionary.

        Parameters:
            other (EnvMapping | dict[str, Any]): The object or dictionary
            containing the values to update the EnvMapping object with.
            clear (list[str], optional): A list of names to set as empty lists
            in the WineEnvMapping object. Defaults to an empty list.

        Raises:
            ValueError: If the 'empty' parameter is not a list.
        """
        clear = assert_type(clear, list) if clear is not None else []

        if isinstance(other, EnvMapping):
            other = other.__dict__
        for key, value in other.items():
            if key not in self._protected:
                if (key in clear) and (isinstance(self.__dict__[key], list)):
                    self.__dict__[key] = []
                self.__setattr__(key, value)

    def unset(self, name: str) -> None:
        """Unset an attribute.

        Unsets a given attribute `name` from the EnvMapping object.

        Parameters:
            name (str): The name of the attribute to unset.
        """
        if name not in self._protected:
            del self.__dict__[name]

    def list(self) -> list[str]:
        return list(self.__dict__.keys())

    def clear(self) -> None:
        self.__dict__.clear()

    def pop(self, name: str) -> Any:
        return self.__dict__.pop(name)

    def popitem(self) -> tuple[str, Any]:
        return self.__dict__.popitem()

    def setdefault(self, name: str, default: Any = None) -> Any:
        if name in self.__dict__:
            return self.__dict__[name]
        self.__setattr__(name, default)
        return default

    def __setattr__(self, name: str, value: Any) -> None:
        # __slots__ case
        for _cls in self.__class__.__mro__:
            if _cls is not object and name in _cls.__slots__:  # type: ignore
                object.__setattr__(self, name, value)
                return
        # protected attributes
        if name in self._protected and self._lock:
            raise AttributeError(
                f"{name} is a protected variable and can't be set by assignement."
            )
        # normal attributes
        elif isinstance(value, list):
            self._append_list(name, value)
        else:
            self.__dict__[name] = value

    def _append_list(self, key, values_list):
        if key in self.__dict__:
            self.__dict__[key] = unique(self.__dict__[key] + values_list)
        else:
            self.__dict__[key] = unique(values_list)

    def env_hook(self, env: dict) -> dict:
        """Called by the env property getter function.

        Does nothing by default. Subclasses can override this method.
        This method is called by the env property getter function
        just before beginning to return the environment variables.
        A working dictionnary is passed to this method, so overriding
        method could manipulate it before returning it..
        """
        return env

    @property
    def env(self) -> dict[str, str]:
        """Returns this EnvMapping as environment variables.

        Returns:
            dict[str, str]: A dictionary containing the environment
            variables.
        """
        hook = self.env_hook(dict(self.__dict__))
        _env = {}
        for k, v in hook.items():
            if isinstance(v, list):
                separator = EnvMapping.__list_separator.get(k, ":")
                _env[k] = separator.join([str(p) for p in v])
            elif isinstance(v, bool):
                _env[k] = str(int(v))
            elif not str(v) or v is None:
                continue
            else:
                _env[k] = str(v)
        return _env

    def dump(self, file: IO[str] = sys.stdout) -> None:
        """Dump the environment variables to a file.

        Args:
            file (IO[str], optional): The file to write the environment
            variables to. Defaults to sys.stdout.

        Returns:
            None: This function does not return anything.
        """
        dump = "".join(f"{k} = {v}\n" for k, v in self.env.items())
        print(dump, file)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __getitem__(self, key: str) -> Any:
        return self.__dict__[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.__setattr__(key, value)

    def __delitem__(self, key: str) -> None:
        self.unset(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.__dict__)

    def __contains__(self, key: str) -> bool:
        return key in self.__dict__

    def __bool__(self) -> bool:
        return any(self.__dict__.values())

    def __str__(self) -> str:
        return str(self.__dict__)

    def __or__(self, other: EnvMapping | dict[str, Any]) -> EnvMapping:
        res = self.copy()
        res.update(other)
        return res

    def __ior__(self, other: EnvMapping | dict[str, Any]) -> None:
        self.update(other)

    def __eq__(self, other: EnvMapping | dict[str, Any]) -> bool:
        other = other.__dict__ if isinstance(other, EnvMapping) else other
        return self.__dict__ == other

    def __ne__(self, other: EnvMapping | dict[str, Any]) -> bool:
        other = other.__dict__ if isinstance(other, EnvMapping) else other
        return self.__dict__ != other
