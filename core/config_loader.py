"""Small utility to load YAML configs consistently across the project."""

import yaml
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env once, as soon as this module is imported anywhere in the
# codebase. Every entrypoint imports from core.config_loader (directly or
# transitively), so this guarantees secrets are available before any
# provider tries to read os.environ.
load_dotenv(PROJECT_ROOT / ".env")


def load_config(filename: str = "config.yaml") -> dict:
    path = PROJECT_ROOT / "config" / filename
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_speakers() -> dict:
    """Returns dict keyed by speaker key ("A"/"B") -> persona info."""
    cfg = load_config("speakers.yaml")
    return cfg["speakers"]
