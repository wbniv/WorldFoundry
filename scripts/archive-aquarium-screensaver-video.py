#!/usr/bin/env python3
"""Archive a coordinator screensaver recording as a one-minute web MP4."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(*args):
    subprocess.run(args, check=True)


def probe(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size",
        "-show_entries", "stream=width,height", "-of", "json", str(path)
    ], text=True)
    return json.loads(result)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--tank", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--apk-sha256", required=True)
    parser.add_argument("--water", choices=("freshwater", "saltwater"))
    parser.add_argument("--job-status", choices=("completed", "recovery-required"), default="completed")
    args = parser.parse_args()
    if not args.slug.replace("-", "").isalnum() or not args.job.startswith("J-"):
        parser.error("Invalid slug or job ID")
    source = args.evidence / "capture.mp4"
    source_info = probe(source)
    source_duration = float(source_info["format"]["duration"])
    if source_duration < 63:
        raise ValueError(f"Source clip too short for a one-minute archive: {source_duration:.2f}s")
    args.archive.mkdir(parents=True, exist_ok=True)
    output = args.archive / f"{args.slug}.mp4"
    poster = args.archive / f"{args.slug}.png"
    run("ffmpeg", "-y", "-v", "error", "-ss", "2", "-i", str(source), "-t", "60.5",
        "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output))
    result = probe(output)
    duration = float(result["format"]["duration"])
    if not 60 <= duration < 61:
        raise ValueError(f"Archive duration is not one minute: {duration:.2f}s")
    run("ffmpeg", "-y", "-v", "error", "-ss", "30", "-i", str(output),
        "-frames:v", "1", str(poster))
    video = next(stream for stream in result["streams"] if "width" in stream)
    entry = {
        "slug": args.slug,
        "tank": args.tank,
        "water": args.water,
        "device": args.device,
        "coordinator_job": args.job,
        "coordinator_status": args.job_status,
        "apk_sha256": args.apk_sha256,
        "file": output.name,
        "poster": poster.name,
        "duration_seconds": duration,
        "width": video["width"],
        "height": video["height"],
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
        "source_duration_seconds": source_duration,
        "source_sha256": sha256(source),
    }
    manifest_path = args.archive / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"schema": 1, "videos": []}
    for item in manifest["videos"]:
        item.setdefault("coordinator_status", "completed")
    manifest["videos"] = [item for item in manifest["videos"] if item["slug"] != args.slug] + [entry]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
