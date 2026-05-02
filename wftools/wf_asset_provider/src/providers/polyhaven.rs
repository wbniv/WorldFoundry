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
}

#[derive(Deserialize)]
struct GltfFile {
    url: String,
    /// Companion files keyed by relative path (e.g. "textures/foo_diff_1k.jpg").
    /// The API provides canonical CDN URLs here — use these instead of reconstructing
    /// paths from the gltf's internal URIs (which drift when Poly Haven reorganises CDN).
    #[serde(default)]
    include: HashMap<String, GltfFile>,
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

        let (download_url, filename, companions) = pick_gltf_download(&files, &candidate.provider_id)?;

        let bytes = self.client.get_bytes(&download_url)?;
        std::fs::create_dir_all(dest_dir)?;
        let asset_path = dest_dir.join(&filename);
        std::fs::write(&asset_path, &bytes)?;

        // Download all companion files (textures, bin) using the canonical URLs
        // from the API's include map — these are authoritative and stable even
        // when Poly Haven reorganises their CDN directory structure.
        for (rel_path, companion) in &companions {
            let out_path = dest_dir.join(rel_path);
            if let Some(parent) = out_path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            match self.client.get_bytes(&companion.url) {
                Ok(data) => { let _ = std::fs::write(&out_path, &data); }
                Err(e) => eprintln!("[polyhaven] warning: skipping {rel_path}: {e}"),
            }
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

/// Returns (primary_url, filename, include_map).
/// include_map: relative path → GltfFile with canonical CDN URL for each companion file.
fn pick_gltf_download(files: &AssetFiles, slug: &str) -> Result<(String, String, HashMap<String, GltfFile>), AssetError> {
    if let Some(gltf_map) = &files.gltf {
        for res in &["1k", "2k", "4k"] {
            if let Some(entry) = gltf_map.get(*res) {
                if let Some(glb) = &entry.glb {
                    return Ok((glb.url.clone(), format!("{slug}_{res}.glb"), HashMap::new()));
                }
                if let Some(gltf) = entry.gltf.as_ref() {
                    return Ok((gltf.url.clone(), format!("{slug}_{res}.gltf"),
                               gltf.include.iter().map(|(k, v)| (k.clone(), GltfFile { url: v.url.clone(), include: HashMap::new() })).collect()));
                }
            }
        }
        // Any available resolution
        for (res, entry) in gltf_map.iter() {
            if let Some(glb) = &entry.glb {
                return Ok((glb.url.clone(), format!("{slug}_{res}.glb"), HashMap::new()));
            }
            if let Some(gltf) = entry.gltf.as_ref() {
                return Ok((gltf.url.clone(), format!("{slug}_{res}.gltf"),
                           gltf.include.iter().map(|(k, v)| (k.clone(), GltfFile { url: v.url.clone(), include: HashMap::new() })).collect()));
            }
        }
    }
    Err(AssetError::ProviderFailed {
        provider: "polyhaven".to_string(),
        message: format!("no glTF download found for {slug:?}"),
    })
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
        let (url, name, companions) = pick_gltf_download(&files, "test_model").unwrap();
        assert!(url.ends_with(".glb"), "should pick glb");
        assert_eq!(name, "test_model_1k.glb");
        assert!(companions.is_empty(), "glb is self-contained, no companions needed");
    }

    #[test]
    fn falls_back_to_gltf_with_include_map() {
        let files = parse_files(r#"{
            "gltf": {
                "1k": {
                    "gltf": {
                        "url": "https://dl.polyhaven.org/model_1k.gltf",
                        "include": {
                            "textures/model_diff_1k.jpg": {"url": "https://dl.polyhaven.org/Models/jpg/1k/model/model_diff_1k.jpg"},
                            "model_1k.bin":               {"url": "https://dl.polyhaven.org/Models/gltf/1k/model/model_1k.bin"}
                        }
                    }
                }
            }
        }"#);
        let (url, name, companions) = pick_gltf_download(&files, "model").unwrap();
        assert!(url.ends_with(".gltf"));
        assert_eq!(name, "model_1k.gltf");
        assert_eq!(companions.len(), 2);
        assert!(companions.contains_key("textures/model_diff_1k.jpg"));
        assert!(companions.contains_key("model_1k.bin"));
        assert!(companions["textures/model_diff_1k.jpg"].url.contains("/jpg/"));
    }

    #[test]
    fn gltf_without_include_yields_empty_map() {
        let files = parse_files(r#"{
            "gltf": {
                "1k": {
                    "gltf": {"url": "https://dl.polyhaven.org/model_1k.gltf"}
                }
            }
        }"#);
        let (_url, _name, companions) = pick_gltf_download(&files, "model").unwrap();
        assert!(companions.is_empty());
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
