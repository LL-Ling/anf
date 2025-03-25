import asyncio
import shutil
from dataclasses import dataclass
import itertools
import time
from typing import Callable, Optional, Any, List, Dict, Union, Tuple, Generator, Sequence
from uuid import uuid4

from ._typing import TaskCoroutine, AsyncTaskCM, SyncTaskCM
from .constant import DEFAULT_MAX_TASKS
from .result import FlowerResult
from .task import FlowerTask
from .utils import permutate_task_params


@dataclass
class _Progress:
    in_progress: List[str]
    fail_progress: List[str]
    total: int = 0
    success: int = 0


class Flower:
    """
    Main class for Flower.

    :param function: global execution function.
    :param max_tasks: maximum number of tasks to run at a time.
           Define a max_tasks like:
           max_tasks = 5 # global task max_tasks is 5
                or
           max_tasks = {
               0: 5,     # priority level of 0 task max_tasks is 5
               1: 3      # priority level of 1 task max_tasks is 3
           }
    :param progress_bar: write tasks progress bar.
    :param detector: function to determine the Success or Failure of a Task.
    :param cancel_while_failed: cancel all tasks while high priority task had failed.
    :param on_startup: coroutine function to run on task start.
    :param on_shutdown: coroutine function to run on task end.
    :param on_task_start: task function to run on task start.
    :param on_task_end: task function to run on task end.
    :param ctx: dict context.
    """
    def __init__(
        self,
        function: Optional[Callable] = None,
        max_tasks: Union[int, Dict[int, int]] = DEFAULT_MAX_TASKS,
        progress_bar: Optional[bool] = False,
        detector: Optional[Callable] = lambda x: not isinstance(x, Exception),
        cancel_while_failed: Optional[bool] = False,
        on_startup: Optional[List[TaskCoroutine]] = None,
        on_shutdown: Optional[List[TaskCoroutine]] = None,
        on_task_start: Optional[List[TaskCoroutine]] = None,
        on_task_end: Optional[List[TaskCoroutine]] = None,
        with_async_task: Optional[Union[AsyncTaskCM, Generator, Callable]] = None,
        with_sync_task: Optional[Union[SyncTaskCM, Generator, Callable]] = None,
        ctx: Optional[Dict[Any, Any]] = None,
    ):
        self.function = function
        self.cancel_while_failed = cancel_while_failed
        self.on_startup = on_startup or []
        self.on_shutdown = on_shutdown or []
        self.on_task_start = on_task_start or []
        self.on_task_end = on_task_end or []
        self.ctx = ctx or {}
        self.results = FlowerResult()
        self.detector = detector
        self._progress_bar = progress_bar
        self._with_async_task = with_async_task
        self._with_sync_task = with_sync_task
        self._max_tasks = max_tasks
        self._semaphore = None
        self._progress = _Progress(in_progress=[], fail_progress=[])
        self._pending_tasks: Dict[int, List[FlowerTask]] = {}

        if self._with_async_task and self._with_sync_task:
            raise ValueError("Only one of 'with_async_task' or 'with_sync_task' can be provided.")

    def __bool__(self) -> bool:
        return self._progress.total == self._progress.success

    def __repr__(self) -> str:
        pending_count = sum(len(tasks) for tasks in self._pending_tasks.values())
        return f'<{self.__class__.__name__} Pending: {pending_count}>'

    async def start_tasks(self) -> "Flower":
        """
        Start flower all tasks.

        :return: Flower obj
        """
        if not self._pending_tasks:
            raise RuntimeError(f'{self.__repr__()} has not no pending_tasks.')

        self.results.clear()
        self._progress = _Progress(in_progress=[], fail_progress=[])

        for event in self.on_startup:
            await event(self.ctx)

        for priority, flower_tasks in sorted(self._pending_tasks.items(), key=lambda x: x[0], reverse=False):
            self._define_semaphore(priority)
            tasks = list(itertools.chain(*[self._create_tasks(task) for task in flower_tasks]))

            if self._progress_bar:
                self._write_progress()

            if self._should_cancel_tasks(await asyncio.gather(*tasks, return_exceptions=True)):
                break

        for event in self.on_shutdown:
            await event(self.ctx)

        self._pending_tasks.clear()
        return self

    def add_task(self, flower_task: FlowerTask, _task_id: Optional[str] = None):
        """
        Add a task to the pending task list.

        :param flower_task: FlowerTask obj.
        :param _task_id: Custom FlowerTask obj task_id.
        """
        flower_task.task_id = _task_id or uuid4().hex[:15]
        self._pending_tasks.setdefault(flower_task.priority, []).append(flower_task)

    def progress_msg(self, max_show_progress: Union[int, None] = None, finish: bool = False) -> str:
        """
        Add a task to the pending task list.
            [ 100% ] | T/S/F: 200/200/0 | Progress Info

        :param max_show_progress: The maximum number of tasks to show progress bar for.
        :param finish: Return finish Progress.
        :return: msg string
        """
        failed_progress_count = len(self._progress.fail_progress)
        msg = (f"[ {((self._progress.success + failed_progress_count) / self._progress.total * 100):.0f}% ] | "
               f"T/S/F: {self._progress.total}/{self._progress.success}/{failed_progress_count} |")

        if finish:
            if max_show_progress and isinstance(max_show_progress, int):
                failed_progress = self._progress.fail_progress[-max_show_progress:]
            else:
                failed_progress = self._progress.fail_progress

            return f"{msg} FailProgress: {failed_progress}"
        else:
            if max_show_progress and isinstance(max_show_progress, int):
                in_progress = self._progress.in_progress[:max_show_progress]
            else:
                in_progress = self._progress.in_progress

            return f"{msg} InProgress: {in_progress}"

    def _define_semaphore(self, priority: int):
        """
        Define a semaphore based on the priority and max_tasks configuration.

        :param priority: The priority level of the task.
        """
        max_tasks = self._max_tasks.get(priority,
                                        DEFAULT_MAX_TASKS) if isinstance(self._max_tasks, dict) else self._max_tasks
        self._semaphore = asyncio.Semaphore(max_tasks)

    def _create_tasks(self, flower_task: FlowerTask) -> List[asyncio.Task]:
        """
        Create a coroutine_task and add it to the tasks list.

        :param flower_task: FlowerTask obj.
        :return: A coroutine task list.
        """
        if flower_task.function is None and self.function is None:
            raise RuntimeError(f'priority {flower_task.priority} exists function-defining task.')

        if flower_task.function is None:
            flower_task.function = self.function

        task_params = permutate_task_params(flower_task)
        if not task_params:
            raise RuntimeError(f'priority {flower_task.function} no exists any params.')

        tasks = []
        for index, (args, kwargs) in enumerate(task_params):
            task_id = f'{flower_task.task_id}-{index}' if flower_task.iter_keys else flower_task.task_id

            ctx = {
                "task_id": task_id,
                "function_name": flower_task.function.__name__,
                "priority": flower_task.priority,
                "args": args,
                "kwargs": kwargs,
                "start_time": 0,
                "end_time": 0,
                "result": None
            }
            ctx = {**self.ctx, **ctx}

            task = asyncio.create_task(self._wrap_semaphore(flower_task.function, args, kwargs, ctx=ctx))
            tasks.append(task)

            if self._progress_bar:
                task.add_done_callback(lambda _: self._write_progress())

        self._progress.total += len(tasks)
        return tasks

    def _should_cancel_tasks(self, results: Tuple[Union[Any, Exception]]) -> bool:
        """
        Determine if tasks should be canceled based on results.

        :param results: List of task results.
        :return: True if tasks should be cancelled, otherwise False.
        """
        if not self.cancel_while_failed:
            return False

        for res in results:
            if not self.detector(res):
                return True

        return False

    def _write_progress(self):
        """
        Write progress bar to progress bar if in_progress have any tasks.
        """
        if self._progress_bar:
            def get_truncated_message(message: str):
                return message[:max(shutil.get_terminal_size().columns - 1, 0)]

            msg = get_truncated_message(self.progress_msg())
            print(f"{msg}", end="\r")

    async def _wrap_semaphore(self, function: Callable, args: Any, kwargs: Any, ctx: Dict[Any, Any]) -> Any:
        """
        Make task work semaphore away.

        :param function: task function
        :return: coroutine result
        """
        async with self._semaphore:
            ctx["start_time"] = time.time()

            for event in self.on_task_start:
                await event(ctx)

            try:
                if self._with_sync_task:
                    with self._with_sync_task(**ctx):
                        task = asyncio.create_task(function(*args, **kwargs))
                elif self._with_async_task:
                    async with self._with_async_task(**ctx):
                        task = asyncio.create_task(function(*args, **kwargs))
                else:
                    task = asyncio.create_task(function(*args, **kwargs))

                self._progress.in_progress.append(ctx["task_id"])
                self.results.add_result(task, ctx["task_id"], ctx["priority"])
                res = await asyncio.wait_for(task, timeout=None)
                ctx["result"] = res
                if self.detector(ctx["result"]):
                    self._progress.success += 1
                else:
                    self._progress.fail_progress.append(ctx["task_id"])
            except Exception as exc:
                res = exc
                ctx["result"] = exc
                ctx["stack"] = task.get_stack() if task else []
                self._progress.fail_progress.append(ctx["task_id"])
            finally:
                ctx["end_time"] = time.time()
                self._progress.in_progress.remove(ctx["task_id"])

            for event in self.on_task_end:
                await event(ctx)

            return res


def get_flower(function: Callable, **kwargs: Any) -> Flower:
    """
    Get flower object for given function.

    :param function: Task function.
    :param kwargs: Flower kwargs
    :return: Flower obj
    """
    return Flower(function, **kwargs)


async def run_flower(function_tasks: Sequence[Any], function: Optional[Callable] = None, **kwargs: Any) -> Flower:
    """
    Run simple task.

    :param function_tasks: Iterable param for function.
    :param function: Run with function.
    :param kwargs: Flower kwargs
    :return: Flower obj
    """
    flower = get_flower(function, **kwargs)

    for task in function_tasks:
        flower_task = task if isinstance(task, FlowerTask) else FlowerTask(task)
        flower.add_task(flower_task, _task_id=flower_task.task_id)

    return await flower.start_tasks()
