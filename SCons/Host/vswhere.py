# MIT License
#
# Copyright The SCons Foundation
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
VSWhere default paths.
"""

import os

from .hostpaths import (
    path_group_push,
    get_path_group_paths,
)

_VSWHERE_GROUP_LIST = []

# For bug 3333: support default location of vswhere for both
# 64 and 32 bit windows installs.
# For bug 3542: also accommodate not being on C: drive.

_VSWHERE_DEFAULT_PATHS = [
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft Visual Studio\Installer"),
    os.path.expandvars(r"%ChocolateyInstall%\bin"),
]

path_group_push(_VSWHERE_GROUP_LIST, _VSWHERE_DEFAULT_PATHS)

def push_vswhere_paths(string_or_list, front=True):
    path_group_push(_VSWHERE_GROUP_LIST, string_or_list, front=front)

def get_vswhere_exe_paths():
    exe_paths = get_path_group_paths(_VSWHERE_GROUP_LIST, file_name='vswhere.exe', find_all=True)
    return exe_paths

