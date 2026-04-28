/// Canonical licence identifiers used across all WF asset tooling.
///
/// Every provider adapter converts its raw API string to a `LicenceId` here.
/// This is the single source of truth — the pyo3 bindings, CLI, and future
/// wf_audit tool all consume this enum.

use std::fmt;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LicenceId {
    /// Public domain / CC0.  The only licence accepted by v1 providers.
    #[serde(rename = "CC0-1.0")]
    Cc0_1_0,

    /// Creative Commons Attribution 4.0 International.
    #[serde(rename = "CC-BY-4.0")]
    CcBy4_0,

    /// Creative Commons Attribution-ShareAlike 4.0.
    /// Rejected by default: share-alike would contaminate WF derivative.
    #[serde(rename = "CC-BY-SA-4.0")]
    CcBySa4_0,

    /// Creative Commons Attribution-NonCommercial 4.0.
    #[serde(rename = "CC-BY-NC-4.0")]
    CcByNc4_0,

    /// Creative Commons Attribution-NonCommercial-ShareAlike 4.0.
    #[serde(rename = "CC-BY-NC-SA-4.0")]
    CcByNcSa4_0,

    /// GNU General Public License v3.  Share-alike, copyleft.
    #[serde(rename = "GPL-3.0")]
    Gpl3_0,

    /// GNU Lesser General Public License v3.
    #[serde(rename = "LGPL-3.0")]
    Lgpl3_0,

    /// Editorial/press-only licence (used on some Sketchfab assets).
    #[serde(rename = "editorial-only")]
    EditorialOnly,

    /// Royalty-on-revenue clause (custom commercial licences).
    #[serde(rename = "royalty-on-revenue")]
    RoyaltyOnRevenue,

    /// Explicitly unknown — provider did not supply a recognisable licence string.
    /// Assets with this ID will never pass the policy filter.
    #[serde(rename = "unknown")]
    Unknown,
}

impl LicenceId {
    /// Canonical string representation (matches SPDX where possible).
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Cc0_1_0         => "CC0-1.0",
            Self::CcBy4_0         => "CC-BY-4.0",
            Self::CcBySa4_0       => "CC-BY-SA-4.0",
            Self::CcByNc4_0       => "CC-BY-NC-4.0",
            Self::CcByNcSa4_0     => "CC-BY-NC-SA-4.0",
            Self::Gpl3_0          => "GPL-3.0",
            Self::Lgpl3_0         => "LGPL-3.0",
            Self::EditorialOnly   => "editorial-only",
            Self::RoyaltyOnRevenue => "royalty-on-revenue",
            Self::Unknown         => "unknown",
        }
    }

    /// Whether assets with this licence require attribution in the credits screen.
    pub fn requires_attribution(&self) -> bool {
        matches!(
            self,
            Self::CcBy4_0
                | Self::CcBySa4_0
                | Self::CcByNc4_0
                | Self::CcByNcSa4_0
                | Self::Gpl3_0
                | Self::Lgpl3_0
        )
    }
}

impl fmt::Display for LicenceId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

#[derive(Debug, Error)]
#[error("unrecognised licence string: {0:?}")]
pub struct UnknownLicence(pub String);

impl LicenceId {
    /// Parse a raw provider string into a canonical `LicenceId`.
    ///
    /// Comparison is case-insensitive and tolerates common variants.
    /// Unknown strings map to `LicenceId::Unknown` (never `Err`), so the
    /// caller always gets a usable value; the `Err` variant is reserved for
    /// future strict-mode use.
    pub fn from_raw(s: &str) -> Self {
        let norm = s.trim().to_ascii_lowercase();
        match norm.as_str() {
            // CC0 — many spellings in the wild
            "cc0-1.0"
            | "cc0 1.0"
            | "cc0"
            | "cc0 universal"
            | "creative commons zero v1.0 universal"
            | "public domain"
            | "public domain dedication"
            | "cc0-1.0 universal"
            | "cc 0"  => Self::Cc0_1_0,

            // CC-BY 4.0
            "cc-by-4.0" | "cc by 4.0" | "attribution 4.0 international"
            | "creative commons attribution 4.0" => Self::CcBy4_0,

            // CC-BY-SA 4.0
            "cc-by-sa-4.0" | "cc by-sa 4.0" | "cc by sa 4.0"
            | "attribution-sharealike 4.0 international"
            | "creative commons attribution-sharealike 4.0" => Self::CcBySa4_0,

            // CC-BY-NC 4.0
            "cc-by-nc-4.0" | "cc by-nc 4.0" | "cc by nc 4.0"
            | "attribution-noncommercial 4.0 international" => Self::CcByNc4_0,

            // CC-BY-NC-SA 4.0
            "cc-by-nc-sa-4.0" | "cc by-nc-sa 4.0" | "cc by nc sa 4.0"
            | "attribution-noncommercial-sharealike 4.0 international" => Self::CcByNcSa4_0,

            // GPL
            "gpl-3.0" | "gpl 3.0" | "gnu gpl v3" | "gnu general public license v3" => Self::Gpl3_0,

            // LGPL
            "lgpl-3.0" | "lgpl 3.0" | "gnu lgpl v3" | "gnu lesser general public license v3" => Self::Lgpl3_0,

            "editorial-only" | "editorial" | "editorial use only" => Self::EditorialOnly,

            "royalty-on-revenue" | "royalty on revenue" | "revenue share" => Self::RoyaltyOnRevenue,

            _ => {
                // Emit a debug trace so we can catch unmapped strings during dev.
                eprintln!("[wf_asset_provider] unmapped licence string: {s:?}");
                Self::Unknown
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Poly Haven ──────────────────────────────────────────────────────────────
    // All assets are CC0; API returns "CC0" or "cc0" in various forms.

    #[test]
    fn polyhaven_cc0_variants() {
        assert_eq!(LicenceId::from_raw("CC0"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("cc0-1.0"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("CC0-1.0"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("CC0 Universal"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("Public Domain"), LicenceId::Cc0_1_0);
    }

    // ── Kenney ──────────────────────────────────────────────────────────────────
    // Static catalog; all assets annotated "CC0" in our curated JSON.

    #[test]
    fn kenney_cc0() {
        assert_eq!(LicenceId::from_raw("CC0"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("CC0 1.0"), LicenceId::Cc0_1_0);
    }

    // ── AmbientCG ───────────────────────────────────────────────────────────────
    // API returns "CC0 1.0" in the `licence` field.

    #[test]
    fn ambientcg_cc0() {
        assert_eq!(LicenceId::from_raw("CC0 1.0"), LicenceId::Cc0_1_0);
    }

    // ── Quaternius ──────────────────────────────────────────────────────────────
    // Static catalog; all assets "CC0".

    #[test]
    fn quaternius_cc0() {
        assert_eq!(LicenceId::from_raw("CC0"), LicenceId::Cc0_1_0);
    }

    // ── OpenGameArt ─────────────────────────────────────────────────────────────
    // API can return a range; only CC0 passes the policy filter, but we must
    // parse the others correctly to reject them cleanly.

    #[test]
    fn opengameart_cc0() {
        assert_eq!(LicenceId::from_raw("CC0-1.0 Universal"), LicenceId::Cc0_1_0);
        assert_eq!(LicenceId::from_raw("Public Domain Dedication"), LicenceId::Cc0_1_0);
    }

    #[test]
    fn opengameart_cc_by() {
        assert_eq!(LicenceId::from_raw("CC BY 4.0"), LicenceId::CcBy4_0);
        assert_eq!(LicenceId::from_raw("Attribution 4.0 International"), LicenceId::CcBy4_0);
    }

    #[test]
    fn opengameart_cc_by_sa() {
        assert_eq!(LicenceId::from_raw("CC BY-SA 4.0"), LicenceId::CcBySa4_0);
        assert_eq!(LicenceId::from_raw("CC BY SA 4.0"), LicenceId::CcBySa4_0);
    }

    #[test]
    fn opengameart_gpl() {
        assert_eq!(LicenceId::from_raw("GPL-3.0"), LicenceId::Gpl3_0);
        assert_eq!(LicenceId::from_raw("GNU GPL v3"), LicenceId::Gpl3_0);
    }

    #[test]
    fn unknown_maps_to_unknown() {
        assert_eq!(LicenceId::from_raw("some bespoke licence 2024"), LicenceId::Unknown);
        assert_eq!(LicenceId::from_raw(""), LicenceId::Unknown);
    }

    // ── Attribution requirement ──────────────────────────────────────────────────

    #[test]
    fn cc0_does_not_require_attribution() {
        assert!(!LicenceId::Cc0_1_0.requires_attribution());
    }

    #[test]
    fn cc_by_requires_attribution() {
        assert!(LicenceId::CcBy4_0.requires_attribution());
        assert!(LicenceId::CcBySa4_0.requires_attribution());
    }

    // ── Round-trip through as_str ────────────────────────────────────────────────

    #[test]
    fn as_str_roundtrip() {
        let ids = [
            LicenceId::Cc0_1_0,
            LicenceId::CcBy4_0,
            LicenceId::CcBySa4_0,
            LicenceId::Gpl3_0,
            LicenceId::Unknown,
        ];
        for id in &ids {
            // as_str() must return a non-empty, stable string
            assert!(!id.as_str().is_empty(), "{id:?} as_str is empty");
        }
    }
}
