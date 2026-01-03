"""Her TUI Application - Split-pane interface using Textual."""

import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from her.core import Her
from her.core.intent import Intent
from her.infra.llm import create_llm, LLMConfig
from her.plugins.rsshub import create_rsshub
from her.ui.panels.intent import IntentPanel
from her.ui.panels.chat import ChatPanel, ChatInput


class HerApp(App):
    """Her TUI Application with split-pane layout."""

    TITLE = "Her - 你的好奇伙伴"

    CSS = """
    Screen {
        layout: horizontal;
    }

    Header {
        background: $primary;
    }

    Footer {
        background: $surface-darken-1;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("ctrl+e", "explore", "探索"),
    ]

    def __init__(self, llm_config: LLMConfig | None = None):
        super().__init__()

        # Create dependencies
        self.llm = create_llm(llm_config)

        # Create plugins - RSSHub as the first plugin
        self.rsshub = create_rsshub()
        plugins = [self.rsshub]

        # Create agent
        self.agent = Her(
            llm=self.llm,
            plugins=plugins,
        )

        # Autonomous behavior control
        self._autonomous_task: asyncio.Task | None = None
        self._last_user_input_time: float = 0
        self._last_share_time: float = 0
        self._is_user_typing = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield IntentPanel()
            yield ChatPanel()
        yield Footer()

    @property
    def intent_panel(self) -> IntentPanel:
        return self.query_one(IntentPanel)

    @property
    def chat_panel(self) -> ChatPanel:
        return self.query_one(ChatPanel)

    async def on_mount(self) -> None:
        """Initialize the app after mount."""
        self.chat_panel.focus_input()

        # Show greeting
        self.chat_panel.add_status("Her 正在准备...")

        # Generate greeting in background
        asyncio.create_task(self._show_greeting())

    async def _show_greeting(self) -> None:
        """Show greeting from Her."""
        try:
            greeting = await self.agent.greet()
            self.chat_panel.add_message("assistant", greeting)

            # Add greeting intent
            self._add_intent_display(
                "greeting",
                "开始新的对话",
            )
        except Exception as e:
            self.chat_panel.add_status(f"出错了: {e}")

        self.chat_panel.focus_input()

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle user input submission."""
        user_input = event.value.strip()
        if not user_input:
            return

        # Update last user input time
        self._last_user_input_time = asyncio.get_event_loop().time()
        self._is_user_typing = True

        # Show user message
        self.chat_panel.add_message("user", user_input)
        self.chat_panel.add_status("Her 正在思考...")

        # Process in background
        asyncio.create_task(self._process_input(user_input))

    async def _process_input(self, user_input: str) -> None:
        """Process user input and show response."""
        try:
            response = await self.agent.respond(user_input)

            # Show response
            self.chat_panel.add_message("assistant", response.message)

            # Show intent in left panel
            self._add_intent_display(
                response.intent.type.value,
                response.intent.reason,
            )

            if response.should_exit:
                self.chat_panel.add_status("再见！")
                await asyncio.sleep(1)
                self.exit()

        except Exception as e:
            self.chat_panel.add_status(f"出错了: {e}")

        # Reset typing flag
        self._is_user_typing = False
        self.chat_panel.focus_input()

    def _add_intent_display(self, intent_type: str, reason: str) -> None:
        """Add intent to the left panel."""
        time_str = datetime.now().strftime("%H:%M:%S")
        self.intent_panel.add_intent(intent_type, reason, time_str)

    async def action_explore(self) -> None:
        """Trigger exploration."""
        self.chat_panel.add_status("开始探索...")
        self._add_intent_display("explore", "用户请求探索")

        try:
            items = await self.agent.explore()
            self.chat_panel.add_status(f"探索完成，发现 {len(items)} 条内容")
            self._add_intent_display("explore_done", f"探索到 {len(items)} 条内容")
        except Exception as e:
            self.chat_panel.add_status(f"探索出错: {e}")

        self.chat_panel.focus_input()

    async def action_quit(self) -> None:
        """Quit application."""
        # Cancel autonomous task
        if self._autonomous_task:
            self._autonomous_task.cancel()
            try:
                await self._autonomous_task
            except asyncio.CancelledError:
                pass

        # Close agent
        self.agent.close()
        self.exit()


def run_app(llm_config: LLMConfig | None = None) -> None:
    """Run the Her TUI application."""
    app = HerApp(llm_config=llm_config)
    app.run()
