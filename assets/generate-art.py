#!/usr/bin/env python3
"""Draw galaxy-360's cover, banner and icon.

Everything here is generated: a deep-blue nebula field, a ringed planet, a starfield, and the wordmark. No third-party
artwork, no Nintendo assets — the shapes are noise and geometry, and the text is set from a font the system already has.

    python3 assets/generate-art.py

Writes assets/cover.png (1200x1536, the console's case ratio), assets/banner.png (1920x480) and assets/icon.png
(512x512). Deterministic: the same seed draws the same picture.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
SEED = 0x3600

# The palette: night blue at the edges, a hot core of cyan and violet where the nebula is thickest, and a pale gold
# sun for the planet's rim.
DEEP = (6, 10, 26)
MID = (22, 40, 96)
HOT = (74, 150, 255)
VIOLET = (138, 92, 255)
SUN = (255, 214, 150)

FONT_CANDIDATES = (
    "/usr/share/fonts/rsms-inter-fonts/Inter-Bold.ttf",
    "/usr/share/fonts/open-sans/OpenSans-ExtraBold.ttf",
    "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
    "/usr/share/fonts/google-noto/NotoSans-CondensedBlack.ttf",
)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def gradient(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    """A vertical ramp, drawn one row at a time and stretched: cheaper than per-pixel work at any real size."""
    strip = Image.new("RGB", (1, height))
    draw = ImageDraw.Draw(strip)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.point((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return strip.resize((width, height), Image.BILINEAR)


def cloud(width: int, height: int, rng: random.Random, cells: int,
          colour: tuple) -> tuple[Image.Image, Image.Image]:
    """One layer of nebula: a coarse noise field blurred into soft lobes, tinted `colour`, additive."""
    small = Image.new("L", (cells, max(2, int(cells * height / width))))
    pixels = small.load()
    for y in range(small.height):
        for x in range(small.width):
            # A few octaves of value noise: the coarse shape, a medium wobble, and a fine grain.
            v = 0.0
            for octave, weight in ((1, 0.55), (2, 0.30), (4, 0.15)):
                v += weight * rng.random() ** 2 * (1.0 + 0.2 * math.sin((x * octave + y * octave) * 0.15))
            pixels[x, y] = min(255, int(v * 210))
    big = small.resize((width, height), Image.BICUBIC).filter(ImageFilter.GaussianBlur(width / 40))
    # The layer fades off at the edges so the field never shows a seam.
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse(
        (-width * 0.15, -height * 0.25, width * 1.15, height * 1.25), fill=255
    )
    mask = mask.filter(ImageFilter.GaussianBlur(width / 14))
    return Image.composite(Image.new("RGB", (width, height), colour), Image.new("RGB", (width, height), (0, 0, 0)), mask).convert("RGB"), big


def nebula_field(width: int, height: int, rng: random.Random) -> Image.Image:
    """The background: the night sky, three nebula lobes, a dust lane and the stars."""
    base = gradient(width, height, (12, 20, 48), DEEP)
    for cells, colour, strength in (
        (14, HOT, 0.42),
        (22, VIOLET, 0.28),
        (9, (240, 248, 255), 0.10),
    ):
        tinted, shade = cloud(width, height, rng, cells, colour)
        shade = shade.point(lambda v, s=strength: int(v * s))
        lobe = ImageChops.multiply(tinted, Image.merge("RGB", (shade, shade, shade)))
        base = ImageChops.add(base, lobe)

    # A dust lane: a dark band across the lower third, softened, so the field has depth rather than a wash.
    lane = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(lane)
    draw.polygon(
        [(0, height * 0.78), (width * 0.35, height * 0.62), (width, height * 0.70), (width, height * 0.86), (0, height * 0.95)],
        fill=140,
    )
    lane = lane.filter(ImageFilter.GaussianBlur(width / 22))
    base = Image.composite(Image.new("RGB", (width, height), DEEP), base, lane)

    # Stars: two sizes, the bright ones with a soft halo.
    for _ in range(int(width * height / 900)):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        r = rng.choice((0.5, 0.6, 0.8, 1.0, 1.4, 2.0))
        tone = rng.randint(190, 255)
        ImageDraw.Draw(base).ellipse((x - r, y - r, x + r, y + r), fill=(tone, tone, min(255, tone + 10)))
    halo = Image.new("RGB", (width, height), (0, 0, 0))
    halo_draw = ImageDraw.Draw(halo)
    for _ in range(int(width * height / 40000)):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        r = rng.uniform(3.0, 7.0)
        halo_draw.ellipse((x - r, y - r, x + r, y + r), fill=(120, 150, 200))
    halo = halo.filter(ImageFilter.GaussianBlur(4))
    return ImageChops.add(base, halo)


def radial(size: int) -> Image.Image:
    """A radial ramp, bright at the centre: the sphere's lighting before it is masked to a circle."""
    steps = 200
    small = Image.new("L", (steps, steps), 0)
    draw = ImageDraw.Draw(small)
    centre = steps / 2
    for i in range(steps, 0, -1):
        t = i / steps
        r = t * centre
        draw.ellipse((centre - r, centre - r, centre + r, centre + r), fill=int(255 * (1.0 - t ** 2)))
    return small.resize((size, size), Image.BICUBIC)


def planet(size: int, rng: random.Random) -> Image.Image:
    """A ringed planet on transparent black: a lit sphere, a terminator, a bright rim, and a ring in front and behind."""
    scale = 4  # drawn large and downsampled, so the curve and the ring's edge are clean
    w = h = size * scale
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cx, cy = w * 0.5, h * 0.52
    radius = w * 0.30

    # The ring, behind the sphere: an ellipse cut in half, drawn first.
    ring_box = (cx - radius * 1.95, cy - radius * 0.62, cx + radius * 1.95, cy + radius * 0.62)
    draw.ellipse(ring_box, outline=(150, 190, 255, 90), width=max(2, int(radius * 0.055)))
    draw.ellipse(
        (ring_box[0] + radius * 0.16, ring_box[1] + radius * 0.06, ring_box[2] - radius * 0.16, ring_box[3] - radius * 0.06),
        outline=(96, 140, 220, 60),
        width=max(1, int(radius * 0.03)),
    )

    # The sphere: a vertical ramp masked by a circle, then a radial shade for the terminator.
    body = gradient(int(radius * 2), int(radius * 2), (92, 176, 255), (18, 32, 88))
    # The light comes from the upper left: the ramp's centre is offset that way, so the lower right falls into night.
    shade = radial(int(radius * 2))
    shade = ImageChops.offset(shade, -int(radius * 0.22), -int(radius * 0.20))
    body = ImageChops.multiply(body, Image.merge("RGB", (shade, shade, shade)))

    moon = Image.new("L", (int(radius * 2), int(radius * 2)), 0)
    ImageDraw.Draw(moon).ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
    image.paste(body, (int(cx - radius), int(cy - radius)), moon)
    # A cloud band or two, clipped to the sphere.
    bands = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(bands)
    for i in range(5):
        y = cy - radius * 0.55 + i * radius * 0.28 + rng.uniform(-6, 6)
        band_draw.ellipse(
            (cx - radius * 1.02, y - radius * 0.06, cx + radius * 1.02, y + radius * 0.06),
            fill=(210, 235, 255, rng.randint(26, 60)),
        )
    bands = bands.filter(ImageFilter.GaussianBlur(radius / 22))
    image = Image.alpha_composite(image, bands)

    # The rim: the sun catching the sphere's edge, one side only.
    rim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_draw.arc(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        start=196,
        end=340,
        fill=(*SUN, 170),
        width=max(2, int(radius * 0.035)),
    )
    image = Image.alpha_composite(image, rim.filter(ImageFilter.GaussianBlur(radius / 90)))

    # The ring's near half, over the sphere.
    front = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    front_draw = ImageDraw.Draw(front)
    front_draw.arc(ring_box, start=-8, end=188, fill=(186, 214, 255, 120), width=max(2, int(radius * 0.055)))
    image = Image.alpha_composite(image, front)

    return image.resize((size, size), Image.LANCZOS)


def tracked(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, face: ImageFont.FreeTypeFont,
            fill: tuple, tracking: float) -> float:
    """Draws `text` with letter spacing and returns the width it took."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=face, fill=fill)
        x += draw.textlength(ch, font=face) + tracking
    return x - xy[0] - tracking


def glow(image: Image.Image, mask: Image.Image, colour: tuple, radius: int, strength: float = 1.0) -> Image.Image:
    """Adds `colour` through `mask`, blurred, as light rather than paint."""
    spread = mask.point(lambda v: min(255, int(v * strength)))
    spread = ImageChops.multiply(Image.merge("RGB", (spread, spread, spread)),
                                 Image.new("RGB", image.size, colour))
    return ImageChops.add(image, spread.filter(ImageFilter.GaussianBlur(radius)).convert(image.mode))


def cover(width: int = 1200, height: int = 1536) -> Image.Image:
    """The case's front: the field and its planet behind, a band of night at the top for the wordmark, a footer band."""
    rng = random.Random(SEED)
    art = nebula_field(width, height, rng).convert("RGBA")

    size = int(width * 0.70)
    body = planet(size, rng)
    art.alpha_composite(body, (int(width * 0.30), int(height * 0.42)))

    def band(top: float, bottom: float, alpha: int) -> None:
        """A flat rectangle of DEEP, so type sits on night rather than on noise."""
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle((0, int(height * top), width, int(height * bottom)),
                                        fill=(*DEEP, alpha))
        nonlocal art
        art = Image.alpha_composite(art, layer)

    band(0.0, 0.345, 236)
    band(0.885, 1.0, 216)

    draw = ImageDraw.Draw(art)
    # The rule under the header band, and over the footer one: the only geometry in the picture.
    draw.line(((0, height * 0.345), (width, height * 0.345)), fill=(70, 120, 210), width=2)
    draw.line(((0, height * 0.885), (width, height * 0.885)), fill=(58, 96, 170), width=2)

    title = font(int(width * 0.150))
    numeral = font(int(width * 0.150))
    sub = font(int(width * 0.036))
    small = font(int(width * 0.022))
    tracking = width * 0.014

    # GALAXY 360, one line, the numeral in the sun's gold.
    word_w = tracked(draw, (0, 0), "GALAXY", title, (255, 255, 255), tracking=tracking)
    num_w = tracked(draw, (0, 0), "360", numeral, SUN, tracking=tracking)
    gap = width * 0.020
    x = (width - (word_w + gap + num_w)) / 2
    y = height * 0.105
    mark = Image.new("L", (width, height), 0)
    tracked(ImageDraw.Draw(mark), (x, y), "GALAXY", title, 255, tracking=tracking)
    tracked(ImageDraw.Draw(mark), (x + word_w + gap, y), "360", numeral, 255, tracking=tracking)
    art = glow(art, mark, (64, 120, 240), int(width * 0.018), 1.0).convert("RGBA")
    draw = ImageDraw.Draw(art)
    tracked(draw, (x, y), "GALAXY", title, (255, 255, 255), tracking=tracking)
    tracked(draw, (x + word_w + gap, y), "360", numeral, SUN, tracking=tracking)

    line = "A NATIVE XBOX 360 PORT"
    taken = tracked(draw, (0, 0), line, sub, (190, 212, 255), tracking=width * 0.008)
    tracked(draw, ((width - taken) / 2, y + title.size * 1.30), line, sub, (190, 212, 255), tracking=width * 0.008)

    foot = "XENON  ·  1280×720  ·  60 HZ  ·  RGH / JTAG"
    taken = tracked(draw, (0, 0), foot, small, (150, 176, 220), tracking=width * 0.005)
    tracked(draw, ((width - taken) / 2, height * 0.937), foot, small, (150, 176, 220), tracking=width * 0.005)
    return art.convert("RGB")


def banner(width: int = 1920, height: int = 480) -> Image.Image:
    rng = random.Random(SEED + 1)
    art = nebula_field(width, height, rng).convert("RGBA")
    body = planet(int(height * 1.15), rng)
    art.alpha_composite(body, (int(width * 0.66), int(-height * 0.26)))

    draw = ImageDraw.Draw(art)
    title = font(int(height * 0.34))
    sub = font(int(height * 0.085))
    x = width * 0.06
    x += tracked(draw, (x, height * 0.20), "GALAXY", title, (255, 255, 255), tracking=height * 0.012) + height * 0.05
    tracked(draw, (x, height * 0.20), "360", title, SUN, tracking=height * 0.012)
    tracked(draw, (width * 0.062, height * 0.66), "A NATIVE XBOX 360 PORT  ·  RGH / JTAG", sub, (198, 218, 255),
            tracking=height * 0.004)
    return art.convert("RGB")


def icon(size: int = 512) -> Image.Image:
    rng = random.Random(SEED + 2)
    art = nebula_field(size, size, rng).convert("RGBA")
    body = planet(int(size * 0.98), rng)
    art.alpha_composite(body, (int(size * 0.01), int(size * 0.01)))
    return art.convert("RGB")


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    cover().save(ROOT / "cover.png", optimize=True)
    banner().save(ROOT / "banner.png", optimize=True)
    icon().save(ROOT / "icon.png", optimize=True)
    for name in ("cover.png", "banner.png", "icon.png"):
        print(f"{name}: {(ROOT / name).stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
