from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

try:
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Footer, Header, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    Text: Any = None
    ComposeResult: Any = Any
    VerticalScroll: type = object  # type: ignore
    Footer: type = object  # type: ignore
    Header: type = object  # type: ignore
    Static: type = object  # type: ignore
    TEXTUAL_AVAILABLE = False

    class App:  # type: ignore
        """Fallback base so importing this module does not require textual."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError('The textual monitor requires the textual package')


MonitorTableFn = Callable[[], Tuple[Any, bool, Any]]


def _missing_textual_error() -> ImportError:
    return ImportError(
        'The cmd_queue textual monitor requires the optional textual '
        'dependency. Install cmd_queue with the optional/textual extras, '
        'or run with with_textual=False.'
    )


class JobTable(Static):  # type: ignore[misc]
    """A small auto-refreshing widget that displays the queue status table."""

    DEFAULT_CSS = """
    JobTable {
        height: 1fr;
        min-height: 8;
        width: 100%;
        overflow: auto;
    }
    """

    def __init__(
        self,
        table_fn: Optional[MonitorTableFn] = None,
        *,
        refresh_rate: float = 0.5,
        **kwargs: Any,
    ) -> None:
        if not TEXTUAL_AVAILABLE:
            raise _missing_textual_error()
        super().__init__(**kwargs)
        self.table_fn = table_fn
        self.refresh_rate = refresh_rate
        self.finished = False
        self.agg_state: Any = None

    def on_mount(self) -> None:
        self.set_interval(self.refresh_rate, self.refresh_status)
        self.refresh_status()

    def refresh_status(self) -> None:
        table_fn = self.table_fn
        if table_fn is None:
            self.update(Text('No status table is configured.', style='yellow'))
            return

        table, finished, agg_state = table_fn()
        self.finished = bool(finished)
        self.agg_state = agg_state
        if table is None:
            table = Text('No status rows yet.', style='dim')
        self.update(table)

        if self.finished:
            app = self.app
            app.graceful_exit = True
            app.exit()


class CmdQueueMonitorApp(App):  # type: ignore[misc]
    """Textual app used by the tmux monitor.

    The constructor and runtime attributes are intentionally stable because
    ``TMUXMultiQueue._textual_monitor`` uses them to coordinate foreground
    attach behavior.
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #status-scroll {
        height: 1fr;
        padding: 0 1;
    }

    #help-line {
        dock: bottom;
        height: 1;
        padding: 0 1;
        color: $text-muted;
        background: $surface;
    }
    """

    def __init__(
        self,
        table_fn: MonitorTableFn,
        kill_fn: Optional[Callable[[], Any]] = None,
        attach_session: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if not TEXTUAL_AVAILABLE:
            raise _missing_textual_error()
        super().__init__(**kwargs)
        self.job_table = JobTable(table_fn, id='job-table')
        self.kill_fn = kill_fn
        self.graceful_exit = False
        self.attach_session = attach_session
        self.attach_requested = False
        self.title = 'Command Queue'
        self.sub_title = 'Monitor'

    @classmethod
    def demo(cls) -> CmdQueueMonitorApp:
        """
        This creates an app instance that we can run.

        CommandLine:
            xdoctest -m cmd_queue.monitor_app CmdQueueMonitorApp.demo:0 --interact

        Example:
            >>> # xdoctest: +REQUIRES(module:textual)
            >>> # xdoctest: +REQUIRES(--interact)
            >>> from cmd_queue.monitor_app import CmdQueueMonitorApp
            >>> self = CmdQueueMonitorApp.demo()
            >>> self.run()
            >>> print(f'self.graceful_exit={self.graceful_exit}')
        """
        from cmd_queue.util import richer as rich

        countdown = 10

        def demo_table_fn():
            nonlocal countdown
            import random

            r = random.random()
            columns = ['name', 'status', 'passed', 'errors', 'total']
            table = rich.table.Table(title='Demo queue status')
            for col in columns:
                table.add_column(col)

            for i in range(100):
                table.add_row(
                    'Job {:0.3f}'.format(i + r),
                    'demo',
                    str(i + r),
                    '0',
                    str(i + r),
                )
            countdown = countdown - 1
            finished = countdown <= 0
            agg_state = None
            return table, finished, agg_state

        return cls(demo_table_fn)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id='status-scroll'):
            yield self.job_table
        yield Static(self._help_text(), id='help-line')
        yield Footer()

    def on_mount(self) -> None:
        self.bind('q', 'quit', description='Quit')
        if self.kill_fn is not None:
            self.bind('k', 'kill_jobs', description='Kill jobs')
        if self.attach_session is not None:
            self.bind('a', 'attach_monitor', description='Attach monitor')

    def _help_text(self) -> Text:
        parts = ['[q] quit']
        if self.kill_fn is not None:
            parts.append('[k] kill jobs')
        if self.attach_session is not None:
            parts.append(f'[a] attach {self.attach_session}')
        return Text('   '.join(parts), style='dim')

    def action_quit(self) -> None:
        self.exit()

    def action_kill_jobs(self) -> None:
        if self.kill_fn is not None:
            self.kill_fn()
        self.graceful_exit = True
        self.exit()

    def action_attach_monitor(self) -> None:
        # The actual tmux attach has to happen *after* the textual app
        # releases the terminal. Flag it and shut down; the caller
        # (TMUXMultiQueue._textual_monitor) checks ``attach_requested``
        # and performs the attach + re-launches the app.
        if self.attach_session is not None:
            self.attach_requested = True
        self.exit()


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/cmd_queue/monitor_app.py
    """
    self = CmdQueueMonitorApp.demo()
    self.run()
    print(f'self.graceful_exit={self.graceful_exit}')
