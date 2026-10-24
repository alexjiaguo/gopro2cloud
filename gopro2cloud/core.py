"""
gopro2cloud.core - Backwards compatibility alias pointing to unicloud.core.
"""

import sys
import unicloud.core

for _attr in dir(unicloud.core):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(unicloud.core, _attr)

# Replace module entry in sys.modules so patching gopro2cloud.core.* patches unicloud.core.*
sys.modules[__name__] = unicloud.core
