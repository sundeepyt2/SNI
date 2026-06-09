from textual.app import App
from textual.theme import Theme

from sni.tui.screens.history import HistoryScreen
from sni.tui.screens.home import HomeScreen


class SNIApp(App):
    TITLE = "SNI"
    SUB_TITLE = "Stream Ninja Interface"

    SCREENS = {
        "home": HomeScreen,
        "history": HistoryScreen,
    }

    CSS = """
Screen {
    background: $surface;
}

#home-content {
    height: 1fr;
}

#watch-pane {
    height: 1fr;
}

#search-input {
    margin: 1 1 0 1;
    border: round #666666;
    height: 3;
}

#search-input:focus {
    border: round #9F2B68;
}

#loading-msg {
    padding: 0 1;
    height: 1;
    color: #AA336A;
}

#results-table {
    height: 10;
    margin: 0 1;
    border: round #666666;
}

#results-table:focus {
    border: round #9F2B68;
}

DataTable > .datatable--header {
    color: #AA336A;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #5c5cd6;
    color: #ffffcc;
}

DataTable > .datatable--hover {
    background: #5c5cd6 50%;
}

#bottom-panels {
    height: 1fr;
    margin: 0 1 1 1;
}

#sub-panel, #dub-panel {
    width: 25;
    margin-right: 1;
}

.panel-title {
    padding: 0 1;
    text-style: bold;
    color: #AA336A;
    background: #111111;
    height: 1;
}

#sub-list, #dub-list {
    height: 1fr;
    border: round #666666;
}

#sub-list:focus, #dub-list:focus {
    border: round #9F2B68;
}

ListView > ListItem {
    padding: 0 1;
    height: 1;
}

ListView > ListItem > Static {
    color: #E0E0E0;
}

ListView > ListItem.--highlight {
    background: #5c5cd6 50%;
}

ListView > ListItem.--highlight > Static {
    color: #ffffcc;
}

#info-box {
    width: 1fr;
    height: 1fr;
    border: round #666666;
    padding: 1;
    overflow-y: auto;
}

#info-box:focus {
    border: round #9F2B68;
}

#help-backdrop {
    width: 100%;
    height: 100%;
    background: #000000 80%;
}

#help-content {
    width: 56;
    height: auto;
    border: round #AA336A;
    background: #0A0A0A;
    padding: 1 2;
    align: center middle;
    margin-top: 2;
}

#help-content > Static {
    text-align: center;
}

#player-info {
    padding: 1 2;
    text-align: center;
    text-style: bold;
    background: #7d56f4 20%;
    color: #E0E0E0;
    border: round #7d56f4;
}

#player-status {
    padding: 1 2;
    text-align: center;
    color: #666666;
}

PlayerOverlay {
    align: center middle;
}

PlayerOverlay > Static, PlayerOverlay > Label {
    width: 50;
}

PlayerOverlay > Horizontal {
    width: 50;
    align: center middle;
}

PlayerOverlay Button {
    margin: 0 1;
}

#history-title {
    padding: 1;
    color: #AA336A;
    text-style: bold;
}

#history-table {
    margin: 0 1;
    border: round #666666;
    height: 1fr;
}

#history-table:focus {
    border: round #9F2B68;
}
"""

    def __init__(self):
        super().__init__()
        self._dub = False

    def on_mount(self) -> None:
        self.register_theme(Theme(
            name="kaizen",
            primary="#7d56f4",
            secondary="#AA336A",
            accent="#9F2B68",
            background="#000000",
            surface="#0A0A0A",
            panel="#111111",
            foreground="#E0E0E0",
            error="#FF0044",
            success="#00FF88",
            warning="#FFAA00",
            dark=True,
            variables={
                "block-cursor-text-style": "none",
                "block-cursor-foreground": "#000000",
                "block-cursor-background": "#AA336A",
                "footer-key-foreground": "#AA336A",
                "input-selection-background": "#7d56f4 40%",
                "button-color-foreground": "#000000",
                "button-color-background": "#7d56f4",
                "button-focus-text-style": "reverse",
            },
        ))
        self.theme = "kaizen"
        self.push_screen("home")
