import os.path
import subprocess


def get_image_hash(filename: str) -> str:
    dirname = os.path.dirname(os.path.abspath(__file__))
    imhash = os.path.join(dirname, "imhash")
    res = subprocess.check_output([imhash, "-f", filename], encoding="utf-8")
    return res.strip()
