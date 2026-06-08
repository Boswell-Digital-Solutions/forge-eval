use serde_json::Value;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

static TEST_DIR_COUNTER: AtomicUsize = AtomicUsize::new(0);

fn make_temp_dir(prefix: &str) -> PathBuf {
    let idx = TEST_DIR_COUNTER.fetch_add(1, Ordering::SeqCst);
    let dir = env::temp_dir().join(format!(
        "forge-evidence-cli-{prefix}-{}-{idx}",
        std::process::id()
    ));
    if dir.exists() {
        fs::remove_dir_all(&dir).expect("remove existing temp dir");
    }
    fs::create_dir_all(&dir).expect("create temp dir");
    dir
}

fn binary_name() -> &'static str {
    if cfg!(windows) {
        "forge-evidence.exe"
    } else {
        "forge-evidence"
    }
}

fn resolve_bin() -> PathBuf {
    if let Some(candidate) = option_env!("CARGO_BIN_EXE_forge-evidence") {
        let path = PathBuf::from(candidate);
        if path.exists() {
            return path;
        }
    }

    if let Ok(current_exe) = env::current_exe() {
        if let Some(debug_dir) = current_exe.parent().and_then(|deps| deps.parent()) {
            let path = debug_dir.join(binary_name());
            if path.exists() {
                return path;
            }
        }
    }

    let manifest_target = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("debug")
        .join(binary_name());
    if manifest_target.exists() {
        return manifest_target;
    }

    panic!(
        "forge-evidence binary not found via CARGO_BIN_EXE_forge-evidence, current_exe fallback, or manifest target dir"
    );
}

fn run_ok(args: &[&str]) -> Vec<u8> {
    let bin = resolve_bin();
    let output = Command::new(bin).args(args).output().expect("run binary");
    assert!(
        output.status.success(),
        "expected success; status={:?}, stderr={}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );
    output.stdout
}

fn run_ok_string(args: &[&str]) -> String {
    String::from_utf8(run_ok(args)).expect("utf8")
}

#[test]
fn canonicalize_different_key_order_matches() {
    let tmp = make_temp_dir("canonical-order");
    let p1 = tmp.join("a.json");
    let p2 = tmp.join("b.json");
    fs::write(&p1, r#"{"b":1,"a":2,"nested":{"z":1,"y":2}}"#).expect("write p1");
    fs::write(&p2, r#"{"nested":{"y":2,"z":1},"a":2,"b":1}"#).expect("write p2");

    let o1 = run_ok(&["canonicalize", p1.to_str().expect("path")]);
    let o2 = run_ok(&["canonicalize", p2.to_str().expect("path")]);

    assert_eq!(o1, o2);
    fs::remove_dir_all(&tmp).expect("cleanup");
}

#[test]
fn canonicalization_is_idempotent() {
    let tmp = make_temp_dir("canonical-idempotent");
    let p = tmp.join("source.json");
    let c = tmp.join("canon.json");
    fs::write(&p, r#"{"a":1,"b":[3,2,1],"n":1.2300}"#).expect("write source");

    let first = run_ok(&["canonicalize", p.to_str().expect("path")]);
    fs::write(&c, &first).expect("write canonical output");
    let second = run_ok(&["canonicalize", c.to_str().expect("path")]);

    assert_eq!(first, second);
    fs::remove_dir_all(&tmp).expect("cleanup");
}

#[test]
fn sha256_vector_abc() {
    let tmp = make_temp_dir("sha256");
    let p = tmp.join("abc.txt");
    fs::write(&p, b"abc").expect("write abc");

    let out = run_ok_string(&["sha256", p.to_str().expect("path")]);
    assert_eq!(
        out.trim(),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
    fs::remove_dir_all(&tmp).expect("cleanup");
}

#[test]
fn artifact_id_is_stable() {
    let tmp = make_temp_dir("artifact-id");
    let p = tmp.join("artifact.json");
    fs::write(&p, r#"{"b":2,"a":1}"#).expect("write artifact");

    let one = run_ok_string(&[
        "artifact-id",
        p.to_str().expect("path"),
        "--kind",
        "risk_heatmap",
    ]);
    let two = run_ok_string(&[
        "artifact-id",
        p.to_str().expect("path"),
        "--kind",
        "risk_heatmap",
    ]);

    assert_eq!(one.trim(), two.trim());
    assert_eq!(one.trim().len(), 64);
    fs::remove_dir_all(&tmp).expect("cleanup");
}

#[test]
fn hashchain_is_stable() {
    let tmp = make_temp_dir("hashchain");
    let d = tmp.join("artifacts");
    fs::create_dir_all(&d).expect("create artifacts dir");
    fs::write(d.join("a.json"), r#"{"x":1,"y":2}"#).expect("write a");
    fs::write(d.join("b.json"), r#"{"x":3,"y":4}"#).expect("write b");

    let one = run_ok_string(&["hashchain", d.to_str().expect("path")]);
    let two = run_ok_string(&["hashchain", d.to_str().expect("path")]);

    assert_eq!(one.trim(), two.trim());

    let parsed: Value = serde_json::from_str(one.trim()).expect("parse hashchain json");
    let chain = parsed
        .get("chain_hashes")
        .and_then(Value::as_array)
        .expect("chain_hashes array");
    assert_eq!(chain.len(), 3);
    let final_chain = parsed
        .get("final_chain_hash")
        .and_then(Value::as_str)
        .expect("final chain hash");
    let last_chain = chain
        .last()
        .and_then(Value::as_str)
        .expect("last chain hash");
    assert_eq!(final_chain, last_chain);

    fs::remove_dir_all(&tmp).expect("cleanup");
}
