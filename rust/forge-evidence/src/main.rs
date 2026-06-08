mod artifact_id;
mod canonical;
mod chain;
mod hash;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;

use artifact_id::artifact_id_hex;
use canonical::canonicalize_json_bytes;
use chain::{compute_hashchain, load_inputs};
use hash::sha256_hex;

#[derive(Debug, Parser)]
#[command(name = "forge-evidence")]
#[command(about = "Deterministic evidence tools")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Canonicalize a JSON file into deterministic compact JSON.
    Canonicalize { input: PathBuf },
    /// Compute SHA-256 digest hex for any input file.
    Sha256 { input: PathBuf },
    /// Compute deterministic artifact-id for a JSON artifact.
    ArtifactId {
        input: PathBuf,
        #[arg(long)]
        kind: String,
    },
    /// Compute hashchain from a directory or manifest JSON file.
    Hashchain { input: PathBuf },
}

fn run() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Canonicalize { input } => {
            let raw = fs::read(&input)
                .with_context(|| format!("failed reading input file {}", input.display()))?;
            let canonical = canonicalize_json_bytes(&raw)?;
            io::stdout()
                .write_all(&canonical)
                .context("failed writing canonicalized output")?;
        }
        Commands::Sha256 { input } => {
            let raw = fs::read(&input)
                .with_context(|| format!("failed reading input file {}", input.display()))?;
            println!("{}", sha256_hex(&raw));
        }
        Commands::ArtifactId { input, kind } => {
            let raw = fs::read(&input)
                .with_context(|| format!("failed reading input file {}", input.display()))?;
            let canonical = canonicalize_json_bytes(&raw)?;
            println!("{}", artifact_id_hex(&kind, &canonical));
        }
        Commands::Hashchain { input } => {
            let inputs = load_inputs(&input)?;
            let result = compute_hashchain(&inputs)?;
            let output = serde_json::to_string(&result)?;
            println!("{}", output);
        }
    }

    Ok(())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err:#}");
        std::process::exit(1);
    }
}
