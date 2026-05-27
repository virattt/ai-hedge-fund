use axum::{
    response::sse::{Event, Sse},
    routing::get,
    Router,
    Json,
};
use std::time::Duration;
use futures_util::stream::Stream;
use tokio_stream::StreamExt;

pub fn router() -> Router {
    Router::new()
        .route("/", get(root))
        .route("/ping", get(ping))
}

async fn root() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "message": "Welcome to AI Hedge Fund API" }))
}

async fn ping() -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
    let stream = tokio_stream::iter(0..5)
        .throttle(Duration::from_secs(1))
        .map(|i| {
            let data = serde_json::json!({
                "ping": format!("ping {}/5", i + 1),
                "timestamp": i + 1
            });
            let event = Event::default().data(data.to_string());
            Ok(event)
        });

    Sse::new(stream).keep_alive(axum::response::sse::KeepAlive::default())
}
