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

        self._explored_today = False
        self._pending_discoveries: list[DiscoveryEvent] = []
        self._explore_task: asyncio.Task | None = None

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
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system="用户要离开了，用简短温暖的话道别。",
            )
            return Response(message=reply, intent=intent, should_exit=True)

        if intent == Intent.EXPLORE:
            await self.explore()
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system=self._build_system_prompt() + "\n\n你刚刚完成了探索，告诉用户你发现了什么有趣的内容。",
            )
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", reply)
            return Response(message=reply, intent=intent)

        if intent == Intent.TODAY:
            reply = self.llm.chat(
                messages=[{"role": "user", "content": user_input}],
                system=self._build_system_prompt() + "\n\n用户想知道今天你看到了什么，根据今日内容详细分享。",
            )
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", reply)
            return Response(message=reply, intent=intent)

        # 普通聊天
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
                await self._emit(StatusEvent(message=f"正在浏览 {source.name}..."))

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
                        StatusEvent(message=f"  ✓ {source.name}: 发现 {len(items)} 条内容")
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
                        StatusEvent(message=f"  ✗ {source.name}: 获取失败 ({e})")
                    )

        self.memory.save_explored_items(all_items)
        self._explored_today = True

        if not silent:
            await self._emit(StatusEvent(message="正在整理今日摘要..."))
        digest = await self._generate_digest(all_items)
        self.memory.save_daily_digest(digest)
        if not silent:
            await self._emit(StatusEvent(message="✓ 探索完成！"))

        return all_items

    async def start_background_explore(self, interval: float = 300) -> None:
        """
        Start background exploration loop.

        Args:
            interval: Seconds between explorations (default 5 minutes)
        """
        if self._explore_task:
            return  # 已经在运行

        async def _loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    items = await self.explore(silent=True)
                    interesting = await self._find_interesting(items)
                    if interesting:
                        self._pending_discoveries.append(interesting)
                except Exception:
                    pass

        self._explore_task = asyncio.create_task(_loop())

    def stop_background_explore(self) -> None:
        """Stop background exploration."""
        if self._explore_task:
            self._explore_task.cancel()
            self._explore_task = None

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
            reason="这个看起来很有趣",
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

        prompt = f"""你刚发现了一个有趣的内容想要分享：
标题：{discovery.title}
来源：{discovery.source}
链接：{discovery.url}

用自然、随意的语气告诉用户这个发现，就像朋友之间分享一样。简短一点。"""

        return self.llm.chat(messages=[{"role": "user", "content": prompt}])

    async def _generate_digest(self, items: list[Item]) -> str:
        """Generate a digest of explored items."""
        if not items:
            return "今天还没有探索到什么内容。"

        items_text = "\n".join(
            f"- [{item.source}] {item.title}: {item.summary[:100]}"
            for item in items[:20]
        )

        return self.llm.chat(
            messages=[
                {"role": "user", "content": prompts.DIGEST.format(items_text=items_text)}
            ]
        )

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

        return prompts.SYSTEM.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            daily_digest=digest,
            today_items=items_text,
            recent_messages=messages_text,
        )

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
        """Generate a proactive greeting based on today's exploration."""
        if not self._explored_today:
            await self.explore()

        # 启动后台探索（永远开启）
        await self.start_background_explore(interval=300)

        digest = self.memory.get_daily_digest()
        if not digest:
            return "嗨！我刚准备好，要不要聊聊？"

        greeting = self.llm.chat(
            messages=[{"role": "user", "content": prompts.GREET.format(digest=digest)}]
        )

        self.memory.add_message("assistant", greeting)
        return greeting

    def close(self) -> None:
        """Clean up resources."""
        self.stop_background_explore()
        self.memory.close()
