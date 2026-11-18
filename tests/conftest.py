import pytest


def pytest_collection_modifyitems(items):
    """Marca cada teste com a camada da pirâmide de acordo com a pasta."""
    for item in items:
        for layer in ("unit", "integration", "e2e"):
            if f"/tests/{layer}/" in str(item.path).replace("\\", "/"):
                item.add_marker(getattr(pytest.mark, layer))
