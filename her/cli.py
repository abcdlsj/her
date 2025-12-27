"""CLI interface for Her."""

import asyncio
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status

from her.agent import Her, Intent
from her.events import EventBus, StatusEvent, DiscoveryEvent, ErrorEvent
from her.sources import RSSHubSource

console = Console()
style = Style.from_dict({"prompt": "#ff6b6b bold"})

_status: Status | None = None


def create_default_agent(event_bus: EventBus) -> Her:
    """Create agent with default sources."""
    sources = [
        RSSHubSource("热榜", [
            "/v2ex/topics/hot",
            "/sspai/index",
            "/woshipm/popular",
        ]),
        RSSHubSource("科技", [
            "/cnbeta",
            "/juejin/trending/all/weekly",
            "/zaobao/realtime/china",
        ]),
        RSSHubSource("生活", [
            "/coolapk/tuwen/latest",
            "/bilibili/weekly",
            "/jike/topic/553870e8e4b0cafb0a1bef68",
        ]),
    ]
    return Her(sources=sources, event_bus=event_bus)


async def handle_events(event_bus: EventBus) -> None:
    """Handle events from the agent (background task)."""
    global _status

    subscription = event_bus.subscribe()

    async for event in subscription:
        if isinstance(event, StatusEvent):
            if _status:
                _status.update(f"[dim]{event.message}[/dim]")
        elif isinstance(event, DiscoveryEvent):
            console.print(
                f"\n[yellow]💡 发现了有趣的内容：{event.title}[/yellow]"
            )
        elif isinstance(event, ErrorEvent):
            if _status:
                _status.update(f"[red]⚠ {event.source}: {event.error}[/red]")


async def run_cli():
    """Run the interactive CLI."""
    global _status

    console.print(
        Panel.fit(
            "[bold magenta]Her[/bold magenta] - Your curious AI companion",
            border_style="magenta",
        )
    )

    event_bus = EventBus()
    agent = create_default_agent(event_bus)

    event_task = asyncio.create_task(handle_events(event_bus))

    try:
        with console.status("[dim]正在探索今日信息...[/dim]", spinner="dots") as status:
            _status = status
            greeting = await agent.greet()
            _status = None

        console.print()
        console.print(Panel(Markdown(greeting), border_style="cyan", title="Her"))

        history_file = Path.home() / ".her" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)),
            style=style,
        )

        while True:
            try:
                discovery = await agent.maybe_share_discovery()
                if discovery:
                    console.print()
                    console.print(
                        Panel(Markdown(discovery), border_style="yellow", title="Her")
                    )

                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.prompt([("class:prompt", "You > ")]),
                )

                if not user_input.strip():
                    continue

                # 用 spinner 显示思考状态
                with console.status("[dim]思考中...[/dim]", spinner="dots") as status:
                    _status = status
                    response = await agent.respond(user_input)
                    _status = None

                console.print(Panel(Markdown(response.message), border_style="cyan", title="Her"))

                if response.should_exit:
                    break

            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    finally:
        event_task.cancel()
        agent.close()


def main():
    """Entry point."""
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
