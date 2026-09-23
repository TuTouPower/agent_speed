from agent_speed.harness.base import BaseHarness
from agent_speed.harness.opencode import OpencodeHarness
from agent_speed.harness.grok import GrokHarness
from agent_speed.harness.codex import CodexHarness
from agent_speed.harness.kimi import KimiHarness
from agent_speed.harness.antigravity import AntigravityHarness
from agent_speed.harness.mimo import MimoHarness


def get_harness(name: str) -> BaseHarness:
    mapping = {
        # 官方权威包名 / CLI
        "opencode": OpencodeHarness,
        "mimo-code": MimoHarness,
        "grok-build": GrokHarness,
        "codex": CodexHarness,
        "kimi-code": KimiHarness,
        "antigravity": AntigravityHarness,
        # 别名向下兼容
        "mimo": MimoHarness,
        "grok": GrokHarness,
        "kimi": KimiHarness,
        "agy": AntigravityHarness,
    }
    cls = mapping.get(name)
    if not cls:
        raise ValueError(f"Unknown harness: {name}")
    return cls()
