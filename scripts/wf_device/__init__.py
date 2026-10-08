"""World Foundry producer helpers and the protected installed coordinator API."""
from pathlib import Path

_installed=Path('/opt/wf-device-coordinator/scripts/wf_device')
if not _installed.is_dir():
    raise ImportError('Install the standalone chromecast-coordinator service; no direct device fallback')
__path__.append(str(_installed))
