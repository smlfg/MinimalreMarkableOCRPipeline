from PIL import Image

from ocr.pre import MIN_TEXTELLER_HEIGHT, ensure_min_height


def test_small_crop_upscaled_keeps_aspect():
    im = Image.new("L", (40, 20), 255)
    out = ensure_min_height(im)
    assert out.height == MIN_TEXTELLER_HEIGHT
    assert out.width == round(40 * MIN_TEXTELLER_HEIGHT / 20)


def test_tall_crop_untouched():
    im = Image.new("L", (300, 207), 255)
    out = ensure_min_height(im)
    assert out.size == (300, 207)


def test_custom_min_height():
    im = Image.new("L", (149, 73), 255)
    out = ensure_min_height(im, 160)
    assert out.height == 160
    assert out.size == (round(149 * 160 / 73), 160)


def test_rgb_becomes_gray():
    im = Image.new("RGB", (10, 10), "white")
    out = ensure_min_height(im)
    assert out.mode == "L"
    assert out.height == MIN_TEXTELLER_HEIGHT
