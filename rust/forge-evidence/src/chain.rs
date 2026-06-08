use crate::artifact_id::artifact_id_hex;
use crate::canonical::canonicalize_json_bytes;
use crate::hash::sha256_hex;
use anyhow::{anyhow, Context, Result};
use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ChainInput {
    pub path: PathBuf,
    pub kind: String,
}

#[derive(Debug, Serialize)]
pub struct ArtifactHashRecord {
    pub index: usize,
    pub path: String,
    pub kind: String,
    pub artifact_sha256: String,
    pub artifact_id: String,
}

#[derive(Debug, Serialize)]
pub struct HashchainResult {
    pub schema_version: String,
    pub kind: String,
    pub artifact_hashes: Vec<ArtifactHashRecord>,
    pub chain_hashes: Vec<String>,
    pub final_chain_hash: String,
}

fn sorted_dir_entries(root: &Path) -> Result<Vec<PathBuf>> {
    let mut files: Vec<PathBuf> = Vec::new();
    let mut stack = vec![root.to_path_buf()];

    while let Some(dir) = stack.pop() {
        let mut entries: Vec<PathBuf> = fs::read_dir(&dir)
            .with_context(|| format!("failed to read directory {}", dir.display()))?
            .filter_map(|entry| entry.ok().map(|e| e.path()))
            .collect();
        entries.sort();

        for path in entries {
            if path.is_dir() {
                stack.push(path);
            } else if path.is_file() {
                files.push(path);
            }
        }
    }

    files.sort();
    Ok(files)
}

fn default_kind_for_path(path: &Path) -> String {
    path.file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("artifact")
        .to_string()
}

fn parse_manifest_entry(entry: &Value, manifest_base: &Path) -> Result<ChainInput> {
    match entry {
        Value::String(raw_path) => {
            let p = manifest_base.join(raw_path);
            Ok(ChainInput {
                kind: default_kind_for_path(&p),
                path: p,
            })
        }
        Value::Object(map) => {
            let path_value = map
                .get("path")
                .ok_or_else(|| anyhow!("manifest entry missing required field 'path'"))?;
            let raw_path = path_value
                .as_str()
                .ok_or_else(|| anyhow!("manifest entry field 'path' must be a string"))?;
            let kind = map
                .get("kind")
                .and_then(Value::as_str)
                .map(ToOwned::to_owned)
                .unwrap_or_else(|| default_kind_for_path(Path::new(raw_path)));
            Ok(ChainInput {
                kind,
                path: manifest_base.join(raw_path),
            })
        }
        _ => Err(anyhow!(
            "manifest entry must be a string or object with 'path'"
        )),
    }
}

fn load_manifest_inputs(manifest_file: &Path) -> Result<Vec<ChainInput>> {
    let bytes = fs::read(manifest_file)
        .with_context(|| format!("failed to read manifest {}", manifest_file.display()))?;
    let value: Value = serde_json::from_slice(&bytes)
        .with_context(|| format!("manifest {} is not valid JSON", manifest_file.display()))?;

    let arr = match value {
        Value::Array(items) => items,
        Value::Object(mut obj) => obj
            .remove("artifacts")
            .and_then(|v| v.as_array().cloned())
            .ok_or_else(|| anyhow!("manifest object must contain array field 'artifacts'"))?,
        _ => return Err(anyhow!("manifest must be an array or object")),
    };

    let base = manifest_file.parent().unwrap_or_else(|| Path::new("."));
    let mut out = Vec::with_capacity(arr.len());
    for item in arr {
        out.push(parse_manifest_entry(&item, base)?);
    }
    if out.is_empty() {
        return Err(anyhow!("manifest produced no inputs"));
    }
    Ok(out)
}

pub fn load_inputs(path: &Path) -> Result<Vec<ChainInput>> {
    if path.is_dir() {
        let mut files = sorted_dir_entries(path)?;
        files.retain(|p| p.extension().and_then(|s| s.to_str()) == Some("json"));
        if files.is_empty() {
            return Err(anyhow!(
                "directory {} contains no .json artifacts",
                path.display()
            ));
        }
        return Ok(files
            .into_iter()
            .map(|p| ChainInput {
                kind: default_kind_for_path(&p),
                path: p,
            })
            .collect());
    }

    if path.is_file() {
        return load_manifest_inputs(path);
    }

    Err(anyhow!(
        "hashchain input path does not exist: {}",
        path.display()
    ))
}

pub fn compute_hashchain(inputs: &[ChainInput]) -> Result<HashchainResult> {
    if inputs.is_empty() {
        return Err(anyhow!("hashchain requires at least one input artifact"));
    }

    let mut artifact_hashes: Vec<ArtifactHashRecord> = Vec::with_capacity(inputs.len());
    for (idx, input) in inputs.iter().enumerate() {
        let raw = fs::read(&input.path)
            .with_context(|| format!("failed to read input artifact {}", input.path.display()))?;
        let canonical = canonicalize_json_bytes(&raw).with_context(|| {
            format!(
                "input artifact {} is not canonicalizable JSON",
                input.path.display()
            )
        })?;
        let sha = sha256_hex(&canonical);
        let artifact_id = artifact_id_hex(&input.kind, &canonical);
        artifact_hashes.push(ArtifactHashRecord {
            index: idx,
            path: input.path.to_string_lossy().to_string(),
            kind: input.kind.clone(),
            artifact_sha256: sha,
            artifact_id,
        });
    }

    let mut chain_hashes: Vec<String> = Vec::with_capacity(inputs.len() + 1);
    let mut prev = sha256_hex(b"forge-evidence-chain-v1");
    chain_hashes.push(prev.clone());
    for record in &artifact_hashes {
        let payload = format!("{}:{}", prev, record.artifact_sha256);
        prev = sha256_hex(payload.as_bytes());
        chain_hashes.push(prev.clone());
    }

    Ok(HashchainResult {
        schema_version: "v1".to_string(),
        kind: "hashchain".to_string(),
        artifact_hashes,
        final_chain_hash: prev.clone(),
        chain_hashes,
    })
}

#[cfg(test)]
mod tests {
    use super::{compute_hashchain, ChainInput};
    use std::env;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static TEST_DIR_COUNTER: AtomicUsize = AtomicUsize::new(0);

    fn make_temp_dir(prefix: &str) -> PathBuf {
        let idx = TEST_DIR_COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = env::temp_dir().join(format!(
            "forge-evidence-{prefix}-{}-{idx}",
            std::process::id()
        ));
        if dir.exists() {
            fs::remove_dir_all(&dir).expect("remove existing temp dir");
        }
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    #[test]
    fn hashchain_is_stable() {
        let temp = make_temp_dir("hashchain-stable");
        let a = temp.join("a.json");
        let b = temp.join("b.json");
        fs::write(&a, r#"{"x":1,"y":2}"#).expect("write a");
        fs::write(&b, r#"{"y":2,"x":1}"#).expect("write b");

        let inputs = vec![
            ChainInput {
                path: a,
                kind: "a".to_string(),
            },
            ChainInput {
                path: b,
                kind: "b".to_string(),
            },
        ];

        let first = compute_hashchain(&inputs).expect("first compute");
        let second = compute_hashchain(&inputs).expect("second compute");

        assert_eq!(first.final_chain_hash, second.final_chain_hash);
        assert_eq!(first.chain_hashes, second.chain_hashes);
        assert_eq!(first.artifact_hashes.len(), 2);
        assert_eq!(first.chain_hashes.len(), 3);

        fs::remove_dir_all(&temp).expect("cleanup");
    }
}
