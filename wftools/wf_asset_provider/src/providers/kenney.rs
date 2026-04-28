/// Kenney provider — https://kenney.nl/
///
/// Kenney has no public search API.  We use a curated static catalog embedded
/// in the binary.  Each entry points to a direct ZIP download on kenney.nl.
/// All assets are CC0.

use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::http::RateLimitedClient;
use crate::licence::LicenceId;
use crate::manifest::{Manifest, today_iso};
use crate::policy::Policy;
use crate::provider::Provider;

pub struct Kenney {
    client: RateLimitedClient,
}

impl Kenney {
    pub fn new() -> Self {
        Self {
            client: RateLimitedClient::new("kenney", 2.0),
        }
    }
}

/// A single entry in the curated catalog.
#[derive(Deserialize)]
struct CatalogEntry {
    id: String,
    title: String,
    thumbnail_url: String,
    download_url: String,
    original_url: String,
    tags: Vec<String>,
}

/// Curated catalog of Kenney CC0 model packs.
/// Full catalog lives in kenney_catalog.json, embedded at compile time.
static CATALOG_JSON: &str = include_str!("kenney_catalog.json");

fn load_catalog() -> Vec<CatalogEntry> {
    serde_json::from_str(CATALOG_JSON).unwrap_or_default()
}

impl Provider for Kenney {
    fn name(&self) -> &str { "kenney" }

    fn search(&self, query: &str, policy: &Policy, limit: usize) -> Result<Vec<AssetCandidate>, AssetError> {
        if !policy.allows(&LicenceId::Cc0_1_0) {
            return Ok(Vec::new());
        }

        let q = query.to_ascii_lowercase();
        let catalog = load_catalog();

        let results = catalog
            .into_iter()
            .filter(|e| {
                e.title.to_ascii_lowercase().contains(&q)
                    || e.id.to_ascii_lowercase().contains(&q)
                    || e.tags.iter().any(|t| t.to_ascii_lowercase().contains(&q))
            })
            .take(limit)
            .map(|e| AssetCandidate {
                provider_id: e.id,
                provider: "kenney".to_string(),
                title: e.title,
                thumbnail_url: e.thumbnail_url,
                licence_id: LicenceId::Cc0_1_0,
                download_url: e.download_url.clone(),
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

        // Kenney distributes ZIPs; extract the first .glb or .gltf found
        let asset_path = extract_gltf_from_zip(&bytes, dest_dir, &candidate.provider_id)?;

        let manifest = Manifest {
            licence_id: "CC0-1.0".to_string(),
            attribution_required: false,
            attribution_string: String::new(),
            licence_url: "https://creativecommons.org/publicdomain/zero/1.0/".to_string(),
            provider: "kenney".to_string(),
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

fn extract_gltf_from_zip(
    zip_bytes: &[u8],
    dest_dir: &Path,
    asset_id: &str,
) -> Result<PathBuf, AssetError> {
    use std::io::Cursor;

    let cursor = Cursor::new(zip_bytes);
    let mut archive = zip::ZipArchive::new(cursor).map_err(|e| AssetError::ProviderFailed {
        provider: "kenney".to_string(),
        message: format!("ZIP open failed: {e}"),
    })?;

    // Collect all names first (by_index takes &mut, can't use in filter_map directly)
    let names: Vec<String> = (0..archive.len())
        .filter_map(|i| archive.by_index(i).ok().map(|f| f.name().to_string()))
        .collect();

    let name = names.iter()
        .find(|n| n.ends_with(".glb"))
        .or_else(|| names.iter().find(|n| n.ends_with(".gltf")))
        .ok_or_else(|| AssetError::ProviderFailed {
            provider: "kenney".to_string(),
            message: format!("no .glb or .gltf found in ZIP for {asset_id:?}"),
        })?
        .clone();

    // Determine the directory prefix of the chosen file so we can extract siblings
    let gltf_dir = std::path::Path::new(&name)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    // Extract the chosen file and all siblings in the same ZIP directory
    let mut primary_out: Option<PathBuf> = None;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| AssetError::ProviderFailed {
            provider: "kenney".to_string(),
            message: format!("ZIP index {i}: {e}"),
        })?;
        let zip_name = file.name().to_string();
        let file_dir = std::path::Path::new(&zip_name)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        if file_dir != gltf_dir {
            continue;
        }
        let basename = std::path::Path::new(&zip_name)
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        if basename.is_empty() {
            continue;
        }
        let out_path = dest_dir.join(&basename);
        let mut out = std::fs::File::create(&out_path)?;
        std::io::copy(&mut file, &mut out)?;
        if zip_name == name {
            primary_out = Some(out_path);
        }
    }

    primary_out.ok_or_else(|| AssetError::ProviderFailed {
        provider: "kenney".to_string(),
        message: format!("failed to extract {name:?}"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    fn make_zip(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let mut buf = Vec::new();
        {
            let mut w = zip::ZipWriter::new(std::io::Cursor::new(&mut buf));
            let opts = zip::write::FileOptions::<()>::default()
                .compression_method(zip::CompressionMethod::Stored);
            for (name, data) in entries {
                w.start_file(*name, opts).unwrap();
                w.write_all(data).unwrap();
            }
            w.finish().unwrap();
        }
        buf
    }

    #[test]
    fn extracts_glb_alone() {
        let dir = TempDir::new().unwrap();
        let zip = make_zip(&[
            ("models/chair.glb", b"glb-data"),
        ]);
        let path = extract_gltf_from_zip(&zip, dir.path(), "chair").unwrap();
        assert_eq!(path.file_name().unwrap(), "chair.glb");
        assert_eq!(std::fs::read(&path).unwrap(), b"glb-data");
    }

    #[test]
    fn extracts_gltf_with_bin_sibling() {
        let dir = TempDir::new().unwrap();
        let zip = make_zip(&[
            ("models/chair.gltf", b"gltf-data"),
            ("models/chair.bin",  b"bin-data"),
        ]);
        let path = extract_gltf_from_zip(&zip, dir.path(), "chair").unwrap();
        assert_eq!(path.file_name().unwrap(), "chair.gltf");
        assert!(dir.path().join("chair.bin").exists(), ".bin sibling must be extracted");
    }

    #[test]
    fn ignores_other_format_dirs() {
        // ZIP contains both FBX and glTF subdirs; only the glTF dir should be extracted
        let dir = TempDir::new().unwrap();
        let zip = make_zip(&[
            ("fbx/chair.fbx",        b"fbx-data"),
            ("gltf/chair.gltf",      b"gltf-data"),
            ("gltf/chair.bin",       b"bin-data"),
        ]);
        let path = extract_gltf_from_zip(&zip, dir.path(), "chair").unwrap();
        assert_eq!(path.file_name().unwrap(), "chair.gltf");
        assert!(dir.path().join("chair.bin").exists());
        assert!(!dir.path().join("chair.fbx").exists(), "FBX must not be extracted");
    }

    #[test]
    fn prefers_glb_over_gltf() {
        let dir = TempDir::new().unwrap();
        let zip = make_zip(&[
            ("models/chair.glb",  b"glb-data"),
            ("models/chair.gltf", b"gltf-data"),
        ]);
        let path = extract_gltf_from_zip(&zip, dir.path(), "chair").unwrap();
        assert_eq!(path.file_name().unwrap(), "chair.glb");
    }

    #[test]
    fn error_on_no_gltf_in_zip() {
        let dir = TempDir::new().unwrap();
        let zip = make_zip(&[("readme.txt", b"text")]);
        assert!(extract_gltf_from_zip(&zip, dir.path(), "x").is_err());
    }

    #[test]
    fn search_filters_by_query() {
        let k = Kenney::new();
        let policy = crate::policy::load_policy(std::path::Path::new("/nonexistent")).0;
        // "dungeon" matches both id and title in the catalog
        let results = k.search("dungeon", &policy, 50).unwrap();
        assert!(!results.is_empty(), "catalog should have at least one dungeon entry");
        for r in &results {
            let hay = format!("{} {}", r.title.to_ascii_lowercase(), r.provider_id.to_ascii_lowercase());
            assert!(
                hay.contains("dungeon"),
                "result {hay:?} doesn't match 'dungeon'"
            );
        }
    }

    #[test]
    fn search_empty_query_returns_nothing() {
        let k = Kenney::new();
        let policy = crate::policy::load_policy(std::path::Path::new("/nonexistent")).0;
        let results = k.search("zzznomatch_xyzzy", &policy, 50).unwrap();
        assert!(results.is_empty());
    }
}
