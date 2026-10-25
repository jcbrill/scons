# SPDX-License-Identifier: MIT
#
# Copyright The SCons Foundation

import SCons
import SCons.Tool.MSCommon

DefaultEnvironment(tools=[])

def DummyVsWhere(msvc_version, vswhere_exe, msvc_channel):
    # not testing versions with vswhere, so return none
    return None

for key in SCons.Tool.MSCommon.vc._VCVER_TO_PRODUCT_DIR:
    SCons.Tool.MSCommon.vc._VCVER_TO_PRODUCT_DIR[key] = [
        (SCons.Util.HKEY_LOCAL_MACHINE, r'')
    ]

SCons.Tool.MSCommon.vc._find_vc_pdir_vswhere = DummyVsWhere
toolset_version_t = SCons.Tool.MSCommon.msvc_query_version_toolset()
print(f'msvc_version={toolset_version_t.vc_version!r}, msvc_toolset_version={toolset_version_t.vc_toolset_version!r}')
