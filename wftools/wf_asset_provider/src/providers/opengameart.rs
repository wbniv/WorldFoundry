/// OpenGameArt provider — https://opengameart.org/
///
/// The Drupal JSON API endpoint (/api/assets) was removed; we now scrape the
/// art-search-advanced HTML page (field_art_type_tid[]=10 for 3D, licence 284 = CC0).
/// Licence quality is mixed; assets are marked `lower_trust = true`.
/// Download: scrape the node page for direct file links.

use std::path::{Path, PathBuf};
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

impl Provider for OpenGameArt {
    fn name(&self) -> &str { "opengameart" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        // Scrape the HTML search page: type 10 = 3D art, licence 284 = CC0
        // (The old /api/assets JSON endpoint was removed)
        let url = format!(
            "https://opengameart.org/art-search-advanced?field_art_type_tid%5B%5D=10&field_art_licence_version_tid%5B%5D=284&keys={}",
            urlenc(query),
        );

        let html_bytes = self.client.get_bytes(&url).unwrap_or_default();
        let html = String::from_utf8_lossy(&html_bytes);

        let mut slugs = extract_content_slugs(&html, limit);

        // If the search didn't return the query as an exact slug match, try a direct
        // content page fetch (handles CLI download where query == provider_id).
        let query_is_slug = query.chars().all(|c| c.is_ascii_alphanumeric() || c == '-');
        if query_is_slug && !slugs.iter().any(|(s, _)| s == query) {
            slugs.insert(0, (query.to_string(), query.replace('-', " ")));
        }

        let results = slugs
            .into_iter()
            .take(limit)
            .map(|(slug, title)| AssetCandidate {
                provider_id: slug.clone(),
                provider: "opengameart".to_string(),
                title,
                thumbnail_url: String::new(),
                licence_id: LicenceId::Cc0_1_0,
                download_url: format!("https://opengameart.org/content/{slug}"),
                original_url: format!("https://opengameart.org/content/{slug}"),
                attribution_string: String::new(),
                attribution_required: false,
                lower_trust: true,
            })
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

        // If it's a ZIP, extract the 3D file from inside it.
        let asset_path = if download_url.to_ascii_lowercase().ends_with(".zip") {
            extract_from_zip(&bytes, dest_dir, &candidate.provider_id)?
        } else {
            let filename = download_url.split('/').last().unwrap_or("asset.glb").to_string();
            let path = dest_dir.join(&filename);
            std::fs::write(&path, &bytes)?;
            path
        };

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

/// Extract (slug, title) pairs from OGA art-search-advanced HTML.
/// Navigation links have title="..." attributes; asset results do not — skip those.
fn extract_content_slugs(html: &str, limit: usize) -> Vec<(String, String)> {
    let mut seen = std::collections::HashSet::new();
    let mut results = Vec::new();
    // OGA asset results: href="/content/<slug>">Title<  (no title= attribute)
    // Navigation links:  href="/content/faq" title="...">FAQ<  (has title= attribute)
    for part in html.split("href=\"/content/") {
        if results.len() >= limit { break; }
        let Some(end) = part.find('"') else { continue };
        let slug = part[..end].to_string();
        if slug.is_empty() || slug.contains('/') || !slug.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
            continue;
        }
        // The char immediately after the closing " should be '>' for asset links.
        // Navigation links have a space then title="..." before '>'.
        let after_slug = &part[end..];
        if !after_slug.starts_with("\">") {
            continue; // has title= or other attributes — navigation link
        }
        if !seen.insert(slug.clone()) { continue; }
        let title = after_slug.get(2..)
            .and_then(|s| s.find('<').map(|j| &s[..j]))
            .map(|t| html_decode(t.trim()))
            .filter(|t| !t.is_empty())
            .unwrap_or_else(|| slug.replace('-', " "));
        results.push((slug, title));
    }
    results
}

fn html_decode(s: &str) -> String {
    s.replace("&#039;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
}

fn extract_download_link(html: &str) -> Option<String> {
    // Scan for href="...<ext>" patterns; terminate URL at closing quote.
    for ext in &[".glb", ".gltf", ".zip", ".obj"] {
        let mut search_from = 0;
        while let Some(rel) = html[search_from..].find(ext) {
            let pos = search_from + rel;
            let prefix = &html[..pos + ext.len()];
            if let Some(href_pos) = prefix.rfind("href=\"") {
                let after_quote = &prefix[href_pos + 6..];
                // URL must end at the next closing quote
                let url = match after_quote.find('"') {
                    Some(end) => &after_quote[..end],
                    None => after_quote,
                };
                if url.starts_with("http") || url.starts_with("/sites/") {
                    let full = if url.starts_with('/') {
                        format!("https://opengameart.org{url}")
                    } else {
                        url.to_string()
                    };
                    // Sanity-check: the URL should actually end with the extension
                    let lc = full.to_ascii_lowercase();
                    if lc.ends_with(ext) {
                        return Some(full);
                    }
                }
            }
            search_from = pos + ext.len();
        }
    }
    None
}

fn extract_from_zip(zip_bytes: &[u8], dest_dir: &Path, asset_id: &str) -> Result<PathBuf, AssetError> {
    use std::io::Cursor;
    let cursor = Cursor::new(zip_bytes);
    let mut archive = zip::ZipArchive::new(cursor).map_err(|e| AssetError::ProviderFailed {
        provider: "opengameart".to_string(),
        message: format!("ZIP open failed: {e}"),
    })?;

    let names: Vec<String> = (0..archive.len())
        .filter_map(|i| archive.by_index(i).ok().map(|f| f.name().to_string()))
        .collect();

    let primary = names.iter()
        .find(|n| n.ends_with(".glb"))
        .or_else(|| names.iter().find(|n| n.ends_with(".gltf")))
        .or_else(|| names.iter().find(|n| n.ends_with(".obj")))
        .ok_or_else(|| AssetError::ProviderFailed {
            provider: "opengameart".to_string(),
            message: format!("no usable 3D file in ZIP for {asset_id:?}"),
        })?
        .clone();

    let mut primary_out: Option<PathBuf> = None;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| AssetError::ProviderFailed {
            provider: "opengameart".to_string(),
            message: format!("ZIP index {i}: {e}"),
        })?;
        let zip_name = file.name().to_string();
        let basename = std::path::Path::new(&zip_name)
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
        provider: "opengameart".to_string(),
        message: format!("failed to extract {primary:?}"),
    })
}

fn urlenc(s: &str) -> String {
    s.chars().map(|c| {
        if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c.to_string() }
        else { format!("%{:02X}", c as u32) }
    }).collect()
}
