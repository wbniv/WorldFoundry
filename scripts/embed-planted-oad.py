#!/usr/bin/env python3
"""Embed the planted settings schema in the engine for the level selector."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
data = args.source.read_bytes()
if len(data) < 80 or (len(data) - 80) % 1491:
    raise ValueError("Invalid planted settings OAD")
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    "// Generated from plantedtanksettings.oad.\n"
    "static const unsigned char plantedOad[] = {\n" +
    "\n".join(",".join(str(value) for value in data[i:i + 24]) + ","
              for i in range(0, len(data), 24)) + "\n};\n"
)
