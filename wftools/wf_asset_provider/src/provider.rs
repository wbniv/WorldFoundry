use std::path::{Path, PathBuf};
use crate::candidate::AssetCandidate;
use crate::error::AssetError;
use crate::manifest::Manifest;
use crate::policy::Policy;

/// All provider adapters implement this trait.
pub trait Provider: Send + Sync {
    fn name(&self) -> &str;

    /// Search for assets matching `query` that pass the `policy` filter.
    ///
    /// Providers should pre-filter by licence where the API supports it, but
    /// the caller always re-applies `policy.allows()` as defence-in-depth.
    fn search(
        &self,
        query: &str,
        policy: &Policy,
        limit: usize,
    ) -> Result<Vec<AssetCandidate>, AssetError>;

    /// Download `candidate` into `dest_dir`, returning the path to the
    /// primary asset file and the provenance manifest.
    fn download(
        &self,
        candidate: &AssetCandidate,
        dest_dir: &Path,
    ) -> Result<(PathBuf, Manifest), AssetError>;
}
