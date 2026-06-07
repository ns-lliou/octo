import json
from config.paths import BASE_DIR

with open(BASE_DIR / "config" / "stacks.json") as _f:
    _stacks: dict = json.load(_f)


def load_stacks() -> dict:
    return _stacks


def get_stack_names() -> list[str]:
    return list(_stacks.keys())


def get_stack(env: str) -> dict:
    return _stacks[env]


def get_knode_stacks() -> dict:
    """Return only stacks that have knode access configured."""
    return {k: v for k, v in _stacks.items() if "knodes" in v}
