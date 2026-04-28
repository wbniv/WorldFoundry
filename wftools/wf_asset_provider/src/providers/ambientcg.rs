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
    data_type: Option<String>,
    // previewImage is {"64-PNG": "url", "256-PNG": "url", …} — not a plain string
    #[serde(default)]
    preview_image: serde_json::Value,
    // licence field was removed from the API; all AmbientCG assets are CC0
    #[serde(default)]
    licence: Option<String>,
    #[serde(default)]
    download_folders: serde_json::Value,
}

impl Provider for AmbientCG {
    fn name(&self) -> &str { "ambientcg" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        // AmbientCG's `type` param is not a reliable filter; we filter by dataType in Rust.
        // Request more than `limit` to compensate for non-3DModel results being filtered out.
        let url = format!(
            "https://ambientcg.com/api/v2/full_json?q={}&limit={}",
            urlenc(query),
            limit * 4,
        );
        let resp: SearchResponse = self.client.get_json(&url)?;

        // If the general search returned no 3D models but the query looks like an exact
        // asset ID (e.g. "3DBread011"), try fetching it directly by ID.
        let id_candidates = if resp.found_assets.iter().all(|a| a.data_type.as_deref() != Some("3DModel")) {
            let id_url = format!(
                "https://ambientcg.com/api/v2/full_json?id={}&include=downloadData",
                urlenc(query),
            );
            self.client.get_json::<SearchResponse>(&id_url)
                .unwrap_or(SearchResponse { found_assets: Vec::new() })
                .found_assets
        } else {
            Vec::new()
        };

        let results = resp.found_assets.into_iter().chain(id_candidates)
            .into_iter()
            .filter(|a| a.data_type.as_deref() == Some("3DModel"))
            .filter_map(|a| {
                // All AmbientCG assets are CC0; use declared licence if present
                let licence = a.licence.as_deref()
                    .map(LicenceId::from_raw)
                    .unwrap_or(LicenceId::Cc0_1_0);
                if !policy.allows(&licence) {
                    return None;
                }
                Some(AssetCandidate {
                    provider_id: a.asset_id.clone(),
                    provider: "ambientcg".to_string(),
                    title: a.display_name,
                    thumbnail_url: pick_thumbnail(&a.preview_image),
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
        // Fetch asset metadata including download links
        let info_url = format!(
            "https://ambientcg.com/api/v2/full_json?id={}&include=downloadData",
            candidate.provider_id
        );
        let resp: SearchResponse = self.client.get_json(&info_url)?;
        let asset = resp.found_assets.into_iter().next().ok_or_else(|| AssetError::ProviderFailed {
            provider: "ambientcg".to_string(),
            message: format!("asset {:?} not found", candidate.provider_id),
        })?;

        // downloadFolders structure changed: now nested under "default.downloadFiletypeCategories.zip.downloads"
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
    // New API shape: {"default": {"downloadFiletypeCategories": {"zip": {"downloads": [{"downloadLink": "..."}]}}}}
    // Old API shape: {"1K-JPG": {"downloadLink": "..."}, ...}
    // Try new shape first, then fall back to old.
    if let Some(downloads) = folders
        .get("default")
        .and_then(|d| d.get("downloadFiletypeCategories"))
        .and_then(|c| c.get("zip"))
        .and_then(|z| z.get("downloads"))
        .and_then(|d| d.as_array())
    {
        // Prefer smallest (LQ-1K) by looking at "attribute" field
        for pref in &["LQ-1K-JPG", "LQ-2K-JPG", "LQ-1K-PNG"] {
            if let Some(entry) = downloads.iter().find(|e| e.get("attribute").and_then(|a| a.as_str()) == Some(pref)) {
                if let Some(link) = entry.get("downloadLink").and_then(|v| v.as_str()) {
                    return Ok(link.to_string());
                }
            }
        }
        // Any download entry
        if let Some(link) = downloads.iter().find_map(|e| e.get("downloadLink").and_then(|v| v.as_str())) {
            return Ok(link.to_string());
        }
    }

    // Old shape fallback
    if let Some(obj) = folders.as_object() {
        for pref in &["1K-JPG", "2K-JPG", "1K-PNG", "2K-PNG"] {
            if let Some(entry) = obj.get(*pref) {
                if let Some(link) = entry.get("downloadLink").and_then(|v| v.as_str()) {
                    return Ok(link.to_string());
                }
            }
        }
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

    // Prefer glTF, fall back to OBJ (AmbientCG 3D models ship as OBJ+MTL+textures)
    let primary = names.iter()
        .find(|n| n.ends_with(".glb") || n.ends_with(".gltf"))
        .or_else(|| names.iter().find(|n| n.ends_with(".obj")))
        .ok_or_else(|| AssetError::ProviderFailed {
            provider: "ambientcg".to_string(),
            message: format!("no glTF or OBJ in ZIP for {asset_id:?}"),
        })?
        .clone();

    // Extract the primary file and all related files (MTL, textures, etc.)
    let mut primary_out: Option<PathBuf> = None;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| AssetError::ProviderFailed {
            provider: "ambientcg".to_string(),
            message: format!("ZIP index {i}: {e}"),
        })?;
        let zip_name = file.name().to_string();
        // Skip directories
        let basename = Path::new(&zip_name)
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        if basename.is_empty() { continue; }
        let out_path = dest_dir.join(&basename);
        let mut out = std::fs::File::create(&out_path)?;
        std::io::copy(&mut file, &mut out)?;
        if zip_name == primary { primary_out = Some(out_path); }
    }

    primary_out.ok_or_else(|| AssetError::ProviderFailed {
        provider: "ambientcg".to_string(),
        message: format!("failed to extract {primary:?}"),
    })
}

fn pick_thumbnail(preview_image: &serde_json::Value) -> String {
    // previewImage is {"64-PNG": "url", "256-PNG": "url", …}; pick smallest available
    if let Some(obj) = preview_image.as_object() {
        for key in &["64-PNG", "128-PNG", "256-PNG"] {
            if let Some(url) = obj.get(*key).and_then(|v| v.as_str()) {
                return url.to_string();
            }
        }
        // fall through to any available URL
        if let Some(url) = obj.values().find_map(|v| v.as_str()) {
            return url.to_string();
        }
    }
    String::new()
}

fn urlenc(s: &str) -> String {
    s.chars().map(|c| {
        if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c.to_string() }
        else { format!("%{:02X}", c as u32) }
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    // Minimal response matching the current AmbientCG API shape (no `licence` field).
    const SEARCH_RESP_3DMODEL: &str = r#"{
        "foundAssets": [
            {
                "assetId": "TableRound001",
                "displayName": "Round Table",
                "dataType": "3DModel",
                "previewImage": {"64-PNG": "https://example.com/thumb.jpg"},
                "downloadFolders": null
            }
        ]
    }"#;

    const SEARCH_RESP_HDRI: &str = r#"{
        "foundAssets": [
            {
                "assetId": "SkyHDRI001",
                "displayName": "Sky HDRI",
                "dataType": "HDRI",
                "previewImage": {"64-PNG": "https://example.com/sky.jpg"},
                "downloadFolders": null
            }
        ]
    }"#;

    const SEARCH_RESP_MIXED: &str = r#"{
        "foundAssets": [
            {
                "assetId": "TableRound001",
                "displayName": "Round Table",
                "dataType": "3DModel",
                "previewImage": {"64-PNG": "https://example.com/table.jpg"},
                "downloadFolders": null
            },
            {
                "assetId": "SkyHDRI001",
                "displayName": "Sky HDRI",
                "dataType": "HDRI",
                "previewImage": {"64-PNG": "https://example.com/sky.jpg"},
                "downloadFolders": null
            },
            {
                "assetId": "ChairWood001",
                "displayName": "Wooden Chair",
                "dataType": "3DModel",
                "licence": "CC0-1.0",
                "previewImage": {"64-PNG": "https://example.com/chair.jpg"},
                "downloadFolders": null
            }
        ]
    }"#;

    fn cc0_policy() -> crate::policy::Policy {
        crate::policy::load_policy(std::path::Path::new("/nonexistent")).0
    }

    fn parse_resp(json: &str) -> SearchResponse {
        serde_json::from_str(json).expect("parse failed")
    }

    #[test]
    fn parses_3dmodel_without_licence_field() {
        let resp = parse_resp(SEARCH_RESP_3DMODEL);
        assert_eq!(resp.found_assets.len(), 1);
        let a = &resp.found_assets[0];
        assert_eq!(a.asset_id, "TableRound001");
        assert_eq!(a.display_name, "Round Table");
        assert_eq!(a.data_type.as_deref(), Some("3DModel"));
        assert_eq!(pick_thumbnail(&a.preview_image), "https://example.com/thumb.jpg");
        assert!(a.licence.is_none(), "licence field absent in response must be None");
    }

    #[test]
    fn filters_out_hdri_assets() {
        let resp = parse_resp(SEARCH_RESP_MIXED);
        let policy = cc0_policy();
        let only_3d: Vec<_> = resp.found_assets.into_iter()
            .filter(|a| a.data_type.as_deref() == Some("3DModel"))
            .filter_map(|a| {
                let licence = a.licence.as_deref()
                    .map(LicenceId::from_raw)
                    .unwrap_or(LicenceId::Cc0_1_0);
                if !policy.allows(&licence) { return None; }
                Some(a.asset_id)
            })
            .collect();
        assert_eq!(only_3d, vec!["TableRound001", "ChairWood001"]);
    }

    #[test]
    fn pure_hdri_response_yields_no_candidates() {
        let resp = parse_resp(SEARCH_RESP_HDRI);
        let filtered: Vec<_> = resp.found_assets.into_iter()
            .filter(|a| a.data_type.as_deref() == Some("3DModel"))
            .collect();
        assert!(filtered.is_empty());
    }

    #[test]
    fn explicit_licence_field_is_respected() {
        let resp = parse_resp(SEARCH_RESP_MIXED);
        let chair = resp.found_assets.into_iter()
            .find(|a| a.asset_id == "ChairWood001").unwrap();
        assert_eq!(chair.licence.as_deref(), Some("CC0-1.0"));
    }
}
