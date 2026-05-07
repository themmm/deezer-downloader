"""Queue page: live view of the threadpool's tasks with progress."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

REFRESH_MS = 500

STATE_LABEL = {
    "pending": "Pending",
    "waiting": "Waiting",
    "active": "Active",
    "mission accomplished": "Done",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

STATE_ICON = {
    "pending": "view-list-symbolic",
    "waiting": "preferences-system-time-symbolic",
    "active": "media-playback-start-symbolic",
    "mission accomplished": "emblem-ok-symbolic",
    "failed": "dialog-error-symbolic",
    "cancelled": "process-stop-symbolic",
}

FINAL_STATES = {"mission accomplished", "failed", "cancelled"}

# Subtasks use shorter state names; map them to the same icons.
SUBTASK_ICON = {
    "waiting": "preferences-system-time-symbolic",
    "active": "media-playback-start-symbolic",
    "done": "emblem-ok-symbolic",
    "failed": "dialog-error-symbolic",
    "cancelled": "process-stop-symbolic",
}

# Commands that report per-item progress via init_subtasks/set_subtask_state.
EXPANDABLE_COMMANDS = {
    "download_deezer_album_and_queue_and_zip",
    "download_deezer_playlist_and_queue_and_zip",
    "download_spotify_playlist_and_queue_and_zip",
    "download_deezer_favorites",
}


class _QueueRow:
    """Wraps a QueuedTask. Reused across refreshes."""

    def __init__(self, task, on_remove):
        self._task = task
        self._on_remove = on_remove
        self._sub_rows: list[tuple[Adw.ActionRow, Gtk.Image]] = []

        title = task.description or task.fn_name
        if task.fn_name in EXPANDABLE_COMMANDS:
            self._row = Adw.ExpanderRow(title=title)
            self._is_expander = True
        else:
            self._row = Adw.ActionRow(title=title)
            self._is_expander = False

        self._progress = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            show_text=False,
            width_request=140,
        )
        self._progress.set_visible(False)
        self._status_icon = Gtk.Image(
            icon_name="preferences-system-time-symbolic",
            valign=Gtk.Align.CENTER,
        )
        self._remove_btn = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text="Remove from queue",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        self._remove_btn.connect("clicked", self._on_remove_clicked)
        self._row.add_suffix(self._progress)
        self._row.add_suffix(self._status_icon)
        self._row.add_suffix(self._remove_btn)
        self.update()

    def _on_remove_clicked(self, _button) -> None:
        self._on_remove(self._task)

    @property
    def widget(self) -> Gtk.Widget:
        return self._row

    @property
    def task(self):
        return self._task

    # --- Updates ----------------------------------------------------------

    def update(self) -> None:
        self._update_main()
        if self._is_expander:
            self._sync_subtasks()

    def _update_main(self) -> None:
        task = self._task
        state = task.state
        self._status_icon.set_from_icon_name(
            STATE_ICON.get(state, "dialog-question-symbolic")
        )

        subtitle = STATE_LABEL.get(state, state)
        if state == "active":
            if task.progress_maximum > 0:
                fraction = min(1.0, task.progress / task.progress_maximum)
                self._progress.set_fraction(fraction)
                self._progress.set_visible(True)
                subtitle = f"Active – {task.progress} / {task.progress_maximum}"
            else:
                self._progress.set_visible(True)
                self._progress.pulse()
                subtitle = "Active"
        elif state == "mission accomplished":
            self._progress.set_visible(False)
            subtitle = "Done"
        elif state == "failed":
            self._progress.set_visible(False)
            err = str(task.exception) if task.exception else ""
            subtitle = f"Failed: {err}" if err else "Failed"
        else:
            self._progress.set_visible(False)

        self._row.set_subtitle(GLib.markup_escape_text(subtitle))

    def _sync_subtasks(self) -> None:
        subtasks = self._task.subtasks or []

        for i in range(len(self._sub_rows), len(subtasks)):
            sub = subtasks[i]
            sub_row = Adw.ActionRow(
                title=GLib.markup_escape_text(sub["label"])
            )
            icon = Gtk.Image(
                icon_name=SUBTASK_ICON.get(sub["state"],
                                           "dialog-question-symbolic"),
                valign=Gtk.Align.CENTER,
            )
            sub_row.add_suffix(icon)
            self._row.add_row(sub_row)
            self._sub_rows.append((sub_row, icon))

        for i, (sub_row, icon) in enumerate(self._sub_rows):
            sub = subtasks[i]
            icon.set_from_icon_name(
                SUBTASK_ICON.get(sub["state"], "dialog-question-symbolic")
            )
            error = sub.get("error")
            if error:
                sub_row.set_subtitle(GLib.markup_escape_text(error))
            else:
                sub_row.set_subtitle("")


class QueuePage(Gtk.Box):
    """Live list of all tasks ever submitted, newest first."""

    def __init__(self, on_toast=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_toast = on_toast or (lambda _msg: None)

        self._rows: dict[int, _QueueRow] = {}

        self.append(self._build_toolbar())

        self._listbox = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
            margin_top=6, margin_bottom=12,
            margin_start=12, margin_end=12,
        )

        self._empty = Adw.StatusPage(
            icon_name="folder-download-symbolic",
            title="Queue is empty",
            description="Search and click the download button to add items.",
        )

        scroller = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        scroller.set_child(self._listbox)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._empty, "empty")
        self._stack.add_named(scroller, "list")
        self._stack.set_visible_child_name("empty")

        self.append(self._stack)

        GLib.timeout_add(REFRESH_MS, self._refresh)

    # --- Toolbar ----------------------------------------------------------

    def _build_toolbar(self) -> Gtk.Widget:
        bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
            margin_top=12, margin_start=12, margin_end=12,
        )
        self._start_btn = Gtk.Button(
            label="Start downloads",
            css_classes=["suggested-action"],
        )
        self._start_btn.connect("clicked", self._on_start)
        bar.append(self._start_btn)

        self._clear_done_btn = Gtk.Button(label="Clear completed")
        self._clear_done_btn.connect("clicked", self._on_clear_completed)
        bar.append(self._clear_done_btn)

        self._clear_all_btn = Gtk.Button(
            label="Clear all",
            css_classes=["destructive-action"],
        )
        self._clear_all_btn.connect("clicked", self._on_clear_all)
        bar.append(self._clear_all_btn)

        return bar

    def _on_start(self, _button) -> None:
        from deezer_downloader.web.music_backend import sched
        started = sched.start_pending()
        if started == 0:
            self._on_toast("Nothing to start")
        else:
            self._on_toast(f"Started {started} download{'s' if started != 1 else ''}")

    def _on_clear_completed(self, _button) -> None:
        from deezer_downloader.web.music_backend import sched
        for task in list(sched.all_tasks):
            if task.state in FINAL_STATES:
                sched.remove_task(task)
        self._prune_rows(sched)

    def _on_clear_all(self, _button) -> None:
        from deezer_downloader.web.music_backend import sched
        for task in list(sched.all_tasks):
            sched.remove_task(task)
        self._prune_rows(sched)

    # --- Per-row remove ---------------------------------------------------

    def _on_row_remove(self, task) -> None:
        from deezer_downloader.web.music_backend import sched
        sched.remove_task(task)
        self._prune_rows(sched)

    # --- Refresh / sync ---------------------------------------------------

    def _refresh(self) -> bool:
        from deezer_downloader.web.music_backend import sched

        tasks = list(sched.all_tasks)
        self._update_toolbar_sensitivity(tasks)

        if not tasks:
            self._stack.set_visible_child_name("empty")
            return True

        self._stack.set_visible_child_name("list")

        for task in tasks:
            key = id(task)
            row = self._rows.get(key)
            if row is None:
                row = _QueueRow(task, self._on_row_remove)
                self._rows[key] = row
                self._listbox.append(row.widget)
            else:
                row.update()

        self._prune_rows(sched)
        return True

    def _update_toolbar_sensitivity(self, tasks) -> None:
        any_pending = any(t.state == "pending" for t in tasks)
        any_done = any(t.state in FINAL_STATES for t in tasks)
        any_at_all = bool(tasks)
        self._start_btn.set_sensitive(any_pending)
        self._clear_done_btn.set_sensitive(any_done)
        self._clear_all_btn.set_sensitive(any_at_all)

    def _prune_rows(self, sched) -> None:
        """Drop rows whose backing task is no longer in all_tasks."""
        live_ids = {id(task) for task in sched.all_tasks}
        for key in list(self._rows.keys()):
            if key in live_ids:
                continue
            row = self._rows.pop(key)
            self._listbox.remove(row.widget)
