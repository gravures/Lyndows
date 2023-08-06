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
import threading
import time

import psutil
import PySimpleGUI as sg

from lyndows.subprocess import Launcher


def worker(window: sg.Window, name, freq):
    print(f"Starting thread 1 - {name} that runs every {freq} ms")
    i = 0
    while True:
        time.sleep(freq / 1000)
        window.write_event_value("-ML-", f"My counter is {i}")
        i += 1


class MonitorWidget:
    def __init__(self, process: psutil.Process):
        if not isinstance(process, psutil.Process):
            raise TypeError("process must be an instance of psutil.Process")

    def _layout(self) -> list:
        return [
            [sg.Text("Multithreaded Window Example")],
            [sg.Text("", size=(15, 1), key="-OUTPUT-")],
            [sg.Multiline(size=(40, 26), key="-ML-", autoscroll=True)],
            [sg.Button("Exit")],
        ]

    def _get_window(self) -> sg.Window:
        return sg.Window("Multithreaded Window", self._layout(), finalize=True)

    def _get_monitoring_thread(self, window) -> threading.Thread:
        return threading.Thread(
            target=worker, args=(window, "monitor", 500), daemon=True
        )

    def run(self):
        window = self._get_window()
        self._get_monitoring_thread(window).start()
        sg.cprint_set_output_destination(window, "-ML-")
        colors = {"-ML-": ("white", "red")}

        while True:
            event, values = window.read()  # type: ignore
            if event in (sg.WIN_CLOSED, "Exit"):
                break
            sg.cprint(event, values[event], c=colors[event])

        window.close()


if __name__ == "__main__":
    launcher = Launcher(None, "/usr/bin/vkcube")
    # MonitorWidget(launcher.process)
