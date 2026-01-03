"""Chat panel - conversation area with input."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Static
from textual.message import Message


class ChatMessage(Static):
    """A single chat message."""
    
    DEFAULT_CSS = """
    ChatMessage {
        padding: 1 2;
        margin-bottom: 1;
    }
    
    ChatMessage.user {
        background: $primary-darken-2;
        border-left: thick $primary;
    }
    
    ChatMessage.assistant {
        background: $secondary-darken-2;
        border-left: thick $secondary;
    }
    
    ChatMessage .role {
        text-style: bold;
        margin-bottom: 1;
    }
    """
    
    def __init__(self, role: str, content: str) -> None:
        super().__init__(classes=role)
        self.role = role
        self.content = content
    
    def compose(self) -> ComposeResult:
        role_display = "You" if self.role == "user" else "Her"
        yield Static(f"[bold]{role_display}[/bold]", classes="role")
        yield Static(self.content)


class ChatArea(VerticalScroll):
    """Scrollable chat message area."""
    
    DEFAULT_CSS = """
    ChatArea {
        height: 1fr;
        padding: 1;
    }
    """


class ChatInput(Input):
    """Chat input field."""
    
    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 1;
    }
    """
    
    class Submitted(Message):
        """Message sent when input is submitted."""
        
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()
    
    def __init__(self) -> None:
        super().__init__(placeholder="输入消息... (Ctrl+C 退出)")
    
    async def action_submit(self) -> None:
        """Handle submit action."""
        if self.value.strip():
            self.post_message(self.Submitted(self.value))
            self.value = ""


class ChatPanel(Container):
    """Right panel with chat area and input."""
    
    DEFAULT_CSS = """
    ChatPanel {
        width: 70%;
        padding: 0;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield ChatArea()
        yield ChatInput()
    
    @property
    def chat_area(self) -> ChatArea:
        return self.query_one(ChatArea)
    
    @property
    def chat_input(self) -> ChatInput:
        return self.query_one(ChatInput)
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat."""
        msg = ChatMessage(role, content)
        self.chat_area.mount(msg)
        self.chat_area.scroll_end(animate=False)
    
    def add_status(self, message: str) -> None:
        """Add a status message."""
        status = Static(f"[dim italic]{message}[/dim italic]")
        self.chat_area.mount(status)
        self.chat_area.scroll_end(animate=False)
    
    def focus_input(self) -> None:
        """Focus the input field."""
        self.chat_input.focus()
