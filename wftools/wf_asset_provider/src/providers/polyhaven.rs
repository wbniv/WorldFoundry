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

        // Prefer 1k glb for speed, fall back to gltf
        let (download_url, filename) = pick_gltf_download(&files, &candidate.provider_id)?;

        let bytes = self.client.get_bytes(&download_url)?;
        std::fs::create_dir_all(dest_dir)?;
        let asset_path = dest_dir.join(&filename);
        std::fs::write(&asset_path, &bytes)?;

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

fn pick_gltf_download(files: &AssetFiles, slug: &str) -> Result<(String, String), AssetError> {
    // Try 1k first, then 2k, then any resolution
    if let Some(gltf_map) = &files.gltf {
        for res in &["1k", "2k", "4k"] {
            if let Some(entry) = gltf_map.get(*res) {
                if let Some(glb) = &entry.glb {
                    return Ok((glb.url.clone(), format!("{slug}_{res}.glb")));
                }
                if let Some(gltf) = &entry.gltf {
                    return Ok((gltf.url.clone(), format!("{slug}_{res}.gltf")));
                }
            }
        }
        // Any available resolution
        if let Some((res, entry)) = gltf_map.iter().next() {
            if let Some(glb) = &entry.glb {
                return Ok((glb.url.clone(), format!("{slug}_{res}.glb")));
            }
        }
    }
    Err(AssetError::ProviderFailed {
        provider: "polyhaven".to_string(),
        message: format!("no glTF download found for {slug:?}"),
    })
}
