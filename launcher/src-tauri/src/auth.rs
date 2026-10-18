//! Talks to the auth server's web API (`POST /authenticate?username=..&password=..`).

use chrono::{DateTime, Duration, Local, NaiveDateTime};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AuthenticateResponse {
    session_key: Option<String>,
    session_key_expiration: Option<String>,
    #[allow(dead_code)]
    message: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Session {
    pub key: String,
    pub expires: NaiveDateTime,
}

impl Session {
    /// Re-authenticate a little before the server-side expiry.
    pub fn is_valid(&self) -> bool {
        Local::now().naive_local() + Duration::minutes(1) < self.expires
    }
}

/// The server sends local time without an offset (e.g. `2026-10-17T10:47:06.7077`).
fn parse_expiration(value: &str) -> Option<NaiveDateTime> {
    NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%S%.f")
        .ok()
        .or_else(|| DateTime::parse_from_rfc3339(value).ok().map(|d| d.with_timezone(&Local).naive_local()))
}

pub async fn authenticate(server: &str, username: &str, password: &str) -> Result<Session, String> {
    let url = format!("{}/authenticate", server.trim_end_matches('/'));
    let response = reqwest::Client::new()
        .post(&url)
        .query(&[("username", username), ("password", password)])
        .send()
        .await
        .map_err(|e| format!("Could not reach the login server at {server}: {e}"))?;

    if !response.status().is_success() {
        return Err("Failed to Authenticate. Please try again.".to_string());
    }

    let body: AuthenticateResponse =
        response.json().await.map_err(|e| format!("Unexpected response from the login server: {e}"))?;
    let key = body.session_key.filter(|k| !k.is_empty()).ok_or("The login server did not return a session key.")?;
    let expires = body
        .session_key_expiration
        .as_deref()
        .and_then(parse_expiration)
        .unwrap_or_else(|| Local::now().naive_local() + Duration::minutes(30));
    Ok(Session { key, expires })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_server_timestamps() {
        assert!(parse_expiration("2026-10-17T10:47:06.707798").is_some());
        assert!(parse_expiration("2026-10-17T10:47:06.7077981").is_some());
        assert!(parse_expiration("2026-10-17T10:47:06").is_some());
        assert!(parse_expiration("2026-10-17T10:47:06Z").is_some());
        assert!(parse_expiration("nonsense").is_none());
    }

    /// Against a running auth server:
    /// `LANDMARK_TEST_SERVER=http://127.0.0.1:5080 LANDMARK_TEST_USER=u LANDMARK_TEST_PASSWORD=p cargo test -- --ignored`
    #[test]
    #[ignore]
    fn authenticates_against_live_server() {
        let server = std::env::var("LANDMARK_TEST_SERVER").expect("LANDMARK_TEST_SERVER");
        let user = std::env::var("LANDMARK_TEST_USER").expect("LANDMARK_TEST_USER");
        let password = std::env::var("LANDMARK_TEST_PASSWORD").expect("LANDMARK_TEST_PASSWORD");
        let error = tauri::async_runtime::block_on(async {
            let session = authenticate(&server, &user, &password).await.expect("valid login");
            assert_eq!(session.key.len(), 32);
            assert!(session.is_valid());
            authenticate(&server, &user, "definitely wrong &+#").await.expect_err("bad password")
        });
        assert_eq!(error, "Failed to Authenticate. Please try again.");
    }

    #[test]
    fn session_validity() {
        let now = Local::now().naive_local();
        assert!(Session { key: "k".into(), expires: now + Duration::minutes(30) }.is_valid());
        assert!(!Session { key: "k".into(), expires: now + Duration::seconds(30) }.is_valid());
    }
}
