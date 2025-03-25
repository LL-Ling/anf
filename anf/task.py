from typing import Any, Callable, Union, List

from .constant import DEFAULT_PRIORITY


class FlowerTask:
    """
    Main class for a task.
    """
    def __init__(self, *args: Any, **kwargs: Any):
        self.args = args
        self.kwargs = kwargs
        self.task_id = None
        self.function = None
        self.priority = DEFAULT_PRIORITY
        self.iter_keys = []

    def set_priority(self, priority: int) -> "FlowerTask":
        """
        Set priority for task.

        :param priority: The smaller the priority, the higher the priority to run.
        """
        self.priority = priority

        return self

    def set_function(self, function: Callable) -> "FlowerTask":
        """
        Set function for task.

        :param function: Function to be run.
        """
        self.function = function

        return self

    def set_task_id(self, task_id: str) -> "FlowerTask":
        """
        Set task_id for task.

        :param task_id: task_id for the task.
        """
        self.task_id = task_id

        return self

    def set_iter(self, iter_key: Union[str, List[str]]) -> "FlowerTask":
        """
        Set iter_key for task.

        :param iter_key: iter_key make task param iterable.
        """
        if isinstance(iter_key, str):
            self.iter_keys.append(iter_key)
        else:
            self.iter_keys.extend(iter_key)

        return self
