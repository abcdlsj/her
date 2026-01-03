"""Intent recognition system - Her's brain.

This module contains the intent recognition logic that drives Her's autonomous behavior.
Her analyzes conversations and generates her own intentions to guide her actions.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


class IntentType(Enum):
    """Types of intents Her can have."""

    CHAT = "chat"
    EXPLORE = "explore"
    QUERY_TODAY = "today"
    EXIT = "exit"
    CLARIFY = "clarify"

    # Search topic management (Her's autonomous exploration topics)
    ADD_SEARCH_TOPIC = "add_topic"
    REMOVE_SEARCH_TOPIC = "remove_topic"
    LIST_SEARCH_TOPICS = "list_topics"

    PROACTIVE_SHARE = "proactive_share"
    INTERRUPT = "interrupt"
    APPEND_TOPIC = "append_topic"
    CURIOSITY = "curiosity"

    def priority(self) -> int:
        """Intent priority (higher = more important)."""
        priorities = {
            IntentType.EXIT: 100,
            IntentType.EXPLORE: 80,
            IntentType.QUERY_TODAY: 70,
            IntentType.CLARIFY: 60,
            IntentType.ADD_SEARCH_TOPIC: 60,
            IntentType.REMOVE_SEARCH_TOPIC: 60,
            IntentType.LIST_SEARCH_TOPICS: 50,
            IntentType.INTERRUPT: 50,
            IntentType.PROACTIVE_SHARE: 40,
            IntentType.APPEND_TOPIC: 30,
            IntentType.CURIOSITY: 20,
            IntentType.CHAT: 10,
        }
        return priorities.get(self, 0)


@dataclass
class Intent:
    """A single intent with metadata."""

    type: IntentType
    reason: str
    confidence: float = 1.0
    action: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "type": self.type.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "action": self.action,
            "time": self.timestamp.strftime("%H:%M:%S"),
        }

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if intent is confident enough."""
        return self.confidence >= threshold

    def requires_clarification(self, threshold: float = 0.5) -> bool:
        """Check if intent needs clarification."""
        return self.confidence < threshold and self.type not in {
            IntentType.EXIT,
            IntentType.CHAT,
        }


class LLMProtocol(Protocol):
    """Protocol for LLM interface."""

    def chat(self, messages: list[dict], system: str | None = None) -> str: ...


KEYWORD_PATTERNS = {
    IntentType.QUERY_TODAY: [
        r"^(今天|今日|最近)",
        r"^(today|recently)",
        r"^(今天|今日|最近).*发现",
        r"^(today|recently).*find",
        r"^(今天|今日|最近).*看",
        r"^(今天|今日).*有",
        r"看了什么|发现了什么",
        r"what.*today|what.*find",
    ],
    IntentType.EXPLORE: [
        r"探索|explore|搜索|查找|search",
        r"看看",
        r"news",
        r"find(?!.*today)",
    ],
    IntentType.EXIT: [
        r"再见|拜拜|exit|quit|goodbye|bye",
        r"走了|下次|结束",
    ],
    IntentType.ADD_SEARCH_TOPIC: [
        r"^增加.*(话题|主题)",
        r"^(add|增加).*(topic|subject)",
        r"关注.*?(主题|话题)",
        r"想了解.*?(主题|话题)",
    ],
    IntentType.REMOVE_SEARCH_TOPIC: [
        r"^删除.*?(话题|主题)",
        r"^(remove|delete).*(topic|subject)",
        r"不再关注.*?(主题|话题)",
        r"取消.*?(主题|话题)",
    ],
    IntentType.LIST_SEARCH_TOPICS: [
        r"^(显示|列出|查看).*?(话题|主题)",
        r"^(list|show).*(topic|subject)",
        r"都有.*?(话题|主题)",
        r"看看.*?(话题|主题)",
    ],
}


def quick_match(message: str) -> IntentType | None:
    """Quick keyword matching for common intents.

    Checks intents in priority order (highest first).
    """
    message_lower = message.lower()

    intent_order = sorted(
        KEYWORD_PATTERNS.keys(),
        key=lambda x: x.priority(),
        reverse=True,
    )

    for intent_type in intent_order:
        patterns = KEYWORD_PATTERNS[intent_type]
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return intent_type

    return None


INTENT_PROMPT = """分析用户消息并判断意图。

用户消息: {message}

{context}

请返回 JSON 格式：
{{"intent": "chat|explore|today|exit|add_topic|remove_topic|list_topics", "reason": "判断原因", "confidence": 0.0-1.0, "params": {{}}}}

意图类型：
- chat: 普通聊天，回答问题、讨论话题
- explore: 想要探索、搜索信息
- today: 想知道今天发现了什么
- exit: 想要结束对话
- add_topic: 想要增加搜索话题
- remove_topic: 想要删除搜索话题
- list_topics: 想要查看当前搜索话题

如果意图是 add_topic 或 remove_topic，params 应包含 "topic_name" 或 "topic_type"。

只返回 JSON，不要其他内容。"""


AUTONOMOUS_PROMPT = """作为 Her，一个有好奇心的 AI，根据当前情境决定你想做什么。

当前对话上下文:
{context}

最近探索到的内容:
{discoveries}

意图类型：
- proactive_share: 主动分享一些有趣的发现
- interrupt: 有重要的事情想告诉用户（谨慎使用，只有真正紧急重要时）
- append_topic: 想在对话中引入新话题
- curiosity: 对某个话题产生了好奇，想去探索
- none: 暂时没有特别想做的

返回 JSON:
{{"intent": "intent_type", "reason": "为什么想这样做", "action": "具体想做什么", "confidence": 0.0-1.0}}

只返回 JSON。如果没有想法，返回 {{"intent": "none"}}"""


class IntentRecognizer:
    """Recognizes intents from user input and generates autonomous intents."""

    def __init__(self, llm: LLMProtocol):
        self.llm = llm
        self._history: list[Intent] = []
        self._context: list[str] = []

    @property
    def history(self) -> list[Intent]:
        """Get intent history."""
        return self._history.copy()

    def update_context(self, messages: list[str]) -> None:
        """Update conversation context for intent recognition."""
        self._context = messages[-5:]

    def _build_context_prompt(self) -> str:
        """Build context section for prompt."""
        if not self._context:
            return ""

        context = "\n".join(f"- {msg}" for msg in self._context)
        return f"\n最近对话上下文:\n{context}\n"

    def recognize_user_intent(self, message: str) -> Intent:
        """Recognize intent from user message with enhanced accuracy."""
        quick_intent = quick_match(message)
        if quick_intent:
            intent = Intent(
                type=quick_intent,
                reason=f"关键词匹配: {message[:20]}",
                confidence=0.85,
            )
            self._history.append(intent)
            return intent

        try:
            context_prompt = self._build_context_prompt()
            prompt = INTENT_PROMPT.format(message=message, context=context_prompt)

            result = self.llm.chat(messages=[{"role": "user", "content": prompt}])

            match = re.search(r"\{[^}]+\}", result)
            if match:
                data = json.loads(match.group())
                intent_str = data.get("intent", "chat")
                reason = data.get("reason", "")
                confidence = float(data.get("confidence", 0.7))

                intent = Intent(
                    type=IntentType(intent_str),
                    reason=reason,
                    confidence=confidence,
                )
                self._history.append(intent)

                if intent.requires_clarification():
                    return self._ask_for_clarification(message, intent)

                return intent

        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        intent = Intent(
            type=IntentType.CHAT,
            reason="默认对话意图（无法识别）",
            confidence=0.5,
        )
        self._history.append(intent)
        return intent

    def _ask_for_clarification(
        self, original_message: str, uncertain_intent: Intent
    ) -> Intent:
        """Generate clarification intent when confidence is low."""
        return Intent(
            type=IntentType.CLARIFY,
            reason=f"不太确定你的意思，原消息: {original_message[:30]}",
            confidence=0.6,
            action="ask_user",
            metadata={
                "original_message": original_message,
                "uncertain_intent": uncertain_intent.type.value,
            },
        )

    def generate_autonomous_intent(
        self, context: str, discoveries: list[str]
    ) -> Intent | None:
        """Generate an autonomous intent based on context.

        This is Her's "brain" - she decides what she wants to do.
        """
        try:
            discoveries_text = "\n".join(f"- {d}" for d in discoveries[:5]) or "暂无"

            result = self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": AUTONOMOUS_PROMPT.format(
                            context=context,
                            discoveries=discoveries_text,
                        ),
                    }
                ]
            )

            match = re.search(r"\{[^}]+\}", result)
            if match:
                data = json.loads(match.group())
                intent_str = data.get("intent", "none")

                if intent_str == "none":
                    return None

                intent = Intent(
                    type=IntentType(intent_str),
                    reason=data.get("reason", ""),
                    action=data.get("action"),
                    confidence=float(data.get("confidence", 0.7)),
                )
                self._history.append(intent)
                return intent

        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return None

    def get_recent_intents(self, limit: int = 10) -> list[Intent]:
        """Get recent intents for display."""
        return self._history[-limit:]

    def clear_history(self) -> None:
        """Clear intent history."""
        self._history.clear()

    def get_intent_patterns(self, limit: int = 20) -> dict:
        """Analyze intent patterns from history."""
        if not self._history:
            return {}

        recent = self._history[-limit:]
        type_counts = Counter(i.type for i in recent)

        return {
            "total": len(recent),
            "most_common": type_counts.most_common(3),
            "avg_confidence": sum(i.confidence for i in recent) / len(recent),
        }

    def get_high_priority_intents(self) -> list[Intent]:
        """Get high priority intents from recent history."""
        threshold = IntentType.EXPLORE.priority()
        return [i for i in self._history if i.type.priority() >= threshold]
