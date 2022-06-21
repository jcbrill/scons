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
MinGW default paths.
"""

import os

from .hostpaths import (
    path_group_push,
    get_path_group_paths,
)

_MINGW_GROUP_LIST = []

_MINGW_DEFAULT_PATHS = [
    r'c:\MinGW\bin',
    r'C:\cygwin64\bin',
    r'C:\msys64',
    r'C:\msys64\mingw64\bin',
    r'C:\cygwin\bin',
    r'C:\msys',
    r'C:\ProgramData\chocolatey\lib\mingw\tools\install\mingw64\bin',
    # One example of default mingw install paths is:
    # C:\mingw-w64\x86_64-6.3.0-posix-seh-rt_v5-rev2\mingw64\bin
    # Use glob'ing to find such and add to mingw_base_paths
    r'C:\mingw-w64\*\mingw64\bin',
]

path_group_push(_MINGW_GROUP_LIST, _MINGW_DEFAULT_PATHS)

def push_mingw_paths(string_or_list, front=True):
    path_group_push(_MINGW_GROUP_LIST, string_or_list, front=front)

def get_mingw_bin_paths():
    bin_paths = get_path_group_paths(_MINGW_GROUP_LIST, file_name='mingw32-make.exe', find_all=True)
    bin_paths = [os.path.dirname(p) for p in bin_paths]
    return bin_paths

