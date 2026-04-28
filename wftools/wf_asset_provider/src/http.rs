use std::time::{Duration, Instant};
use std::sync::Mutex;
use reqwest::blocking::Client;
use crate::error::AssetError;

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
}

impl RateLimitedClient {
    pub fn new(provider: impl Into<String>, requests_per_second: f64) -> Self {
        let interval_ms = (1000.0 / requests_per_second) as u64;
        Self {
            client: Client::builder()
                .user_agent("WorldFoundry-AssetBrowser/0.1 (wf-asset-browser; +https://github.com/worldfoundry)")
                .timeout(Duration::from_secs(30))
                .build()
                .expect("reqwest client init"),
            min_interval: Duration::from_millis(interval_ms),
            last_request: Mutex::new(None),
            provider: provider.into(),
        }
    }

    /// GET `url`, honouring the rate limit.  Retries once on transient failure.
    pub fn get_json<T: serde::de::DeserializeOwned>(&self, url: &str) -> Result<T, AssetError> {
        self.throttle();
        self.get_json_inner(url, 0)
    }

    /// GET `url` and return raw bytes (for binary assets / images).
    pub fn get_bytes(&self, url: &str) -> Result<Vec<u8>, AssetError> {
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
        resp.bytes().map(|b| b.to_vec()).map_err(|e| AssetError::Http {
            provider: self.provider.clone(),
            message: e.to_string(),
        })
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
                // 429 Too Many Requests — wait 2× min_interval and retry once.
                std::thread::sleep(self.min_interval * 2);
                self.throttle();
                self.get_json_inner(url, 1)
            }
            Ok(r) => Err(AssetError::Http {
                provider: self.provider.clone(),
                message: format!("HTTP {} for {url}", r.status()),
            }),
            Err(_) if attempt == 0 => {
                // Network error — retry once after a short pause.
                std::thread::sleep(Duration::from_millis(500));
                self.throttle();
                self.get_json_inner(url, 1)
            }
            Err(e) => Err(e),
        }
    }
}
