/// AmbientCG provider — https://ambientcg.com/
///
/// API: https://ambientcg.com/api/v2/full_json
/// We filter to `licence = "CC0 1.0"` and `type = "3DModel"`.
/// Rate limit: 2 req/sec (conservative; no stated limit from AmbientCG).

use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct AmbientCG {
    client: RateLimitedClient,
}

impl AmbientCG {
    pub fn new() -> Self {
        Self {
            client: RateLimitedClient::new("ambientcg", 2.0),
        }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SearchResponse {
    #[serde(default)]
    found_assets: Vec<AmbientCGAsset>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AmbientCGAsset {
    asset_id: String,
    display_name: String,
    #[serde(default)]
    preview_image_url: Option<String>,
    licence: String,
    #[serde(default)]
    download_folders: serde_json::Value,
}

impl Provider for AmbientCG {
    fn name(&self) -> &str { "ambientcg" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        let url = format!(
            "https://ambientcg.com/api/v2/full_json?type=3DModel&licence=CC0+1.0&q={}&limit={}",
            urlenc(query),
            limit,
        );
        let resp: SearchResponse = self.client.get_json(&url)?;

        let results = resp
            .found_assets
            .into_iter()
            .filter_map(|a| {
                let licence = LicenceId::from_raw(&a.licence);
                if !policy.allows(&licence) {
                    return None;
                }
                Some(AssetCandidate {
                    provider_id: a.asset_id.clone(),
                    provider: "ambientcg".to_string(),
                    title: a.display_name,
                    thumbnail_url: a.preview_image_url.unwrap_or_default(),
                    licence_id: licence,
                    download_url: format!("https://ambientcg.com/api/v2/full_json?id={}&downloadType=zip", a.asset_id),
                    original_url: format!("https://ambientcg.com/view?id={}", a.asset_id),
                    attribution_string: String::new(),
                    attribution_required: false,
                    lower_trust: false,
                })
            })
            .collect();

        Ok(results)
    }

    fn download(&self, candidate: &AssetCandidate, dest_dir: &Path) -> Result<(PathBuf, Manifest), AssetError> {
        // Fetch the download info to get the actual ZIP URL
        let info_url = format!(
            "https://ambientcg.com/api/v2/full_json?id={}&downloadType=zip",
            candidate.provider_id
        );
        let resp: SearchResponse = self.client.get_json(&info_url)?;
        let asset = resp.found_assets.into_iter().next().ok_or_else(|| AssetError::ProviderFailed {
            provider: "ambientcg".to_string(),
            message: format!("asset {:?} not found", candidate.provider_id),
        })?;

        // Pick the 1K zip from downloadFolders if available, else any
        let zip_url = pick_zip_url(&asset.download_folders, &candidate.provider_id)?;

        let bytes = self.client.get_bytes(&zip_url)?;
        std::fs::create_dir_all(dest_dir)?;
        let zip_path = dest_dir.join("asset.zip");
        std::fs::write(&zip_path, &bytes)?;

        let asset_path = extract_gltf_from_zip(&bytes, dest_dir, &candidate.provider_id)?;
        let _ = std::fs::remove_file(&zip_path);

        let manifest = Manifest {
            licence_id: "CC0-1.0".to_string(),
            attribution_required: false,
            attribution_string: String::new(),
            licence_url: "https://creativecommons.org/publicdomain/zero/1.0/".to_string(),
            provider: "ambientcg".to_string(),
            provider_id: candidate.provider_id.clone(),
            download_date: today_iso(),
            original_url: candidate.original_url.clone(),
            download_url: zip_url,
            derived_from: Vec::new(),
        };
        manifest.write(dest_dir)?;
        Ok((asset_path, manifest))
    }
}

fn pick_zip_url(folders: &serde_json::Value, asset_id: &str) -> Result<String, AssetError> {
    // AmbientCG downloadFolders is a map of resolution → {downloadLink, ...}
    // Prefer "1K-JPG" then "2K-JPG" then any
    if let Some(obj) = folders.as_object() {
        for pref in &["1K-JPG", "2K-JPG", "1K-PNG", "2K-PNG"] {
            if let Some(entry) = obj.get(*pref) {
                if let Some(link) = entry.get("downloadLink").and_then(|v| v.as_str()) {
                    return Ok(link.to_string());
                }
            }
        }
        // Fall through to any available
        for (_res, entry) in obj {
            if let Some(link) = entry.get("downloadLink").and_then(|v| v.as_str()) {
                return Ok(link.to_string());
            }
        }
    }
    Err(AssetError::ProviderFailed {
        provider: "ambientcg".to_string(),
        message: format!("no download link found for {asset_id:?}"),
    })
}

fn extract_gltf_from_zip(zip_bytes: &[u8], dest_dir: &Path, asset_id: &str) -> Result<PathBuf, AssetError> {
    use std::io::Cursor;
    let cursor = Cursor::new(zip_bytes);
    let mut archive = zip::ZipArchive::new(cursor).map_err(|e| AssetError::ProviderFailed {
        provider: "ambientcg".to_string(),
        message: format!("ZIP open failed: {e}"),
    })?;

    let names: Vec<String> = (0..archive.len())
        .filter_map(|i| archive.by_index(i).ok().map(|f| f.name().to_string()))
        .collect();

    let name = names.iter()
        .find(|n| n.ends_with(".glb") || n.ends_with(".gltf"))
        .ok_or_else(|| AssetError::ProviderFailed {
            provider: "ambientcg".to_string(),
            message: format!("no glTF in ZIP for {asset_id:?}"),
        })?
        .clone();

    let mut file = archive.by_name(&name).map_err(|e| AssetError::ProviderFailed {
        provider: "ambientcg".to_string(),
        message: format!("{e}"),
    })?;
    let basename = Path::new(&name).file_name().unwrap_or_default().to_string_lossy().to_string();
    let out_path = dest_dir.join(basename);
    let mut out = std::fs::File::create(&out_path)?;
    std::io::copy(&mut file, &mut out)?;
    Ok(out_path)
}

fn urlenc(s: &str) -> String {
    s.chars().map(|c| {
        if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c.to_string() }
        else { format!("%{:02X}", c as u32) }
    }).collect()
}
