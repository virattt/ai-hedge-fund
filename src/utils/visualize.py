from langgraph.graph.state import CompiledGraph
from langchain_core.runnables.graph import MermaidDrawMethod

def get_graph(app: CompiledGraph) -> bytes:
    return app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)

def save_graph_as_png(app: CompiledGraph, output_file_path) -> None:
    png_image = get_graph(app)
    file_path = output_file_path if len(output_file_path) > 0 else "graph.png"
    with open(file_path, "wb") as f:
        f.write(png_image)