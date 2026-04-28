/// Quaternius provider — https://quaternius.com/
///
/// No public search API.  Static curated catalog of CC0 model packs.
/// All assets are CC0; packs are distributed as ZIPs.

use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct Quaternius {
    client: RateLimitedClient,
}

impl Quaternius {
    pub fn new() -> Self {
        Self {
            client: RateLimitedClient::new("quaternius", 2.0),
        }
    }
}

#[derive(Deserialize)]
struct CatalogEntry {
    id: String,
    title: String,
    thumbnail_url: String,
    download_url: String,
    original_url: String,
    tags: Vec<String>,
}

static CATALOG_JSON: &str = include_str!("quaternius_catalog.json");

fn load_catalog() -> Vec<CatalogEntry> {
    serde_json::from_str(CATALOG_JSON).unwrap_or_default()
}

impl Provider for Quaternius {
    fn name(&self) -> &str { "quaternius" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        let q = query.to_ascii_lowercase();
        let results = load_catalog()
            .into_iter()
            .filter(|e| {
                e.title.to_ascii_lowercase().contains(&q)
                    || e.id.to_ascii_lowercase().contains(&q)
                    || e.tags.iter().any(|t| t.to_ascii_lowercase().contains(&q))
            })
            .take(limit)
            .map(|e| AssetCandidate {
                provider_id: e.id,
                provider: "quaternius".to_string(),
                title: e.title,
                thumbnail_url: e.thumbnail_url,
                licence_id: LicenceId::Cc0_1_0,
                download_url: e.download_url,
                original_url: e.original_url,
                attribution_string: String::new(),
                attribution_required: false,
                lower_trust: false,
            })
            .collect();

        Ok(results)
    }

    fn download(&self, candidate: &AssetCandidate, dest_dir: &Path) -> Result<(PathBuf, Manifest), AssetError> {
        let bytes = self.client.get_bytes(&candidate.download_url)?;
        std::fs::create_dir_all(dest_dir)?;
        let asset_path = extract_gltf_from_zip(&bytes, dest_dir, &candidate.provider_id)?;

        let manifest = Manifest {
            licence_id: "CC0-1.0".to_string(),
            attribution_required: false,
            attribution_string: String::new(),
            licence_url: "https://creativecommons.org/publicdomain/zero/1.0/".to_string(),
            provider: "quaternius".to_string(),
            provider_id: candidate.provider_id.clone(),
            download_date: today_iso(),
            original_url: candidate.original_url.clone(),
            download_url: candidate.download_url.clone(),
            derived_from: Vec::new(),
        };
        manifest.write(dest_dir)?;
        Ok((asset_path, manifest))
    }
}

fn extract_gltf_from_zip(zip_bytes: &[u8], dest_dir: &Path, asset_id: &str) -> Result<PathBuf, AssetError> {
    use std::io::Cursor;
    let cursor = Cursor::new(zip_bytes);
    let mut archive = zip::ZipArchive::new(cursor).map_err(|e| AssetError::ProviderFailed {
        provider: "quaternius".to_string(),
        message: format!("ZIP open failed: {e}"),
    })?;

    let names: Vec<String> = (0..archive.len())
        .filter_map(|i| archive.by_index(i).ok().map(|f| f.name().to_string()))
        .collect();

    let name = names.iter()
        .find(|n| n.ends_with(".glb") || n.ends_with(".gltf"))
        .ok_or_else(|| AssetError::ProviderFailed {
            provider: "quaternius".to_string(),
            message: format!("no glTF in ZIP for {asset_id:?}"),
        })?
        .clone();

    let mut file = archive.by_name(&name).map_err(|e| AssetError::ProviderFailed {
        provider: "quaternius".to_string(),
        message: format!("{e}"),
    })?;
    let basename = Path::new(&name).file_name().unwrap_or_default().to_string_lossy().to_string();
    let out_path = dest_dir.join(basename);
    let mut out = std::fs::File::create(&out_path)?;
    std::io::copy(&mut file, &mut out)?;
    Ok(out_path)
}
