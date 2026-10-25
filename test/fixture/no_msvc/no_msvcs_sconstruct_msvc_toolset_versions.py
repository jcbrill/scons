# SPDX-License-Identifier: MIT
#
# Copyright The SCons Foundation

import SCons
import SCons.Tool.MSCommon

DefaultEnvironment(tools=[])

def _msvc_toolset_versions_list(tsversions_t):
    vc_toolsets = tsversions_t.vc_toolsets if tsversions_t else []
    return vc_toolsets

def DummyVsWhere(msvc_version, vswhere_exe, msvc_channel):
    # not testing versions with vswhere, so return none
    return None

for key in SCons.Tool.MSCommon.vc._VCVER_TO_PRODUCT_DIR:
    SCons.Tool.MSCommon.vc._VCVER_TO_PRODUCT_DIR[key] = [
        (SCons.Util.HKEY_LOCAL_MACHINE, r'')
    ]

SCons.Tool.MSCommon.vc._find_vc_pdir_vswhere = DummyVsWhere
toolset_version_list = _msvc_toolset_versions_list(SCons.Tool.MSCommon.msvc_toolset_versions())
print('toolset_version_list=' + repr(toolset_version_list))
