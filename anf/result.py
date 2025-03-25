import asyncio
from dataclasses import dataclass
from typing import Dict, Union


@dataclass
class TaskResult:
    task: asyncio.Task
    priority: int


class FlowerResult:
    """
    Main class for FlowerResult.
    Store the Flower task results and provide methods to access the results.
    """

    def __init__(self):
        self._result: Dict[str, TaskResult] = {}

    def add_result(self, task: asyncio.Task, task_id: str, priority: int):
        """
        Add a task to the result dict.

        :param task_id: Task id
        :param priority: Task sort priority
        :param task: Task to add
        """
        self._result[task_id] = TaskResult(task, priority)

    def all_result(self) -> Dict[str, TaskResult]:
        """
        Get all flower task result object.

        :return: task info.
        """
        return self._result

    def get_result(self, task_id: str) -> Union[TaskResult, None]:
        """
        Get flower task result object by task id.

        :param task_id: The ID of the task.
        :return: task info.
        """
        return self._result.get(task_id, None)

    def clear(self):
        """
        Clear flower result state.
        """
        self._result.clear()
