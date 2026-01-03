"""Intent panel - displays Her's thinking process."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class IntentItem(Static):
    """A single intent display."""
    
    DEFAULT_CSS = """
    IntentItem {
        padding: 0 1;
        margin-bottom: 1;
        border-left: thick $primary;
        background: $surface;
    }
    
    IntentItem .intent-time {
        color: $text-muted;
    }
    
    IntentItem .intent-type {
        color: $primary;
        text-style: bold;
    }
    
    IntentItem .intent-reason {
        color: $text;
    }
    """


class IntentPanel(VerticalScroll):
    """Left panel showing Her's intent history."""
    
    DEFAULT_CSS = """
    IntentPanel {
        width: 30%;
        min-width: 25;
        border-right: solid $primary-lighten-2;
        padding: 1;
        background: $surface-darken-1;
    }
    
    IntentPanel > Static.title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
        border-bottom: dashed $primary-darken-2;
        margin-bottom: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Static("🧠 Her 的思考", classes="title")
    
    def add_intent(self, intent_type: str, reason: str, time_str: str) -> None:
        """Add a new intent to the display."""
        # Create formatted content
        content = f"[dim]{time_str}[/dim] [{intent_type}]\n{reason}"
        
        item = IntentItem(content)
        self.mount(item)
        self.scroll_end(animate=False)
    
    def clear_intents(self) -> None:
        """Clear all intents."""
        for child in self.query(IntentItem):
            child.remove()
