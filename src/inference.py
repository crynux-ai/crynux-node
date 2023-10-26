import argparse
import os
from typing import Optional, Type

import pydantic
from huggingface_hub.utils._errors import RepositoryNotFoundError
from requests.exceptions import HTTPError

from sd_task.inference_task_args.task_args import InferenceTaskArgs
from sd_task.inference_task_runner.errors import (ModelDownloadError,
                                                  TaskExecutionError)
from sd_task.inference_task_runner.inference_task import run_task


def travel_exc(e: BaseException):
    queue = [e]
    exc_set = set(queue)

    while len(queue) > 0:
        exc = queue.pop(0)
        yield exc
        if exc.__cause__ is not None and exc.__cause__ not in exc_set:
            queue.append(exc.__cause__)
            exc_set.add(exc.__cause__)
        if exc.__context__ is not None and exc.__context__ not in exc_set:
            queue.append(exc.__context__)
            exc_set.add(exc.__context__)


def match_exception(
    e: Exception, target: Type[Exception], message: Optional[str] = None
) -> bool:
    for exc in travel_exc(e):
        if isinstance(exc, target) and (message is None or message in str(exc)):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=str)
    parser.add_argument("task_args", type=str)
    args = parser.parse_args()

    output_dir: str = args.output_dir
    task_args_str: str = args.task_args

    try:
        task_args = InferenceTaskArgs.model_validate_json(task_args_str)
        imgs = run_task(task_args)
        for i, img in enumerate(imgs):
            dst = os.path.join(output_dir, f"{i}.png")
            img.save(dst)
    except pydantic.ValidationError:
        print("Task args validation error")
        raise
    except TaskExecutionError:
        print("Task execution error")
        raise
    except ModelDownloadError as e:
        if match_exception(e, RepositoryNotFoundError) or match_exception(e, HTTPError):
            print("Task model not found")
        else:
            print("Task download error")
        raise


if __name__ == "__main__":
    main()
