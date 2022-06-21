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
Base class and decorator for host paths.
"""

import os
import functools
import inspect
import glob

from collections import (
    UserList,
)

from collections.abc import (
    MappingView,
)

_SequenceTypes = (list, tuple, UserList, MappingView)

class HostPathsException(Exception):
    pass

class HostPathsError(HostPathsException):
    pass

def _flatten_string_or_list(string_or_list, strip=True, filter=True, _count=None, _scalar=True):
    if _count is None:
        _count = [0]
    errors = []
    gather = []
    if isinstance(string_or_list, str):
        elem = string_or_list.strip() if strip else string_or_list
        if elem or not filter:
            gather.append(elem)
        _count[0] += 1
        return errors, gather
    elif isinstance(string_or_list, _SequenceTypes):
        for elem in string_or_list:
            rerrors, rgather = _flatten_string_or_list(elem, strip=strip, filter=filter, _count=_count, _scalar=False)
            errors.extend(rerrors)
            gather.extend(rgather)
        return errors, gather
    if _scalar:
        errstr = 'TypeError: expected str instance, found {}'.format(type(string_or_list).__name__)
    else:
        errstr = 'TypeError: sequence item {}: expected str instance, found {}'.format(_count[0], type(string_or_list).__name__)
    errors.append(errstr)
    gather.append(string_or_list)
    _count[0] += 1
    return errors, gather

def _flatten(string_or_list):
    path_errs, path_list = _flatten_string_or_list(string_or_list)
    if path_errs:
        errmsg = 'Values must strings or sequences of strings:\nvalue: {}\n{}'.format(string_or_list, '\n'.join(path_errs))
        raise HostPathsError(errmsg)
    return path_list

def _prepare_arguments(path_suffix, file_name, filter_regex):

    if path_suffix:
        path_suffix = path_suffix.strip()
        if not path_suffix:
            path_suffix = None

    if file_name:
        file_name = file_name.strip()
        if not file_name:
            file_name = None

    if file_name:
        # file specified: must be a file
        check_func = os.path.isfile
    else:
        # file not specified: must be a directory
        check_func = os.path.isdir

    if not filter_regex:
        match_func = None
    else:
        if isinstance(filter_regex, str):
            match_func = re.compile(filter_regex, re.IGNORECASE).match
        else:
            match_fn = getattr(filter_regex, 'match', None)
            match_func = match_fn if match_fn and callable(match_fn) else None

    return (path_suffix, file_name, check_func, match_func)

def _process_pathlist(path_list, path_suffix, file_name, check_func, match_func, find_all):

    result = []

    seen_path = set()

    for p in path_list:

        p = p.strip()
        if not p:
            continue

        if path_suffix:
            p = os.path.join(p, path_suffix)

        if file_name:
            p = os.path.join(p, file_name)

        p = os.path.expanduser(p)
        p = os.path.expandvars(p)
        p = os.path.realpath(p)
        p = os.path.normcase(p)

        if p in seen_path:
            continue

        seen_path.add(p)

        for path in glob.glob(p):

            if not check_func(path):
                continue

            if match_func and not match_func(path):
                continue

            if path != p:

                path = os.path.realpath(path)
                path = os.path.normcase(path)

                if path in seen_path:
                    continue

                seen_path.add(path)

            result.append(path)

            if not find_all:
                return result

    return result

def _group_list_paths(group_list, path_suffix, file_name, check_func, match_func, find_all):

    result = []

    seen_path = set()

    for path_list in group_list:

        rval = _process_pathlist(path_list, path_suffix, file_name, check_func, match_func, find_all)
        if not rval:
            continue

        if not find_all:
            return rval

        for path in rval:
            if path in seen_path:
                continue
            seen_path.add(path)
            result.append(path)

    return result

def _group_list_invoke(group_list, path_suffix, file_name, filter_regex, find_all):

    path_suffix, file_name, check_func, match_func = _prepare_arguments(path_suffix, file_name, filter_regex)

    result = _group_list_paths(group_list, path_suffix, file_name, check_func, match_func, find_all)

    return result

def _path_group_pop(group_list, front=True):
    if front:
        path_list = group_list.pop(0)
    else:
        path_list = group_list.pop()
    return path_list

def path_group_push(group_list, string_or_list, front=True):
    path_list = _flatten(string_or_list)
    if front:
        group_list.insert(0, path_list)
    else:
        group_list.append(path_list)

def get_path_group_paths(group_list, path_suffix=None, file_name=None, filter_regex=None, find_all=True):
    result = _group_list_invoke(group_list, path_suffix, file_name, filter_regex, find_all)
    return result

