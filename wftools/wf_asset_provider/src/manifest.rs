use std::path::Path;
use serde::{Deserialize, Serialize};
use crate::error::AssetError;

/// Provenance record written as `manifest.json` next to the downloaded asset.
///
/// Every field is required.  `write_manifest` asserts completeness at write
/// time — missing fields fail loudly rather than silently writing partial data.
#[derive(Debug, Serialize, Deserialize)]
pub struct Manifest {
    pub licence_id: String,
    pub attribution_required: bool,
    pub attribution_string: String,
    pub licence_url: String,
    pub provider: String,
    pub provider_id: String,
    pub download_date: String,   // ISO 8601 date, e.g. "2026-04-28"
    pub original_url: String,
    pub download_url: String,
    /// List of asset IDs this is derived from (empty for a clean first import).
    pub derived_from: Vec<String>,
}

impl Manifest {
    /// Validate that no required string field is empty, then write to `<dir>/manifest.json`.
    pub fn write(&self, dir: &Path) -> Result<(), AssetError> {
        let required_non_empty = [
            ("licence_id",      self.licence_id.as_str()),
            ("licence_url",     self.licence_url.as_str()),
            ("provider",        self.provider.as_str()),
            ("provider_id",     self.provider_id.as_str()),
            ("download_date",   self.download_date.as_str()),
            ("original_url",    self.original_url.as_str()),
            ("download_url",    self.download_url.as_str()),
        ];
        for (field, value) in &required_non_empty {
            if value.is_empty() {
                return Err(AssetError::ManifestField(field.to_string()));
            }
        }

        let path = dir.join("manifest.json");
        let json = serde_json::to_string_pretty(self)
            .map_err(|e| AssetError::Io(std::io::Error::new(std::io::ErrorKind::Other, e)))?;
        std::fs::write(&path, json)?;
        Ok(())
    }
}

/// Read today's date as an ISO 8601 string without pulling in chrono.
pub fn today_iso() -> String {
    // Use the system's `date` command as a no-dep fallback; acceptable because
    // manifest writing is a rare, interactive operation.
    if let Ok(out) = std::process::Command::new("date").arg("+%Y-%m-%d").output() {
        if let Ok(s) = std::str::from_utf8(&out.stdout) {
            return s.trim().to_string();
        }
    }
    "unknown".to_string()
}
