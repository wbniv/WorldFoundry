/// Sketchfab provider — https://api.sketchfab.com/v3/
///
/// Supports CC0 through paid ("Standard") licences on the same search endpoint.
/// Search requires no authentication; download requires a Bearer API token.
/// Rate limit: ~60 req/min; we use 1 req/sec to be conservative.

use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct Sketchfab {
    client: RateLimitedClient,
    api_key: Option<String>,
}

impl Sketchfab {
    pub fn new(api_key: Option<String>) -> Self {
        Self {
            client: RateLimitedClient::new("sketchfab", 1.0),
            api_key,
        }
    }

    fn slug_to_licence(slug: &str) -> LicenceId {
        match slug {
            "0"        => LicenceId::Cc0_1_0,
            "by"       => LicenceId::CcBy4_0,
            "bysa"     => LicenceId::CcBySa4_0,
            "bync"     => LicenceId::CcByNc4_0,
            "byncsa"   => LicenceId::CcByNcSa4_0,
            "bynd"     => LicenceId::CcByNd4_0,
            "byncnd"   => LicenceId::CcByNcNd4_0,
            "ed"       => LicenceId::EditorialOnly,
            "sketchfab" => LicenceId::RoyaltyFree,
            _          => LicenceId::Unknown,
        }
    }
}

// ── Sketchfab API response types ─────────────────────────────────────────────

#[derive(Deserialize)]
struct SearchResponse {
    results: Vec<ModelEntry>,
}

#[derive(Deserialize)]
struct ModelEntry {
    uid: String,
    name: String,
    #[serde(default)]
    thumbnails: Thumbnails,
    user: UserEntry,
    license: Option<LicenceEntry>,
    #[serde(rename = "viewerUrl", default)]
    viewer_url: String,
}

#[derive(Deserialize, Default)]
struct Thumbnails {
    #[serde(default)]
    images: Vec<ThumbnailImage>,
}

#[derive(Deserialize)]
struct ThumbnailImage {
    url: String,
    #[serde(default)]
    width: u32,
}

#[derive(Deserialize)]
struct UserEntry {
    #[serde(default)]
    username: String,
    #[serde(rename = "displayName", default)]
    display_name: String,
}

#[derive(Deserialize)]
struct LicenceEntry {
    slug: String,
}

#[derive(Deserialize)]
struct DownloadResponse {
    gltf: Option<DownloadUrl>,
    source: Option<DownloadUrl>,
}

#[derive(Deserialize)]
struct DownloadUrl {
    url: String,
}

// ── Provider impl ─────────────────────────────────────────────────────────────

impl Provider for Sketchfab {
    fn name(&self) -> &str { "sketchfab" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        // Encode query: replace spaces with + for URL safety.
        let encoded = query.split_whitespace().collect::<Vec<_>>().join("+");
        let url = format!(
            "https://api.sketchfab.com/v3/models?q={encoded}&downloadable=true&count={limit}&sort_by=-likeCount"
        );

        let response: SearchResponse = self.client.get_json(&url)?;
        let mut results = Vec::new();

        for model in response.results {
            let licence_id = model.license.as_ref()
                .map(|l| Self::slug_to_licence(&l.slug))
                .unwrap_or(LicenceId::Unknown);

            if !policy.allows(&licence_id) {
                continue;
            }

            let thumbnail_url = model.thumbnails.images.iter()
                .find(|img| img.width >= 256)
                .or_else(|| model.thumbnails.images.last())
                .map(|img| img.url.clone())
                .unwrap_or_default();

            let author = if model.user.display_name.is_empty() {
                model.user.username.clone()
            } else {
                model.user.display_name.clone()
            };

            let attribution_required = licence_id.requires_attribution();
            let attribution_string = if attribution_required {
                format!("\"{}\" by {} ({})", model.name, author, model.viewer_url)
            } else {
                String::new()
            };

            results.push(AssetCandidate {
                provider_id:         model.uid.clone(),
                provider:            "sketchfab".to_string(),
                title:               model.name.clone(),
                thumbnail_url,
                licence_id,
                download_url:        format!("https://api.sketchfab.com/v3/models/{}/download", model.uid),
                original_url:        model.viewer_url.clone(),
                attribution_string,
                attribution_required,
                lower_trust:         false,
            });
        }

        Ok(results)
    }

    fn download(&self, candidate: &AssetCandidate, dest_dir: &Path) -> Result<(PathBuf, Manifest), AssetError> {
        let api_key = self.api_key.as_deref().ok_or_else(|| AssetError::AuthRequired {
            provider: "sketchfab".to_string(),
        })?;

        let url = format!("https://api.sketchfab.com/v3/models/{}/download", candidate.provider_id);
        let dl: DownloadResponse = self.client.get_json_authed(&url, api_key)?;

        let download_url = dl.gltf.as_ref()
            .or(dl.source.as_ref())
            .map(|u| u.url.as_str())
            .ok_or_else(|| AssetError::ProviderFailed {
                provider: "sketchfab".to_string(),
                message: format!("no glTF download URL in response for {}", candidate.provider_id),
            })?;

        let bytes = self.client.get_bytes(download_url)?;
        std::fs::create_dir_all(dest_dir)?;

        let filename = format!("{}.glb", candidate.provider_id);
        let asset_path = dest_dir.join(&filename);
        std::fs::write(&asset_path, &bytes)?;

        let manifest = Manifest {
            licence_id:            candidate.licence_id.as_str().to_string(),
            attribution_required:  candidate.attribution_required,
            attribution_string:    candidate.attribution_string.clone(),
            licence_url:           candidate.licence_id.licence_url().to_string(),
            provider:              "sketchfab".to_string(),
            provider_id:           candidate.provider_id.clone(),
            download_date:         today_iso(),
            original_url:          candidate.original_url.clone(),
            download_url:          download_url.to_string(),
            derived_from:          Vec::new(),
        };

        manifest.write(dest_dir)?;
        Ok((asset_path, manifest))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slug_mapping_cc0() {
        assert_eq!(Sketchfab::slug_to_licence("0"), LicenceId::Cc0_1_0);
    }

    #[test]
    fn slug_mapping_by() {
        assert_eq!(Sketchfab::slug_to_licence("by"),    LicenceId::CcBy4_0);
        assert_eq!(Sketchfab::slug_to_licence("bysa"),  LicenceId::CcBySa4_0);
        assert_eq!(Sketchfab::slug_to_licence("bync"),  LicenceId::CcByNc4_0);
        assert_eq!(Sketchfab::slug_to_licence("byncsa"), LicenceId::CcByNcSa4_0);
        assert_eq!(Sketchfab::slug_to_licence("bynd"),  LicenceId::CcByNd4_0);
        assert_eq!(Sketchfab::slug_to_licence("byncnd"), LicenceId::CcByNcNd4_0);
    }

    #[test]
    fn slug_mapping_editorial() {
        assert_eq!(Sketchfab::slug_to_licence("ed"), LicenceId::EditorialOnly);
    }

    #[test]
    fn slug_mapping_paid() {
        assert_eq!(Sketchfab::slug_to_licence("sketchfab"), LicenceId::RoyaltyFree);
    }

    #[test]
    fn slug_mapping_unknown() {
        assert_eq!(Sketchfab::slug_to_licence("something-new"), LicenceId::Unknown);
    }
}
