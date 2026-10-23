"""Terminal UI for running a sync. Owner: Vedant.

Launch with `customer-sync-tui`. It drives the same pieces as the CLI
(a source, run_sync, CustomerStore); no sync logic lives here.
"""

from __future__ import annotations

from datetime import datetime

from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Digits,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    RichLog,
    TabbedContent,
    TabPane,
)

from customer_sync.api_client import FileSource, RandomUserClient
from customer_sync.cli import _display_uuid, run_sync
from customer_sync.contracts import Customer, RecordSource, SyncError, SyncSummary
from customer_sync.storage import CustomerStore

COUNTS = ("added", "updated", "unchanged", "rejected")
API_INPUTS = ("#seed", "#results", "#pages")


class SyncApp(App[None]):
    """Pick a source, run one sync, and see the counts, rejections, and stored rows."""

    TITLE = "Customer Data Sync"
    BINDINGS = [("r", "run", "Run sync"), ("q", "quit", "Quit")]
    CSS = """
    #form { width: 36; padding: 1 2 0 2; background: $boost; scrollbar-size-vertical: 1; }
    #form Label { color: $text-muted; text-style: bold; }
    #form RadioSet { width: 100%; border-title-color: $text-muted; border-title-style: bold; }
    #api-fields, #api-fields Vertical { height: auto; }
    #seed-col { width: 2fr; }
    #run { width: 100%; margin-top: 1; }
    #main { padding: 0 1; }
    #cards { height: auto; }
    .card { width: 1fr; height: auto; border: round $primary; border-title-style: bold; }
    .card Digits { width: 100%; text-align: center; }
    .added { border: round $success; border-title-color: $success; }
    .added Digits { color: $success; }
    .updated { border: round $warning; border-title-color: $warning; }
    .updated Digits { color: $warning; }
    .unchanged { border-title-color: $primary; }
    .unchanged Digits { color: $primary; }
    .rejected { border: round $error; border-title-color: $error; }
    .rejected Digits { color: $error; }
    TabbedContent { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with VerticalScroll(id="form"):
                with RadioSet(id="source") as source:
                    source.border_title = "Source"
                    yield RadioButton("Saved file", value=True, id="file")
                    yield RadioButton("Live API", id="api")
                yield Label("File")
                yield Input("tests/fixtures/integration/day1.json", id="path")
                with Horizontal(id="api-fields"):
                    with Vertical(id="seed-col"):
                        yield Label("Seed")
                        yield Input("team2", id="seed", disabled=True)
                    with Vertical():
                        yield Label("Results")
                        yield Input("50", id="results", type="integer", disabled=True)
                    with Vertical():
                        yield Label("Pages")
                        yield Input("1", id="pages", type="integer", disabled=True)
                yield Label("Database")
                yield Input("customers.db", id="db")
                yield Button("Run sync", id="run", variant="primary")
            with Vertical(id="main"):
                with Horizontal(id="cards"):
                    for name in COUNTS:
                        card = Vertical(Digits("0", id=name), classes=f"card {name}")
                        card.border_title = name.capitalize()
                        yield card
                with TabbedContent():
                    with TabPane("Rejections"):
                        yield DataTable(id="rejections", zebra_stripes=True, cursor_type="row")
                    with TabPane("Database"):
                        yield DataTable(id="customers", zebra_stripes=True, cursor_type="row")
                    with TabPane("Run log", id="log-tab"):
                        yield RichLog(id="log", markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.theme = "tokyo-night"
        self.query_one("#rejections", DataTable).add_columns("#", "uuid", "code", "reason")
        self.query_one("#customers", DataTable).add_columns(
            "uuid", "name", "email", "phone", "city", "country", "registered"
        )

    @on(RadioSet.Changed, "#source")
    def _source_changed(self, event: RadioSet.Changed) -> None:
        use_api = event.pressed.id == "api"
        self.query_one("#path", Input).disabled = use_api
        for selector in API_INPUTS:
            self.query_one(selector, Input).disabled = not use_api

    def _text(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    @on(Button.Pressed, "#run")
    def action_run(self) -> None:
        """Build the source from the form and start a sync in a worker thread."""
        button = self.query_one("#run", Button)
        if button.disabled:
            return
        if self.query_one("#api", RadioButton).value:
            try:
                results, pages = int(self._text("#results")), int(self._text("#pages"))
            except ValueError:
                results = pages = 0
            if results < 1 or pages < 1:
                self.notify(
                    "Results and pages must be whole numbers of 1 or more.",
                    title="Check the inputs",
                    severity="error",
                )
                return
            seed = self._text("#seed") or "team2"
            source: RecordSource = RandomUserClient(seed=seed, results=results, pages=pages)
            label = f"api seed={seed} results={results} pages={pages}"
        else:
            source = FileSource(self._text("#path"))
            label = f"file {self._text('#path')}"
        button.disabled = True
        button.label = "Running…"
        self._sync(source, self._text("#db") or "customers.db", label)

    @work(thread=True, exclusive=True)
    def _sync(self, source: RecordSource, db: str, label: str) -> None:
        # The store is opened in this thread: SQLite connections stay on their own thread.
        try:
            with CustomerStore(db) as store:
                summary = run_sync(source, store)
                customers = store.all()
        except SyncError as exc:
            self.call_from_thread(self._show_error, label, str(exc))
        else:
            self.call_from_thread(self._show_result, label, summary, customers)

    def _show_result(self, label: str, summary: SyncSummary, customers: list[Customer]) -> None:
        for name in COUNTS:
            self.query_one(f"#{name}", Digits).update(str(getattr(summary, name)))
        rejections = self.query_one("#rejections", DataTable)
        rejections.clear()
        rejections.add_rows(
            (r.index, Text(_display_uuid(r.uuid)), Text(r.code), Text(r.reason))
            for r in summary.rejections
        )
        table = self.query_one("#customers", DataTable)
        table.clear()
        table.add_rows(
            [
                Text(v)
                for v in (
                    _display_uuid(c.uuid),
                    f"{c.first_name} {c.last_name}",
                    c.email,
                    c.phone or "",
                    c.city or "",
                    c.country or "",
                    c.registered_at[:10],
                )
            ]
            for c in customers
        )
        counts = (
            f"+{summary.added} added  ~{summary.updated} updated  "
            f"={summary.unchanged} unchanged  ✗{summary.rejected} rejected"
        )
        self._log_line(f"[green]✓[/] {escape(label)}  [b]{counts}[/]")
        self.notify(counts, title="Sync complete")
        self._enable_run()

    def _show_error(self, label: str, message: str) -> None:
        self._log_line(f"[red]✗ {escape(label)}[/]  {escape(message)}")
        self.notify(message, title="Sync failed", severity="error")
        self._enable_run()

    def _log_line(self, line: str) -> None:
        self.query_one("#log", RichLog).write(f"[dim]{datetime.now():%H:%M:%S}[/]  {line}")

    def _enable_run(self) -> None:
        button = self.query_one("#run", Button)
        button.disabled = False
        button.label = "Run sync"


def main() -> None:
    SyncApp().run()
