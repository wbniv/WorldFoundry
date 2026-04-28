use std::path::PathBuf;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AssetError {
    #[error("HTTP error from {provider}: {message}")]
    Http { provider: String, message: String },

    #[error("JSON parse error from {provider}: {message}")]
    JsonParse { provider: String, message: String },

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("manifest field {0:?} is empty — refusing to write incomplete provenance")]
    ManifestField(String),

    #[error("policy file {0:?} could not be read: {1}")]
    PolicyRead(PathBuf, String),

    #[error("policy file {0:?} contains invalid TOML: {1}")]
    PolicyParse(PathBuf, String),

    #[error("licence mismatch: asset {asset_id:?} claims {claimed:?} but download indicates {found:?}")]
    LicenceMismatch {
        asset_id: String,
        claimed: String,
        found: String,
    },

    #[error("provider {provider:?} failed after retries: {message}")]
    ProviderFailed { provider: String, message: String },
}
