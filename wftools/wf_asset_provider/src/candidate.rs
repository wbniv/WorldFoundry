use serde::{Deserialize, Serialize};
use crate::licence::LicenceId;

/// One asset returned by a provider's search call, before download.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetCandidate {
    /// Stable identifier string used by this provider (e.g. `"medieval-tree-04"`).
    pub provider_id: String,

    /// Slug identifying the provider (e.g. `"polyhaven"`, `"kenney"`).
    pub provider: String,

    /// Human-readable asset title.
    pub title: String,

    /// URL to a thumbnail image (JPEG/PNG, typically 256×256 or 512×512).
    pub thumbnail_url: String,

    /// Canonical licence after mapping through `LicenceId::from_raw`.
    pub licence_id: LicenceId,

    /// Direct download URL for the primary asset file (typically `.glb` or `.zip`).
    pub download_url: String,

    /// Permalink to the asset on the provider's website.
    pub original_url: String,

    /// Attribution credit string if the licence requires it; empty otherwise.
    pub attribution_string: String,

    /// Whether the licence requires this asset to be credited.
    pub attribution_required: bool,

    /// Provider reports this asset as coming from an open-upload bazaar with
    /// weaker licence-accuracy guarantees.  Surfaced as a warning in the UI.
    pub lower_trust: bool,
}
