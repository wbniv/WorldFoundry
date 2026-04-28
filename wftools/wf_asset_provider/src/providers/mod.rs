pub mod polyhaven;
pub mod kenney;
pub mod ambientcg;
pub mod quaternius;
pub mod opengameart;

use crate::provider::Provider;

/// Return all registered providers by name slug.
pub fn all_providers() -> Vec<(&'static str, Box<dyn Provider>)> {
    vec![
        ("polyhaven",   Box::new(polyhaven::PolyHaven::new())),
        ("kenney",      Box::new(kenney::Kenney::new())),
        ("ambientcg",   Box::new(ambientcg::AmbientCG::new())),
        ("quaternius",  Box::new(quaternius::Quaternius::new())),
        ("opengameart", Box::new(opengameart::OpenGameArt::new())),
    ]
}

/// Return a subset of providers matching the given slugs.
/// Unknown slugs are silently skipped.
pub fn providers_by_name(names: &[&str]) -> Vec<(&'static str, Box<dyn Provider>)> {
    all_providers()
        .into_iter()
        .filter(|(name, _)| names.contains(name))
        .collect()
}
