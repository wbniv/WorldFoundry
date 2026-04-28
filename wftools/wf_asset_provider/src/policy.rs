use std::collections::HashSet;
use std::path::{Path, PathBuf};
use serde::Deserialize;
use crate::error::AssetError;
use crate::licence::LicenceId;

/// Parsed `licence_policy.toml` — the project's asset acceptance rules.
#[derive(Debug, Clone)]
pub struct Policy {
    pub accept_ids: HashSet<String>,
    pub reject_ids: HashSet<String>,
    pub reject_default_ids: HashSet<String>,
    pub require_attribution_credits: bool,
    /// The file that was read, for diagnostic messages.
    pub policy_path: Option<PathBuf>,
}

impl Policy {
    /// Returns `true` if the given licence ID is allowed by this policy.
    pub fn allows(&self, id: &LicenceId) -> bool {
        let s = id.as_str();
        // An explicit accept beats an explicit reject (waivers work this way).
        if self.accept_ids.contains(s) {
            return true;
        }
        if self.reject_ids.contains(s) || self.reject_default_ids.contains(s) {
            return false;
        }
        // Anything not listed is implicitly rejected.
        false
    }
}

// ── TOML schema ──────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct TomlPolicy {
    #[serde(default)]
    require_attribution_credits: bool,
    #[serde(default)]
    licence: Vec<TomlLicence>,
    #[serde(default)]
    waiver: Vec<TomlWaiver>,
}

#[derive(Deserialize)]
struct TomlLicence {
    id: String,
    status: String,
    // reason and requires_attribution are informational; not used for filtering
    #[allow(dead_code)]
    reason: Option<String>,
    #[allow(dead_code)]
    requires_attribution: Option<bool>,
}

#[derive(Deserialize)]
struct TomlWaiver {
    #[allow(dead_code)]
    asset_id: String,
    #[allow(dead_code)]
    licence_id: String,
    #[allow(dead_code)]
    approved_by: Option<String>,
    #[allow(dead_code)]
    approved_at: Option<String>,
    #[allow(dead_code)]
    reason: Option<String>,
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Walk up from `start_dir` until we find `licence_policy.toml`.
///
/// Returns the path if found, `None` if we reach the filesystem root.
pub fn find_policy_file(start_dir: &Path) -> Option<PathBuf> {
    let mut dir = start_dir.to_path_buf();
    loop {
        let candidate = dir.join("licence_policy.toml");
        if candidate.is_file() {
            return Some(candidate);
        }
        let parent = dir.parent()?;
        if parent == dir {
            return None;
        }
        dir = parent.to_path_buf();
    }
}

/// Load and parse `licence_policy.toml`.
///
/// On error (file not found, malformed TOML), returns a fallback policy that
/// accepts `CC0-1.0` only and sets `policy_path = None`.  The fallback is a
/// deliberate fail-closed behaviour: new checkouts work without a policy file,
/// but only the safest possible licence class passes through.
pub fn load_policy(start_dir: &Path) -> (Policy, Option<AssetError>) {
    let path = match find_policy_file(start_dir) {
        Some(p) => p,
        None => return (cc0_fallback(None), None),
    };

    let text = match std::fs::read_to_string(&path) {
        Ok(t) => t,
        Err(e) => {
            let err = AssetError::PolicyRead(path.clone(), e.to_string());
            return (cc0_fallback(None), Some(err));
        }
    };

    let parsed: TomlPolicy = match toml::from_str(&text) {
        Ok(p) => p,
        Err(e) => {
            let err = AssetError::PolicyParse(path.clone(), e.to_string());
            return (cc0_fallback(None), Some(err));
        }
    };

    let mut accept_ids = HashSet::new();
    let mut reject_ids = HashSet::new();
    let mut reject_default_ids = HashSet::new();

    for entry in &parsed.licence {
        match entry.status.as_str() {
            "accept" => { accept_ids.insert(entry.id.clone()); }
            "reject" => { reject_ids.insert(entry.id.clone()); }
            "reject-default" => { reject_default_ids.insert(entry.id.clone()); }
            other => {
                eprintln!("[wf_asset_provider] unknown licence status {other:?} for id {:?}", entry.id);
            }
        }
    }

    let _ = &parsed.waiver; // loaded but not yet used in v1 filtering

    (
        Policy {
            accept_ids,
            reject_ids,
            reject_default_ids,
            require_attribution_credits: parsed.require_attribution_credits,
            policy_path: Some(path),
        },
        None,
    )
}

fn cc0_fallback(path: Option<PathBuf>) -> Policy {
    let mut accept_ids = HashSet::new();
    accept_ids.insert("CC0-1.0".to_string());
    Policy {
        accept_ids,
        reject_ids: HashSet::new(),
        reject_default_ids: HashSet::new(),
        require_attribution_credits: true,
        policy_path: path,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    fn write_policy(dir: &Path, content: &str) -> PathBuf {
        let p = dir.join("licence_policy.toml");
        std::fs::write(&p, content).unwrap();
        p
    }

    fn temp_dir_with_policy(content: &str) -> TempDir {
        let dir = TempDir::new().unwrap();
        write_policy(dir.path(), content);
        dir
    }

    const MINIMAL_TOML: &str = r#"
require_attribution_credits = true

[[licence]]
id = "CC0-1.0"
status = "accept"
reason = "public domain"

[[licence]]
id = "CC-BY-SA-4.0"
status = "reject"
reason = "share-alike would contaminate WF derivative"
"#;

    #[test]
    fn loads_accept() {
        let dir = temp_dir_with_policy(MINIMAL_TOML);
        let (policy, err) = load_policy(dir.path());
        assert!(err.is_none());
        assert!(policy.allows(&LicenceId::Cc0_1_0));
    }

    #[test]
    fn rejects_share_alike() {
        let dir = temp_dir_with_policy(MINIMAL_TOML);
        let (policy, _) = load_policy(dir.path());
        assert!(!policy.allows(&LicenceId::CcBySa4_0));
    }

    #[test]
    fn rejects_unlisted() {
        let dir = temp_dir_with_policy(MINIMAL_TOML);
        let (policy, _) = load_policy(dir.path());
        assert!(!policy.allows(&LicenceId::Gpl3_0));
    }

    #[test]
    fn fallback_when_no_file() {
        let dir = TempDir::new().unwrap();
        let (policy, _) = load_policy(dir.path());
        assert!(policy.allows(&LicenceId::Cc0_1_0));
        assert!(!policy.allows(&LicenceId::CcBy4_0));
        assert!(policy.policy_path.is_none());
    }

    #[test]
    fn fallback_on_malformed_toml() {
        let dir = TempDir::new().unwrap();
        write_policy(dir.path(), "not valid toml {{{{");
        let (policy, err) = load_policy(dir.path());
        assert!(err.is_some());
        assert!(policy.allows(&LicenceId::Cc0_1_0));
        assert!(!policy.allows(&LicenceId::CcBy4_0));
    }

    #[test]
    fn walks_up_directory_tree() {
        // Create a/b/c with policy at a/
        let root = TempDir::new().unwrap();
        let deep = root.path().join("a").join("b").join("c");
        std::fs::create_dir_all(&deep).unwrap();
        write_policy(root.path().join("a").as_path(), MINIMAL_TOML);

        let (policy, err) = load_policy(&deep);
        assert!(err.is_none());
        assert!(policy.allows(&LicenceId::Cc0_1_0));
    }
}
