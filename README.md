## Async and Flower
**anf** allows you to elegantly organize and execute your tasks.

## Installation
```console
$ pip install anf
```

## Example
```Python
import asyncio

from anf import run_flower
from anf import FlowerTask

async def fn_param(param: str) -> bool:
    print(param)
    await asyncio.sleep(2)
    return True

async def main():
    function_params = [
        FlowerTask("p1").set_task_id("task_id-1"),
        FlowerTask("p2"),
    ]
    
    # run with FlowerTask list
    await run_flower(function_params, fn_param, max_tasks=2)

    # run with simple list and set iter
    await run_flower(["p1", "p2"], fn_param, max_tasks=1).set_iter(["param"])

if __name__ == '__main__':
    asyncio.run(main())
```
