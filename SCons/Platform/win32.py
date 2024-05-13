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

"""Platform-specific initialization for Win32 systems.

There normally shouldn't be any need to import this module directly.  It
will usually be imported through the generic SCons.Platform.Platform()
selection method.
"""

import os
import os.path
import platform
import sys
import tempfile

from collections import namedtuple
import re

from SCons.Platform.posix import exitvalmap
from SCons.Platform import TempFileMunge
from SCons.Platform.virtualenv import ImportVirtualenv
from SCons.Platform.virtualenv import ignore_virtualenv, enable_virtualenv
import SCons.Util

CHOCO_DEFAULT_PATH = [
    r'C:\ProgramData\chocolatey\bin'
]

if False:
    # Now swap out shutil.filecopy and filecopy2 for win32 api native CopyFile
    try:
        from ctypes import windll
        import shutil

        CopyFile = windll.kernel32.CopyFileA
        SetFileTime = windll.kernel32.SetFileTime

        _shutil_copy = shutil.copy
        _shutil_copy2 = shutil.copy2

        shutil.copy2 = CopyFile

        def win_api_copyfile(src,dst) -> None:
            CopyFile(src,dst)
            os.utime(dst)

        shutil.copy = win_api_copyfile

    except AttributeError:
        parallel_msg = \
            "Couldn't override shutil.copy or shutil.copy2 falling back to shutil defaults"







try:
    import threading
    spawn_lock = threading.Lock()

    # This locked version of spawnve works around a Windows
    # MSVCRT bug, because its spawnve is not thread-safe.
    # Without this, python can randomly crash while using -jN.
    # See the python bug at https://github.com/python/cpython/issues/50725
    # and SCons issue at https://github.com/SCons/scons/issues/2449
    def spawnve(mode, file, args, env):
        spawn_lock.acquire()
        try:
            if mode == os.P_WAIT:
                ret = os.spawnve(os.P_NOWAIT, file, args, env)
            else:
                ret = os.spawnve(mode, file, args, env)
        finally:
            spawn_lock.release()
        if mode == os.P_WAIT:
            pid, status = os.waitpid(ret, 0)
            ret = status >> 8
        return ret
except ImportError:
    # Use the unsafe method of spawnve.
    # Please, don't try to optimize this try-except block
    # away by assuming that the threading module is always present.
    # In the test test/option-j.py we intentionally call SCons with
    # a fake threading.py that raises an import exception right away,
    # simulating a non-existent package.
    def spawnve(mode, file, args, env):
        return os.spawnve(mode, file, args, env)

# The upshot of all this is that, if you are using Python 1.5.2,
# you had better have cmd or command.com in your PATH when you run
# scons.


def piped_spawn(sh, escape, cmd, args, env, stdout, stderr):
    # There is no direct way to do that in python. What we do
    # here should work for most cases:
    #   In case stdout (stderr) is not redirected to a file,
    #   we redirect it into a temporary file tmpFileStdout
    #   (tmpFileStderr) and copy the contents of this file
    #   to stdout (stderr) given in the argument
    # Note that because this will paste shell redirection syntax
    # into the cmdline, we have to call a shell to run the command,
    # even though that's a bit of a performance hit.
    if not sh:
        sys.stderr.write("scons: Could not find command interpreter, is it in your PATH?\n")
        return 127

    # one temporary file for stdout and stderr
    tmpFileStdout, tmpFileStdoutName = tempfile.mkstemp(text=True)
    os.close(tmpFileStdout)  # don't need open until the subproc is done
    tmpFileStderr, tmpFileStderrName = tempfile.mkstemp(text=True)
    os.close(tmpFileStderr)

    # check if output is redirected
    stdoutRedirected = False
    stderrRedirected = False
    for arg in args:
        # are there more possibilities to redirect stdout ?
        if arg.find(">", 0, 1) != -1 or arg.find("1>", 0, 2) != -1:
            stdoutRedirected = True
        # are there more possibilities to redirect stderr ?
        if arg.find("2>", 0, 2) != -1:
            stderrRedirected = True

    # redirect output of non-redirected streams to our tempfiles
    if not stdoutRedirected:
        args.append(">" + tmpFileStdoutName)
    if not stderrRedirected:
        args.append("2>" + tmpFileStderrName)

    # actually do the spawn
    try:
        args = [sh, '/C', escape(' '.join(args))]
        ret = spawnve(os.P_WAIT, sh, args, env)
    except OSError as e:
        # catch any error
        try:
            ret = exitvalmap[e.errno]
        except KeyError:
            sys.stderr.write("scons: unknown OSError exception code %d - %s: %s\n" % (e.errno, cmd, e.strerror))
        if stderr is not None:
            stderr.write("scons: %s: %s\n" % (cmd, e.strerror))

    # copy child output from tempfiles to our streams
    # and do clean up stuff
    if stdout is not None and not stdoutRedirected:
        try:
            with open(tmpFileStdoutName, "rb") as tmpFileStdout:
                output = tmpFileStdout.read()
                stdout.write(output.decode(stdout.encoding, "replace"))
            os.remove(tmpFileStdoutName)
        except OSError:
            pass

    if stderr is not None and not stderrRedirected:
        try:
            with open(tmpFileStderrName, "rb") as tmpFileStderr:
                errors = tmpFileStderr.read()
                stderr.write(errors.decode(stderr.encoding, "replace"))
            os.remove(tmpFileStderrName)
        except OSError:
            pass

    return ret


def exec_spawn(l, env):
    try:
        result = spawnve(os.P_WAIT, l[0], l, env)
    except OSError as e:
        try:
            result = exitvalmap[e.errno]
            sys.stderr.write("scons: %s: %s\n" % (l[0], e.strerror))
        except KeyError:
            result = 127
            if len(l) > 2:
                if len(l[2]) < 1000:
                    command = ' '.join(l[0:3])
                else:
                    command = l[0]
            else:
                command = l[0]
            sys.stderr.write("scons: unknown OSError exception code %d - '%s': %s\n" % (e.errno, command, e.strerror))
    return result

# configuration for msvc special handling

class _MSVCRewrite:

    #  rewrite  filter  action
    #  -------  ------  ----------------------------------
    #  True     False   rewrite streams
    #  True     True    filter records and rewrite streams
    #  False    False   skip processing
    #  False    True    skip processing

    _msvc_common_environ = [
        'filter_enabled',
        'filter_debug',
        'write_banner_full',
        'write_banner_stderr',
        'write_diagnostic_stderr',
        'write_warning_stderr',
        'write_error_stderr',
    ]

    MSVCProgramConfig = namedtuple("MSVCProgramConfig", [
        'program',
    ] + _msvc_common_environ + [
        're_banner',
        're_error',
        're_warning',
        'filter_func',
        'filter_debug_stderr',
    ])

    MSVCConfig = namedtuple("MSVCConfig", [
        'rewrite_enabled',
    ] + _msvc_common_environ + [
        'filter_debug_stderr',
    ])

    environ_prefix = 'SCONS_MSVC'
    environ_enabled_symbols = ('1', 'true', 'yes', 't', 'y')

    @classmethod
    def _environ_enabled(cls, key, default=False):
        rval = os.environ.get(key)
        if rval is None:
            return default
        rval = bool(rval.lower() in cls.environ_enabled_symbols)
        return rval

    cfg = None
    cfg_dict = None

    @classmethod
    def _initialize(cls):

        config_dict = {}

        for key, suffix, default in [
            ('rewrite_enabled', 'OUTPUT_REWRITE', False),
            ('filter_enabled', 'OUTPUT_FILTER', False),
            ('filter_debug', 'OUTPUT_FILTER_DEBUG', False),
            ('write_banner_full', 'WRITE_BANNER_FULL', True),
            ('write_banner_stderr', 'WRITE_BANNER_STDERR', False),
            ('write_diagnostic_stderr', 'WRITE_DIAGNOSTIC_STDERR', False),
            ('write_warning_stderr', 'WRITE_WARNING_STDERR', True),
            ('write_error_stderr', 'WRITE_ERROR_STDERR', True),

        ]:
            config_dict[key] = cls._environ_enabled(
                '_'.join([cls.environ_prefix, suffix]), default
            )

        config_dict['filter_debug_stderr'] = config_dict['write_diagnostic_stderr']

        cls.cfg = cls.MSVCConfig(**config_dict)
        cls.cfg_dict = config_dict

    program_cfg = {}

    @classmethod
    def _program_register(cls, program, envsuffix, re_banner, re_error, re_warning, filter_func):

        basename, ext = os.path.splitext(program)

        program_dict = {
            'program': basename,
            're_banner': re_banner,
            're_error': re_error,
            're_warning': re_warning,
            'filter_func': filter_func,
        }

        for key, suffix in [
            ('filter_enabled', 'OUTPUT_FILTER'),
            ('filter_debug', 'OUTPUT_FILTER_DEBUG'),
            ('write_banner_full', 'WRITE_BANNER_FULL'),
            ('write_banner_stderr', 'WRITE_BANNER_STDERR'),
            ('write_diagnostic_stderr', 'WRITE_DIAGNOSTIC_STDERR'),
            ('write_warning_stderr', 'WRITE_WARNING_STDERR'),
            ('write_error_stderr', 'WRITE_ERROR_STDERR'),

        ]:
            default = cls.cfg_dict[key]
            program_dict[key] = cls._environ_enabled(
                '_'.join([cls.environ_prefix, suffix, envsuffix]), default
            )

        program_dict['filter_debug_stderr'] = program_dict['write_diagnostic_stderr']

        program_cfg = cls.MSVCProgramConfig(**program_dict)

        cls.program_cfg[basename] = program_cfg
        cls.program_cfg[program] = program_cfg

        return program_cfg

    re_redirect_stream = re.compile(r'^[12]?>')

    @classmethod
    def get_program_config(cls, args, env):

        # TODO(JCB): no reliable method to verify (e.g., man-in-the-middle):
        #     link == msvc link.exe
        #     cl == msvc cl.exe

        if not cls.cfg.rewrite_enabled:
            return None

        program = args[0].lower()
        program_cfg = cls.program_cfg.get(program)
        if not program_cfg:
            return None

        for arg in args:
            if cls.re_redirect_stream.match(arg):
                return None

        # TODO(JCB) check known argument(s) for program?

        return program_cfg

    # program banner

    re_banner_any = re.compile('^(?P<full>(?P<version>Microsoft\s+.+\n)Copyright\s+.+\n\n)', re.MULTILINE | re.IGNORECASE)

    @classmethod
    def _program_banner(cls, program_cfg, content):

        m_banner = program_cfg.re_banner.match(content)
        if m_banner:
            banner_group = 'full' if program_cfg.write_banner_full else 'version'
            banner = m_banner.group(banner_group)
            content = content[m_banner.span()[-1]:]
        else:
            banner = None

        return banner, content

    # cl filter (ASSUMES: /c filename)

    re_cl_filespec = [
        # match quoted filename: ' /c " my file .c" '
        re.compile(r'\s/c\s+"(?P<pathspec>[^"]+)"(?:\s|$)'),
        # match bare filename: ' /c myfile.c '
        re.compile(r'\s/c\s+(?P<pathspec>[^"\s]+)(?:\s|$)'),
    ]

    @classmethod
    def _filter_cl_filename_cmdline(cls, line, argstr):
        # method:
        #   match command file for pathspec ' /c pathpec '
        #   get file name from pathspec
        #   check if file name matches current record

        if not line:
            return False

        m_filespec = None

        for re_filespec in cls.re_cl_filespec:
            m_filespec = re_filespec.search(argstr)
            if m_filespec:
                break

        if not m_filespec:
            return False

        pathspec = m_filespec.group('pathspec')

        _, filename = os.path.split(pathspec)
        if not filename:
            return False

        if filename == line:
            return True

        if filename == line.rstrip():
            return True

        return False

    @classmethod
    def _filter_cl_filename_argstr(cls, line, argstr):
        # (unreliable) method:
        #   assume line contains filename
        #   construct regex for command-line pathspec suffix
        #   check if regex matches argument string

        if not line:
            return False

        # TODO(JCB): correctness not guaranteed
        regex_str = r'["\s/\\]' + re.escape(line.rstrip()) + r'(?:["\s]|$)'
        re_filespec = re.compile(regex_str)

        if re_filespec.search(argstr):
            return True

        return False

    @classmethod
    def _filter_cl_filename(cls, line, argstr):

        if cls._filter_cl_filename_cmdline(line, argstr):
            return True

        if cls._filter_cl_filename_argstr(line, argstr):
            return True

        return False

    @classmethod
    def _filter_cl_record(cls, program_cfg, line, argstr):

        if cls._filter_cl_filename(line, argstr):
            return True

        return False

    # link filter

    re_link_outspec = [
        # match quoted filename: ' "/OUT: my program .exe" '
        re.compile(r'\s"/OUT:(?P<pathspec>[^"]+)"(?:\s|$)'),
        # match bare filename: ' /OUT: myprogram.exe '
        re.compile(r'\s/OUT:(?P<pathspec>\S+)(?:\s|$)'),
    ]

    @classmethod
    def _filter_link_libexp(cls, line, argstr):
        # method:
        #   match command file for outspec ' /OUT:outspec '
        #   get the basename from the output file name
        #   build regex for basename.lib and basename.exp
        #   check regex matches current record

        if not line:
            return False

        m_outspec = None

        for re_outspec in cls.re_link_outspec:
            m_outspec = re_outspec.search(argstr)
            if m_outspec:
                break

        if not m_outspec:
            return False

        pathspec = m_outspec.group('pathspec')

        pathbasename, fileext = os.path.splitext(pathspec)
        if not fileext:
            return False

        pathprefix, basename = os.path.split(pathbasename)
        if not basename:
            return False

        re_pathbasename = re.escape(pathbasename)

        regex_str = fr'\s"?(?P<lib>{re_pathbasename}\.lib)"?.*"?(?P<exp>{re_pathbasename}\.exp)"?'
        re_libexp = re.compile(regex_str, re.IGNORECASE)

        if not re_libexp.search(line):
            return False

        return True

    @classmethod
    def _filter_link_record(cls, program_cfg, line, argstr):

        if cls._filter_link_libexp(line, argstr):
            return True

        return False

    # destination stream

    re_error_cl = re.compile(r'^.+\s(error)\s(D|C)[0-9]{3,4}\s*\:.+$')
    re_warning_cl = re.compile(r'^.+\s(warning)\s(D|C)[0-9]{3,4}\s*\:.+$')

    re_error_link = re.compile(r'^.+\s(error)\s(LNK)[0-9]{3,4}\s*\:.+$')
    re_warning_link = re.compile(r'^.+\s(warning)\s(LNK)[0-9]{3,4}\s*\:.+$')

    # TODO(JCB) need note regex?

    @classmethod
    def _write_stderr(cls, program_cfg, line):

        if program_cfg.re_error.match(line):
            return program_cfg.write_error_stderr

        if program_cfg.re_warning.match(line):
            return program_cfg.write_warning_stderr

        return program_cfg.write_diagnostic_stderr

    # stream rewriting and optional record filtering

    @classmethod
    def spawn(cls, sh, escape, cmd, args, env, program_cfg):

        # copy arguments for local modification
        args = list(args)

        tmp_stdout, tmp_stdout_name = tempfile.mkstemp()
        os.close(tmp_stdout)

        # redirect stdout and stderr: 1>tmpfile 2>&1
        args.append(f'1>{tmp_stdout_name}')
        args.append('2>&1')

        argstr = ' '.join(args)
        ret = exec_spawn([sh, '/C', escape(argstr)], env)

        try:
            with open(tmp_stdout_name, 'rb') as tmp_stdout:

                do_once = True
                while do_once:
                    do_once = False

                    content = tmp_stdout.read()
                    if not content:
                        break

                    content = content.decode('oem', 'replace')
                    content = content.replace('\r\n', '\n')

                    banner, content = cls._program_banner(program_cfg, content)
                    if banner:
                        # local assignment in case system streams are modified during runtime
                        stream = sys.stderr if program_cfg.write_banner_stderr else sys.stdout
                        stream.write(banner)

                    if not content:
                        break

                    # assume only *ONE* matching line is suppressed
                    filter_func = program_cfg.filter_func if program_cfg.filter_enabled else None

                    for linenum, line in enumerate(content.splitlines()):

                        if filter_func:
                            if filter_func(program_cfg, line, argstr):
                                if program_cfg.filter_debug:
                                    stream = sys.stderr if program_cfg.filter_debug_stderr else sys.stdout
                                    stream.write(f'***FILTER***: ')
                                    stream.write(line)
                                    stream.write('\n')
                                filter_func = None
                                continue

                        stream = sys.stderr if cls._write_stderr(program_cfg, line) else sys.stdout
                        stream.write(line)
                        stream.write('\n')

            os.remove(tmp_stdout_name)
        except OSError:
            pass

        return ret

    @classmethod
    def setup(cls):

        cls._initialize()

        cls._program_register(
            'cl.exe', 'CL',
            cls.re_banner_any, cls.re_error_cl, cls.re_warning_cl,
            cls._filter_cl_record
        )

        cls._program_register(
            'link.exe', 'LINK',
            cls.re_banner_any, cls.re_error_link, cls.re_warning_link,
            cls._filter_link_record
        )

_MSVCRewrite.setup()

# special handling for msvc output hook

def spawn(sh, escape, cmd, args, env):
    if not sh:
        sys.stderr.write("scons: Could not find command interpreter, is it in your PATH?\n")
        return 127

    program_cfg = _MSVCRewrite.get_program_config(args, env)
    if program_cfg:
        return _MSVCRewrite.spawn(sh, escape, cmd, args, env, program_cfg)

    return exec_spawn([sh, '/C', escape(' '.join(args))], env)

# Windows does not allow special characters in file names anyway, so no
# need for a complex escape function, we will just quote the arg, except
# that "cmd /c" requires that if an argument ends with a backslash it
# needs to be escaped so as not to interfere with closing double quote
# that we add.
def escape(x):
    if x[-1] == '\\':
        x = x + '\\'
    return '"' + x + '"'

# Get the windows system directory name
_system_root = None


def get_system_root():
    global _system_root
    if _system_root is not None:
        return _system_root

    # A resonable default if we can't read the registry
    val = os.environ.get('SystemRoot', "C:\\WINDOWS")

    if SCons.Util.can_read_reg:
        try:
            # Look for Windows NT system root
            k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                      'Software\\Microsoft\\Windows NT\\CurrentVersion')
            val, tok = SCons.Util.RegQueryValueEx(k, 'SystemRoot')
        except SCons.Util.RegError:
            try:
                # Okay, try the Windows 9x system root
                k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                          'Software\\Microsoft\\Windows\\CurrentVersion')
                val, tok = SCons.Util.RegQueryValueEx(k, 'SystemRoot')
            except KeyboardInterrupt:
                raise
            except:
                pass

    _system_root = val
    return val


def get_program_files_dir():
    """
    Get the location of the program files directory
    Returns
    -------

    """
    # Now see if we can look in the registry...
    val = ''
    if SCons.Util.can_read_reg:
        try:
            # Look for Windows Program Files directory
            k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                      'Software\\Microsoft\\Windows\\CurrentVersion')
            val, tok = SCons.Util.RegQueryValueEx(k, 'ProgramFilesDir')
        except SCons.Util.RegError:
            val = ''

    if val == '':
        # A reasonable default if we can't read the registry
        # (Actually, it's pretty reasonable even if we can :-)
        val = os.path.join(os.path.dirname(get_system_root()),"Program Files")

    return val


class ArchDefinition:
    """
    Determine which windows CPU were running on.
    A class for defining architecture-specific settings and logic.
    """
    def __init__(self, arch, synonyms=[]) -> None:
        self.arch = arch
        self.synonyms = synonyms

SupportedArchitectureList = [
    ArchDefinition(
        'x86',
        ['i386', 'i486', 'i586', 'i686'],
    ),

    ArchDefinition(
        'x86_64',
        ['AMD64', 'amd64', 'em64t', 'EM64T', 'x86_64'],
    ),

    ArchDefinition(
        'arm64',
        ['ARM64', 'aarch64', 'AARCH64', 'AArch64'],
    ),

    ArchDefinition(
        'ia64',
        ['IA64'],
    ),
]

SupportedArchitectureMap = {}
for a in SupportedArchitectureList:
    SupportedArchitectureMap[a.arch] = a
    for s in a.synonyms:
        SupportedArchitectureMap[s] = a


def get_architecture(arch=None):
    """Returns the definition for the specified architecture string.

    If no string is specified, the system default is returned (as defined
    by the registry PROCESSOR_ARCHITECTURE value, PROCESSOR_ARCHITEW6432
    environment variable, PROCESSOR_ARCHITECTURE environment variable, or
    the platform machine).
    """
    if arch is None:
        if SCons.Util.can_read_reg:
            try:
                k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                          'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment')
                val, tok = SCons.Util.RegQueryValueEx(k, 'PROCESSOR_ARCHITECTURE')
            except SCons.Util.RegError:
                val = ''
            if val and val in SupportedArchitectureMap:
                arch = val
    if arch is None:
        arch = os.environ.get('PROCESSOR_ARCHITEW6432')
        if not arch:
            arch = os.environ.get('PROCESSOR_ARCHITECTURE')
    return SupportedArchitectureMap.get(arch, ArchDefinition(platform.machine(), [platform.machine()]))


def generate(env):
    # Attempt to find cmd.exe (for WinNT/2k/XP) or
    # command.com for Win9x
    cmd_interp = ''
    # First see if we can look in the registry...
    if SCons.Util.can_read_reg:
        try:
            # Look for Windows NT system root
            k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                          'Software\\Microsoft\\Windows NT\\CurrentVersion')
            val, tok = SCons.Util.RegQueryValueEx(k, 'SystemRoot')
            cmd_interp = os.path.join(val, 'System32\\cmd.exe')
        except SCons.Util.RegError:
            try:
                # Okay, try the Windows 9x system root
                k=SCons.Util.RegOpenKeyEx(SCons.Util.hkey_mod.HKEY_LOCAL_MACHINE,
                                              'Software\\Microsoft\\Windows\\CurrentVersion')
                val, tok = SCons.Util.RegQueryValueEx(k, 'SystemRoot')
                cmd_interp = os.path.join(val, 'command.com')
            except KeyboardInterrupt:
                raise
            except:
                pass

    # For the special case of not having access to the registry, we
    # use a temporary path and pathext to attempt to find the command
    # interpreter.  If we fail, we try to find the interpreter through
    # the env's PATH.  The problem with that is that it might not
    # contain an ENV and a PATH.
    if not cmd_interp:
        systemroot = get_system_root()
        tmp_path = systemroot + os.pathsep + \
                   os.path.join(systemroot,'System32')
        tmp_pathext = '.com;.exe;.bat;.cmd'
        if 'PATHEXT' in os.environ:
            tmp_pathext = os.environ['PATHEXT']
        cmd_interp = SCons.Util.WhereIs('cmd', tmp_path, tmp_pathext)
        if not cmd_interp:
            cmd_interp = SCons.Util.WhereIs('command', tmp_path, tmp_pathext)

    if not cmd_interp:
        cmd_interp = env.Detect('cmd')
        if not cmd_interp:
            cmd_interp = env.Detect('command')

    if 'ENV' not in env:
        env['ENV']        = {}

    # Import things from the external environment to the construction
    # environment's ENV.  This is a potential slippery slope, because we
    # *don't* want to make builds dependent on the user's environment by
    # default.  We're doing this for SystemRoot, though, because it's
    # needed for anything that uses sockets, and seldom changes, and
    # for SystemDrive because it's related.
    #
    # Weigh the impact carefully before adding other variables to this list.
    import_env = ['SystemDrive', 'SystemRoot', 'TEMP', 'TMP', 'USERPROFILE']
    for var in import_env:
        v = os.environ.get(var)
        if v:
            env['ENV'][var] = v

    if 'COMSPEC' not in env['ENV']:
        v = os.environ.get("COMSPEC")
        if v:
            env['ENV']['COMSPEC'] = v

    env.AppendENVPath('PATH', get_system_root() + '\\System32')

    env['ENV']['PATHEXT'] = '.COM;.EXE;.BAT;.CMD'
    env['OBJPREFIX']      = ''
    env['OBJSUFFIX']      = '.obj'
    env['SHOBJPREFIX']    = '$OBJPREFIX'
    env['SHOBJSUFFIX']    = '$OBJSUFFIX'
    env['PROGPREFIX']     = ''
    env['PROGSUFFIX']     = '.exe'
    env['LIBPREFIX']      = ''
    env['LIBSUFFIX']      = '.lib'
    env['SHLIBPREFIX']    = ''
    env['SHLIBSUFFIX']    = '.dll'
    env['LIBPREFIXES']    = ['$LIBPREFIX']
    env['LIBSUFFIXES']    = ['$LIBSUFFIX']
    env['LIBLITERALPREFIX'] = ''
    env['PSPAWN']         = piped_spawn
    env['SPAWN']          = spawn
    env['SHELL']          = cmd_interp
    env['TEMPFILE']       = TempFileMunge
    env['TEMPFILEPREFIX'] = '@'
    env['MAXLINELENGTH']  = 2048
    env['ESCAPE']         = escape

    env['HOST_OS']        = 'win32'
    env['HOST_ARCH']      = get_architecture().arch

    if enable_virtualenv and not ignore_virtualenv:
        ImportVirtualenv(env)


# Local Variables:
# tab-width:4
# indent-tabs-mode:nil
# End:
# vim: set expandtab tabstop=4 shiftwidth=4:
