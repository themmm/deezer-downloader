import os
import threading
import time
from queue import Queue
import traceback

local_obj = threading.local()

# Module-level stop flag set by stop_workers_now(); downloads check this
# between tracks so they bail out fast on app shutdown.
_global_stop = threading.Event()


class ThreadpoolScheduler:

    def __init__(self):
        self.task_queue = Queue() # threadsafe queue where we put/get QueuedTask objects
        self.worker_threads = [] # list of WorkerThread objects

        # self.commands: {'function_name': function_pointer_to_the_function}
        # {'download_deezer_song_and_queue': <function download_deezer_song_and_queue at 0x7ff81d739280>}
        self.commands = {}

        # list of all QueuedTask objects we processed during runtime (used by /queue)
        self.all_tasks = []

    def run_workers(self, num_workers):
        for i in range(num_workers):
            t = WorkerThread(i, self.task_queue)
            t.start()
            self.worker_threads.append(t)

    def enqueue_task(self, description, command, **kwargs):
        q = QueuedTask(description, command, self.commands[command], **kwargs)
        self.task_queue.put(q)
        self.all_tasks.append(q)
        return q

    def add_pending(self, description, command, **kwargs):
        """Create a task in 'pending' state. It is appended to all_tasks but
        not pushed onto the worker queue, so workers don't pick it up until
        start_pending() is called."""
        q = QueuedTask(description, command, self.commands[command], **kwargs)
        q.state = "pending"
        self.all_tasks.append(q)
        return q

    def start_pending(self) -> int:
        """Move pending tasks onto the worker queue. Returns how many were
        started."""
        started = 0
        for task in self.all_tasks:
            if task.state == "pending" and not task.cancelled:
                task.state = "waiting"
                self.task_queue.put(task)
                started += 1
        return started

    def remove_task(self, task) -> None:
        """Cancel and remove a task from all_tasks. Workers see the cancel
        flag when they pull the task and skip it; in-progress tasks honour
        the flag at the next iteration boundary."""
        task.cancelled = True
        try:
            self.all_tasks.remove(task)
        except ValueError:
            pass

    def register_command(self):
        def decorator(fun):
            self.commands[fun.__name__] = fun
            return fun
        return decorator

    def stop_workers(self):
        """Graceful stop: signal workers to exit and wait for them. Used by
        the long-running web server on atexit."""
        for i in range(len(self.worker_threads)):
            self.task_queue.put(False)
        for worker in self.worker_threads:
            worker.join()
        # print("All workers stopped")

    def stop_workers_now(self):
        """Immediate stop: flag the scheduler as stopping and remove any
        partial files for currently active tasks. Workers are daemon
        threads so the process exiting kills them; we do not join."""
        _global_stop.set()
        for _ in range(len(self.worker_threads)):
            try:
                self.task_queue.put_nowait(False)
            except Exception:
                pass
        for task in self.all_tasks:
            if task.state != "active":
                continue
            partial = getattr(task, "current_output_file", None)
            if not partial:
                continue
            try:
                if os.path.exists(partial):
                    os.unlink(partial)
            except OSError:
                pass


class WorkerThread(threading.Thread):

    def __init__(self, index, task_queue):
        super().__init__(daemon=True)
        self.index = index # just an id per Worker
        self.task_queue = task_queue # shared between all WorkerThreads

    def run(self):
        while True:
            # print(f"Worker {self.index} is waiting for a task")
            task = self.task_queue.get(block=True)
            if not task:
                # print(f"Worker {self.index} is exiting")
                return
            if task.cancelled or _global_stop.is_set():
                task.state = "cancelled"
                continue
            # print(f"Worker {self.index} is now working on task: {task.kwargs}")
            task.state = "active"
            self.ts_started = time.time()
            task.worker_index = self.index
            local_obj.current_task = task
            try:
                task.result = task.exec()
                if task.cancelled or _global_stop.is_set():
                    task.state = "cancelled"
                else:
                    task.state = "mission accomplished"
            except Exception as ex:
                print(traceback.format_exc())
                print(f"Task {task.fn_name} failed with parameters '{task.kwargs}'\nReason: {ex}")
                if task.cancelled or _global_stop.is_set():
                    task.state = "cancelled"
                else:
                    task.state = "failed"
                    task.exception = ex
            finally:
                task.current_output_file = None
            self.ts_finished = time.time()
            # print(f"worker {self.index} is done with task: {task.kwargs} (state={task.state})")


class QueuedTask:
    def __init__(self, description, fn_name, fn, **kwargs):
        self.description = description
        self.fn_name = fn_name
        self.fn = fn
        self.kwargs = kwargs
        self.state = "waiting"
        self.exception = None
        self.result = None
        self.progress = 0
        self.progress_maximum = 0
        self.ts_queued = time.time()
        self.ts_started = 0
        self.ts_finished = 0
        self.cancelled = False
        # Path of the file currently being written, if any. Used for
        # partial-file cleanup on app shutdown.
        self.current_output_file = None
        # Per-item state for tasks that download many things (album,
        # playlist, favorites). Each entry: {"label": str, "state": str,
        # "error": str | None}. ``state`` is one of
        # waiting/active/done/failed/cancelled.
        self.subtasks = []
        # Pre-resolved track data, populated by the GUI's background
        # preloader so the user sees the track list before starting the
        # download. The command then reuses this instead of re-fetching.
        self.preload_data = None

    def exec(self):
        return self.fn(**self.kwargs)


def report_progress(value, maximum):
    local_obj.current_task.progress = value
    local_obj.current_task.progress_maximum = maximum


def init_subtasks(labels):
    """Initialise per-item subtasks on the current task in the 'waiting'
    state. Pass a list of human-readable labels (one per item)."""
    local_obj.current_task.subtasks = [
        {"label": label, "state": "waiting", "error": None}
        for label in labels
    ]


def set_subtask_state(index, state, error=None):
    """Update one subtask. ``state`` is one of waiting/active/done/failed/cancelled."""
    subtasks = getattr(local_obj.current_task, "subtasks", None)
    if not subtasks or not (0 <= index < len(subtasks)):
        return
    subtasks[index]["state"] = state
    if error is not None:
        subtasks[index]["error"] = str(error)


def get_current_task():
    """Return the task currently running on this worker thread, if any."""
    return getattr(local_obj, "current_task", None)


def is_cancelled() -> bool:
    """Return True if the current task or the whole scheduler should stop."""
    task = getattr(local_obj, "current_task", None)
    if task is not None and task.cancelled:
        return True
    return _global_stop.is_set()


def set_current_output_file(path: str) -> None:
    task = getattr(local_obj, "current_task", None)
    if task is not None:
        task.current_output_file = path


def clear_current_output_file() -> None:
    task = getattr(local_obj, "current_task", None)
    if task is not None:
        task.current_output_file = None
