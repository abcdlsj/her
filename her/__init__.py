"""Her - 拟人化自主探索 Agent.

A proactive, personified agent that explores information autonomously.
"""

from her.core import Her, Intent, IntentType, Memory
from her.infra import create_llm, LLMConfig
from her.plugins.rsshub import RSSHub

__all__ = [
    "Her",
    "Intent",
    "IntentType",
    "Memory",
    "create_llm",
    "LLMConfig",
    "RSSHub",
]
