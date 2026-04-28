use std::hash::{Hash, Hasher};
use std::collections::hash_map::DefaultHasher;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use std::sync::Mutex;
use reqwest::blocking::Client;
use crate::error::AssetError;

const JSON_TTL_SECS: u64 = 3_600;       // 1 hour
const BYTES_TTL_SECS: u64 = 7 * 86_400; // 7 days

/// A synchronous HTTP client with per-provider rate limiting and simple retry.
///
/// Blender's plugin calls into the Rust layer from Python worker threads using
/// blocking (synchronous) reqwest, so the whole HTTP stack is sync here.
/// The tokio runtime is not used in the pyo3 path.
pub struct RateLimitedClient {
    client: Client,
    /// Minimum interval between requests for this provider.
    min_interval: Duration,
    /// Tracks when the last request was sent.
    last_request: Mutex<Option<Instant>>,
    provider: String,
    cache_dir: PathBuf,
}

impl RateLimitedClient {
    pub fn new(provider: impl Into<String>, requests_per_second: f64) -> Self {
        let interval_ms = (1000.0 / requests_per_second) as u64;
        let provider = provider.into();
        let cache_dir = cache_dir(&provider);
        Self {
            client: Client::builder()
                .user_agent("WorldFoundry-AssetBrowser/0.1 (wf-asset-browser; +https://github.com/worldfoundry)")
                .timeout(Duration::from_secs(30))
                .build()
                .expect("reqwest client init"),
            min_interval: Duration::from_millis(interval_ms),
            last_request: Mutex::new(None),
            provider,
            cache_dir,
        }
    }

    /// GET `url`, honouring the rate limit.  Returns cached JSON if fresh.
    pub fn get_json<T: serde::de::DeserializeOwned>(&self, url: &str) -> Result<T, AssetError> {
        let key = cache_key(url);
        let body_path = self.cache_dir.join(&key);
        let meta_path = self.cache_dir.join(format!("{key}.meta"));

        if let Some(bytes) = read_if_fresh(&body_path, &meta_path, JSON_TTL_SECS) {
            return serde_json::from_slice(&bytes).map_err(|e| AssetError::JsonParse {
                provider: self.provider.clone(),
                message: format!("{url} (cache): {e}"),
            });
        }

        self.throttle();
        let result = self.get_json_inner::<serde_json::Value>(url, 0)?;
        if let Ok(bytes) = serde_json::to_vec(&result) {
            let _ = write_cache(&self.cache_dir, &body_path, &meta_path, &bytes);
        }
        serde_json::from_value(result).map_err(|e| AssetError::JsonParse {
            provider: self.provider.clone(),
            message: format!("{url}: {e}"),
        })
    }

    /// GET `url` and return raw bytes.  Returns cached bytes if fresh.
    pub fn get_bytes(&self, url: &str) -> Result<Vec<u8>, AssetError> {
        let key = cache_key(url);
        let body_path = self.cache_dir.join(&key);
        let meta_path = self.cache_dir.join(format!("{key}.meta"));

        if let Some(bytes) = read_if_fresh(&body_path, &meta_path, BYTES_TTL_SECS) {
            return Ok(bytes);
        }

        self.throttle();
        let resp = self.client.get(url).send().map_err(|e| AssetError::Http {
            provider: self.provider.clone(),
            message: e.to_string(),
        })?;
        if !resp.status().is_success() {
            return Err(AssetError::Http {
                provider: self.provider.clone(),
                message: format!("HTTP {} for {url}", resp.status()),
            });
        }
        let bytes = resp.bytes().map(|b| b.to_vec()).map_err(|e| AssetError::Http {
            provider: self.provider.clone(),
            message: e.to_string(),
        })?;
        let _ = write_cache(&self.cache_dir, &body_path, &meta_path, &bytes);
        Ok(bytes)
    }

    fn throttle(&self) {
        let mut last = self.last_request.lock().unwrap();
        if let Some(t) = *last {
            let elapsed = t.elapsed();
            if elapsed < self.min_interval {
                std::thread::sleep(self.min_interval - elapsed);
            }
        }
        *last = Some(Instant::now());
    }

    fn get_json_inner<T: serde::de::DeserializeOwned>(
        &self,
        url: &str,
        attempt: u8,
    ) -> Result<T, AssetError> {
        let resp = self.client.get(url).send().map_err(|e| AssetError::Http {
            provider: self.provider.clone(),
            message: e.to_string(),
        });
        match resp {
            Ok(r) if r.status().is_success() => {
                r.json::<T>().map_err(|e| AssetError::JsonParse {
                    provider: self.provider.clone(),
                    message: format!("{url}: {e}"),
                })
            }
            Ok(r) if r.status() == 429 && attempt == 0 => {
                std::thread::sleep(self.min_interval * 2);
                self.throttle();
                self.get_json_inner(url, 1)
            }
            Ok(r) => Err(AssetError::Http {
                provider: self.provider.clone(),
                message: format!("HTTP {} for {url}", r.status()),
            }),
            Err(_) if attempt == 0 => {
                std::thread::sleep(Duration::from_millis(500));
                self.throttle();
                self.get_json_inner(url, 1)
            }
            Err(e) => Err(e),
        }
    }
}

// ── Cache helpers ─────────────────────────────────────────────────────────────

fn cache_dir(provider: &str) -> PathBuf {
    let base = std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| std::env::temp_dir());
    base.join(".cache").join("wf_asset_provider").join(provider)
}

fn cache_key(url: &str) -> String {
    let mut h = DefaultHasher::new();
    url.hash(&mut h);
    format!("{:016x}", h.finish())
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn read_if_fresh(body_path: &PathBuf, meta_path: &PathBuf, ttl_secs: u64) -> Option<Vec<u8>> {
    let meta = std::fs::read(meta_path).ok()?;
    let ts: u64 = std::str::from_utf8(&meta).ok()?.trim().parse().ok()?;
    if now_secs().saturating_sub(ts) > ttl_secs {
        return None;
    }
    std::fs::read(body_path).ok()
}

fn write_cache(cache_dir: &PathBuf, body_path: &PathBuf, meta_path: &PathBuf, bytes: &[u8]) -> std::io::Result<()> {
    std::fs::create_dir_all(cache_dir)?;
    std::fs::write(body_path, bytes)?;
    std::fs::write(meta_path, now_secs().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn cache_key_is_deterministic() {
        let k1 = cache_key("https://example.com/api?q=table");
        let k2 = cache_key("https://example.com/api?q=table");
        assert_eq!(k1, k2);
        assert_eq!(k1.len(), 16);
    }

    #[test]
    fn cache_key_differs_for_different_urls() {
        let k1 = cache_key("https://example.com/a");
        let k2 = cache_key("https://example.com/b");
        assert_ne!(k1, k2);
    }

    #[test]
    fn read_if_fresh_returns_none_when_expired() {
        let dir = tempfile::tempdir().unwrap();
        let body = dir.path().join("body");
        let meta = dir.path().join("meta");
        std::fs::write(&body, b"data").unwrap();
        // Write a timestamp 2 hours ago
        let old_ts = now_secs().saturating_sub(7201);
        std::fs::write(&meta, old_ts.to_string()).unwrap();
        assert!(read_if_fresh(&body, &meta, 3600).is_none());
    }

    #[test]
    fn read_if_fresh_returns_data_when_current() {
        let dir = tempfile::tempdir().unwrap();
        let body = dir.path().join("body");
        let meta = dir.path().join("meta");
        std::fs::write(&body, b"hello").unwrap();
        std::fs::write(&meta, now_secs().to_string()).unwrap();
        let data = read_if_fresh(&body, &meta, 3600).unwrap();
        assert_eq!(data, b"hello");
    }
}
