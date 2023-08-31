from h_worker.task.utils import get_image_hash

import concurrent.futures


def test_image_hash():
    h = get_image_hash("test.png")
    assert h == "0xee96b9d99124a466"


def test_img_hash_multithread():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = []
        for _ in range(3):
            f = pool.submit(get_image_hash, "test.png")
            futures.append(f)
        for f in concurrent.futures.as_completed(futures):
            assert f.result() == "0xee96b9d99124a466"
