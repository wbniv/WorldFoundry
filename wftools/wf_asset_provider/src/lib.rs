pub mod licence;
pub mod candidate;
pub mod manifest;
pub mod policy;
pub mod error;
pub mod http;
pub mod provider;
pub mod providers;

#[cfg(feature = "python")]
pub mod pybind;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pymodule]
fn wf_asset_provider(m: &Bound<'_, PyModule>) -> PyResult<()> {
    pybind::wf_asset_provider(m)
}
