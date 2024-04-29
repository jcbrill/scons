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
import re
import sys
import tempfile

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

#  rewrite  filter  action
#  -------  ------  ----------------------------------
#  True     False   rewrite streams
#  True     True    filter records and rewrite streams
#  False    False   skip processing
#  False    True    skip processing

msvc_rewrite_enabled = True
msvc_filter_enabled = False

msvc_suppress_cl = False
msvc_suppress_link = False

# special handling for msvc cl/link output

re_msvc_program = re.compile(r'^(?P<basename>cl|link)(\.exe)?$', re.IGNORECASE)

re_msvc_redirect_stdout = re.compile(r'^[1]?>(?P<stderr>&\s*2)*')
re_msvc_redirect_stderr = re.compile(r'^[2]?>(?P<stdout>&\s*1)*')

def _msvc_program(args, env):

    # TODO: need method to verify:
    #     link == msvc link.exe
    #     cl == msvc cl.exe

    m_program = re_msvc_program.match(args[0])
    if not m_program:
        return None

    for arg in args:
        if re_msvc_redirect_stdout.match(arg):
            return None
        if re_msvc_redirect_stderr.match(arg):
            return None

    program = m_program.group('basename').lower()
    return program

msvc_banner_write_stdout = True
msvc_banner_write_full = True

re_msvc_banner = re.compile('^(?P<full>(?P<version>Microsoft\s+.+\n)Copyright\s+.+\n\n)', re.MULTILINE | re.IGNORECASE)
re_msvc_banner_group = 'full' if msvc_banner_write_full else 'version'

def _msvc_banner(content):

    m_banner = re_msvc_banner.match(content)
    if m_banner:
        banner = m_banner.group(re_msvc_banner_group)
        content = content[m_banner.span()[-1]:]
    else:
        banner = None

    return banner, content

# https://stackoverflow.com/questions/62878395/regex-for-illegal-filenames-in-windows
re_filename_restrict = re.compile(r'^[^\x00-\x1F\xA5\\?*:\"";|\/<>]+$')
re_filename_legal = re.compile(r'^(?!(?:\x20+.+)?$)(?!(?:\..+)?$).+(?<![\x20.])$')

def _msvc_suppress_cl_filename(line, argstr):

    if not re_filename_restrict.match(line):
        return None

    if not re_filename_legal.match(line):
        return None

    _, tail = os.path.split(line)

    if not tail:
        return None

    # TODO: regex instead of blind search?

    if tail not in argstr:
        return None

    return line

def _msvc_suppress_cl_message(program, line, argstr):

    message = _msvc_suppress_cl_filename(line, argstr)
    if message:
        return message

    return None

re_msvc_link_outspec = re.compile(r'\s/OUT:(?P<pathspec>"[^"]+"|\S+)(?:\s|$)', re.IGNORECASE)

def _msvc_suppress_link_libexp(line, argstr):

    m_outspec = re_msvc_link_outspec.search(argstr)
    if not m_outspec:
        return None

    pathspec = m_outspec.group('pathspec')

    pathbasename, fileext = os.path.splitext(pathspec)
    if not fileext:
        return None

    pathprefix, basename = os.path.split(pathbasename)
    if not basename:
        return None

    if not re_filename_restrict.match(basename):
        return None

    if not re_filename_legal.match(basename):
        return None

    re_pathbasename = re.escape(pathbasename)

    regex_str = fr'\s"?(?P<lib>{re_pathbasename}\.lib)"?.*"?(?P<exp>{re_pathbasename}\.exp)"?'
    re_libexp = re.compile(regex_str, re.IGNORECASE)

    if not re_libexp.search(line):
        return None

    return line

def _msvc_suppress_link_message(program, line, argstr):

    message = _msvc_suppress_link_libexp(line, argstr)
    if message:
        return message

    return None

msvc_suppress_program_map = {
    'cl': _msvc_suppress_cl_message if (msvc_filter_enabled and msvc_suppress_cl) else None,
    'link': _msvc_suppress_link_message if (msvc_filter_enabled and msvc_suppress_link) else None,
}

re_msvc_errwarn = re.compile(r'^.+\s+(warning|error)\s+[A-Z]+[0-9]+\s*\:.+$', re.IGNORECASE)

def _msvc_errwarn(line):

    if re_msvc_errwarn.match(line):
        return True

    return False

def _msvc_spawn(sh, escape, cmd, args, env, program):

    # copy arguments for local modification
    args = list(args)

    tmp_stdout, tmp_stdout_name = tempfile.mkstemp()
    os.close(tmp_stdout)

    # redirect stdout and stderr: 1>tmpfile 2>&1
    args.append(f'1>"{tmp_stdout_name}"')
    args.append("2>&1")

    argstr = ' '.join(args)
    ret = exec_spawn([sh, '/C', escape(argstr)], env)

    try:
        with open(tmp_stdout_name, "rb") as tmp_stdout:

            do_once = True
            while do_once:
                do_once = False

                content = tmp_stdout.read()
                if not content:
                    break

                content = content.decode("oem", "replace")
                content = content.replace("\r\n", "\n")

                banner, content = _msvc_banner(content)
                if banner:
                    # original destination streams for banner: cl stderr, link stdout
                    # local assignment in case system streams are modified during runtime
                    stream = sys.stdout if msvc_banner_write_stdout else sys.stderr
                    stream.write(banner)

                if not content:
                    break

                # assumption: only *one* matching line is suppressed
                suppress_func = msvc_suppress_program_map.get(program, False)

                for linenum, line in enumerate(content.splitlines()):

                    if suppress_func:
                        message = suppress_func(program, line, argstr)
                        if message:
                            suppress_func = None
                            continue

                    stream = sys.stderr if _msvc_errwarn(line) else sys.stdout
                    stream.write(line + '\n')

        os.remove(tmp_stdout_name)
    except OSError:
        pass

    return ret

# special handling for msvc output hook

def spawn(sh, escape, cmd, args, env):
    if not sh:
        sys.stderr.write("scons: Could not find command interpreter, is it in your PATH?\n")
        return 127

    if msvc_rewrite_enabled:
        program = _msvc_program(args, env)
        if program:
            return _msvc_spawn(sh, escape, cmd, args, env, program)

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
