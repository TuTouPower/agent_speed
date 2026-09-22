from agent_speed.harness.base import BaseHarness
from agent_speed.harness.opencode import OpencodeHarness
from agent_speed.harness.grok import GrokHarness
from agent_speed.harness.codex import CodexHarness
from agent_speed.harness.kimi import KimiHarness
from agent_speed.harness.antigravity import AntigravityHarness


def get_harness(name: str) -> BaseHarness:
    mapping = {
        "opencode": OpencodeHarness,
        "grok": GrokHarness,
        "codex": CodexHarness,
        "kimi": KimiHarness,
        "antigravity": AntigravityHarness,
        "agy": AntigravityHarness,
    }
    cls = mapping.get(name)
    if not cls:
        raise ValueError(f"Unknown harness: {name}")
    return cls()
