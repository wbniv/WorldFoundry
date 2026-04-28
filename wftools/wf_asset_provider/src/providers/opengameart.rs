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
        if query_is_slug && !slugs.iter().any(|(s, _, _)| s == query) {
            slugs.insert(0, (query.to_string(), query.replace('-', " "), String::new()));
        }

        let results = slugs
            .into_iter()
            .take(limit)
            .map(|(slug, title, thumb_url)| AssetCandidate {
                provider_id: slug.clone(),
                provider: "opengameart".to_string(),
                title,
                thumbnail_url: thumb_url,
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

/// Extract (slug, title, thumbnail_url) triples from OGA art-search-advanced HTML.
/// Navigation links have title="..." attributes; asset results do not — skip those.
/// The thumbnail is scraped from the <img src="/sites/default/files/..."> that appears
/// in the result row before each content link.
fn extract_content_slugs(html: &str, limit: usize) -> Vec<(String, String, String)> {
    let mut seen = std::collections::HashSet::new();
    let mut results = Vec::new();
    let needle = "href=\"/content/";
    let mut pos = 0;
    while results.len() < limit {
        let Some(rel) = html[pos..].find(needle) else { break };
        let abs = pos + rel;
        let rest = &html[abs + needle.len()..];
        let Some(end) = rest.find('"') else { pos = abs + 1; continue };
        let slug = rest[..end].to_string();
        // validate: no slashes, ascii alnum + hyphen only
        if slug.is_empty() || slug.contains('/') || !slug.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
            pos = abs + 1;
            continue;
        }
        // Asset links: href="/content/<slug>">Title  (no title= attribute before >)
        // Navigation links: href="/content/faq" title="...">  — has space+title= after slug
        let after_slug = &rest[end..];
        if !after_slug.starts_with("\">") {
            pos = abs + 1;
            continue;
        }
        if !seen.insert(slug.clone()) {
            pos = abs + 1;
            continue;
        }
        let title = after_slug.get(2..)
            .and_then(|s| s.find('<').map(|j| &s[..j]))
            .map(|t| html_decode(t.trim()))
            .filter(|t| !t.is_empty())
            .unwrap_or_else(|| slug.replace('-', " "));

        // OGA puts the title link first, then a second anchor with the preview img.
        // Look forward up to 2 kB from the current position.
        let window_end = (abs + 2048).min(html.len());
        let thumb_url = extract_img_url_forward(&html[abs..window_end]);

        results.push((slug, title, thumb_url));
        pos = abs + 1;
    }
    results
}

/// Return the first OGA-hosted <img src=...> found scanning forward through `window`.
/// OGA uses single-quoted src attributes: <img src='...'>.
fn extract_img_url_forward(window: &str) -> String {
    let mut search = window;
    while let Some(img_pos) = search.find("<img ") {
        let chunk = &search[img_pos..];
        for (open, close) in &[("src='", '\''), ("src=\"", '"')] {
            if let Some(src_off) = chunk.find(open) {
                let src_rest = &chunk[src_off + open.len()..];
                if let Some(q) = src_rest.find(*close) {
                    let src = &src_rest[..q];
                    if src.contains("/sites/default/files/") {
                        return if src.starts_with('/') {
                            format!("https://opengameart.org{src}")
                        } else {
                            src.to_string()
                        };
                    }
                }
            }
        }
        search = &search[img_pos + 5..];
    }
    String::new()
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

#[cfg(test)]
mod tests {
    use super::*;

    // Mirrors the real OGA search HTML structure: title link first, preview img link second.
    const OGA_SEARCH_SNIPPET: &str = r#"
      <span class="art-preview-title"><a href="/content/night-table">Night table</a></span>
      </div></div></div>
      <div class="field field-name-field-art-preview">
        <a href="/content/night-table"><img src='https://opengameart.org/sites/default/files/styles/thumbnail/public/uv_0.png' alt='Preview'></a>
      </div>
    "#;

    #[test]
    fn extracts_slug_title_and_thumbnail() {
        let results = extract_content_slugs(OGA_SEARCH_SNIPPET, 5);
        assert_eq!(results.len(), 1, "should find one slug");
        let (slug, title, thumb) = &results[0];
        assert_eq!(slug, "night-table");
        assert_eq!(title, "Night table");
        assert!(thumb.contains("uv_0.png"), "thumbnail URL should contain image filename: {thumb}");
        assert!(thumb.starts_with("https://"), "thumbnail URL should be absolute: {thumb}");
    }

    #[test]
    fn navigation_links_skipped() {
        let html = r#"<a href="/content/faq" title="FAQ">FAQ</a> <a href="/content/night-table">Night table</a>"#;
        let results = extract_content_slugs(html, 5);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].0, "night-table");
    }

    #[test]
    fn no_thumbnail_yields_empty_string() {
        let html = r#"<a href="/content/no-thumb">No thumb</a>"#;
        let results = extract_content_slugs(html, 5);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].2, "", "should be empty when no img in window");
    }
}
