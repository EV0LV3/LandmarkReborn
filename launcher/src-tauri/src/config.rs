//! `LauncherConfig.json`: the auth web API address and the remembered game location.

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

pub const CONFIG_FILE_NAME: &str = "LauncherConfig.json";
pub const DEFAULT_SERVER: &str = "http://127.0.0.1:5080";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct LauncherConfig {
    /// Base URL of the auth server's web API.
    #[serde(default = "default_server")]
    pub server: String,
    /// Path to Landmark64.exe, remembered after it has been selected once.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub game_path: Option<String>,
}

fn default_server() -> String {
    DEFAULT_SERVER.to_string()
}

impl Default for LauncherConfig {
    fn default() -> Self {
        Self { server: default_server(), game_path: None }
    }
}

/// A config file beside the executable wins (portable installs, as with the original launcher);
/// otherwise the per-user app config directory is used.
pub fn resolve_path(app_config_dir: Option<PathBuf>) -> PathBuf {
    if let Some(portable) = std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|dir| dir.join(CONFIG_FILE_NAME)))
        .filter(|path| path.is_file())
    {
        return portable;
    }
    app_config_dir
        .map(|dir| dir.join(CONFIG_FILE_NAME))
        .unwrap_or_else(|| PathBuf::from(CONFIG_FILE_NAME))
}

pub fn load(path: &Path) -> Result<LauncherConfig, String> {
    match fs::read_to_string(path) {
        Ok(text) => {
            // Files written by Windows tools often start with a BOM.
            let text = text.trim_start_matches('\u{feff}');
            serde_json::from_str(text).map_err(|e| format!("{} is not valid: {e}", path.display()))
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            let config = LauncherConfig::default();
            // Best effort: give the user a file to edit.
            let _ = save(path, &config);
            Ok(config)
        }
        Err(e) => Err(format!("Could not read {}: {e}", path.display())),
    }
}

pub fn save(path: &Path, config: &LauncherConfig) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("Could not create {}: {e}", parent.display()))?;
    }
    let text = serde_json::to_string_pretty(config).map_err(|e| e.to_string())?;
    fs::write(path, text + "\n").map_err(|e| format!("Could not write {}: {e}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_original_format_with_bom() {
        let config: LauncherConfig =
            serde_json::from_str("{ \"Server\": \"http://127.0.0.1:20000\" }").unwrap();
        assert_eq!(config.server, "http://127.0.0.1:20000");
        assert!(config.game_path.is_none());

        let dir = std::env::temp_dir().join(format!("lm-launcher-test-{}", std::process::id()));
        let path = dir.join(CONFIG_FILE_NAME);
        fs::create_dir_all(&dir).unwrap();
        fs::write(&path, "\u{feff}{ \"Server\": \"http://h:1\", \"GamePath\": \"C:/g/Landmark64.exe\" }").unwrap();
        let loaded = load(&path).unwrap();
        assert_eq!(loaded.server, "http://h:1");
        assert_eq!(loaded.game_path.as_deref(), Some("C:/g/Landmark64.exe"));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn missing_file_yields_defaults() {
        let path = std::env::temp_dir().join(format!("lm-missing-{}", std::process::id())).join(CONFIG_FILE_NAME);
        let config = load(&path).unwrap();
        assert_eq!(config.server, DEFAULT_SERVER);
        let _ = fs::remove_dir_all(path.parent().unwrap());
    }
}
