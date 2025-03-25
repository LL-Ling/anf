from typing import Protocol, Dict, Any


class TaskCoroutine(Protocol):
    __qualname__: str

    async def __call__(self, ctx: Dict[Any, Any]) -> any: ...


class AsyncTaskCM(Protocol):
    __qualname__: str

    def __init__(self, **kwargs) -> None: ...

    async def __aenter__(self) -> None: ...

    async def __aexit__(self, exc_type, exc_value, traceback) -> None: ...


class SyncTaskCM(Protocol):
    __qualname__: str

    def __init__(self, **kwargs) -> None: ...

    def __enter__(self) -> None: ...

    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
