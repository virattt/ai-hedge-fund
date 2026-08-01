import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_NAME = "gpt-5.5"


def _parse(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text())


def test_default_model_is_registered() -> None:
    models = json.loads((ROOT / "src/llm/api_models.json").read_text())
    registered_model_names = {model["model_name"] for model in models}

    assert DEFAULT_MODEL_NAME in registered_model_names


def test_python_defaults_use_registered_default_constant() -> None:
    models_tree = _parse("src/llm/models.py")
    default_assignments = [
        node
        for node in models_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEFAULT_MODEL_NAME" for target in node.targets)
    ]
    assert default_assignments
    assert isinstance(default_assignments[0].value, ast.Constant)
    assert default_assignments[0].value.value == DEFAULT_MODEL_NAME

    schemas_tree = _parse("app/backend/models/schemas.py")
    request_class = next(
        node
        for node in schemas_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BaseHedgeFundRequest"
    )
    model_name_field = next(
        node
        for node in request_class.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "model_name"
    )
    assert isinstance(model_name_field.value, ast.Name)
    assert model_name_field.value.id == "DEFAULT_MODEL_NAME"

    llm_tree = _parse("src/utils/llm.py")
    fallback_assignments = [
        node
        for node in ast.walk(llm_tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "model_name" for target in node.targets)
        and any(isinstance(child, ast.Name) and child.id == "DEFAULT_MODEL_NAME" for child in ast.walk(node.value))
    ]
    assert len(fallback_assignments) >= 2


def test_frontend_default_model_matches_registry_default() -> None:
    frontend_models = (ROOT / "app/frontend/src/data/models.ts").read_text()

    assert f'model.model_name === "{DEFAULT_MODEL_NAME}"' in frontend_models
    assert 'model.model_name === "gpt-4.1"' not in frontend_models


def test_no_python_runtime_default_references_removed_model() -> None:
    checked_files = [
        ROOT / "src/main.py",
        ROOT / "src/utils/llm.py",
        ROOT / "app/backend/models/schemas.py",
        ROOT / "app/backend/services/backtest_service.py",
    ]

    for path in checked_files:
        assert "gpt-4.1" not in path.read_text(), path
