"""CLI interface for Her."""

import asyncio
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from her.agent import Her
from her.config import create_sources_from_config, load_config
from her.events import EventBus, StatusEvent, DiscoveryEvent, ErrorEvent

console = Console()
style = Style.from_dict({
    "prompt": "#ff6b6b bold",
    "bottom-toolbar": "bg:#333333 #888888",
})

_current_status: str = ""
_spinner_status = None


def get_bottom_toolbar():
    """Return the bottom toolbar content."""
    if _current_status:
        return HTML(f'<style bg="#333333" fg="#888888"> 💭 {_current_status} </style>')
    return HTML('<style bg="#333333" fg="#666666"> ─── Her 在后台探索中 ─── </style>')


def create_agent(event_bus: EventBus) -> Her:
    """Create agent with sources from config."""
    config = load_config()
    sources = create_sources_from_config(config)

    if not sources:
        console.print("[yellow]没有配置信息源，使用默认配置[/yellow]")
        from her.config import get_default_sources, save_sources
        default = get_default_sources()
        save_sources(default)
        sources = create_sources_from_config()

    return Her(sources=sources, event_bus=event_bus)


async def handle_events(event_bus: EventBus) -> None:
    """Handle events from the agent (background task)."""
    global _current_status, _spinner_status

    subscription = event_bus.subscribe()

    async for event in subscription:
        if isinstance(event, StatusEvent):
            if _spinner_status:
                _spinner_status.update(f"[dim]{event.message}[/dim]")
            else:
                _current_status = event.message

        elif isinstance(event, DiscoveryEvent):
            pass

        elif isinstance(event, ErrorEvent):
            if _spinner_status:
                _spinner_status.update(f"[red]⚠ {event.source}: {event.error}[/red]")
            else:
                _current_status = f"⚠ {event.source}: {event.error}"


async def run_cli():
    """Run the interactive CLI."""
    global _current_status, _spinner_status

    console.print(
        Panel.fit(
            "[bold magenta]Her[/bold magenta] - 你的好奇伙伴",
            border_style="magenta",
        )
    )

    event_bus = EventBus()
    agent = create_agent(event_bus)

    event_task = asyncio.create_task(handle_events(event_bus))

    try:
        with console.status("[dim]让我先看看最近有什么...[/dim]", spinner="dots") as status:
            _spinner_status = status
            greeting = await agent.greet()
            _spinner_status = None

        console.print()
        console.print(Panel(Markdown(greeting), border_style="cyan", title="Her"))

        history_file = Path.home() / ".her" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)),
            style=style,
            bottom_toolbar=get_bottom_toolbar,
            refresh_interval=1.0,
        )

        while True:
            try:
                discovery = await agent.maybe_share_discovery()
                if discovery:
                    console.print()
                    console.print(
                        Panel(Markdown(discovery), border_style="yellow", title="Her 💡")
                    )

                console.print()
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.prompt([("class:prompt", "You > ")]),
                )

                if not user_input.strip():
                    continue

                with console.status("[dim]想想...[/dim]", spinner="dots") as status:
                    _spinner_status = status
                    response = await agent.respond(user_input)
                    _spinner_status = None

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
        console.print("\n[dim]下次见！[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
