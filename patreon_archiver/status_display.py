"""Live progress display for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import RenderableType

    from .typing import Stats

__all__ = ('STATUS_REFRESH_HZ', 'StatusDisplay')

STATUS_REFRESH_HZ = 10
"""Refresh rate used by the live status display.

:meta hide-value:
"""
_LABEL_WIDTH = 20
_VALUE_WIDTH = 6


class StatusDisplay:
    """Rich-based live progress display with a spinner line and queue statistics."""
    def __init__(self, stats: Stats, *, stream: Any) -> None:
        self._stats = stats
        self._message = 'Starting workers...'
        self._spinner = Spinner('dots', text=Text(self._message))
        self._console = Console(file=stream, force_terminal=True)
        self._live = Live(self._render(),
                          console=self._console,
                          refresh_per_second=STATUS_REFRESH_HZ,
                          transient=True)

    def refresh(self) -> None:
        """Re-render the live display with the latest queue statistics."""
        self._live.update(self._render())

    def set_message(self, message: str) -> None:
        """
        Replace the status message shown next to the spinner.

        Parameters
        ----------
        message : str
            Text rendered beside the spinner glyph.
        """
        self._message = message
        self._spinner.update(text=Text(message))
        self._live.update(self._render())

    def start(self) -> None:
        """Start the live display."""
        self._live.start()

    def stop(self) -> None:
        """Stop the live display and clear the rendered region."""
        self._live.stop()

    def write(self, message: str) -> None:
        """
        Print a persistent status line above the live display.

        Parameters
        ----------
        message : str
            Text to print to the attached console.
        """
        self._console.print(message)

    def _render(self) -> RenderableType:
        stats = self._stats
        stat_lines = Text('\n').join([
            _format_stat_line('Total posts fetched:', stats.posts_handled),
            _format_processing_line(stats.yt_dlp_current_uri, stats.yt_dlp_current_index,
                                    stats.yt_dlp_total_uris),
            _format_stat_line('Image posts:', stats.images_processed),
            _format_stat_line('Podcast posts:', stats.podcasts_processed),
            _format_stat_line('Other post types:', stats.others_processed)
        ])
        return Group(self._spinner, stat_lines)


def _format_stat_line(label: str, value: int) -> Text:
    return Text.assemble((label.ljust(_LABEL_WIDTH), 'bold'), ' ', str(value).rjust(_VALUE_WIDTH))


def _format_processing_line(uri: str | None, index: int, total: int) -> Text:
    label = 'yt-dlp processing:'.ljust(_LABEL_WIDTH)
    if uri is None or total == 0:
        return Text.assemble((label, 'bold'), ' n/a')
    return Text.assemble((label, 'bold'), ' ', uri, ' ', f'({index}/{total})')
