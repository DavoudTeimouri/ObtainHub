use anyhow::Result;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use tempfile;

/// Calculate SHA256 of bytes
pub fn calculate_sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

/// Extract archive bytes to destination directory with zip-slip protection
pub fn extract_archive(name: &str, bytes: &[u8], dest: &Path) -> Result<()> {
    let name_lower = name.to_lowercase();

    if name_lower.ends_with(".zip") {
        extract_zip(bytes, dest)
    } else if name_lower.ends_with(".tar.gz") || name_lower.ends_with(".tgz") {
        extract_tar_gz(bytes, dest)
    } else if name_lower.ends_with(".tar.xz") || name_lower.ends_with(".txz") {
        extract_tar_xz(bytes, dest)
    } else {
        // Single binary or unknown - just copy
        let dest_path = dest.join(name);
        if let Some(parent) = dest_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&dest_path, bytes)?;
        Ok(())
    }
}

fn extract_zip(bytes: &[u8], dest: &Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(cursor)?;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = dest.join(file.name());

        // Zip-slip guard: reject entries that escape dest
        let mut normalized = PathBuf::new();
        for c in outpath.components() {
            match c {
                std::path::Component::ParentDir => { normalized.pop(); }
                std::path::Component::CurDir => {}
                other => normalized.push(other.as_os_str()),
            }
        }
        if !normalized.starts_with(dest) {
            anyhow::bail!("Refusing to extract '{}': path escapes install directory", file.name());
        }

        if file.name().ends_with('/') {
            std::fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let mut outfile = std::fs::File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
        }
    }
    Ok(())
}

fn extract_tar_gz(bytes: &[u8], dest: &Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let decoder = flate2::read::GzDecoder::new(cursor);
    let mut archive = tar::Archive::new(decoder);
    archive.unpack(dest)?;
    Ok(())
}

fn extract_tar_xz(bytes: &[u8], dest: &Path) -> Result<()> {
    use std::io::{BufWriter, Write};

    // Decompress to a temp file first
    let temp_dir = tempfile::tempdir()?;
    let temp_tar = temp_dir.path().join("archive.tar");
    let mut writer = BufWriter::new(std::fs::File::create(&temp_tar)?);

    lzma_rs::xz_decompress(&mut std::io::Cursor::new(bytes), &mut writer)?;
    writer.flush()?;
    drop(writer);

    // Now extract the tar file
    let tar_file = std::fs::File::open(&temp_tar)?;
    let mut archive = tar::Archive::new(tar_file);
    archive.unpack(dest)?;

    Ok(())
}
