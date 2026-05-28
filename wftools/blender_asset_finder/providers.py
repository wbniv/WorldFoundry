"""
Pure-Python asset provider — search, download, and provenance tracking
across multiple online providers. Replaces the wf_asset_provider Rust
extension; requires only Python stdlib (3.11+ for tomllib).
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

# ── Licence IDs ──────────────────────────────────────────────────────────────

CC0         = "CC0-1.0"
CC_BY       = "CC-BY-4.0"
CC_BY_SA    = "CC-BY-SA-4.0"
CC_BY_NC    = "CC-BY-NC-4.0"
CC_BY_NC_SA = "CC-BY-NC-SA-4.0"
CC_BY_ND    = "CC-BY-ND-4.0"
CC_BY_NC_ND = "CC-BY-NC-ND-4.0"
MIT         = "MIT"
APACHE2     = "Apache-2.0"
BSD2        = "BSD-2-Clause"
BSD3        = "BSD-3-Clause"
GPL2        = "GPL-2.0"
GPL3        = "GPL-3.0"
ROYALTY_FREE = "royalty-free"
EDITORIAL    = "editorial-only"
UNKNOWN      = "unknown"

_LICENCE_URLS: dict[str, str] = {
    CC0:         "https://creativecommons.org/publicdomain/zero/1.0/",
    CC_BY:       "https://creativecommons.org/licenses/by/4.0/",
    CC_BY_SA:    "https://creativecommons.org/licenses/by-sa/4.0/",
    CC_BY_NC:    "https://creativecommons.org/licenses/by-nc/4.0/",
    CC_BY_NC_SA: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    CC_BY_ND:    "https://creativecommons.org/licenses/by-nd/4.0/",
    CC_BY_NC_ND: "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    MIT:         "https://opensource.org/licenses/MIT",
    APACHE2:     "https://www.apache.org/licenses/LICENSE-2.0",
    BSD2:        "https://opensource.org/licenses/BSD-2-Clause",
    BSD3:        "https://opensource.org/licenses/BSD-3-Clause",
    GPL2:        "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
    GPL3:        "https://www.gnu.org/licenses/gpl-3.0.html",
    ROYALTY_FREE: "",
    EDITORIAL:   "",
    UNKNOWN:     "",
}

# MIT/Apache/BSD require preserving copyright notices (attribution in spirit if not CC name)
_ATTRIBUTION_REQUIRED = {
    CC_BY, CC_BY_SA, CC_BY_NC, CC_BY_NC_SA, CC_BY_ND, CC_BY_NC_ND,
    MIT, APACHE2, BSD2, BSD3,
}

_RAW_TO_LICENCE: dict[str, str] = {
    # CC0
    "cc0": CC0, "cc0-1.0": CC0, "cc0 1.0": CC0,
    "cc0 1.0 universal (cc0 1.0) public domain dedication": CC0,
    "publicdomain": CC0, "public domain": CC0,
    # CC-BY
    "cc-by": CC_BY, "cc-by-4.0": CC_BY, "cc by 4.0": CC_BY,
    "attribution 4.0 international (cc by 4.0)": CC_BY,
    # CC-BY-SA
    "cc-by-sa": CC_BY_SA, "cc-by-sa-4.0": CC_BY_SA, "cc by-sa 4.0": CC_BY_SA,
    "attribution-sharealike 4.0 international (cc by-sa 4.0)": CC_BY_SA,
    # CC-BY-NC
    "cc-by-nc": CC_BY_NC, "cc-by-nc-4.0": CC_BY_NC,
    "attribution-noncommercial 4.0 international (cc by-nc 4.0)": CC_BY_NC,
    # CC-BY-NC-SA
    "cc-by-nc-sa": CC_BY_NC_SA, "cc-by-nc-sa-4.0": CC_BY_NC_SA,
    # CC-BY-ND
    "cc-by-nd": CC_BY_ND, "cc-by-nd-4.0": CC_BY_ND,
    # CC-BY-NC-ND
    "cc-by-nc-nd": CC_BY_NC_ND, "cc-by-nc-nd-4.0": CC_BY_NC_ND,
    # Permissive OSS (attribution required — keep copyright notice)
    "mit": MIT,
    "apache-2.0": APACHE2, "apache 2.0": APACHE2, "apache2": APACHE2,
    "bsd-2-clause": BSD2, "bsd 2-clause": BSD2, "bsd2": BSD2,
    "bsd-3-clause": BSD3, "bsd 3-clause": BSD3, "bsd3": BSD3,
    # Copyleft OSS — usable but derivative works must remain GPL
    "gpl-2.0": GPL2, "gplv2": GPL2, "gpl2": GPL2, "gpl v2": GPL2,
    "gpl-3.0": GPL3, "gplv3": GPL3, "gpl3": GPL3, "gpl v3": GPL3,
    "gpl": GPL3,
    # Paid / editorial
    "royalty-free": ROYALTY_FREE, "sketchfab": ROYALTY_FREE,
    "editorial-only": EDITORIAL, "ed": EDITORIAL,
    # Truly unknown
    "custom": UNKNOWN,
}

# Sketchfab API licence slug → canonical ID
_SKETCHFAB_SLUGS: dict[str, str] = {
    "0":         CC0,
    "by":        CC_BY,
    "bysa":      CC_BY_SA,
    "bync":      CC_BY_NC,
    "byncsa":    CC_BY_NC_SA,
    "bynd":      CC_BY_ND,
    "byncnd":    CC_BY_NC_ND,
    "ed":        EDITORIAL,
    "sketchfab": ROYALTY_FREE,
}


def licence_from_raw(raw: str) -> str:
    return _RAW_TO_LICENCE.get(raw.lower().strip(), UNKNOWN)


def _licence_url(lid: str) -> str:
    return _LICENCE_URLS.get(lid, "")


def _requires_attribution(lid: str) -> bool:
    return lid in _ATTRIBUTION_REQUIRED


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class AssetCandidate:
    provider: str
    provider_id: str
    title: str
    thumbnail_url: str
    licence_id: str
    download_url: str
    original_url: str
    attribution_string: str
    attribution_required: bool
    lower_trust: bool = False


@dataclass
class Credentials:
    sketchfab_api_key: Optional[str] = None


@dataclass
class Policy:
    accept_ids: set
    reject_ids: set
    reject_default_ids: set
    require_attribution_credits: bool
    policy_path: Optional[str]

    def allows(self, licence_id: str) -> bool:
        if licence_id in self.accept_ids:
            return True
        if licence_id in self.reject_ids or licence_id in self.reject_default_ids:
            return False
        return False

    @classmethod
    def cc0_only(cls, path: Optional[str] = None) -> "Policy":
        return cls(
            accept_ids={"CC0-1.0"},
            reject_ids=set(),
            reject_default_ids=set(),
            require_attribution_credits=True,
            policy_path=path,
        )


# ── Policy loading ────────────────────────────────────────────────────────────

def _find_policy_file(start_dir: str) -> Optional[str]:
    d = Path(start_dir).resolve()
    while True:
        candidate = d / "licence_policy.toml"
        if candidate.is_file():
            return str(candidate)
        parent = d.parent
        if parent == d:
            return None
        d = parent


def load_policy(start_dir: str) -> Policy:
    """Walk up from start_dir looking for licence_policy.toml.
    Returns CC0-only fallback if not found or unparseable."""
    path = _find_policy_file(start_dir)
    if path is None:
        return Policy.cc0_only()

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"[providers] policy read error: {e}", file=sys.stderr)
        return Policy.cc0_only()

    try:
        if sys.version_info >= (3, 11):
            import tomllib
            data = tomllib.loads(text)
        else:
            try:
                import tomli as tomllib  # type: ignore[import]
                data = tomllib.loads(text)
            except ImportError:
                print("[providers] tomllib unavailable; using CC0 fallback", file=sys.stderr)
                return Policy.cc0_only(path)
    except Exception as e:
        print(f"[providers] policy parse error: {e}", file=sys.stderr)
        return Policy.cc0_only()

    accept_ids: set = set()
    reject_ids: set = set()
    reject_default_ids: set = set()

    for entry in data.get("licence", []):
        lid    = entry.get("id", "")
        status = entry.get("status", "")
        if status == "accept":
            accept_ids.add(lid)
        elif status == "reject":
            reject_ids.add(lid)
        elif status == "reject-default":
            reject_default_ids.add(lid)
        else:
            print(f"[providers] unknown licence status {status!r} for {lid!r}", file=sys.stderr)

    return Policy(
        accept_ids=accept_ids,
        reject_ids=reject_ids,
        reject_default_ids=reject_default_ids,
        require_attribution_credits=data.get("require_attribution_credits", False),
        policy_path=path,
    )


# ── HTTP helpers ──────────────────────────────────────────────────────────────

_UA = "WFAssetBrowser/0.2 (github.com/worldfoundry)"


def _http_get(url: str, headers: Optional[dict] = None, timeout: int = 30) -> bytes:
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_json(url: str, headers: Optional[dict] = None) -> object:
    return json.loads(_http_get(url, headers=headers))


# ── Manifest writing ──────────────────────────────────────────────────────────

def _write_manifest(candidate: AssetCandidate, dest_dir: Path, download_url: str) -> dict:
    m = {
        "licence_id":           candidate.licence_id,
        "attribution_required": candidate.attribution_required,
        "attribution_string":   candidate.attribution_string,
        "licence_url":          _licence_url(candidate.licence_id),
        "provider":             candidate.provider,
        "provider_id":          candidate.provider_id,
        "download_date":        date.today().isoformat(),
        "original_url":         candidate.original_url,
        "download_url":         download_url,
        "derived_from":         [],
    }
    (dest_dir / "manifest.json").write_text(
        json.dumps(m, indent=2), encoding="utf-8"
    )
    return m


# ── ZIP extraction ────────────────────────────────────────────────────────────

def _extract_gltf_from_zip(zip_bytes: bytes, dest_dir: Path, provider: str, asset_id: str) -> Path:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        target = next(
            (n for n in names if n.endswith(".glb")),
            next((n for n in names if n.endswith(".gltf")), None),
        )
        if target is None:
            raise RuntimeError(f"{provider}: no .glb/.gltf in ZIP for {asset_id!r}")
        basename = os.path.basename(target) or "model.glb"
        out_path = dest_dir / basename
        out_path.write_bytes(zf.read(target))
        return out_path


# ── Provider base class ───────────────────────────────────────────────────────

class Provider(ABC):
    name: str  # set on each subclass

    @abstractmethod
    def search(self, query: str, policy: Policy, limit: int) -> list: ...

    @abstractmethod
    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path: ...


# ── PolyHaven ─────────────────────────────────────────────────────────────────

class PolyHaven(Provider):
    name = "polyhaven"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        if not policy.allows(CC0):
            return []
        time.sleep(1.0)
        data = _get_json("https://api.polyhaven.com/assets?type=models")
        q = query.lower()
        results = []
        for slug in data:
            if q not in slug.lower():
                continue
            results.append(AssetCandidate(
                provider="polyhaven",
                provider_id=slug,
                title=slug.replace("-", " "),
                thumbnail_url=f"https://cdn.polyhaven.com/asset_img/thumbs/{slug}.png?width=256",
                licence_id=CC0,
                download_url=f"https://api.polyhaven.com/files/{slug}",
                original_url=f"https://polyhaven.com/a/{slug}",
                attribution_string="",
                attribution_required=False,
            ))
            if len(results) >= limit:
                break
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        files = _get_json(f"https://api.polyhaven.com/files/{candidate.provider_id}")
        gltf_map = files.get("gltf", {})
        dl_url = filename = None
        for res in ("1k", "2k", "4k"):
            entry = gltf_map.get(res, {})
            if entry.get("glb", {}).get("url"):
                dl_url  = entry["glb"]["url"]
                filename = f"{candidate.provider_id}_{res}.glb"
                break
            if entry.get("gltf", {}).get("url"):
                dl_url  = entry["gltf"]["url"]
                filename = f"{candidate.provider_id}_{res}.gltf"
                break
        if not dl_url:
            raise RuntimeError(f"polyhaven: no glTF download for {candidate.provider_id!r}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / filename).write_bytes(_http_get(dl_url))
        _write_manifest(candidate, dest_dir, dl_url)
        return dest_dir / filename


# ── Kenney ────────────────────────────────────────────────────────────────────

_kenney_catalog: Optional[list] = None

def _load_kenney_catalog() -> list:
    global _kenney_catalog
    if _kenney_catalog is None:
        p = Path(__file__).with_name("kenney_catalog.json")
        _kenney_catalog = json.loads(p.read_text(encoding="utf-8"))
    return _kenney_catalog


class Kenney(Provider):
    name = "kenney"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        if not policy.allows(CC0):
            return []
        q = query.lower()
        results = []
        for e in _load_kenney_catalog():
            if not (q in e["title"].lower() or q in e["id"].lower() or
                    any(q in t.lower() for t in e.get("tags", []))):
                continue
            results.append(AssetCandidate(
                provider="kenney",
                provider_id=e["id"],
                title=e["title"],
                thumbnail_url=e["thumbnail_url"],
                licence_id=CC0,
                download_url=e["download_url"],
                original_url=e["original_url"],
                attribution_string="",
                attribution_required=False,
            ))
            if len(results) >= limit:
                break
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        data = _http_get(candidate.download_url)
        out = _extract_gltf_from_zip(data, dest_dir, "kenney", candidate.provider_id)
        _write_manifest(candidate, dest_dir, candidate.download_url)
        return out


# ── AmbientCG ─────────────────────────────────────────────────────────────────

class AmbientCG(Provider):
    name = "ambientcg"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        if not policy.allows(CC0):
            return []
        time.sleep(0.5)
        url = (
            "https://ambientcg.com/api/v2/full_json"
            f"?type=3DModel&licence=CC0+1.0"
            f"&q={urllib.parse.quote(query)}&limit={limit}"
        )
        data = _get_json(url)
        results = []
        for a in data.get("foundAssets", []):
            lid = licence_from_raw(a.get("licence", ""))
            if not policy.allows(lid):
                continue
            aid = a["assetId"]
            results.append(AssetCandidate(
                provider="ambientcg",
                provider_id=aid,
                title=a.get("displayName", aid),
                thumbnail_url=a.get("previewImageUrl") or "",
                licence_id=lid,
                download_url=f"https://ambientcg.com/api/v2/full_json?id={aid}&downloadType=zip",
                original_url=f"https://ambientcg.com/view?id={aid}",
                attribution_string="",
                attribution_required=False,
            ))
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        aid = candidate.provider_id
        info = _get_json(
            f"https://ambientcg.com/api/v2/full_json?id={aid}&downloadType=zip"
        )
        assets = info.get("foundAssets", [])
        if not assets:
            raise RuntimeError(f"ambientcg: asset {aid!r} not found")
        folders = assets[0].get("downloadFolders", {})
        zip_url = None
        for pref in ("1K-JPG", "2K-JPG", "1K-PNG", "2K-PNG"):
            link = folders.get(pref, {}).get("downloadLink")
            if link:
                zip_url = link
                break
        if not zip_url:
            for entry in folders.values():
                if entry.get("downloadLink"):
                    zip_url = entry["downloadLink"]
                    break
        if not zip_url:
            raise RuntimeError(f"ambientcg: no download link for {aid!r}")
        data = _http_get(zip_url)
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = _extract_gltf_from_zip(data, dest_dir, "ambientcg", aid)
        _write_manifest(candidate, dest_dir, zip_url)
        return out


# ── Quaternius ────────────────────────────────────────────────────────────────

_quaternius_catalog: Optional[list] = None

def _load_quaternius_catalog() -> list:
    global _quaternius_catalog
    if _quaternius_catalog is None:
        p = Path(__file__).with_name("quaternius_catalog.json")
        _quaternius_catalog = json.loads(p.read_text(encoding="utf-8"))
    return _quaternius_catalog


class Quaternius(Provider):
    name = "quaternius"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        if not policy.allows(CC0):
            return []
        q = query.lower()
        results = []
        for e in _load_quaternius_catalog():
            if not (q in e["title"].lower() or q in e["id"].lower() or
                    any(q in t.lower() for t in e.get("tags", []))):
                continue
            results.append(AssetCandidate(
                provider="quaternius",
                provider_id=e["id"],
                title=e["title"],
                thumbnail_url=e["thumbnail_url"],
                licence_id=CC0,
                download_url=e["download_url"],
                original_url=e["original_url"],
                attribution_string="",
                attribution_required=False,
            ))
            if len(results) >= limit:
                break
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        data = _http_get(candidate.download_url)
        out = _extract_gltf_from_zip(data, dest_dir, "quaternius", candidate.provider_id)
        _write_manifest(candidate, dest_dir, candidate.download_url)
        return out


# ── OpenGameArt ───────────────────────────────────────────────────────────────

class OpenGameArt(Provider):
    name = "opengameart"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        if not policy.allows(CC0):
            return []
        time.sleep(1.0)
        url = (
            f"https://opengameart.org/api/assets"
            f"?field_art_type=3&keys={urllib.parse.quote(query)}&limit={limit * 3}"
        )
        try:
            data = _get_json(url)
        except Exception:
            return []
        results = []
        for node_wrap in data.get("nodes", []):
            a = node_wrap.get("node", {})
            lid = licence_from_raw(a.get("field_art_licence") or "")
            if not policy.allows(lid):
                continue
            nid = a.get("nid", "")
            results.append(AssetCandidate(
                provider="opengameart",
                provider_id=nid,
                title=a.get("title", nid),
                thumbnail_url=a.get("field_preview_image") or "",
                licence_id=lid,
                download_url=f"https://opengameart.org/node/{nid}",
                original_url=f"https://opengameart.org/node/{nid}",
                attribution_string="",
                attribution_required=False,
                lower_trust=True,
            ))
            if len(results) >= limit:
                break
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        html = _http_get(candidate.download_url).decode("utf-8", errors="replace")
        dl_url = _oga_extract_link(html)
        if not dl_url:
            raise RuntimeError(
                f"opengameart: no downloadable file found for {candidate.provider_id!r}"
            )
        data = _http_get(dl_url)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = dl_url.split("/")[-1] or "asset.glb"
        out = dest_dir / filename
        out.write_bytes(data)
        _write_manifest(candidate, dest_dir, dl_url)
        return out


def _oga_extract_link(html: str) -> Optional[str]:
    for ext in (".glb", ".gltf", ".zip", ".obj"):
        pos = html.find(ext)
        if pos == -1:
            continue
        prefix = html[: pos + len(ext)]
        href_pos = prefix.rfind('href="')
        if href_pos == -1:
            continue
        return prefix[href_pos + 6:].strip('"')
    return None


# ── Sketchfab ─────────────────────────────────────────────────────────────────

class Sketchfab(Provider):
    name = "sketchfab"

    def search(self, query: str, policy: Policy, limit: int) -> list:
        time.sleep(1.0)
        url = (
            f"https://api.sketchfab.com/v3/models"
            f"?q={urllib.parse.quote(query)}"
            f"&downloadable=true&count={limit}&sort_by=-likeCount"
        )
        data = _get_json(url)
        results = []
        for m in data.get("results", []):
            slug = (m.get("license") or {}).get("slug", "")
            lid  = _SKETCHFAB_SLUGS.get(slug, UNKNOWN)
            if not policy.allows(lid):
                continue
            uid      = m["uid"]
            user     = m.get("user", {})
            author   = user.get("displayName") or user.get("username", "")
            view_url = m.get("viewerUrl", "")
            attr_req = _requires_attribution(lid)
            attr_str = f'"{m["name"]}" by {author} ({view_url})' if attr_req else ""
            thumbs   = m.get("thumbnails", {}).get("images", [])
            thumb    = next(
                (t["url"] for t in thumbs if t.get("width", 0) >= 256),
                thumbs[-1]["url"] if thumbs else "",
            )
            results.append(AssetCandidate(
                provider="sketchfab",
                provider_id=uid,
                title=m["name"],
                thumbnail_url=thumb,
                licence_id=lid,
                download_url=f"https://api.sketchfab.com/v3/models/{uid}/download",
                original_url=view_url,
                attribution_string=attr_str,
                attribution_required=attr_req,
            ))
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        if not creds.sketchfab_api_key:
            raise RuntimeError(
                "Sketchfab download requires an API key. "
                "Set it in Edit → Preferences → Add-ons → World Foundry."
            )
        url     = f"https://api.sketchfab.com/v3/models/{candidate.provider_id}/download"
        dl_info = _get_json(url, headers={"Authorization": f"Bearer {creds.sketchfab_api_key}"})
        dl_url  = (
            (dl_info.get("gltf") or {}).get("url")
            or (dl_info.get("source") or {}).get("url")
        )
        if not dl_url:
            raise RuntimeError(f"sketchfab: no download URL for {candidate.provider_id!r}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{candidate.provider_id}.glb"
        out.write_bytes(_http_get(dl_url))
        _write_manifest(candidate, dest_dir, dl_url)
        return out


# ── Godot Asset Library ───────────────────────────────────────────────────────

class GodotAssetLibrary(Provider):
    name = "godot"
    _BASE = "https://asset-library.godotengine.org"
    # TODO: update to store.godotengine.org endpoint when Asset Store API ships

    def search(self, query: str, policy: Policy, limit: int) -> list:
        url = (
            f"{self._BASE}/asset"
            f"?filter={urllib.parse.quote(query)}"
            f"&max_results={limit * 3}"
            f"&type=any&support=official,community"
        )
        try:
            data = _get_json(url)
        except Exception:
            return []
        results = []
        for a in data.get("result", []):
            lid = licence_from_raw(a.get("cost") or "")
            if not policy.allows(lid):
                continue
            asset_id = str(a.get("asset_id", ""))
            author   = a.get("author", "")
            attr_req = _requires_attribution(lid)
            attr_str = f'"{a.get("title", asset_id)}" by {author}' if attr_req else ""
            results.append(AssetCandidate(
                provider="godot",
                provider_id=asset_id,
                title=a.get("title", asset_id),
                thumbnail_url=a.get("icon_url") or "",
                licence_id=lid,
                download_url=f"{self._BASE}/asset/{asset_id}",
                original_url=f"https://godotengine.org/asset-library/asset/{asset_id}",
                attribution_string=attr_str,
                attribution_required=attr_req,
                lower_trust=True,
            ))
            if len(results) >= limit:
                break
        return results

    def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path:
        detail = _get_json(candidate.download_url)
        zip_url = detail.get("download_url") or ""
        if not zip_url:
            raise RuntimeError(f"godot: no download_url for asset {candidate.provider_id!r}")
        data = _http_get(zip_url)
        dest_dir.mkdir(parents=True, exist_ok=True)
        _IMPORTABLE = {".glb", ".gltf", ".obj", ".fbx"}
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if Path(name).suffix.lower() in _IMPORTABLE:
                    out = dest_dir / Path(name).name
                    out.write_bytes(zf.read(name))
                    _write_manifest(candidate, dest_dir, zip_url)
                    return out
            sample = zf.namelist()[:10]
        raise RuntimeError(
            f"godot: zip for {candidate.provider_id!r} contains no importable 3D file "
            f"(found: {sample})"
        )


# ── Registry and top-level API ────────────────────────────────────────────────

_ALL_PROVIDERS: dict[str, Provider] = {
    "polyhaven":   PolyHaven(),
    "kenney":      Kenney(),
    "ambientcg":   AmbientCG(),
    "quaternius":  Quaternius(),
    "opengameart": OpenGameArt(),
    "sketchfab":   Sketchfab(),
    "godot":       GodotAssetLibrary(),
}

PROVIDER_NAMES = list(_ALL_PROVIDERS)


def search(
    query: str,
    policy: Policy,
    credentials: Optional[Credentials] = None,
    providers: Optional[list] = None,
    limit: int = 50,
) -> list:
    """Search across providers. Mirrors the old wf_asset_provider.search() signature."""
    creds = credentials or Credentials()
    prov_map = (
        {n: _ALL_PROVIDERS[n] for n in providers if n in _ALL_PROVIDERS}
        if providers
        else _ALL_PROVIDERS
    )
    results = []
    for prov in prov_map.values():
        try:
            r = prov.search(query, policy, limit)
            results.extend(c for c in r if policy.allows(c.licence_id))
        except Exception as e:
            print(f"[providers] {prov.name} search failed: {e}", file=sys.stderr)
    return results[:limit]


def download(
    candidate: AssetCandidate,
    dest_dir: str,
    credentials: Optional[Credentials] = None,
) -> tuple:
    """Download candidate to dest_dir/<provider>/<id>/. Returns (path_str, manifest_dict)."""
    creds = credentials or Credentials()
    prov  = _ALL_PROVIDERS.get(candidate.provider)
    if prov is None:
        raise ValueError(f"unknown provider {candidate.provider!r}")
    dest  = Path(dest_dir) / candidate.provider / candidate.provider_id
    path  = prov.download(candidate, dest, creds)
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    return str(path), manifest
