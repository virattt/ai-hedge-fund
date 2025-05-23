import json
from pathlib import Path
from typing import List, Dict

import numpy as np
import plotly.graph_objects as go


def load_timeline(path: str | Path | None = None) -> List[Dict]:
    """Load timeline data from a JSON file."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "docs" / "blockchain_timeline.json"
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_sphere(events: List[Dict]) -> None:
    """Render timeline events on a 3-D sphere using Plotly."""
    if not events:
        raise ValueError("No events provided")

    n = len(events)
    radius = 1.0
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    phi = np.linspace(0, np.pi, n)

    x = radius * np.sin(phi) * np.cos(theta)
    y = radius * np.sin(phi) * np.sin(theta)
    z = radius * np.cos(phi)

    labels = [f"{e['year']}: {e['event']}" for e in events]

    scatter = go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="markers+text",
        text=labels,
        textposition="top center",
        marker=dict(size=5, color="red"),
    )

    u, v = np.mgrid[0 : 2 * np.pi : 50j, 0 : np.pi : 25j]
    sphere_x = radius * np.cos(u) * np.sin(v)
    sphere_y = radius * np.sin(u) * np.sin(v)
    sphere_z = radius * np.cos(v)

    surface = go.Surface(x=sphere_x, y=sphere_y, z=sphere_z, opacity=0.3, showscale=False)

    fig = go.Figure([surface, scatter])
    fig.update_layout(title="Blockchain Timeline Sphere", scene=dict(aspectmode="cube"))
    fig.show()


def main():
    events = load_timeline()
    plot_sphere(events)


if __name__ == "__main__":
    main()
