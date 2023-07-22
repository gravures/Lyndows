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
import os
import subprocess
import shlex
from pathlib import Path
import logging

from lyndows import wine

logger = logging.getLogger(__name__)


#
# External process handling
#
class EProcess:
    def __init__(self, program, *args, env={}):
        if isinstance(program, wine.Executable):
            self.program = program
        else:
            self.program = wine.Executable(program)
        self.set_arguments(*args)
        self.env = env
        self._process = None

    def set_arguments(self, *args):
        self._arguments = []
        self.add_arguments(*args)

    def add_arguments(self, *args):
        for tup in args:
            if not (isinstance(tup, tuple) and len(tup) < 3):
                raise TypeError(f"args should be tuples('opt', [<value>]):\n {args}")
            tmp = []
            for e in tup:
                if isinstance(e, Path):
                    e = self.program.get_path(e)
                tmp.append(str(e))
            self._arguments += tmp

    def get_arguments(self):
        return self._arguments
    
    def compile_args(self):
        return shlex.join(self.program.get_command() + self._arguments)

    def run(self, isolation=False, text=True, **kwargs):
        if self._process is not None:
            raise RuntimeError("This EProcess is already running.")
        
        args = self.compile_args()
        for arg in ('args', 'env', 'text', 'shell'):
            kwargs.pop(arg, None)

        _env = dict()
        if not isolation:
            _env |= os.environ
        _env |= self.program.get_env()
        _env |= self.env

        codec = "UTF-8" if text else None

        logger.debug("ENVIRON: %s\n" % _env)
        logger.debug("E-PROCESS: %s\n" % str(args))

        cp = subprocess.run(
            args,
            env=_env,
            capture_output=True,
            text=text,
            encoding=codec,
            check=False,
            shell=True,
            **kwargs
        )
        return cp
    
    def popen(self, isolation=False, text=True, **kwargs):
        if self._process is not None:
            raise RuntimeError("This EProcess is already running.")
        
        args = self.program.get_command() + self._arguments
        for arg in ('args', 'env', 'text', 'shell'):
            kwargs.pop(arg, None)

        _env = dict()
        if not isolation:
            _env |= os.environ
        _env |= self.program.get_env()
        _env |= self.env

        codec = "UTF-8" if text else None

        self._process = subprocess.Popen(
            args, 
            env=_env,
            text=text,
            encoding=codec,
            shell=False,
            **kwargs
        )

    def wait(self, timeout=None):
        if self._process is not None:
            return self._process.wait(timeout)

    def poll(self):
        if self._process is not None:
            return self._process.poll()
        
    def terminate(self):
        if self._process is not None:
            self._process.terminate()
        if self._process.poll() is None:
            self._process = None
        
    def kill(self):
        if self._process is not None:
            self._process.kill()
        if self._process.poll() is None:
            self._process = None