from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables.graph import MermaidDrawMethod


def save_graph_as_png(app: CompiledStateGraph, output_file_path) -> None:
    png_image = app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)
    file_path = output_file_path if len(output_file_path) > 0 else "graph.png"
    with open(file_path, "wb") as f:
        f.write(png_image)