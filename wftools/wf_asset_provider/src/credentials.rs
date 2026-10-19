/// API credentials for providers that require authentication.
///
/// Passed in from the calling layer (Blender addon prefs or CLI env var);
/// never read from a project file to keep secrets out of version control.
#[derive(Debug, Clone, Default)]
pub struct Credentials {
    /// Bearer token for Sketchfab API downloads.
    /// Obtain from sketchfab.com/settings#api-token.
    pub sketchfab_api_key: Option<String>,
}

impl Credentials {
    pub fn empty() -> Self {
        Self::default()
    }
}
