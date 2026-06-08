use anyhow::{anyhow, Context, Result};
use serde_json::{Number, Value};
use std::io::Write;

fn write_number<W: Write>(writer: &mut W, num: &Number) -> Result<()> {
    // Policy: use serde_json's normalized number representation.
    // This keeps canonicalization deterministic without introducing additional float heuristics.
    if let Some(f) = num.as_f64() {
        if !f.is_finite() {
            return Err(anyhow!("non-finite float encountered"));
        }
    }
    writer.write_all(num.to_string().as_bytes())?;
    Ok(())
}

fn write_string<W: Write>(writer: &mut W, value: &str) -> Result<()> {
    serde_json::to_writer(writer, value).context("failed to write JSON string")
}

fn write_value<W: Write>(writer: &mut W, value: &Value) -> Result<()> {
    match value {
        Value::Null => writer.write_all(b"null")?,
        Value::Bool(v) => {
            if *v {
                writer.write_all(b"true")?
            } else {
                writer.write_all(b"false")?
            }
        }
        Value::Number(num) => write_number(writer, num)?,
        Value::String(s) => write_string(writer, s)?,
        Value::Array(items) => {
            writer.write_all(b"[")?;
            for (idx, item) in items.iter().enumerate() {
                if idx > 0 {
                    writer.write_all(b",")?;
                }
                write_value(writer, item)?;
            }
            writer.write_all(b"]")?;
        }
        Value::Object(map) => {
            writer.write_all(b"{")?;
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_unstable();
            for (idx, key) in keys.iter().enumerate() {
                if idx > 0 {
                    writer.write_all(b",")?;
                }
                write_string(writer, key)?;
                writer.write_all(b":")?;
                let next = map
                    .get(*key)
                    .ok_or_else(|| anyhow!("object key missing while canonicalizing"))?;
                write_value(writer, next)?;
            }
            writer.write_all(b"}")?;
        }
    }
    Ok(())
}

pub fn canonicalize_json_bytes(bytes: &[u8]) -> Result<Vec<u8>> {
    let parsed: Value = serde_json::from_slice(bytes).context("invalid JSON input")?;
    let mut out = Vec::new();
    write_value(&mut out, &parsed)?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::canonicalize_json_bytes;

    #[test]
    fn canonical_sorts_keys() {
        let one = br#"{"b":1,"a":2,"nested":{"z":1,"y":2}}"#;
        let two = br#"{"nested":{"y":2,"z":1},"a":2,"b":1}"#;
        let c1 = canonicalize_json_bytes(one).expect("canonicalize one");
        let c2 = canonicalize_json_bytes(two).expect("canonicalize two");
        assert_eq!(c1, c2);
        assert_eq!(c1, br#"{"a":2,"b":1,"nested":{"y":2,"z":1}}"#.to_vec());
    }

    #[test]
    fn canonicalization_is_idempotent() {
        let raw = br#"{"x":[{"b":2,"a":1}],"y":1.2500}"#;
        let c1 = canonicalize_json_bytes(raw).expect("first canonicalization");
        let c2 = canonicalize_json_bytes(&c1).expect("second canonicalization");
        assert_eq!(c1, c2);
    }
}
