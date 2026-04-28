/// pyo3 bindings — exposes the asset provider to the Blender plugin.
///
/// Built only when the `python` feature is enabled (so the CLI binary doesn't
/// pull in libpython).  The resulting `.so` is named `wf_asset_provider`.

use pyo3::prelude::*;
use std::path::Path;

use crate::candidate::AssetCandidate;
use crate::licence::LicenceId;
use crate::manifest::Manifest;
use crate::policy::{self, Policy};
use crate::providers;

// ── Python-visible types ─────────────────────────────────────────────────────

#[pyclass(name = "AssetCandidate")]
#[derive(Clone)]
pub struct PyAssetCandidate {
    inner: AssetCandidate,
}

#[pymethods]
impl PyAssetCandidate {
    #[getter] fn provider_id(&self) -> &str    { &self.inner.provider_id }
    #[getter] fn provider(&self) -> &str       { &self.inner.provider }
    #[getter] fn title(&self) -> &str          { &self.inner.title }
    #[getter] fn thumbnail_url(&self) -> &str  { &self.inner.thumbnail_url }
    #[getter] fn licence_id(&self) -> String   { self.inner.licence_id.as_str().to_string() }
    #[getter] fn download_url(&self) -> &str   { &self.inner.download_url }
    #[getter] fn original_url(&self) -> &str   { &self.inner.original_url }
    #[getter] fn attribution_string(&self) -> &str { &self.inner.attribution_string }
    #[getter] fn attribution_required(&self) -> bool { self.inner.attribution_required }
    #[getter] fn lower_trust(&self) -> bool    { self.inner.lower_trust }

    fn __repr__(&self) -> String {
        format!("AssetCandidate({:?} / {:?}  {})", self.inner.provider, self.inner.provider_id, self.inner.licence_id)
    }
}

#[pyclass(name = "Policy")]
#[derive(Clone)]
pub struct PyPolicy {
    inner: Policy,
}

#[pymethods]
impl PyPolicy {
    #[getter]
    fn accept_ids(&self) -> Vec<String> {
        self.inner.accept_ids.iter().cloned().collect()
    }

    #[getter]
    fn reject_ids(&self) -> Vec<String> {
        self.inner.reject_ids.iter().cloned().collect()
    }

    #[getter]
    fn require_attribution_credits(&self) -> bool {
        self.inner.require_attribution_credits
    }

    #[getter]
    fn policy_path(&self) -> Option<String> {
        self.inner.policy_path.as_ref().map(|p| p.to_string_lossy().to_string())
    }

    fn allows(&self, licence_id: &str) -> bool {
        let id = LicenceId::from_raw(licence_id);
        self.inner.allows(&id)
    }

    fn __repr__(&self) -> String {
        let path = self.inner.policy_path.as_ref()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| "<fallback>".to_string());
        format!("Policy(path={path:?}, accept={:?})", self.inner.accept_ids)
    }
}

#[pyclass(name = "Manifest")]
pub struct PyManifest {
    inner: Manifest,
}

#[pymethods]
impl PyManifest {
    #[getter] fn licence_id(&self) -> &str         { &self.inner.licence_id }
    #[getter] fn attribution_required(&self) -> bool { self.inner.attribution_required }
    #[getter] fn attribution_string(&self) -> &str  { &self.inner.attribution_string }
    #[getter] fn licence_url(&self) -> &str         { &self.inner.licence_url }
    #[getter] fn provider(&self) -> &str            { &self.inner.provider }
    #[getter] fn provider_id(&self) -> &str         { &self.inner.provider_id }
    #[getter] fn download_date(&self) -> &str       { &self.inner.download_date }
    #[getter] fn original_url(&self) -> &str        { &self.inner.original_url }
    #[getter] fn download_url(&self) -> &str        { &self.inner.download_url }
    #[getter] fn derived_from(&self) -> Vec<String> { self.inner.derived_from.clone() }
}

// ── Python functions ──────────────────────────────────────────────────────────

/// Load `licence_policy.toml` by walking up from `blend_dir`.
///
/// Returns a `Policy` object.  If no file is found or the file is malformed,
/// returns a fallback CC0-only policy and prints a warning to stderr.
#[pyfunction]
fn load_policy(blend_dir: &str) -> PyResult<PyPolicy> {
    let dir = Path::new(blend_dir);
    let (pol, warn) = policy::load_policy(dir);
    if let Some(w) = warn {
        eprintln!("[wf_asset_provider] policy warning: {w}");
    }
    Ok(PyPolicy { inner: pol })
}

/// Search all (or a subset of) providers for assets matching `query`.
///
/// `providers`: list of provider slugs to query; pass empty list for all.
/// Returns list of `AssetCandidate` objects, policy-filtered.
#[pyfunction]
#[pyo3(signature = (query, policy, providers=None, limit=50))]
fn search(
    query: &str,
    policy: &PyPolicy,
    providers: Option<Vec<String>>,
    limit: usize,
) -> PyResult<Vec<PyAssetCandidate>> {
    let provider_list = match providers {
        Some(ref names) if !names.is_empty() => {
            let slices: Vec<&str> = names.iter().map(|s| s.as_str()).collect();
            crate::providers::providers_by_name(&slices)
        }
        _ => crate::providers::all_providers(),
    };

    let mut results = Vec::new();
    for (_name, provider) in &provider_list {
        match provider.search(query, &policy.inner, limit) {
            Ok(mut candidates) => {
                // Defence-in-depth: re-apply policy filter
                candidates.retain(|c| policy.inner.allows(&c.licence_id));
                results.extend(candidates);
            }
            Err(e) => {
                eprintln!("[wf_asset_provider] {} search failed: {e}", provider.name());
            }
        }
    }
    results.truncate(limit);
    Ok(results.into_iter().map(|c| PyAssetCandidate { inner: c }).collect())
}

/// Download `candidate` to `dest_dir/<provider>/<asset-id>/`.
///
/// Returns `(asset_path_str, manifest)`.
#[pyfunction]
fn download(candidate: &PyAssetCandidate, dest_dir: &str) -> PyResult<(String, PyManifest)> {
    let providers_list = crate::providers::all_providers();
    let provider = providers_list
        .iter()
        .find(|(name, _)| *name == candidate.inner.provider.as_str())
        .map(|(_, p)| p.as_ref())
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err(
            format!("unknown provider {:?}", candidate.inner.provider),
        ))?;

    let asset_dest = std::path::Path::new(dest_dir)
        .join(&candidate.inner.provider)
        .join(&candidate.inner.provider_id);

    let (path, manifest) = provider.download(&candidate.inner, &asset_dest)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    Ok((path.to_string_lossy().to_string(), PyManifest { inner: manifest }))
}

/// Validate that the licence field in a written `manifest.json` matches
/// the candidate's claimed licence.  Returns `True` if they match.
#[pyfunction]
fn validate_licence_match(manifest_path: &str, candidate: &PyAssetCandidate) -> PyResult<bool> {
    let text = std::fs::read_to_string(manifest_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("{manifest_path}: {e}")))?;
    let m: serde_json::Value = serde_json::from_str(&text)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{manifest_path}: {e}")))?;
    let manifest_licence = m["licence_id"].as_str().unwrap_or("");
    Ok(manifest_licence == candidate.inner.licence_id.as_str())
}

// ── Module entry point ────────────────────────────────────────────────────────

#[pymodule]
pub fn wf_asset_provider(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(load_policy, m)?)?;
    m.add_function(wrap_pyfunction!(search, m)?)?;
    m.add_function(wrap_pyfunction!(download, m)?)?;
    m.add_function(wrap_pyfunction!(validate_licence_match, m)?)?;
    m.add_class::<PyPolicy>()?;
    m.add_class::<PyAssetCandidate>()?;
    m.add_class::<PyManifest>()?;
    Ok(())
}
