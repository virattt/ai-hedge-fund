//! CLI commands for ChatGPT subscription authentication.

use anyhow::Result;
use clap::{Parser, Subcommand};

use crate::llm::chatgpt_subscription;

#[derive(Parser, Debug)]
pub struct ChatGptArgs {
    #[command(subcommand)]
    pub command: ChatGptCommand,
}

#[derive(Subcommand, Debug)]
pub enum ChatGptCommand {
    /// Sign in with ChatGPT Plus/Pro via OAuth PKCE
    Login,
    /// Remove stored subscription credentials
    Logout,
    /// Show subscription authentication status
    Status,
}

pub async fn run(args: ChatGptArgs) -> Result<()> {
    match args.command {
        ChatGptCommand::Login => {
            let creds = chatgpt_subscription::sign_in().await?;
            let email = creds.email.unwrap_or_else(|| "unknown".to_string());
            println!("Signed in to ChatGPT subscription as {email}.");
        }
        ChatGptCommand::Logout => {
            chatgpt_subscription::sign_out().await?;
            println!("Signed out of ChatGPT subscription.");
        }
        ChatGptCommand::Status => {
            let status = chatgpt_subscription::status().await;
            if status.authenticated {
                if let Some(email) = status.email {
                    println!("ChatGPT subscription: authenticated as {email}");
                } else {
                    println!("ChatGPT subscription: authenticated");
                }
            } else {
                println!("ChatGPT subscription: not authenticated");
                println!("Run `chatgpt login` to sign in with ChatGPT Plus or Pro.");
            }
        }
    }
    Ok(())
}

/// Run ChatGPT CLI when invoked as `chatgpt login|logout|status`.
pub async fn try_run_from_env() -> Option<Result<()>> {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) != Some("chatgpt") {
        return None;
    }

    let mut trimmed = args.clone();
    trimmed.remove(1);
    let parsed = ChatGptArgs::try_parse_from(trimmed);
    Some(match parsed {
        Ok(args) => run(args).await,
        Err(err) => Err(err.into()),
    })
}
