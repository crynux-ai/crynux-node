import argparse
import json
import logging
import os
import sys
from datetime import datetime

import pydantic
from gpt_task.inference import run_task as gpt_run_task
from gpt_task.models import GPTTaskArgs
from sd_task.inference_task_args.task_args import InferenceTaskArgs
from sd_task.inference_task_runner.inference_task import run_task as sd_run_task
from sd_task.prefetch import prefetch_models as sd_prefetch_models
from gpt_task.prefetch import prefetch_models as gpt_prefetch_models


_logger = logging.getLogger(__name__)
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
_logger.addHandler(handler)
_logger.setLevel(logging.INFO)


def sd_inference(output_dir: str, task_args_str: str):
    task_args = InferenceTaskArgs.model_validate_json(task_args_str)
    imgs = sd_run_task(task_args)
    for i, img in enumerate(imgs):
        dst = os.path.join(output_dir, f"{i}.png")
        img.save(dst)


def gpt_inference(output_dir: str, task_args_str: str):
    task_args = GPTTaskArgs.model_validate_json(task_args_str)
    resp = gpt_run_task(task_args)

    dst = os.path.join(output_dir, "response.json")
    with open(dst, mode="w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False)


def _inference(args):
    task_type: int = args.task_type
    output_dir: str = args.output_dir
    task_args_str: str = args.task_args

    try:
        _logger.info(
            f"Inference task starts at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if task_type == 0:
            # sd task
            sd_inference(output_dir, task_args_str)
        elif task_type == 1:
            # gpt task
            gpt_inference(output_dir, task_args_str)
        else:
            raise ValueError(f"unknown task type {task_type}")

        _logger.info(
            f"Inference task finishes at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except pydantic.ValidationError:
        _logger.info("Task args invalid")
        raise


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="job")

    subparsers.add_parser("prefetch")

    inference_parser = subparsers.add_parser("inference")
    inference_parser.add_argument("task_type", type=int, choices=[0, 1])
    inference_parser.add_argument("output_dir", type=str)
    inference_parser.add_argument("task_args", type=str)

    args = parser.parse_args(argv)
    job = args.job

    try:
        if job == "prefetch":
            sd_prefetch_models()
            gpt_prefetch_models()
        else:
            _inference(args)
    except Exception as e:
        _logger.exception(e)
        _logger.error("crynux worker process error")


if __name__ == "__main__":
    main()
