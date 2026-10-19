"""World Foundry producer helpers and the protected installed coordinator API."""
from pathlib import Path
import sys

_installed=Path('/opt/wf-device-coordinator/scripts/wf_device')
if not _installed.is_dir():
    raise ImportError('Install the standalone chromecast-coordinator service; no direct device fallback')
__path__.append(str(_installed))

# This namespace shim bypasses the installed package's __init__. Load its
# reviewed dependency closure too, so client-side APK validation works without
# installing jsonschema globally on the producer host.
_vendor=_installed.parents[1]/'vendor'
if _vendor.is_dir():
    sys.path.insert(0,str(_vendor))
