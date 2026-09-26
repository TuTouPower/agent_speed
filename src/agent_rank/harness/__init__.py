from agent_rank.harness.base import BaseHarness
from agent_rank.harness.opencode import OpencodeHarness
from agent_rank.harness.grok import GrokHarness
from agent_rank.harness.codex import CodexHarness
from agent_rank.harness.kimi import KimiHarness
from agent_rank.harness.antigravity import AntigravityHarness
from agent_rank.harness.mimo import MimoHarness
from agent_rank.harness.mcode import McodeHarness


def get_harness(name: str) -> BaseHarness:
    mapping = {
        # 官方权威包名 / CLI
        "opencode": OpencodeHarness,
        "minimax-code": McodeHarness,
        "mimo-code": MimoHarness,
        "grok-build": GrokHarness,
        "codex": CodexHarness,
        "kimi-code": KimiHarness,
        "antigravity": AntigravityHarness,
        # 别名向下兼容
        "mcode": McodeHarness,
        "mimo": MimoHarness,
        "grok": GrokHarness,
        "kimi": KimiHarness,
        "agy": AntigravityHarness,
    }
    cls = mapping.get(name)
    if not cls:
        raise ValueError(f"Unknown harness: {name}")
    return cls()
