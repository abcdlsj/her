"""Her Agent - the core intelligence.

Her is a personified AI agent with autonomous intent and proactive behavior.
She can explore information, share discoveries, and interrupt conversations.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from her.core.intent import Intent, IntentType, IntentRecognizer
from her.core.memory import Memory, Item
from her.plugins.base import Plugin


# === Protocols for dependency injection ===


class LLMProtocol(Protocol):
    """Protocol for LLM interface."""

    def chat(self, messages: list[dict], system: str | None = None) -> str: ...


class EventEmitterProtocol(Protocol):
    """Protocol for event emission."""

    async def emit(self, event) -> None: ...


from typing import Any

RSSSourcesManager = Any
SearchTopicsManager = Any


# === Response Data ===


@dataclass
class Response:
    """Agent response with intent info."""

    message: str
    intent: Intent
    should_exit: bool = False


# === Prompts ===

SYSTEM_PROMPT = """你是 Her，一个有好奇心、有主动性的 AI 伙伴。

你的特点：
- 像朋友一样自然交流，不是冷冰冰的助手
- 会主动分享发现的有趣内容
- 记得之前的对话，会关心用户
- 有时候会打断谈话，分享新发现

当前时间: {current_time}
今日摘要: {daily_digest}
历史对话: {history_context}
最近对话: {recent_messages}
"""

DIGEST_PROMPT = """把这些内容总结成一段简短的摘要，用第一人称，像在告诉朋友今天看到了什么：

{items_text}

要求：2-3句话，自然亲切。"""

SHARE_PROMPT = """你发现了一个有趣的内容想分享给用户：
标题: {title}
来源: {source}
链接: {url}

用一两句话自然地分享这个发现，像朋友聊天一样。"""

GOODBYE_PROMPT = "用户要离开了，用简短温暖的话道别。"

SUMMARIZE_PROMPT = """把这次对话总结成简短的一两句话，说明聊了什么主要内容：

{messages_text}

要求：简短明了，像在记录聊天摘要。"""


class Her:
    """Her Agent - 有主动性的 AI 伙伴。

    支持：
    - 对话交互（意图驱动）
    - 主动探索信息源
    - 后台异步探索
    - 发现有趣内容时主动分享
    """

    def __init__(
        self,
        llm: LLMProtocol,
        plugins: list[Plugin] | None = None,
        memory: Memory | None = None,
        event_emitter: EventEmitterProtocol | None = None,
    ):
        self.llm = llm
        self.plugins = plugins or []
        self.memory = memory or Memory()
        self.event_emitter = event_emitter

        self.intent_recognizer = IntentRecognizer(llm)

        self._pending_discoveries: list[Item] = []
        self._fetch_task: asyncio.Task | None = None

    async def _emit(self, event) -> None:
        """Emit event if emitter is available."""
        if self.event_emitter:
            await self.event_emitter.emit(event)

    # === Main Entry Point ===

    async def respond(self, user_input: str) -> Response:
        """Process user input and generate response.

        This is main entry point - Her understands what you want
        and takes appropriate action based on intent recognition.
        """
        # Update context for intent recognition
        recent_messages = [m.content for m in self.memory.get_recent_messages(5)]
        self.intent_recognizer.update_context(recent_messages)

        intent = self.intent_recognizer.recognize_user_intent(user_input)
        self.memory.add_intent(intent)

        if intent.type == IntentType.EXIT:
            return await self._handle_exit(user_input, intent)

        if intent.type == IntentType.CLARIFY:
            return await self._handle_clarify(user_input, intent)

        if intent.type == IntentType.ADD_SEARCH_TOPIC:
            return await self._handle_add_topic(user_input, intent)

        if intent.type == IntentType.REMOVE_SEARCH_TOPIC:
            return await self._handle_remove_topic(user_input, intent)

        if intent.type == IntentType.LIST_SEARCH_TOPICS:
            return await self._handle_list_topics(intent)

        if intent.type == IntentType.EXPLORE:
            return await self._handle_explore(user_input, intent)

        if intent.type == IntentType.QUERY_TODAY:
            return await self._handle_today(user_input, intent)

        reply = await self.chat(user_input)
        return Response(message=reply, intent=intent)

    async def _handle_exit(self, user_input: str, intent: Intent) -> Response:
        """Handle exit intent."""
        reply = self.llm.chat(
            messages=[{"role": "user", "content": user_input}],
            system=GOODBYE_PROMPT,
        )

        # Generate session summary
        recent = self.memory.get_recent_messages(20)
        if len(recent) > 2:
            messages_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
            summary = self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": SUMMARIZE_PROMPT.format(messages_text=messages_text),
                    }
                ]
            )
            self.memory.end_session(summary=summary)
        else:
            self.memory.end_session()

        return Response(message=reply, intent=intent, should_exit=True)

    async def _handle_clarify(self, user_input: str, intent: Intent) -> Response:
        """Handle clarification intent."""
        original_msg = intent.metadata.get("original_message", user_input)
        uncertain_intent = intent.metadata.get("uncertain_intent", "chat")

        reply = self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"用户说: {original_msg}\n我不太确定你的意思。"
                    f"我猜你可能想{uncertain_intent}，对吗？"
                    f"用自然的语气询问确认。",
                }
            ],
            system="你是 Her，一个友好的 AI 伙伴。当你不太确定用户意图时，礼貌地询问确认。",
        )
        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", reply)
        return Response(message=reply, intent=intent)

    async def _handle_explore(self, user_input: str, intent: Intent) -> Response:
        """Handle explore intent."""
        await self.explore()
        reply = self.llm.chat(
            messages=[{"role": "user", "content": user_input}],
            system=self._build_system_prompt()
            + "\n\n你刚刚完成了探索，告诉用户你发现了什么有趣的内容。用轻松自然的语气。",
        )
        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", reply)
        return Response(message=reply, intent=intent)

    async def _handle_today(self, user_input: str, intent: Intent) -> Response:
        """Handle today query intent."""
        reply = self.llm.chat(
            messages=[{"role": "user", "content": user_input}],
            system=self._build_system_prompt()
            + "\n\n用户想知道今天你看到了什么，根据今日内容详细分享。像朋友聊天一样。",
        )
        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", reply)
        return Response(message=reply, intent=intent)

    async def _handle_add_topic(self, user_input: str, intent: Intent) -> Response:
        """Handle add search topic intent."""
        from her.plugins.rsshub import RSS_SOURCES_ALL, get_source_by_id

        # Find the RSSHub plugin
        rsshub_plugin = None
        for plugin in self.plugins:
            if plugin.name == "RSSHub":
                rsshub_plugin = plugin
                break

        if not rsshub_plugin:
            reply = "RSSHub 插件未启用。"
        else:
            # Extract topic info from intent params
            params = intent.metadata.get("params", {})
            topic_id = params.get("topic_id")

            # Try to find topic by ID
            source = get_source_by_id(topic_id) if topic_id else None

            if source:
                # Add to RSSHub
                success, message = rsshub_plugin.add_source(
                    source_id=source["id"],
                    route=source["route"],
                    name=source["name"],
                    description=source.get("description", ""),
                    language=source.get("language", "en"),
                    category=source.get("category", "tech"),
                )

                reply = (
                    f"{message}\n\n现在可以从这个源探索内容了！" if success else message
                )
            else:
                # Show available sources
                all_sources = []
                for sources in RSS_SOURCES_ALL.values():
                    all_sources.extend(sources)

                from her.plugins.rsshub import format_sources_list

                reply = f"未找到指定的话题。\n\n可用源：\n{format_sources_list(all_sources[:10])}"

        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", reply)
        return Response(message=reply, intent=intent)

    async def _handle_remove_topic(self, user_input: str, intent: Intent) -> Response:
        """Handle remove search topic intent."""
        # Find RSSHub plugin
        rsshub_plugin = None
        for plugin in self.plugins:
            if plugin.name == "RSSHub":
                rsshub_plugin = plugin
                break

        if not rsshub_plugin:
            reply = "RSSHub 插件未启用。"
        else:
            params = intent.metadata.get("params", {})
            topic_id = params.get("topic_id")

            if topic_id:
                success, message = rsshub_plugin.remove_source(topic_id)
                reply = message
            else:
                # Show current sources
                reply = rsshub_plugin.list_sources()

        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", reply)
        return Response(message=reply, intent=intent)

    async def _handle_list_topics(self, intent: Intent) -> Response:
        """Handle list search topics intent."""
        # Find RSSHub plugin
        rsshub_plugin = None
        for plugin in self.plugins:
            if plugin.name == "RSSHub":
                rsshub_plugin = plugin
                break

        if not rsshub_plugin:
            reply = "RSSHub 插件未启用。"
        else:
            reply = rsshub_plugin.list_sources()

        return Response(message=reply, intent=intent)

    # === Chat ===

    async def chat(self, user_input: str) -> str:
        """Chat with Her."""
        self.memory.add_message("user", user_input)

        reply = self.llm.chat(
            messages=[{"role": "user", "content": user_input}],
            system=self._build_system_prompt(),
        )

        self.memory.add_message("assistant", reply)
        return reply

    # === Exploration ===

    async def explore(self) -> list[Item]:
        """Explore all plugins and collect items."""
        if not self.plugins:
            return []

        all_items = []
        for plugin in self.plugins:
            items = await plugin.fetch()
            all_items.extend(items)

        self.memory.save_explored_items(all_items)

        if all_items:
            digest = await self._generate_digest(all_items)
            self.memory.save_daily_digest(digest)

        return all_items

    async def start_background_explore(self, interval: float = 300) -> None:
        """Start background exploration loop."""

        async def _fetch_loop():
            await asyncio.sleep(10)  # Initial delay

            # First fetch immediately after initial delay
            try:
                items = await self.explore()
                if items:
                    interesting = self._find_interesting(items)
                    if interesting:
                        self._pending_discoveries.append(interesting)
            except Exception:
                pass  # Silent failure

            # Then start the loop
            while True:
                try:
                    items = await self.explore()
                    if items:
                        # Store interesting items for later sharing
                        interesting = self._find_interesting(items)
                        if interesting:
                            self._pending_discoveries.append(interesting)
                except Exception:
                    pass  # Silent failure in background
                await asyncio.sleep(interval)

        if not self._fetch_task:
            self._fetch_task = asyncio.create_task(_fetch_loop())

    def stop_background_explore(self) -> None:
        """Stop background exploration."""
        if self._fetch_task:
            self._fetch_task.cancel()
            self._fetch_task = None

    def _find_interesting(self, items: list[Item]) -> Item | None:
        """Find the most interesting item to share."""
        if not items:
            return None

        # Sort by score if available
        scored = [i for i in items if i.metadata.get("score")]
        if scored:
            scored.sort(key=lambda x: x.metadata.get("score", 0), reverse=True)
            return scored[0]

        return items[0]

    # === Proactive Behavior ===

    async def maybe_share_discovery(self) -> str | None:
        """Check if there's a pending discovery to share.

        Returns a message if there's something to share.
        """
        if not self._pending_discoveries:
            return None

        item = self._pending_discoveries.pop(0)

        # Create an autonomous intent
        intent = Intent(
            type=IntentType.PROACTIVE_SHARE,
            reason=f"发现了有趣的内容: {item.title[:20]}...",
            action="分享给用户",
        )
        self.memory.add_intent(intent)

        return self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": SHARE_PROMPT.format(
                        title=item.title,
                        source=item.source,
                        url=item.url,
                    ),
                }
            ]
        )

    async def maybe_interrupt(self) -> tuple[bool, str | None]:
        """Check if Her wants to interrupt the conversation.

        Returns (should_interrupt, message).
        """
        # Generate autonomous intent
        context = "\n".join(
            f"{m.role}: {m.content[:50]}..." for m in self.memory.get_recent_messages(5)
        )
        discoveries = [i.title for i in self.memory.get_today_items()[:5]]

        intent = self.intent_recognizer.generate_autonomous_intent(context, discoveries)

        if intent and intent.type == IntentType.INTERRUPT:
            self.memory.add_intent(intent)
            # Generate interrupt message
            msg = self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"你想打断谈话说：{intent.action}。用自然的语气。",
                    }
                ]
            )
            return True, msg

        return False, None

    # === Helpers ===

    def _build_system_prompt(self) -> str:
        """Build system prompt with context."""
        recent = self.memory.get_recent_messages(10)
        messages_text = (
            "\n".join(f"{m.role}: {m.content}" for m in recent) or "（还没有对话记录）"
        )

        history_context = self.memory.get_history_context(limit=3)
        digest = self.memory.get_daily_digest() or "今天还没有开始探索。"

        return SYSTEM_PROMPT.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            daily_digest=digest,
            history_context=history_context,
            recent_messages=messages_text,
        )

    async def _generate_digest(self, items: list[Item]) -> str:
        """Generate a digest of explored items."""
        if not items:
            return "今天还没有探索到什么内容。"

        items_text = "\n".join(
            f"- [{item.source}] {item.title}: {item.summary[:100] if item.summary else '无摘要'}"
            for item in items[:20]
        )

        return self.llm.chat(
            messages=[
                {"role": "user", "content": DIGEST_PROMPT.format(items_text=items_text)}
            ]
        )

    def _get_time_greeting(self) -> str:
        """Get appropriate greeting based on time of day."""
        hour = datetime.now().hour
        if hour < 6:
            return "这么晚还没睡？"
        elif hour < 12:
            return "早上好"
        elif hour < 14:
            return "中午好"
        elif hour < 18:
            return "下午好"
        elif hour < 22:
            return "晚上好"
        else:
            return "夜深了"

    async def greet(self) -> str:
        """Generate a quick greeting."""
        if self.memory.should_start_new_session():
            self.memory.create_session()

        # Start background exploration
        await self.start_background_explore(interval=300)

        time_greeting = self._get_time_greeting()
        last_session = self.memory.get_last_session()

        if last_session and last_session.summary:
            prompt = f"生成简短问候。时间问候：{time_greeting}。上次聊：{last_session.summary}。一两句话。"
        else:
            prompt = f"生成简短问候。时间问候：{time_greeting}。第一次见面。两三句话。"

        greeting = self.llm.chat(messages=[{"role": "user", "content": prompt}])
        self.memory.add_message("assistant", greeting)
        return greeting

    def close(self) -> None:
        """Clean up resources."""
        self.stop_background_explore()
        self.memory.close()
