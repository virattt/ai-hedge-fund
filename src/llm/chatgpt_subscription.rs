//! ChatGPT Plus/Pro subscription auth and Codex API helpers.
//!
//! OAuth PKCE flow against auth.openai.com, token refresh, and credential persistence.

use anyhow::{anyhow, Context, Result};
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine as _;
use rand::RngCore;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
#[cfg(test)]
use std::net::TcpListener as StdTcpListener;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
#[cfg(test)]
use std::sync::Mutex as StdMutex;
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tokio::sync::Mutex;

pub const CODEX_BASE_URL: &str = "https://chatgpt.com/backend-api/codex";
pub const CODEX_RESPONSES_URL: &str = "https://chatgpt.com/backend-api/codex/responses";
pub const OPENAI_TOKEN_URL: &str = "https://auth.openai.com/oauth/token";
pub const OPENAI_AUTHORIZE_URL: &str = "https://auth.openai.com/oauth/authorize";
pub const CLIENT_ID: &str = "app_EMoamEEZ73f0CkXaXp7hrann";
pub const CREDENTIALS_KEY: &str = "https://chatgpt.com/backend-api/codex";
pub const KEYRING_SERVICE: &str = "open-hedge";
pub const ORIGINATOR: &str = "open-hedge";

const TOKEN_REFRESH_BUFFER_MS: u64 = 5 * 60 * 1000;
const CODEX_CALLBACK_HOST: &str = "localhost";
const CODEX_CALLBACK_PORT: u16 = 1455;
const CODEX_CALLBACK_FALLBACK_PORT: u16 = 1457;
const CODEX_CALLBACK_PATH: &str = "/auth/callback";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CodexCredentials {
    pub access_token: String,
    pub refresh_token: String,
    pub expires_at_ms: u64,
    pub account_id: Option<String>,
    pub email: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChatGptSubscriptionStatus {
    pub authenticated: bool,
    pub email: Option<String>,
}

#[derive(Debug, Clone)]
pub struct PkcePair {
    pub verifier: String,
    pub challenge: String,
}

#[derive(Debug, Clone, Deserialize)]
struct TokenResponse {
    access_token: String,
    refresh_token: String,
    #[serde(default)]
    id_token: Option<String>,
    expires_in: u64,
    #[serde(default)]
    email: Option<String>,
}

#[derive(Debug, Clone)]
struct OAuthCallback {
    code: String,
    state: String,
}

struct JwtClaims {
    account_id: Option<String>,
    email: Option<String>,
}

#[derive(Debug)]
enum RefreshError {
    Fatal(anyhow::Error),
    Transient(anyhow::Error),
}

struct AuthState {
    credentials: Mutex<Option<CodexCredentials>>,
    refresh_mutex: Mutex<()>,
    auth_generation: AtomicU64,
}

static AUTH_STATE: OnceLock<AuthState> = OnceLock::new();

fn auth_state() -> &'static AuthState {
    AUTH_STATE.get_or_init(|| AuthState {
        credentials: Mutex::new(None),
        refresh_mutex: Mutex::new(()),
        auth_generation: AtomicU64::new(0),
    })
}

pub fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

impl CodexCredentials {
    pub fn is_expired(&self) -> bool {
        now_ms() + TOKEN_REFRESH_BUFFER_MS >= self.expires_at_ms
    }
}

pub fn generate_pkce_pair() -> PkcePair {
    let mut verifier_bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut verifier_bytes);
    let verifier = URL_SAFE_NO_PAD.encode(verifier_bytes);

    let mut hasher = Sha256::new();
    hasher.update(verifier.as_bytes());
    let challenge = URL_SAFE_NO_PAD.encode(hasher.finalize());

    PkcePair {
        verifier,
        challenge,
    }
}

pub fn generate_oauth_state() -> String {
    let mut state_bytes = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut state_bytes);
    state_bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn extract_jwt_claims(jwt: &str) -> (Option<String>, Option<String>) {
    let Some(payload_b64) = jwt.split('.').nth(1) else {
        return (None, None);
    };
    let Ok(payload) = URL_SAFE_NO_PAD.decode(payload_b64) else {
        return (None, None);
    };
    let Ok(claims) = serde_json::from_slice::<serde_json::Value>(&payload) else {
        return (None, None);
    };

    let claims = JwtClaims {
        account_id: claims
            .get("chatgpt_account_id")
            .and_then(|v| v.as_str())
            .or_else(|| {
                claims
                    .get("https://api.openai.com/auth")
                    .and_then(|v| v.get("chatgpt_account_id"))
                    .and_then(|v| v.as_str())
            })
            .or_else(|| {
                claims
                    .get("organizations")
                    .and_then(|v| v.as_array())
                    .and_then(|arr| arr.first())
                    .and_then(|org| org.get("id"))
                    .and_then(|v| v.as_str())
            })
            .map(str::to_owned),
        email: claims
            .get("email")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
    };

    (claims.account_id, claims.email)
}

/// Path to the file fallback for Codex OAuth credentials.
pub fn credentials_file_path() -> PathBuf {
    if let Ok(path) = std::env::var("OPEN_HEDGE_CODEX_AUTH_PATH") {
        let trimmed = path.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }

    for var in ["HOME", "USERPROFILE"] {
        if let Ok(home) = std::env::var(var) {
            let trimmed = home.trim();
            if !trimmed.is_empty() {
                return PathBuf::from(trimmed)
                    .join(".open-hedge")
                    .join("codex-auth.json");
            }
        }
    }

    PathBuf::from(".open-hedge/codex-auth.json")
}

fn auth_file_path() -> PathBuf {
    credentials_file_path()
}

fn read_credentials_from_keyring() -> Option<CodexCredentials> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, CREDENTIALS_KEY).ok()?;
    let json = entry.get_password().ok()?;
    serde_json::from_str(&json).ok()
}

fn write_credentials_to_keyring(creds: &CodexCredentials) -> Result<()> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, CREDENTIALS_KEY)?;
    let json = serde_json::to_string(creds)?;
    entry.set_password(&json)?;
    Ok(())
}

fn delete_credentials_from_keyring() -> Result<()> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, CREDENTIALS_KEY)?;
    match entry.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(err.into()),
    }
}

fn read_credentials_from_file() -> Option<CodexCredentials> {
    let path = auth_file_path();
    let content = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

fn write_credentials_to_file(creds: &CodexCredentials) -> Result<()> {
    let path = auth_file_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let json = serde_json::to_string_pretty(creds)?;
    std::fs::write(path, json)?;
    Ok(())
}

fn delete_credentials_from_file() -> Result<()> {
    let path = auth_file_path();
    if path.exists() {
        std::fs::remove_file(path)?;
    }
    Ok(())
}

pub fn load_credentials_from_storage() -> Option<CodexCredentials> {
    read_credentials_from_file().or_else(read_credentials_from_keyring)
}

fn persist_credentials(creds: &CodexCredentials) -> Result<()> {
    write_credentials_to_file(creds).with_context(|| {
        format!(
            "Failed to save credentials to {}",
            auth_file_path().display()
        )
    })?;
    let _ = write_credentials_to_keyring(creds);
    Ok(())
}

fn delete_credentials_from_storage() -> Result<()> {
    let _ = delete_credentials_from_keyring();
    delete_credentials_from_file()
}

pub async fn ensure_credentials_loaded() {
    let state = auth_state();
    let mut guard = state.credentials.lock().await;
    if guard.is_none() {
        *guard = load_credentials_from_storage();
    }
}

pub fn is_authenticated_sync() -> bool {
    if let Some(state) = AUTH_STATE.get() {
        if let Ok(guard) = state.credentials.try_lock() {
            if guard.is_some() {
                return true;
            }
        }
    }
    load_credentials_from_storage().is_some()
}

pub async fn is_authenticated() -> bool {
    ensure_credentials_loaded().await;
    auth_state().credentials.lock().await.is_some()
}

pub async fn status() -> ChatGptSubscriptionStatus {
    ensure_credentials_loaded().await;
    let creds = auth_state().credentials.lock().await.clone();
    match creds {
        Some(c) => ChatGptSubscriptionStatus {
            authenticated: true,
            email: c.email,
        },
        None => ChatGptSubscriptionStatus {
            authenticated: false,
            email: None,
        },
    }
}

pub async fn sign_out() -> Result<()> {
    let state = auth_state();
    state.auth_generation.fetch_add(1, Ordering::SeqCst);
    *state.credentials.lock().await = None;
    delete_credentials_from_storage()?;
    Ok(())
}

fn build_authorize_url(redirect_uri: &str, challenge: &str, oauth_state: &str) -> Result<String> {
    let mut auth_url = url::Url::parse(OPENAI_AUTHORIZE_URL)?;
    auth_url
        .query_pairs_mut()
        .append_pair("client_id", CLIENT_ID)
        .append_pair("redirect_uri", redirect_uri)
        .append_pair(
            "scope",
            "openid profile email offline_access api.connectors.read api.connectors.invoke",
        )
        .append_pair("response_type", "code")
        .append_pair("code_challenge", challenge)
        .append_pair("code_challenge_method", "S256")
        .append_pair("id_token_add_organizations", "true")
        .append_pair("state", oauth_state)
        .append_pair("codex_cli_simplified_flow", "true")
        .append_pair("originator", ORIGINATOR);
    Ok(auth_url.to_string())
}

fn open_auth_url(url: &str) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open").arg(url).spawn()?;
        return Ok(());
    }
    #[cfg(target_os = "linux")]
    {
        if std::process::Command::new("xdg-open")
            .arg(url)
            .spawn()
            .is_ok()
        {
            return Ok(());
        }
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", url])
            .spawn()?;
        return Ok(());
    }
    #[allow(unreachable_code)]
    {
        println!("Open this URL in your browser to sign in:\n{url}");
        Ok(())
    }
}

async fn start_oauth_callback_server() -> Result<(
    String,
    tokio::sync::oneshot::Receiver<Result<OAuthCallback>>,
)> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    for port in [CODEX_CALLBACK_PORT, CODEX_CALLBACK_FALLBACK_PORT] {
        let addr = format!("{CODEX_CALLBACK_HOST}:{port}");
        if let Ok(listener) = TcpListener::bind(&addr).await {
            let redirect_uri = format!("http://{CODEX_CALLBACK_HOST}:{port}{CODEX_CALLBACK_PATH}");
            tokio::spawn(run_callback_server(listener, tx));
            return Ok((redirect_uri, rx));
        }
    }

    Err(anyhow!(
        "Failed to bind OAuth callback server on ports 1455/1457"
    ))
}

async fn run_callback_server(
    listener: TcpListener,
    tx: tokio::sync::oneshot::Sender<Result<OAuthCallback>>,
) {
    let result = async {
        let (mut stream, _) = listener
            .accept()
            .await
            .context("Failed to accept OAuth callback")?;
        let mut buffer = vec![0u8; 8192];
        let n = stream
            .read(&mut buffer)
            .await
            .context("Failed to read OAuth callback")?;
        let request = String::from_utf8_lossy(&buffer[..n]);
        let request_line = request.lines().next().unwrap_or_default();
        let path = request_line
            .split_whitespace()
            .nth(1)
            .unwrap_or_default();
        let parsed = url::Url::parse(&format!("http://localhost{path}"))
            .context("Failed to parse callback URL")?;

        let code = parsed
            .query_pairs()
            .find(|(k, _)| k == "code")
            .map(|(_, v)| v.to_string())
            .ok_or_else(|| anyhow!("Missing authorization code in callback"))?;
        let state = parsed
            .query_pairs()
            .find(|(k, _)| k == "state")
            .map(|(_, v)| v.to_string())
            .ok_or_else(|| anyhow!("Missing OAuth state in callback"))?;

        let response_body = "Authentication successful. You can close this tab.";
        let response = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            response_body.len(),
            response_body
        );
        stream.write_all(response.as_bytes()).await.ok();
        stream.shutdown().await.ok();

        Ok(OAuthCallback { code, state })
    }
    .await;

    let _ = tx.send(result);
}

fn token_endpoint_url() -> String {
    std::env::var("OPEN_HEDGE_CODEX_TOKEN_URL").unwrap_or_else(|_| OPENAI_TOKEN_URL.to_string())
}

async fn exchange_code(
    client: &Client,
    code: &str,
    verifier: &str,
    redirect_uri: &str,
) -> Result<TokenResponse> {
    let body = [
        ("grant_type", "authorization_code"),
        ("client_id", CLIENT_ID),
        ("code", code),
        ("redirect_uri", redirect_uri),
        ("code_verifier", verifier),
    ];

    let response = client
        .post(token_endpoint_url())
        .header("Content-Type", "application/x-www-form-urlencoded")
        .form(&body)
        .send()
        .await?;

    let status = response.status();
    let text = response.text().await?;
    if !status.is_success() {
        return Err(anyhow!("Token exchange failed (HTTP {status}): {text}"));
    }

    serde_json::from_str(&text).context("Failed to parse token response")
}

async fn refresh_token(
    client: &Client,
    refresh_token: &str,
) -> Result<CodexCredentials, RefreshError> {
    let body = [
        ("grant_type", "refresh_token"),
        ("client_id", CLIENT_ID),
        ("refresh_token", refresh_token),
    ];

    let response = client
        .post(token_endpoint_url())
        .header("Content-Type", "application/x-www-form-urlencoded")
        .form(&body)
        .send()
        .await
        .map_err(|e| RefreshError::Transient(e.into()))?;

    let status = response.status();
    let text = response
        .text()
        .await
        .map_err(|e| RefreshError::Transient(e.into()))?;

    if !status.is_success() {
        let err = anyhow!("Token refresh failed (HTTP {status}): {text}");
        if status.as_u16() == 400 || status.as_u16() == 401 || status.as_u16() == 403 {
            return Err(RefreshError::Fatal(err));
        }
        return Err(RefreshError::Transient(err));
    }

    let tokens: TokenResponse =
        serde_json::from_str(&text).map_err(|e| RefreshError::Transient(e.into()))?;

    Ok(tokens_to_credentials(&tokens))
}

fn tokens_to_credentials(tokens: &TokenResponse) -> CodexCredentials {
    let jwt = tokens
        .id_token
        .as_deref()
        .unwrap_or(tokens.access_token.as_str());
    let (account_id, jwt_email) = extract_jwt_claims(jwt);

    CodexCredentials {
        access_token: tokens.access_token.clone(),
        refresh_token: tokens.refresh_token.clone(),
        expires_at_ms: now_ms() + tokens.expires_in * 1000,
        account_id,
        email: jwt_email.or_else(|| tokens.email.clone()),
    }
}

pub async fn sign_in() -> Result<CodexCredentials> {
    let client = Client::new();
    let (redirect_uri, callback_rx) = start_oauth_callback_server().await?;
    let pkce = generate_pkce_pair();
    let oauth_state = generate_oauth_state();
    let auth_url = build_authorize_url(&redirect_uri, &pkce.challenge, &oauth_state)?;

    println!("Opening browser for ChatGPT subscription sign-in...");
    open_auth_url(&auth_url)?;

    let callback = callback_rx
        .await
        .map_err(|_| anyhow!("OAuth callback was cancelled"))??;

    if callback.state != oauth_state {
        return Err(anyhow!("OAuth state mismatch"));
    }

    let tokens = exchange_code(&client, &callback.code, &pkce.verifier, &redirect_uri).await?;
    let creds = tokens_to_credentials(&tokens);
    persist_credentials(&creds)?;
    println!(
        "Credentials saved to {} (and OS keychain when available).",
        auth_file_path().display()
    );

    let state = auth_state();
    *state.credentials.lock().await = Some(creds.clone());
    Ok(creds)
}

pub async fn get_valid_access_token() -> Result<String> {
    ensure_credentials_loaded().await;
    let state = auth_state();

    let creds = state.credentials.lock().await.clone().ok_or_else(|| {
        anyhow!("ChatGPT subscription is not authenticated. Run `chatgpt login`.")
    })?;

    if !creds.is_expired() {
        return Ok(creds.access_token);
    }

    let _refresh_guard = state.refresh_mutex.lock().await;

    if let Some(fresh) = state.credentials.lock().await.clone() {
        if !fresh.is_expired() {
            return Ok(fresh.access_token);
        }
    }

    let generation = state.auth_generation.load(Ordering::SeqCst);
    let refresh_token_value = state
        .credentials
        .lock()
        .await
        .as_ref()
        .map(|c| c.refresh_token.clone())
        .ok_or_else(|| {
            anyhow!("ChatGPT subscription is not authenticated. Run `chatgpt login`.")
        })?;

    let client = Client::new();
    let refreshed = match refresh_token(&client, &refresh_token_value).await {
        Ok(refreshed) => refreshed,
        Err(RefreshError::Fatal(err)) => {
            let _ = sign_out().await;
            return Err(err);
        }
        Err(RefreshError::Transient(err)) => return Err(err),
    };

    if state.auth_generation.load(Ordering::SeqCst) != generation {
        return Err(anyhow!("Sign-out occurred during token refresh"));
    }

    persist_credentials(&refreshed)?;
    *state.credentials.lock().await = Some(refreshed.clone());
    Ok(refreshed.access_token)
}

pub fn build_codex_request_body(
    model: &str,
    instructions: &str,
    user_prompt: &str,
) -> serde_json::Value {
    serde_json::json!({
        "model": model,
        "instructions": instructions,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    { "type": "input_text", "text": user_prompt }
                ]
            }
        ],
        "stream": true,
        "store": false,
        "text": {
            "format": { "type": "json_object" }
        }
    })
}

pub fn extract_text_from_codex_response(response: &serde_json::Value) -> Option<String> {
    if let Some(text) = response.get("output_text").and_then(|v| v.as_str()) {
        return Some(text.to_string());
    }

    response
        .get("output")
        .and_then(|output| output.as_array())
        .and_then(|items| {
            items.iter().find_map(|item| {
                item.get("content")
                    .and_then(|c| c.as_array())
                    .and_then(|parts| {
                        parts.iter().find_map(|part| {
                            part.get("text")
                                .and_then(|t| t.as_str())
                                .map(str::to_string)
                        })
                    })
            })
        })
}

fn parse_sse_data_line(line: &str) -> Option<&str> {
    let line = line.trim();
    if line.is_empty() || line.starts_with(':') {
        return None;
    }
    let data = line
        .strip_prefix("data: ")
        .or_else(|| line.strip_prefix("data:"))?
        .trim();
    if data == "[DONE]" || data.is_empty() {
        return None;
    }
    Some(data)
}

fn stream_error_from_event(event: &serde_json::Value) -> Option<String> {
    if let Some(error) = event.get("error") {
        if let Some(message) = error.get("message").and_then(|m| m.as_str()) {
            return Some(message.to_string());
        }
        if error.is_string() {
            return error.as_str().map(str::to_owned);
        }
    }
    event
        .get("response")
        .and_then(|response| response.get("error"))
        .and_then(|error| error.get("message"))
        .and_then(|m| m.as_str())
        .map(str::to_owned)
}

/// Parse a Codex `/responses` SSE body and return the assembled text output.
pub fn parse_codex_sse_response(body: &str) -> Result<String> {
    let mut delta_text = String::new();
    let mut completed_text: Option<String> = None;

    for line in body.lines() {
        let Some(data) = parse_sse_data_line(line) else {
            continue;
        };

        let event: serde_json::Value = match serde_json::from_str(data) {
            Ok(event) => event,
            Err(_) => continue,
        };

        match event.get("type").and_then(|value| value.as_str()) {
            Some("response.output_text.delta") => {
                if let Some(delta) = event.get("delta").and_then(|value| value.as_str()) {
                    delta_text.push_str(delta);
                }
            }
            Some("response.output_text.done") => {
                if let Some(text) = event.get("text").and_then(|value| value.as_str()) {
                    if delta_text.is_empty() {
                        delta_text.push_str(text);
                    }
                }
            }
            Some("response.completed") | Some("response.incomplete") => {
                if let Some(response) = event.get("response") {
                    if let Some(text) = extract_text_from_codex_response(response) {
                        completed_text = Some(text);
                    }
                }
            }
            Some("response.error") | Some("error") | Some("response.failed") => {
                if let Some(message) = stream_error_from_event(&event) {
                    return Err(anyhow!("Codex stream error: {message}"));
                }
            }
            Some("response.refusal.done") => {
                if let Some(refusal) = event.get("refusal").and_then(|value| value.as_str()) {
                    return Err(anyhow!("Codex stream refusal: {refusal}"));
                }
            }
            _ => {}
        }
    }

    if !delta_text.is_empty() {
        return Ok(delta_text);
    }

    completed_text.ok_or_else(|| anyhow!("Codex SSE stream did not contain text output"))
}

pub async fn call_codex_responses(
    client: &Client,
    access_token: &str,
    account_id: Option<&str>,
    model: &str,
    instructions: &str,
    user_prompt: &str,
) -> Result<String> {
    let payload = build_codex_request_body(model, instructions, user_prompt);

    let mut request = client
        .post(CODEX_RESPONSES_URL)
        .header("Authorization", format!("Bearer {access_token}"))
        .header("Content-Type", "application/json")
        .header("originator", ORIGINATOR)
        .header("OpenAI-Beta", "responses=experimental");

    if let Some(id) = account_id.filter(|s| !s.is_empty()) {
        request = request.header("ChatGPT-Account-Id", id);
    }

    let response = request.json(&payload).send().await?;
    let status = response.status();
    let body = response.text().await.unwrap_or_default();

    if !status.is_success() {
        return Err(anyhow!(
            "Codex Responses API failed (HTTP {status}): {body}"
        ));
    }

    if body.contains("data:") {
        return parse_codex_sse_response(&body);
    }

    let json: serde_json::Value = serde_json::from_str(&body).unwrap_or(serde_json::Value::Null);
    extract_text_from_codex_response(&json)
        .ok_or_else(|| anyhow!("Codex response did not contain text output: {body}"))
}

#[cfg(test)]
pub fn set_test_credentials(creds: Option<CodexCredentials>) {
    let state = auth_state();
    if let Ok(mut guard) = state.credentials.try_lock() {
        *guard = creds;
    }
}

#[cfg(test)]
static ENV_TEST_LOCK: StdMutex<()> = StdMutex::new(());

#[cfg(test)]
pub(crate) fn env_test_guard() -> std::sync::MutexGuard<'static, ()> {
    ENV_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn env_test_guard() -> std::sync::MutexGuard<'static, ()> {
        super::env_test_guard()
    }

    #[test]
    fn pkce_challenge_matches_verifier() {
        let pair = generate_pkce_pair();
        assert!(!pair.verifier.is_empty());
        assert!(!pair.challenge.is_empty());
        assert_ne!(pair.verifier, pair.challenge);

        let mut hasher = Sha256::new();
        hasher.update(pair.verifier.as_bytes());
        let expected = URL_SAFE_NO_PAD.encode(hasher.finalize());
        assert_eq!(pair.challenge, expected);
    }

    #[test]
    fn oauth_state_is_32_hex_chars() {
        let state = generate_oauth_state();
        assert_eq!(state.len(), 32);
        assert!(state.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn extract_jwt_claims_reads_account_and_email() {
        let payload = serde_json::json!({
            "chatgpt_account_id": "acct_123",
            "email": "user@example.com"
        });
        let encoded = URL_SAFE_NO_PAD.encode(payload.to_string());
        let jwt = format!("header.{encoded}.signature");
        let (account_id, email) = extract_jwt_claims(&jwt);
        assert_eq!(account_id.as_deref(), Some("acct_123"));
        assert_eq!(email.as_deref(), Some("user@example.com"));
    }

    #[test]
    fn credentials_expiry_uses_refresh_buffer() {
        let creds = CodexCredentials {
            access_token: "a".into(),
            refresh_token: "r".into(),
            expires_at_ms: now_ms() + TOKEN_REFRESH_BUFFER_MS + 60_000,
            account_id: None,
            email: None,
        };
        assert!(!creds.is_expired());

        let expired = CodexCredentials {
            expires_at_ms: now_ms() + TOKEN_REFRESH_BUFFER_MS - 1,
            ..creds
        };
        assert!(expired.is_expired());
    }

    #[test]
    fn build_codex_request_body_matches_responses_api() {
        let body = build_codex_request_body("gpt-5.4-mini", "system", "user");
        assert_eq!(
            body.get("model").and_then(|v| v.as_str()),
            Some("gpt-5.4-mini")
        );
        assert_eq!(
            body.get("instructions").and_then(|v| v.as_str()),
            Some("system")
        );
        assert_eq!(body.get("stream").and_then(|v| v.as_bool()), Some(true));
        assert_eq!(body.get("store").and_then(|v| v.as_bool()), Some(false));
        assert_eq!(
            body.get("text")
                .and_then(|v| v.get("format"))
                .and_then(|v| v.get("type"))
                .and_then(|v| v.as_str()),
            Some("json_object")
        );
        assert!(body.get("input").and_then(|v| v.as_array()).is_some());
    }

    #[test]
    fn extract_text_from_codex_response_parses_output_array() {
        let response = serde_json::json!({
            "output": [{
                "type": "message",
                "content": [{ "type": "output_text", "text": "{\"signal\":\"bullish\"}" }]
            }]
        });
        let text = extract_text_from_codex_response(&response).unwrap();
        assert!(text.contains("bullish"));
    }

    #[test]
    fn parse_codex_sse_response_assembles_delta_chunks() {
        let fixture = concat!(
            "data: {\"type\":\"response.created\",\"response\":{\"id\":\"resp_1\"}}\n\n",
            "data: {\"type\":\"response.output_text.delta\",\"item_id\":\"msg_1\",\"output_index\":0,\"delta\":\"{\\\"signal\\\":\"}\n\n",
            "data: {\"type\":\"response.output_text.delta\",\"item_id\":\"msg_1\",\"output_index\":0,\"delta\":\"\\\"bullish\\\"}\"}\n\n",
            "data: {\"type\":\"response.output_text.done\",\"item_id\":\"msg_1\",\"output_index\":0,\"text\":\"{\\\"signal\\\":\\\"bullish\\\"}\"}\n\n",
            "data: [DONE]\n\n",
        );

        let text = parse_codex_sse_response(fixture).unwrap();
        assert_eq!(text, r#"{"signal":"bullish"}"#);
    }

    #[test]
    fn parse_codex_sse_response_falls_back_to_completed_event() {
        let fixture = concat!(
            "data: {\"type\":\"response.completed\",\"response\":{\"output\":[{\"type\":\"message\",\"content\":[{\"type\":\"output_text\",\"text\":\"{\\\"signal\\\":\\\"neutral\\\"}\"}]}]}}\n\n",
            "data: [DONE]\n\n",
        );

        let text = parse_codex_sse_response(fixture).unwrap();
        assert!(text.contains("neutral"));
    }

    #[test]
    fn parse_codex_sse_response_surfaces_stream_errors() {
        let fixture = concat!(
            "data: {\"type\":\"response.error\",\"error\":{\"message\":\"rate limited\"}}\n\n",
            "data: [DONE]\n\n",
        );

        let err = parse_codex_sse_response(fixture).unwrap_err();
        assert!(err.to_string().contains("rate limited"));
    }

    #[test]
    fn persist_credentials_always_writes_file() {
        let _guard = env_test_guard();
        let path = std::env::temp_dir().join(format!(
            "open-hedge-codex-persist-{}.json",
            std::process::id()
        ));
        std::env::set_var("OPEN_HEDGE_CODEX_AUTH_PATH", &path);

        let creds = CodexCredentials {
            access_token: "access".into(),
            refresh_token: "refresh".into(),
            expires_at_ms: now_ms() + 3_600_000,
            account_id: Some("acct".into()),
            email: Some("user@example.com".into()),
        };

        persist_credentials(&creds).unwrap();
        assert!(path.exists());
        let loaded = load_credentials_from_storage().unwrap();
        assert_eq!(loaded, creds);

        delete_credentials_from_file().unwrap();
        std::env::remove_var("OPEN_HEDGE_CODEX_AUTH_PATH");
    }

    #[test]
    fn file_fallback_persists_credentials() {
        let _guard = env_test_guard();
        let path =
            std::env::temp_dir().join(format!("open-hedge-codex-auth-{}.json", std::process::id()));
        std::env::set_var("OPEN_HEDGE_CODEX_AUTH_PATH", &path);

        let creds = CodexCredentials {
            access_token: "access".into(),
            refresh_token: "refresh".into(),
            expires_at_ms: now_ms() + 3_600_000,
            account_id: Some("acct".into()),
            email: Some("user@example.com".into()),
        };

        write_credentials_to_file(&creds).unwrap();
        let loaded = read_credentials_from_file().unwrap();
        assert_eq!(loaded, creds);

        delete_credentials_from_file().unwrap();
        assert!(read_credentials_from_file().is_none());
        std::env::remove_var("OPEN_HEDGE_CODEX_AUTH_PATH");
    }

    #[tokio::test]
    async fn refresh_dedup_returns_same_token() {
        let state = auth_state();
        state.auth_generation.store(0, Ordering::SeqCst);
        set_test_credentials(Some(CodexCredentials {
            access_token: "old".into(),
            refresh_token: "refresh".into(),
            expires_at_ms: now_ms() + 3_600_000,
            account_id: None,
            email: None,
        }));

        let token = get_valid_access_token().await.unwrap();
        assert_eq!(token, "old");
    }

    #[tokio::test]
    async fn refresh_token_success_updates_credentials() {
        let listener = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let listener = tokio::net::TcpListener::from_std(listener).unwrap();
        let token_url = format!("http://{}/oauth/token", listener.local_addr().unwrap());
        let path = std::env::temp_dir().join(format!(
            "open-hedge-codex-auth-refresh-ok-{}.json",
            std::process::id()
        ));

        {
            let _guard = env_test_guard();
            std::env::set_var("OPEN_HEDGE_CODEX_TOKEN_URL", &token_url);
            std::env::set_var("OPEN_HEDGE_CODEX_AUTH_PATH", &path);
            set_test_credentials(Some(CodexCredentials {
                access_token: "old".into(),
                refresh_token: "refresh".into(),
                expires_at_ms: 0,
                account_id: None,
                email: None,
            }));
        }

        tokio::spawn(async move {
            if let Ok((mut stream, _)) = listener.accept().await {
                let mut buffer = vec![0u8; 4096];
                let _ = stream.read(&mut buffer).await;
                let body = serde_json::json!({
                    "access_token": "fresh_access",
                    "refresh_token": "fresh_refresh",
                    "expires_in": 3600
                });
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.to_string().len(),
                    body
                );
                let _ = stream.write_all(response.as_bytes()).await;
            }
        });

        let token = get_valid_access_token().await.unwrap();
        assert_eq!(token, "fresh_access");

        std::env::remove_var("OPEN_HEDGE_CODEX_TOKEN_URL");
        std::env::remove_var("OPEN_HEDGE_CODEX_AUTH_PATH");
        let _ = delete_credentials_from_file();
        set_test_credentials(None);
    }

    #[tokio::test]
    async fn fatal_refresh_clears_credentials() {
        let listener = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let listener = tokio::net::TcpListener::from_std(listener).unwrap();
        let token_url = format!("http://{}/oauth/token", listener.local_addr().unwrap());
        let path = std::env::temp_dir().join(format!(
            "open-hedge-codex-auth-refresh-fatal-{}.json",
            std::process::id()
        ));

        {
            let _guard = env_test_guard();
            std::env::set_var("OPEN_HEDGE_CODEX_TOKEN_URL", &token_url);
            std::env::set_var("OPEN_HEDGE_CODEX_AUTH_PATH", &path);
            write_credentials_to_file(&CodexCredentials {
                access_token: "old".into(),
                refresh_token: "refresh".into(),
                expires_at_ms: 0,
                account_id: None,
                email: None,
            })
            .unwrap();
            set_test_credentials(Some(CodexCredentials {
                access_token: "old".into(),
                refresh_token: "refresh".into(),
                expires_at_ms: 0,
                account_id: None,
                email: None,
            }));
        }

        tokio::spawn(async move {
            if let Ok((mut stream, _)) = listener.accept().await {
                let mut buffer = vec![0u8; 4096];
                let _ = stream.read(&mut buffer).await;
                let response = "HTTP/1.1 401 Unauthorized\r\nContent-Length: 24\r\n\r\n{\"error\":\"invalid_grant\"}";
                let _ = stream.write_all(response.as_bytes()).await;
            }
        });

        let result = get_valid_access_token().await;
        assert!(result.is_err());
        assert!(!is_authenticated().await);

        std::env::remove_var("OPEN_HEDGE_CODEX_TOKEN_URL");
        std::env::remove_var("OPEN_HEDGE_CODEX_AUTH_PATH");
        set_test_credentials(None);
    }
}
