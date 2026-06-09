from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpModal(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss"),
        ("?", "dismiss"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("", id="help-backdrop")
        yield Static(self._render_help(), id="help-content")

    def _render_help(self) -> str:
        lines = []
        header = "[bold #AA336A]Keybinds[/]"
        lines.append(f"{header:^72}")
        lines.append("")

        lines.append("[bold #B3BEFE]Navigation[/]")
        lines.append("  [bold #E49BA7]Tab[/]          Switch tabs forward")
        lines.append("  [bold #E49BA7]Ctrl+Tab[/]     Switch tabs backward")
        lines.append("  [bold #E49BA7]Esc[/]          Back / Quit")
        lines.append("")

        lines.append("[bold #B3BEFE]Focus Controls[/]")
        lines.append("  [bold #E49BA7]![/]            Focus search input")
        lines.append("  [bold #E49BA7]@[/]            Focus results table")
        lines.append("  [bold #E49BA7]#[/]            Focus Sub episode list")
        lines.append("  [bold #E49BA7]$[/]            Focus Dub episode list")
        lines.append("  [bold #E49BA7]%[/]            Focus InfoBox")
        lines.append("")

        lines.append("[bold #B3BEFE]Actions[/]")
        lines.append("  [bold #E49BA7]?[/]            Show/hide this help")
        lines.append("  [bold #E49BA7]Enter[/]        Perform action")
        lines.append("")

        lines.append("[bold #B3BEFE]Lists & Table[/]")
        lines.append("  [bold #E49BA7]Up/k[/]         Move up")
        lines.append("  [bold #E49BA7]Down/j[/]       Move down")
        lines.append("")

        return "\n".join(lines)

    def action_dismiss(self):
        self.app.pop_screen()
