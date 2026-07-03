import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Point the dataset file store at a temp dir so uploads/deletes are isolated."""
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path / "data"))
    # Settings singleton is reset by the root autouse fixture; env is read fresh.
    yield
