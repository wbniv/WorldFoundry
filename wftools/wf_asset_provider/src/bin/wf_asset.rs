/// wf-asset CLI — search and download CC0 assets from supported providers.
///
/// Usage:
///   wf-asset search "tree" [--provider polyhaven] [--limit 20]
///   wf-asset download polyhaven/medieval-tree-04 --dest wflevels/test/assets
///   wf-asset policy show [--blend-dir .]
///   wf-asset providers list

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use wf_asset_provider::policy::load_policy;
use wf_asset_provider::providers::{all_providers, providers_by_name};

#[derive(Parser)]
#[command(name = "wf-asset", about = "World Foundry asset browser CLI")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Search across providers for assets matching a query
    Search {
        /// Search query (e.g. "tree", "barrel", "lava rock")
        query: String,

        /// Restrict to specific provider(s), comma-separated
        #[arg(long, value_delimiter = ',')]
        provider: Vec<String>,

        /// Maximum results to return
        #[arg(long, default_value = "20")]
        limit: usize,

        /// Directory to load licence_policy.toml from (walks up if not found here)
        #[arg(long, default_value = ".")]
        policy_dir: PathBuf,
    },

    /// Download an asset by provider/id
    Download {
        /// Asset identifier as "provider/asset-id" (e.g. "polyhaven/oak-tree")
        asset: String,

        /// Destination directory for the downloaded asset
        #[arg(long)]
        dest: PathBuf,

        /// Directory to load licence_policy.toml from
        #[arg(long, default_value = ".")]
        policy_dir: PathBuf,
    },

    /// Show or manage the licence policy
    Policy {
        #[command(subcommand)]
        cmd: PolicyCmd,
    },

    /// List registered providers
    Providers {
        #[command(subcommand)]
        cmd: ProvidersCmd,
    },
}

#[derive(Subcommand)]
enum PolicyCmd {
    /// Show the active policy (reads licence_policy.toml from current or parent dir)
    Show {
        #[arg(long, default_value = ".")]
        blend_dir: PathBuf,
    },
}

#[derive(Subcommand)]
enum ProvidersCmd {
    /// List all registered providers
    List,
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Search { query, provider, limit, policy_dir } => {
            let (pol, warn) = load_policy(&policy_dir);
            if let Some(w) = warn {
                eprintln!("warning: {w}");
            }
            match &pol.policy_path {
                Some(p) => eprintln!("policy: {}", p.display()),
                None    => eprintln!("policy: fallback (CC0-only — no licence_policy.toml found)"),
            }

            let provider_list = if provider.is_empty() {
                all_providers()
            } else {
                let slices: Vec<&str> = provider.iter().map(|s| s.as_str()).collect();
                providers_by_name(&slices)
            };

            let mut all_results = Vec::new();
            for (name, prov) in &provider_list {
                eprint!("  searching {name}... ");
                match prov.search(&query, &pol, limit) {
                    Ok(mut results) => {
                        results.retain(|c| pol.allows(&c.licence_id));
                        eprintln!("{} results", results.len());
                        all_results.extend(results);
                    }
                    Err(e) => eprintln!("FAILED: {e}"),
                }
            }

            all_results.truncate(limit);
            println!("\n{} results after policy filter:", all_results.len());
            for c in &all_results {
                println!(
                    "  [{}/{}] {:50}  {}{}",
                    c.provider,
                    c.provider_id,
                    c.title,
                    c.licence_id,
                    if c.lower_trust { "  ⚠ lower-trust" } else { "" },
                );
            }
        }

        Commands::Download { asset, dest, policy_dir } => {
            let (pol, warn) = load_policy(&policy_dir);
            if let Some(w) = warn {
                eprintln!("warning: {w}");
            }

            let parts: Vec<&str> = asset.splitn(2, '/').collect();
            if parts.len() != 2 {
                eprintln!("error: asset must be in 'provider/asset-id' format");
                std::process::exit(1);
            }
            let (provider_name, asset_id) = (parts[0], parts[1]);

            let providers = providers_by_name(&[provider_name]);
            let (_, prov) = providers.first().unwrap_or_else(|| {
                eprintln!("error: unknown provider {:?}", provider_name);
                std::process::exit(1);
            });

            // Quick search to resolve the candidate
            eprintln!("resolving {asset}...");
            let results = prov.search(asset_id, &pol, 10).unwrap_or_default();
            let candidate = results.iter().find(|c| c.provider_id == asset_id);

            let candidate = match candidate {
                Some(c) => c.clone(),
                None => {
                    // Build a minimal candidate if not found via search
                    eprintln!("not found via search; attempting direct download");
                    wf_asset_provider::candidate::AssetCandidate {
                        provider_id: asset_id.to_string(),
                        provider: provider_name.to_string(),
                        title: asset_id.to_string(),
                        thumbnail_url: String::new(),
                        licence_id: wf_asset_provider::licence::LicenceId::Cc0_1_0,
                        download_url: format!("https://api.{provider_name}.com/files/{asset_id}"),
                        original_url: String::new(),
                        attribution_string: String::new(),
                        attribution_required: false,
                        lower_trust: false,
                    }
                }
            };

            if !pol.allows(&candidate.licence_id) {
                eprintln!("error: licence {:?} is not accepted by policy", candidate.licence_id.as_str());
                std::process::exit(1);
            }

            let asset_dest = dest.join(&candidate.provider).join(&candidate.provider_id);
            eprintln!("downloading to {}...", asset_dest.display());

            match prov.download(&candidate, &asset_dest) {
                Ok((path, _manifest)) => {
                    println!("downloaded: {}", path.display());
                }
                Err(e) => {
                    eprintln!("error: {e}");
                    std::process::exit(1);
                }
            }
        }

        Commands::Policy { cmd } => match cmd {
            PolicyCmd::Show { blend_dir } => {
                let (pol, warn) = load_policy(&blend_dir);
                if let Some(w) = warn {
                    eprintln!("warning: {w}");
                }
                match &pol.policy_path {
                    Some(p) => println!("policy file: {}", p.display()),
                    None    => println!("policy file: not found — using fallback (CC0-only)"),
                }
                let mut accept: Vec<_> = pol.accept_ids.iter().cloned().collect();
                accept.sort();
                let mut reject: Vec<_> = pol.reject_ids.iter().chain(pol.reject_default_ids.iter()).cloned().collect();
                reject.sort();
                println!("accept: {}", accept.join(", "));
                println!("reject: {}", reject.join(", "));
                println!("require_attribution_credits: {}", pol.require_attribution_credits);
            }
        },

        Commands::Providers { cmd } => match cmd {
            ProvidersCmd::List => {
                for (name, _) in all_providers() {
                    println!("{name}");
                }
            }
        },
    }
}
