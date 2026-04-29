pub mod polyhaven;
pub mod kenney;
pub mod ambientcg;
pub mod quaternius;
pub mod opengameart;
pub mod sketchfab;

use crate::credentials::Credentials;
use crate::provider::Provider;

/// Return all registered providers by name slug.
pub fn all_providers(creds: &Credentials) -> Vec<(&'static str, Box<dyn Provider>)> {
    vec![
        ("polyhaven",   Box::new(polyhaven::PolyHaven::new())),
        ("kenney",      Box::new(kenney::Kenney::new())),
        ("ambientcg",   Box::new(ambientcg::AmbientCG::new())),
        ("quaternius",  Box::new(quaternius::Quaternius::new())),
        ("opengameart", Box::new(opengameart::OpenGameArt::new())),
        ("sketchfab",   Box::new(sketchfab::Sketchfab::new(creds.sketchfab_api_key.clone()))),
    ]
}

/// Return a subset of providers matching the given slugs.
/// Unknown slugs are silently skipped.
pub fn providers_by_name(names: &[&str], creds: &Credentials) -> Vec<(&'static str, Box<dyn Provider>)> {
    all_providers(creds)
        .into_iter()
        .filter(|(name, _)| names.contains(name))
        .collect()
}
