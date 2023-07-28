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
import time
from collections import namedtuple

import psutil

from lyndows.util import format_bytes

logger = logging.getLogger(__name__)


def cpucount():
    return psutil.cpu_count(True)


def hyper_threading():
    return psutil.cpu_count(True) > psutil.cpu_count(logical=False)


def cpuloads() -> tuple[float, float, float]:
    Loads = namedtuple("cpu_loads", ["last_min", "last_5min", "last_15min"])
    loads = [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()]
    return Loads(loads[0], loads[1], loads[2])


def cpufreq():
    freqs = psutil.cpu_freq(True)
    Freqs = namedtuple("cpu_freqs", ["percent"])
    return [
        Freqs(int((stat.current - stat.min) / (stat.max - stat.min) * 100))  # type: ignore
        for stat in freqs
    ]


def memory():
    mem = psutil.virtual_memory()
    sysmem = namedtuple("sys_memory", ["total", "used", "free", "available"])
    return sysmem(
        format_bytes(mem.total),
        format_bytes(mem.used),
        format_bytes(mem.free),
        format_bytes(mem.available),
    )


def swap_mem():
    return psutil.swap_memory().percent


def temperatures() -> tuple[tuple[str, float, str]]:
    stats = psutil.sensors_temperatures()
    Stat = namedtuple("sys_temperature", ["unit", "temp", "status"])
    export = ("coretemp", "acpitz", "nvme")
    result = []

    def get_status(current: float, high: float | None, critical: float | None) -> str:
        if (high is None) or (critical is None):
            return "unknown"
        if current >= critical:
            return "critical"
        return "high" if current >= high else "normal"

    for name, stat in stats.items():
        if name in export:
            result.append(
                Stat(
                    name,
                    stat[0].current,
                    get_status(stat[0].current, stat[0].high, stat[0].critical),
                )
            )
    return tuple(result)


def get_process_with_pid(pid: int) -> psutil.Process | None:
    return psutil.Process(pid) if psutil.pid_exists(pid) else None


def get_process_by_name(name: str) -> list(dict[str, str]):  # type: ignore
    return [
        p.info  # type: ignore
        for p in psutil.process_iter(["pid", "name", "username"])
        if name.lower() == p.name().lower()
    ]


# TODO: extend this, check parent, cmdline, pid, etc...
def wait_proc(name: str, retry: int = 100, idle: float = 0.3) -> psutil.Process | None:
    i = 0
    process = None
    while True:
        for p in psutil.process_iter():
            if p.name().lower() == "cmd.exe":
                process = p
                break
        if process:
            break
        if i > retry:
            break
        time.sleep(idle)
        i += 1
    return process
