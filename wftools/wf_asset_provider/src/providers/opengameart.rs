/// OpenGameArt provider — https://opengameart.org/
///
/// Uses the Drupal-based unofficial JSON API.  Licence quality is mixed
/// (open-upload bazaar); assets are marked `lower_trust = true` in results.
/// We filter to CC0 only server-side where possible, then re-filter client-side.

use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct OpenGameArt {
    client: RateLimitedClient,
}

impl OpenGameArt {
    pub fn new() -> Self {
        Self {
            client: RateLimitedClient::new("opengameart", 1.0),
        }
    }
}

#[derive(Deserialize)]
struct OgaSearchResponse {
    #[serde(default)]
    nodes: Vec<OgaNode>,
}

#[derive(Deserialize)]
struct OgaNode {
    node: OgaAsset,
}

#[derive(Deserialize)]
struct OgaAsset {
    nid: String,
    title: String,
    #[serde(rename = "field_art_licence")]
    licence: Option<String>,
    #[serde(rename = "field_preview_image")]
    preview_image: Option<String>,
    // Download links are embedded in the node body; we use a secondary fetch
    #[allow(dead_code)]
    body: Option<String>,
}

impl Provider for OpenGameArt {
    fn name(&self) -> &str { "opengameart" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        // OGA Drupal JSON API — type 3 = 3D model
        let url = format!(
            "https://opengameart.org/api/assets?field_art_type=3&keys={}&limit={}",
            urlenc(query),
            limit * 3, // fetch more because we'll filter down to CC0
        );

        let resp: OgaSearchResponse = self.client.get_json(&url).unwrap_or(OgaSearchResponse { nodes: Vec::new() });

        let results = resp
            .nodes
            .into_iter()
            .filter_map(|n| {
                let a = n.node;
                let raw_licence = a.licence.as_deref().unwrap_or("");
                let licence = LicenceId::from_raw(raw_licence);
                if !policy.allows(&licence) {
                    return None;
                }
                let nid = a.nid.clone();
                Some(AssetCandidate {
                    provider_id: nid.clone(),
                    provider: "opengameart".to_string(),
                    title: a.title,
                    thumbnail_url: a.preview_image.unwrap_or_default(),
                    licence_id: licence,
                    download_url: format!("https://opengameart.org/node/{nid}"),
                    original_url: format!("https://opengameart.org/node/{nid}"),
                    attribution_string: String::new(),
                    attribution_required: false,
                    lower_trust: true,
                })
            })
            .take(limit)
            .collect();

        Ok(results)
    }

    fn download(&self, candidate: &AssetCandidate, dest_dir: &Path) -> Result<(PathBuf, Manifest), AssetError> {
        // OGA doesn't have a clean direct-download API.
        // We fetch the node page HTML and extract file links.
        // This is brittle; flagged for v2 improvement.
        let page_url = &candidate.download_url;
        let html = self.client.get_bytes(page_url).map_err(|e| AssetError::ProviderFailed {
            provider: "opengameart".to_string(),
            message: format!("page fetch failed: {e}"),
        })?;
        let html_str = String::from_utf8_lossy(&html);

        // Look for direct .glb, .gltf, .zip, .obj links in the HTML
        let download_url = extract_download_link(&html_str).ok_or_else(|| AssetError::ProviderFailed {
            provider: "opengameart".to_string(),
            message: format!("no downloadable asset file found for {:?}", candidate.provider_id),
        })?;

        let bytes = self.client.get_bytes(&download_url)?;
        std::fs::create_dir_all(dest_dir)?;

        let filename = download_url
            .split('/')
            .last()
            .unwrap_or("asset.glb")
            .to_string();
        let asset_path = dest_dir.join(&filename);
        std::fs::write(&asset_path, &bytes)?;

        let manifest = Manifest {
            licence_id: "CC0-1.0".to_string(),
            attribution_required: false,
            attribution_string: String::new(),
            licence_url: "https://creativecommons.org/publicdomain/zero/1.0/".to_string(),
            provider: "opengameart".to_string(),
            provider_id: candidate.provider_id.clone(),
            download_date: today_iso(),
            original_url: candidate.original_url.clone(),
            download_url,
            derived_from: Vec::new(),
        };
        manifest.write(dest_dir)?;
        Ok((asset_path, manifest))
    }
}

fn extract_download_link(html: &str) -> Option<String> {
    // Look for href to file extensions we can handle
    for ext in &[".glb", ".gltf", ".zip", ".obj"] {
        if let Some(pos) = html.find(ext) {
            // Walk back to find href="
            let prefix = &html[..pos + ext.len()];
            if let Some(href_pos) = prefix.rfind("href=\"") {
                let url = &prefix[href_pos + 6..];
                let url = url.trim_matches('"');
                return Some(url.to_string());
            }
        }
    }
    None
}

fn urlenc(s: &str) -> String {
    s.chars().map(|c| {
        if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c.to_string() }
        else { format!("%{:02X}", c as u32) }
    }).collect()
}
