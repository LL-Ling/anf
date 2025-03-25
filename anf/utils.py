import hashlib
import json
import re
import shutil

from .task import FlowerTask

import inspect
import itertools
from typing import List, Tuple, Dict, Iterable, Any, Optional, Callable
from inspect import Parameter


def get_function_params(func: callable) -> Dict[str, Dict]:
    """
    Get parameters of a function, including their properties.

    :param func: The function to inspect.
    :return: Dictionary with parameter names and their properties.
    """
    signature = inspect.signature(func)
    params = {}

    for name, param in signature.parameters.items():
        param_info = {
            'kind': param.kind,
            'default': param.default if param.default != Parameter.empty else None,
            'required': param.default == Parameter.empty and param.kind not in (Parameter.VAR_POSITIONAL,
                                                                                Parameter.VAR_KEYWORD)
        }
        params[name] = param_info
    return params


def permutate_task_params(task: FlowerTask, function: Optional[Callable] = None) -> List[Tuple[List, Dict]]:
    """
    Permutate a tasks parameters for a function.

    :param task: The FlowerTask task with parameters to permutate.
    :param function: The function of the task to permutate.
    :return: List for function parameters.
    """
    if not task.function and not function:
        raise ValueError("Task function is not set.")

    func = task.function or function
    sig = inspect.signature(func)
    params = get_function_params(func)

    try:
        bound_args = sig.bind(*task.args, **task.kwargs)
    except TypeError as e:
        raise RuntimeError(f"Invalid arguments for {func}: {e}") from e
    bound_args.apply_defaults()

    for key in task.iter_keys:
        if key not in params:
            raise RuntimeError(f"iter_key '{key}' does not exist in function parameters.")
        if params[key]['kind'] in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            raise RuntimeError(f"iter_key '{key}' cannot be a variable-length parameter (*args or **kwargs).")
        value = bound_args.arguments[key]
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise RuntimeError(f"iter_key '{key}' value must be a non-string/bytes iterable.")

    param_names = list(sig.parameters.keys())
    param_value_lists = []
    for name in param_names:
        value = bound_args.arguments[name]

        if name in task.iter_keys:
            if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
                raise RuntimeError(f"iter_key '{name}' value must be a non-string/bytes iterable.")
            param_value_lists.append(list(value))
        else:
            param_value_lists.append([value])

    permutations = itertools.product(*param_value_lists)

    results = []
    for perm in permutations:
        args = []
        kwargs = {}
        var_args = []
        var_kwargs = {}

        for name, value in zip(param_names, perm):
            param_kind = params[name]['kind']

            if param_kind == Parameter.VAR_POSITIONAL:
                var_args.extend(value if isinstance(value, Iterable) else [value])
            elif param_kind == Parameter.VAR_KEYWORD:
                var_kwargs.update(value if isinstance(value, dict) else {})
            elif param_kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD):
                args.append(value)
            else:
                kwargs[name] = value

        final_args = args + var_args
        final_kwargs = {**kwargs, **var_kwargs}

        results.append((final_args, final_kwargs))

    return results


def modify_msg_with_terminal(msg: str, msg_head_width: int = 0, fill_char: str = " ") -> str:
    """
    Fill the remaining msg length with fill_char to complete one line based on the terminal width using padding.

    :param msg: need modify msg.
    :param msg_head_width: msg head width.
    :param fill_char: default fill char.
    :return: link string
    """
    term_width = shutil.get_terminal_size().columns
    max_first = max(term_width - msg_head_width, 0)

    first_part = msg[:max_first]
    filled_first = first_part.ljust(max_first, fill_char)
    lines = [filled_first]

    remaining = msg[max_first:]
    while remaining:
        chunk = remaining[:term_width]
        filled_chunk = chunk.ljust(term_width, fill_char)
        lines.append(filled_chunk)
        remaining = remaining[term_width:]

    return '\n'.join(lines)


def link_param(*args, max_length: int = 40, **kwargs) -> str:
    """
    To join parameters with an underscore '_' and return a string.

    :param args: link parameters.
    :param max_length: max string length to link, previous link in etc.
    :param kwargs: link keyword arguments.
    :return: link string
    """
    def process_value(value: Any) -> str:
        if isinstance(value, (str, int, float, bool)):
            return re.sub(r'[^a-zA-Z0-9_]', '_', str(value))
        else:
            try:
                serialized = json.dumps(value, sort_keys=True)
            except (TypeError, ValueError):
                serialized = repr(value)
            return hashlib.sha1(serialized.encode()).hexdigest()[:8]

    parts = []

    for arg in args:
        parts.append(process_value(arg))

    for k, v in kwargs.items():
        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', str(k))
        parts.append(safe_key)
        parts.append(process_value(v))

    param_str = '_'.join(parts)
    param_str = re.sub(r'[^a-zA-Z0-9_]', '_', param_str)

    if len(param_str) > max_length:
        truncate_hash = hashlib.sha1(param_str.encode()).hexdigest()[:8]
        truncate_at = max_length - len(truncate_hash) - 1
        param_str = f"{param_str[:truncate_at]}_{truncate_hash}_etc"

    return param_str
