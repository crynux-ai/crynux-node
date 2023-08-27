from PIL import Image
import imagehash


def get_image_hash(image_path: str):
    img = Image.open(image_path)
    h = imagehash.phash(img)
    return "0x" + str(h)
