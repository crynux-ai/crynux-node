from h_worker.task.utils import get_image_hash


def test_image_hash():
    h = get_image_hash("test.png")
    assert h == "0xee96b9d99124a466"
