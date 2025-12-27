"""Her Agent - the core intelligence."""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from her import prompts
from her.events import (
    EventBus,
    StatusEvent,
    ExploreStartEvent,
    ExploreEndEvent,
    DiscoveryEvent,
    ErrorEvent,
)
from her.llm import LLM, LLMConfig, create_llm
from her.memory import Memory
from her.sources.base import Item, Source


class Intent(Enum):
    EXPLORE = "explore"
    TODAY = "today"
    EXIT = "exit"
    CHAT = "chat"
    MODIFY_SOURCE = "modify_source"


@dataclass
class Response:
    """Agent response with optional action."""

    message: str
    intent: Intent
    should_exit: bool = False


class Her:
    """
    Her Agent - 有主动性的 AI 伙伴。

    支持：
    - 对话交互
    - 主动探索信息源
    - 后台异步探索
    - 发现有趣内容时主动分享
    - 会话记忆（记住上次聊了什么）
    """

    def __init__(
        self,
        sources: list[Source],
        memory: Memory | None = None,
        llm: LLM | None = None,
        llm_config: LLMConfig | None = None,
        event_bus: EventBus | None = None,
    ):
        self.sources = sources
        self.memory = memory or Memory()
        self.llm = llm or create_llm(llm_config)
        self.event_bus = event_bus or EventBus()

        self._pending_discoveries: list[DiscoveryEvent] = []
        self._explore_task: asyncio.Task | None = None
        self._fetch_task: asyncio.Task | None = None

    async def _emit(self, event) -> None:
        """Emit event to bus."""
        await self.event_bus.emit(event)

    def _parse_intent(self, message: str) -> Intent:
        """Use LLM to understand user intent."""
        try:
            result = self.llm.chat(
                messages=[{"role": "user", "content": prompts.INTENT.format(message=message)}]
            )
            match = re.search(r'\{[^}]+\}', result)
            if match:
                data = json.loads(match.group())
                intent_str = data.get("intent", "chat")
                return Intent(intent_str)
        except (json.JSONDecodeError, ValueError):
            pass
        return Intent.CHAT

    async def respond(self, user_input: str) -> Response:
        """
        Process user input and generate response.

        This is the main entry point - Her understands what you want
        and takes appropriate action.
        """
        intent = self._parse_intent(user_input)

        if intent == Intent.EXIT:
            summary = self._generate_session_summary()
            self.memory.end_session(summary)
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system="用户要离开了，用简短温暖的话道别。如果这次聊得不错，可以提一下下次再聊。",
            )
            return Response(message=reply, intent=intent, should_exit=True)

        if intent == Intent.EXPLORE:
            await self._emit(StatusEvent(message="好的，让我去看看最新的内容..."))
            await self.explore()
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system=self._build_system_prompt() + "\n\n你刚刚完成了探索，告诉用户你发现了什么有趣的内容。用轻松自然的语气。",
            )
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", reply)
            return Response(message=reply, intent=intent)

        if intent == Intent.TODAY:
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system=self._build_system_prompt() + "\n\n用户想知道今天你看到了什么，根据今日内容详细分享。像朋友聊天一样。",
            )
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", reply)
            return Response(message=reply, intent=intent)

        return Response(
            message=await self.chat(user_input),
            intent=Intent.CHAT,
        )

    async def explore(self, silent: bool = False) -> list[Item]:
        """
        Explore all sources and collect items.

        Args:
            silent: If True, don't emit status events (for background exploration)
        """
        all_items: list[Item] = []

        for source in self.sources:
            if not silent:
                await self._emit(ExploreStartEvent(source_name=source.name))
                await self._emit(StatusEvent(message=f"溜达去看看 {source.name}..."))

            try:
                items = await source.fetch()
                all_items.extend(items)
                if not silent:
                    await self._emit(
                        ExploreEndEvent(
                            source_name=source.name,
                            item_count=len(items),
                            success=True,
                        )
                    )
                    await self._emit(
                        StatusEvent(message=f"  ✓ {source.name}: 看到 {len(items)} 条有意思的")
                    )
            except Exception as e:
                if not silent:
                    await self._emit(
                        ExploreEndEvent(
                            source_name=source.name,
                            item_count=0,
                            success=False,
                            error=str(e),
                        )
                    )
                    await self._emit(ErrorEvent(source=source.name, error=str(e)))
                    await self._emit(
                        StatusEvent(message=f"  ✗ {source.name}: 没刷到 ({e})")
                    )

        self.memory.save_explored_items(all_items)

        if not silent and all_items:
            await self._emit(StatusEvent(message="整理一下看到的东西..."))

        if all_items:
            digest = await self._generate_digest(all_items)
            self.memory.save_daily_digest(digest)

        if not silent:
            await self._emit(StatusEvent(message="✓ 溜达完了！"))

        return all_items

    async def _start_background_fetcher(self, interval: float = 300) -> None:
        """
        Start pure background data fetching (no blocking).

        This runs completely in the background, never blocks conversation.
        """
        async def _fetch_loop():
            await asyncio.sleep(10)
            while True:
                try:
                    await self._emit(StatusEvent(message="后台刷新中..."))
                    items = await self.explore(silent=True)
                    if items:
                        interesting = await self._find_interesting(items)
                        if interesting:
                            self._pending_discoveries.append(interesting)
                            await self._emit(StatusEvent(message=f"发现了点有趣的：{interesting.title[:20]}..."))
                except Exception as e:
                    await self._emit(StatusEvent(message=f"后台刷新出了点问题: {e}"))
                await asyncio.sleep(interval)

        if not self._fetch_task:
            self._fetch_task = asyncio.create_task(_fetch_loop())

    async def start_background_explore(self, interval: float = 300) -> None:
        """Start background exploration loop (alias for backwards compat)."""
        await self._start_background_fetcher(interval)

    def stop_background_explore(self) -> None:
        """Stop background exploration."""
        if self._fetch_task:
            self._fetch_task.cancel()
            self._fetch_task = None

    async def _find_interesting(self, items: list[Item]) -> DiscoveryEvent | None:
        """Find something interesting to share from explored items."""
        if not items:
            return None

        top_items = sorted(
            items,
            key=lambda x: x.metadata.get("score", 0),
            reverse=True,
        )[:3]

        if not top_items:
            return None

        best = top_items[0]
        return DiscoveryEvent(
            title=best.title,
            url=best.url,
            source=best.source,
            reason="这个看起来挺有意思",
            metadata=best.metadata,
        )

    async def maybe_share_discovery(self) -> str | None:
        """
        Check if there's a pending discovery to share.

        Returns a message if there's something to share, None otherwise.
        """
        if not self._pending_discoveries:
            return None

        discovery = self._pending_discoveries.pop(0)
        await self._emit(discovery)

        prompt = prompts.SHARE_DISCOVERY.format(
            title=discovery.title,
            source=discovery.source,
            url=discovery.url,
        )

        return self.llm.chat(messages=[{"role": "user", "content": prompt}])

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
                {"role": "user", "content": prompts.DIGEST.format(items_text=items_text)}
            ]
        )

    def _generate_session_summary(self) -> str | None:
        """Generate a summary of the current session for memory."""
        messages = self.memory.get_recent_messages(20)
        if len(messages) < 2:
            return None

        convo = "\n".join(f"{m.role}: {m.content[:100]}" for m in messages[-10:])
        return self.llm.chat(
            messages=[{"role": "user", "content": prompts.SESSION_SUMMARY.format(conversation=convo)}]
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

    def _build_system_prompt(self) -> str:
        """Build system prompt with context."""
        recent = self.memory.get_recent_messages(10)
        messages_text = (
            "\n".join(f"{m.role}: {m.content}" for m in recent) or "（还没有对话记录）"
        )

        digest = self.memory.get_daily_digest() or "今天还没有开始探索。"

        today_items = self.memory.get_today_items()
        items_text = "\n".join(
            f"- [{item.source}] {item.title}" for item in today_items[:15]
        ) or "（还没有探索内容）"

        last_session = self.memory.get_last_session()
        last_session_text = ""
        if last_session and last_session.summary:
            time_diff = datetime.now() - last_session.ended_at if last_session.ended_at else None
            if time_diff:
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}天前"
                elif time_diff.seconds > 3600:
                    time_str = f"{time_diff.seconds // 3600}小时前"
                else:
                    time_str = "刚才"
                last_session_text = f"\n上次聊天（{time_str}）：{last_session.summary}"

        return prompts.SYSTEM.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            daily_digest=digest,
            today_items=items_text,
            recent_messages=messages_text,
        ) + last_session_text

    async def chat(self, user_input: str) -> str:
        """Chat with Her."""
        self.memory.add_message("user", user_input)

        reply = self.llm.chat(
            messages=[{"role": "user", "content": user_input}],
            system=self._build_system_prompt(),
        )

        self.memory.add_message("assistant", reply)
        return reply

    async def greet(self) -> str:
        """
        Generate a quick greeting without blocking.

        Uses cached data if available, starts background fetch.
        """
        if self.memory.should_start_new_session():
            self.memory.create_session()

        await self._start_background_fetcher(interval=300)

        last_session = self.memory.get_last_session()
        cached_items = self.memory.get_cached_items(limit=20)
        time_greeting = self._get_time_greeting()

        if last_session and last_session.summary:
            time_diff = datetime.now() - last_session.ended_at if last_session.ended_at else None
            if time_diff and time_diff.days == 0:
                prompt = f"""生成一个简短的问候。
时间问候：{time_greeting}
上次聊天内容：{last_session.summary}
要求：自然地提到上次聊的内容，像老朋友一样打招呼。一两句话就好。"""
            elif time_diff and time_diff.days <= 7:
                prompt = f"""生成一个简短的问候。
时间问候：{time_greeting}
{time_diff.days}天前聊过：{last_session.summary}
要求：可以轻描淡写地提一下好久没聊了。一两句话。"""
            else:
                prompt = f"""生成一个简短的问候。
时间问候：{time_greeting}
要求：简单自然的问候，像朋友打招呼。一两句话。"""
        elif cached_items:
            sample = cached_items[0]
            prompt = f"""生成一个简短的问候。
时间问候：{time_greeting}
最近看到的内容：{sample.title}（来自{sample.source}）
要求：简单问候，可以顺便提一嘴最近看到的东西。一两句话。"""
        else:
            prompt = f"""生成一个简短的问候。
时间问候：{time_greeting}
这是第一次见面。
要求：友好自然的自我介绍。两三句话。"""

        greeting = self.llm.chat(messages=[{"role": "user", "content": prompt}])
        self.memory.add_message("assistant", greeting)
        return greeting

    def close(self) -> None:
        """Clean up resources."""
        self.stop_background_explore()
        self.memory.close()
