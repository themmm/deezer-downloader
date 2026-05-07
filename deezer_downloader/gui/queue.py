"""Queue page: live view of the threadpool's tasks with progress."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

REFRESH_MS = 500

STATE_LABEL = {
    "waiting": "Waiting",
    "active": "Active",
    "mission accomplished": "Done",
    "failed": "Failed",
}

STATE_ICON = {
    "waiting": "preferences-system-time-symbolic",
    "active": "media-playback-start-symbolic",
    "mission accomplished": "emblem-ok-symbolic",
    "failed": "dialog-error-symbolic",
}


class _QueueRow(Adw.ActionRow):
    """One row representing a QueuedTask. Reused across refreshes."""

    def __init__(self, task):
        super().__init__(title=task.description or task.fn_name)
        self._task = task
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
        self.add_suffix(self._progress)
        self.add_suffix(self._status_icon)
        self.update()

    def update(self) -> None:
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
                self._progress.pulse_step = 0.0
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

        self.set_subtitle(GLib.markup_escape_text(subtitle))


class QueuePage(Gtk.Box):
    """Live list of all tasks ever submitted, newest first."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self._rows: dict[int, _QueueRow] = {}

        self._listbox = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
            margin_top=12, margin_bottom=12,
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

    def _refresh(self) -> bool:
        from deezer_downloader.web.music_backend import sched

        tasks = list(sched.all_tasks)
        if not tasks:
            self._stack.set_visible_child_name("empty")
            return True

        self._stack.set_visible_child_name("list")

        # Add new rows for tasks we haven't seen.
        for task in tasks:
            key = id(task)
            row = self._rows.get(key)
            if row is None:
                row = _QueueRow(task)
                self._rows[key] = row
                self._listbox.prepend(row)
            else:
                row.update()
        return True
