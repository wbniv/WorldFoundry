"""The runtime type-name lookup must stay aligned with levcomp's class IDs."""
from pathlib import Path
import re


def test_type_names_match_levcomp_class_order():
    oas = Path(__file__).resolve().parents[1] / "wfsource/source/oas"
    names = re.findall(r'"([A-Za-z0-9_]+)"', (oas / "objects.names").read_text())
    classes = (oas / "objects.lc").read_text().split("{", 1)[1].split("}", 1)[0].split()
    assert [name.lower() for name in names] == [name.lower() for name in classes]
