mod auth;
mod config;
mod game_patch;

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;

use crate::auth::Session;
use crate::config::LauncherConfig;

const GAME_EXECUTABLE: &str = "Landmark64.exe";

struct Credentials {
    username: String,
    password: String,
}

struct LauncherState {
    config_path: PathBuf,
    config: Mutex<LauncherConfig>,
    session: Mutex<Option<Session>>,
    credentials: Mutex<Option<Credentials>>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct StateView {
    server: String,
    game_path: Option<String>,
    config_path: String,
    username: Option<String>,
}

fn view(state: &LauncherState) -> StateView {
    let config = state.config.lock().unwrap();
    StateView {
        server: config.server.clone(),
        game_path: config.game_path.clone(),
        config_path: state.config_path.display().to_string(),
        username: state.credentials.lock().unwrap().as_ref().map(|c| c.username.clone()),
    }
}

#[tauri::command]
fn get_state(state: State<'_, LauncherState>) -> StateView {
    view(&state)
}

#[tauri::command]
async fn login(username: String, password: String, state: State<'_, LauncherState>) -> Result<StateView, String> {
    let username = username.trim().to_string();
    if username.is_empty() || password.is_empty() {
        return Err("Enter a username and password.".to_string());
    }
    let server = state.config.lock().unwrap().server.clone();
    let session = auth::authenticate(&server, &username, &password).await?;

    *state.session.lock().unwrap() = Some(session);
    // Kept in memory only, so an expired session can be renewed when Play is pressed.
    *state.credentials.lock().unwrap() = Some(Credentials { username, password });
    Ok(view(&state))
}

#[tauri::command]
fn logout(state: State<'_, LauncherState>) -> StateView {
    *state.session.lock().unwrap() = None;
    *state.credentials.lock().unwrap() = None;
    view(&state)
}

fn is_game_executable(path: &Path) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name.eq_ignore_ascii_case(GAME_EXECUTABLE))
}

fn pick_game(app: &AppHandle) -> Result<Option<PathBuf>, String> {
    let picked = app
        .dialog()
        .file()
        .set_title("Locate Landmark64.exe")
        .add_filter("Landmark Applications", &["exe"])
        .blocking_pick_file();
    let Some(picked) = picked else {
        return Ok(None);
    };
    let path = picked.into_path().map_err(|e| e.to_string())?;
    if !is_game_executable(&path) {
        return Err(format!("Please select {GAME_EXECUTABLE}."));
    }
    Ok(Some(path))
}

fn remember_game(state: &LauncherState, path: &Path) -> Result<(), String> {
    let mut config = state.config.lock().unwrap();
    config.game_path = Some(path.display().to_string());
    config::save(&state.config_path, &config)
}

#[tauri::command]
async fn select_game(app: AppHandle, state: State<'_, LauncherState>) -> Result<StateView, String> {
    if let Some(path) = pick_game(&app)? {
        // Saving is best effort; the path is still used for this run.
        if let Err(e) = remember_game(&state, &path) {
            eprintln!("{e}");
        }
    }
    Ok(view(&state))
}

#[tauri::command]
async fn play(app: AppHandle, state: State<'_, LauncherState>) -> Result<(), String> {
    // Locate the game, asking once if it is unknown or has moved.
    let configured = state.config.lock().unwrap().game_path.clone().map(PathBuf::from);
    let game = match configured.filter(|p| p.is_file()) {
        Some(path) => path,
        None => {
            let path = pick_game(&app)?.ok_or("Landmark Location wasn't set! Please try again.")?;
            if let Err(e) = remember_game(&state, &path) {
                eprintln!("{e}");
            }
            path
        }
    };

    // Renew the session key if it has (nearly) expired.
    let current = state.session.lock().unwrap().clone().filter(Session::is_valid);
    let session = match current {
        Some(session) => session,
        None => {
            let (username, password) = {
                let credentials = state.credentials.lock().unwrap();
                let c = credentials.as_ref().ok_or("Please log in first.")?;
                (c.username.clone(), c.password.clone())
            };
            let server = state.config.lock().unwrap().server.clone();
            let session = auth::authenticate(&server, &username, &password).await?;
            *state.session.lock().unwrap() = Some(session.clone());
            session
        }
    };

    let working_dir = game.parent().ok_or("Invalid game location.")?;
    let mut command = Command::new(&game);
    command
        .args([format!("SessionId={}", session.key), "CasSessionId=0".into(), "STEAM_ENABLED=0".into()])
        .current_dir(working_dir);
    game_patch::spawn_patched(&mut command).map_err(|e| format!("Could not start {}: {e}", game.display()))?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let config_path = config::resolve_path(app.path().app_config_dir().ok());
            let config = config::load(&config_path).unwrap_or_else(|e| {
                eprintln!("{e}; using defaults");
                LauncherConfig::default()
            });
            app.manage(LauncherState {
                config_path,
                config: Mutex::new(config),
                session: Mutex::new(None),
                credentials: Mutex::new(None),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_state, login, logout, select_game, play])
        .run(tauri::generate_context!())
        .expect("error while running the Landmark launcher");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_landmark_executable_is_accepted() {
        assert!(is_game_executable(Path::new("C:/Games/Landmark/Landmark64.exe")));
        assert!(is_game_executable(Path::new("C:/Games/Landmark/landmark64.EXE")));
        assert!(!is_game_executable(Path::new("C:/Games/Landmark/Launcher.exe")));
    }
}
