/// Poly Haven provider — https://api.polyhaven.com/
///
/// All Poly Haven assets are CC0-1.0.  The API supports server-side category
/// filtering but not text search; we fetch the full model list and filter
/// client-side by title/slug match.  Rate limit: 1 req/sec (their advisory).

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct PolyHaven {
    client: RateLimitedClient,
}

impl PolyHaven {
    pub fn new() -> Self {
        Self {
            client: RateLimitedClient::new("polyhaven", 1.0),
        }
    }
}

#[derive(Deserialize)]
struct AssetFiles {
    #[serde(default)]
    gltf: Option<HashMap<String, GltfEntry>>,
}

#[derive(Deserialize)]
struct GltfEntry {
    gltf: Option<GltfFile>,
    glb: Option<GltfFile>,
    bin: Option<GltfFile>,
}

#[derive(Deserialize)]
struct GltfFile {
    url: String,
}

impl Provider for PolyHaven {
    fn name(&self) -> &str { "polyhaven" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        // Fetch full model list (type=models keeps it manageable)
        let url = "https://api.polyhaven.com/assets?type=models";
        let list: HashMap<String, serde_json::Value> = self.client.get_json(url)?;

        let q = query.to_ascii_lowercase();
        let mut results = Vec::new();

        for (slug, _) in &list {
            if !slug.to_ascii_lowercase().contains(&q) {
                continue;
            }

            let candidate = AssetCandidate {
                provider_id: slug.clone(),
                provider: "polyhaven".to_string(),
                title: slug.replace('-', " "),
                thumbnail_url: format!("https://cdn.polyhaven.com/asset_img/thumbs/{slug}.png?width=256"),
                licence_id: LicenceId::Cc0_1_0,
                download_url: format!("https://api.polyhaven.com/files/{slug}"),
                original_url: format!("https://polyhaven.com/a/{slug}"),
                attribution_string: String::new(),
                attribution_required: false,
                lower_trust: false,
            };

            results.push(candidate);
            if results.len() >= limit {
                break;
            }
        }

        Ok(results)
    }

    fn download(&self, candidate: &AssetCandidate, dest_dir: &Path) -> Result<(PathBuf, Manifest), AssetError> {
        // Resolve the actual download URL by fetching the /files/<id> endpoint
        let files_url = format!("https://api.polyhaven.com/files/{}", candidate.provider_id);
        let files: AssetFiles = self.client.get_json(&files_url)?;

        // Prefer 1k glb for speed, fall back to gltf + optional companion bin
        let (download_url, filename, bin_url) = pick_gltf_download(&files, &candidate.provider_id)?;

        let bytes = self.client.get_bytes(&download_url)?;
        std::fs::create_dir_all(dest_dir)?;
        let asset_path = dest_dir.join(&filename);
        std::fs::write(&asset_path, &bytes)?;

        // If we downloaded a .gltf, fetch all buffer URIs it references.
        // bin_url from the API is a fallback; parsing the gltf is authoritative.
        if filename.ends_with(".gltf") {
            fetch_gltf_buffers(&self.client, &bytes, dest_dir, &download_url)?;
        } else if let Some(bin_url) = bin_url {
            // .glb shouldn't need this, but keep as a belt-and-suspenders fallback
            let bin_name = std::path::Path::new(&bin_url)
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| format!("{}.bin", candidate.provider_id));
            let bin_bytes = self.client.get_bytes(&bin_url)?;
            std::fs::write(dest_dir.join(&bin_name), &bin_bytes)?;
        }

        let manifest = Manifest {
            licence_id: "CC0-1.0".to_string(),
            attribution_required: false,
            attribution_string: String::new(),
            licence_url: "https://creativecommons.org/publicdomain/zero/1.0/".to_string(),
            provider: "polyhaven".to_string(),
            provider_id: candidate.provider_id.clone(),
            download_date: today_iso(),
            original_url: candidate.original_url.clone(),
            download_url: download_url.clone(),
            derived_from: Vec::new(),
        };

        manifest.write(dest_dir)?;
        Ok((asset_path, manifest))
    }
}

fn pick_gltf_download(files: &AssetFiles, slug: &str) -> Result<(String, String, Option<String>), AssetError> {
    // Returns (primary_url, filename, optional_bin_url)
    if let Some(gltf_map) = &files.gltf {
        for res in &["1k", "2k", "4k"] {
            if let Some(entry) = gltf_map.get(*res) {
                if let Some(glb) = &entry.glb {
                    return Ok((glb.url.clone(), format!("{slug}_{res}.glb"), None));
                }
                if let Some(gltf) = &entry.gltf {
                    let bin_url = entry.bin.as_ref().map(|b| b.url.clone());
                    return Ok((gltf.url.clone(), format!("{slug}_{res}.gltf"), bin_url));
                }
            }
        }
        // Any available resolution
        if let Some((res, entry)) = gltf_map.iter().next() {
            if let Some(glb) = &entry.glb {
                return Ok((glb.url.clone(), format!("{slug}_{res}.glb"), None));
            }
            if let Some(gltf) = &entry.gltf {
                let bin_url = entry.bin.as_ref().map(|b| b.url.clone());
                return Ok((gltf.url.clone(), format!("{slug}_{res}.gltf"), bin_url));
            }
        }
    }
    Err(AssetError::ProviderFailed {
        provider: "polyhaven".to_string(),
        message: format!("no glTF download found for {slug:?}"),
    })
}

/// Parse gltf_bytes as glTF JSON and download all relative buffer + image URIs.
/// base_url is the URL the .gltf was fetched from, used to resolve relative URIs.
fn fetch_gltf_buffers(client: &RateLimitedClient, gltf_bytes: &[u8], dest_dir: &Path, base_url: &str) -> Result<(), AssetError> {
    let json: serde_json::Value = match serde_json::from_slice(gltf_bytes) {
        Ok(v) => v,
        Err(_) => return Ok(()),
    };

    let base = base_url.rfind('/').map(|i| &base_url[..=i]).unwrap_or(base_url);

    let mut uris: Vec<String> = Vec::new();
    for section in &["buffers", "images"] {
        if let Some(arr) = json.get(section).and_then(|v| v.as_array()) {
            for entry in arr {
                if let Some(uri) = entry.get("uri").and_then(|u| u.as_str()) {
                    if !uri.starts_with("data:") {
                        uris.push(uri.to_string());
                    }
                }
            }
        }
    }

    for uri in uris {
        let fetch_url = if uri.starts_with("http://") || uri.starts_with("https://") {
            uri.clone()
        } else {
            format!("{base}{uri}")
        };
        // Preserve relative path (e.g. "textures/foo.png") under dest_dir
        let out_path = dest_dir.join(&uri);
        if let Some(parent) = out_path.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                eprintln!("[polyhaven] warning: could not create dir for {uri}: {e}");
                continue;
            }
        }
        match client.get_bytes(&fetch_url) {
            Ok(bytes) => { let _ = std::fs::write(&out_path, &bytes); }
            Err(e) => eprintln!("[polyhaven] warning: skipping {uri}: {e}"),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_files(json: &str) -> AssetFiles {
        serde_json::from_str(json).expect("parse failed")
    }

    #[test]
    fn prefers_glb_over_gltf() {
        let files = parse_files(r#"{
            "gltf": {
                "1k": {
                    "glb": {"url": "https://cdn.polyhaven.com/model_1k.glb"},
                    "gltf": {"url": "https://cdn.polyhaven.com/model_1k.gltf"},
                    "bin": {"url": "https://cdn.polyhaven.com/model_1k.bin"}
                }
            }
        }"#);
        let (url, name, bin) = pick_gltf_download(&files, "test_model").unwrap();
        assert!(url.ends_with(".glb"), "should pick glb");
        assert_eq!(name, "test_model_1k.glb");
        assert!(bin.is_none(), "glb is self-contained, no bin needed");
    }

    #[test]
    fn falls_back_to_gltf_with_bin() {
        let files = parse_files(r#"{
            "gltf": {
                "1k": {
                    "gltf": {"url": "https://cdn.polyhaven.com/outdoor_table_chair_set_01_1k.gltf"},
                    "bin":  {"url": "https://cdn.polyhaven.com/outdoor_table_chair_set_01_1k.bin"}
                }
            }
        }"#);
        let (url, name, bin) = pick_gltf_download(&files, "outdoor_table_chair_set_01").unwrap();
        assert!(url.ends_with(".gltf"));
        assert_eq!(name, "outdoor_table_chair_set_01_1k.gltf");
        assert_eq!(bin.as_deref(), Some("https://cdn.polyhaven.com/outdoor_table_chair_set_01_1k.bin"));
    }

    #[test]
    fn gltf_without_bin_entry_yields_none_bin() {
        let files = parse_files(r#"{
            "gltf": {
                "1k": {
                    "gltf": {"url": "https://cdn.polyhaven.com/model_1k.gltf"}
                }
            }
        }"#);
        let (_url, _name, bin) = pick_gltf_download(&files, "model").unwrap();
        assert!(bin.is_none());
    }

    #[test]
    fn prefers_1k_over_2k() {
        let files = parse_files(r#"{
            "gltf": {
                "2k": {"glb": {"url": "https://cdn.polyhaven.com/model_2k.glb"}},
                "1k": {"glb": {"url": "https://cdn.polyhaven.com/model_1k.glb"}}
            }
        }"#);
        let (url, name, _) = pick_gltf_download(&files, "model").unwrap();
        assert!(url.contains("1k"), "should pick 1k: {url}");
        assert_eq!(name, "model_1k.glb");
    }

    #[test]
    fn no_gltf_section_returns_error() {
        let files = parse_files(r#"{"hdri": {}}"#);
        assert!(pick_gltf_download(&files, "model").is_err());
    }

    #[test]
    fn search_filters_by_slug() {
        let list_json = r#"{
            "outdoor_table_chair_set_01": {},
            "wooden_chair_01": {},
            "coffee_table_round": {}
        }"#;
        let list: std::collections::HashMap<String, serde_json::Value> =
            serde_json::from_str(list_json).unwrap();
        let q = "table";
        let matched: Vec<_> = list.keys()
            .filter(|k| k.to_ascii_lowercase().contains(q))
            .collect();
        assert_eq!(matched.len(), 2);
        assert!(matched.iter().any(|k| k.contains("outdoor_table")));
        assert!(matched.iter().any(|k| k.contains("coffee_table")));
    }
}
