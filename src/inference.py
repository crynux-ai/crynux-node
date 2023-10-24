import argparse
import os
from typing import Type

import pydantic

from sd_task.inference_task_args.task_args import InferenceTaskArgs
from sd_task.inference_task_runner.errors import (ModelDownloadError,
                                                  TaskExecutionError)
from sd_task.inference_task_runner.inference_task import run_task
from huggingface_hub.utils._errors import RepositoryNotFoundError


def travel_cause(e: BaseException):
    while e.__cause__:
        e = e.__cause__
        yield e


def match_exception(e: Exception, target: Type[Exception]) -> bool:
    if isinstance(e, target):
        return True
    for exc in travel_cause(e):
        if isinstance(exc, target):
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
        if match_exception(e, RepositoryNotFoundError):
            print("Task model not found")
        else:
            print("Task download error")
        raise


if __name__ == "__main__":
    main()
