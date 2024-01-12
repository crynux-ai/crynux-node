import os.path
import json
import tempfile

from h_worker.task.utils import get_image_hash, get_gpt_resp_hash

import concurrent.futures


def test_image_hash():
    h = get_image_hash("test.png")
    assert h == "0x9c3bc76699c63609"


def test_img_hash_multithread():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = []
        for _ in range(3):
            f = pool.submit(get_image_hash, "test.png")
            futures.append(f)
        for f in concurrent.futures.as_completed(futures):
            assert f.result() == "0x9c3bc76699c63609"


def test_gpu_resp_hash():
    resp = {
        "model": "gpt2",
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": '\n\nI have a chat bot, called "Eleanor" which was developed by my team on Skype. '
                    "The only thing I will say is this",
                },
                "index": 0,
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 30, "total_tokens": 41},
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        resp_file = os.path.join(tmp_dir, "resp.json")

        with open(resp_file, mode="w", encoding="utf-8") as f:
            json.dump(resp, f, ensure_ascii=False)
        
        h = get_gpt_resp_hash(resp_file)
        assert h == "0xd5188d83d2abbd4322fdd950b02c39b6bdbbe2cb5a160233607336db41bd262f"

