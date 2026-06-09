from textual.reactive import reactive
from textual.widgets import Static

from sni.providers.base import AnimeResult
from sni.tui.widgets.ascii_art import KAIZEN_JAPANESE_ASCII, SUNDEEP_ASCII


class InfoBox(Static):
    has_anime = reactive(False, init=False)
    title = reactive("", init=False)
    description = reactive("", init=False)
    genres = reactive("", init=False)
    score = reactive(0.0, init=False)

    def __init__(self, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self._init_content_set = False

    def _make_no_anime_content(self):
        lines = []
        ascii_lines = SUNDEEP_ASCII.strip("\n").split("\n")
        for line in ascii_lines:
            lines.append(f"[#AA336A]{line}[/]")
        lines.append("")
        placeholder = KAIZEN_JAPANESE_ASCII.strip("\n").split("\n")
        for line in placeholder[-8:]:
            lines.append(f"[#666666]{line}[/]")
        return "\n".join(lines)

    def _make_anime_content(self):
        lines = []
        lines.append(f"[bold #AA336A]{self.title}[/]")
        lines.append("")
        if self.score:
            lines.append(f"[#888888]Score:[/] [#E0E0E0]{self.score:.1f}[/]")
        if self.genres:
            lines.append(f"[#888888]Genres:[/] [#E0E0E0]{self.genres}[/]")
            lines.append("")
        if self.description:
            lines.append("[#888888]Description:[/]")
            lines.append(f"[#E0E0E0]{self.description[:500]}[/]")
        return "\n".join(lines)

    def on_mount(self) -> None:
        self.update(self._make_no_anime_content())

    def watch_has_anime(self, value: bool):
        if value:
            self.update(self._make_anime_content())
        else:
            self.update(self._make_no_anime_content())

    def set_info(self, anime: AnimeResult):
        self.title = anime.title or ""
        self.description = anime.description or ""
        self.genres = ", ".join(anime.genres) if anime.genres else ""
        self.score = anime.score or 0.0
        self.has_anime = True

    def clear_info(self):
        self.title = ""
        self.description = ""
        self.genres = ""
        self.score = 0.0
        self.has_anime = False
