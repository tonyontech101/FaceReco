"""
One-off backfill script.

For every image already stored in the database this script:
  1. Computes the dominant color of the image file (human name + hex).
  2. Writes a rich 4-5 sentence description that references that color.

It uses ExcelImageStore.update_image(), so embeddings and other fields are
left untouched. Safe to re-run (it simply recomputes and overwrites the
description and color).
"""

import os
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from PIL import Image

from image_storage import ExcelImageStore

DATABASE_PATH = os.path.join(ROOT_DIR, "data", "image_database.xlsx")
IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")


# Named color palette (name -> RGB). Used to label the dominant color.
NAMED_COLORS = [
    ("Black", (20, 20, 20)),
    ("Dark gray", (80, 80, 80)),
    ("Gray", (128, 128, 128)),
    ("Silver", (190, 190, 190)),
    ("White", (240, 240, 240)),
    ("Cream", (235, 225, 200)),
    ("Beige", (214, 197, 160)),
    ("Brown", (120, 75, 40)),
    ("Golden brown", (181, 121, 58)),
    ("Tan", (196, 154, 108)),
    ("Red", (190, 45, 45)),
    ("Orange", (220, 130, 40)),
    ("Yellow", (225, 200, 70)),
    ("Green", (70, 140, 70)),
    ("Teal", (45, 120, 120)),
    ("Blue", (55, 90, 175)),
    ("Navy", (35, 45, 90)),
    ("Purple", (110, 70, 150)),
    ("Pink", (215, 150, 170)),
]


def nearest_color_name(rgb):
    """Return (name, hex) of the nearest named color to the given RGB tuple."""
    r, g, b = rgb
    best_name = None
    best_dist = None
    for name, (cr, cg, cb) in NAMED_COLORS:
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_name = name
    hex_code = "#{:02x}{:02x}{:02x}".format(r, g, b)
    return best_name, hex_code


def _is_background(rgb):
    """Near-white or near-black pixels are treated as background."""
    r, g, b = rgb
    brightness = (r + g + b) / 3
    return brightness < 40 or brightness > 218


def _saturation(rgb):
    r, g, b = rgb
    return max(r, g, b) - min(r, g, b)


def dominant_color(file_path):
    """
    Compute the dominant *subject* color of an image.

    Crops to the central region (where the subject usually is), quantizes to a
    small palette, and picks the most prominent color that is not plain
    white/black background. Falls back to the overall most common color if
    everything looks like background.
    """
    with Image.open(file_path) as img:
        img = img.convert("RGB")

        # Center-crop to ~60% to bias toward the subject, not the backdrop
        w, h = img.size
        cw, ch = int(w * 0.6), int(h * 0.6)
        left = (w - cw) // 2
        top = (h - ch) // 2
        img = img.crop((left, top, left + cw, top + ch))
        img = img.resize((80, 80))

        quantized = img.quantize(colors=8, method=Image.MEDIANCUT)
        palette = quantized.getpalette()
        color_counts = Counter(quantized.getdata())

        candidates = []
        for idx, count in color_counts.items():
            base = idx * 3
            rgb = (palette[base], palette[base + 1], palette[base + 2])
            candidates.append((count, rgb))

        candidates.sort(reverse=True, key=lambda c: c[0])

        # Foreground candidates = not background
        foreground = [(count, rgb) for count, rgb in candidates if not _is_background(rgb)]

        if foreground:
            # Score by prominence, giving saturated colors a boost so a vivid
            # subject wins over a large muted patch.
            foreground.sort(
                key=lambda c: c[0] * (1 + _saturation(c[1]) / 128.0),
                reverse=True,
            )
            return foreground[0][1]

        # Everything is background-like: return the most common color as-is
        return candidates[0][1]


def canonical_object(object_name, filename):
    """Map raw/odd object names to a canonical object key."""
    name = (object_name or "").lower()
    fname = (filename or "").lower()
    text = name + " " + fname

    if "banana" in text:
        return "banana"
    if "watch" in text:
        return "watch"
    if "wallet" in text:
        return "wallet"
    if "dog" in text or "golden" in text or "retriever" in text or "puppy" in text:
        return "dog"
    if "ballpen" in text or "balpen" in text or "pen" in text:
        return "ballpen"
    # Person names (single-name portrait files)
    person_names = {"chris", "daniel", "james", "robin"}
    if name in person_names or os.path.splitext(fname)[0] in person_names:
        return "person"
    return "generic"


def build_description(canonical, color_name, display_name):
    """Return a 4-5 sentence description that references the dominant color."""
    cl = color_name.lower()

    if canonical == "dog":
        return (
            f"This image shows a dog, one of the most loyal and beloved domestic "
            f"companions in the world. Its coat carries a predominantly {cl} tone "
            f"that gives the animal a warm, recognizable appearance. Dogs are prized "
            f"for their intelligence, affectionate nature, and remarkably keen senses "
            f"of smell and hearing. This particular photo captures the pet in a "
            f"natural, candid pose. Within the local database it is filed under the "
            f"Animal category."
        )
    if canonical == "banana":
        return (
            f"This image shows a banana, a soft and energy-rich tropical fruit enjoyed "
            f"across the globe. Its skin displays a mostly {cl} shade that signals its "
            f"ripeness and freshness. Bananas are an excellent natural source of "
            f"potassium, dietary fiber, and quick-release carbohydrates. The curved "
            f"shape and smooth peel make it one of the most instantly recognizable "
            f"fruits. It is stored under the Food category in the local database."
        )
    if canonical == "watch":
        return (
            f"This image shows a wristwatch, a timepiece that blends everyday utility "
            f"with personal style. The piece is dominated by a {cl} finish that lends "
            f"it a distinctive, polished character. Watches are worn on the wrist and "
            f"have long served as both practical instruments and fashion accessories. "
            f"Fine details such as the dial, hands, and band all contribute to its "
            f"overall look. It belongs to the Accessory category in the local database."
        )
    if canonical == "ballpen":
        return (
            f"This image shows a ballpen, a dependable everyday writing instrument "
            f"found in homes, schools, and offices. Its body is mainly {cl}, giving it "
            f"a clean and familiar look. Ballpens use a small rotating ball at the tip "
            f"to deliver a steady, smudge-resistant flow of ink. They are valued for "
            f"being affordable, portable, and reliable for daily note-taking. In the "
            f"local database it is categorized under Stationery."
        )
    if canonical == "wallet":
        return (
            f"This image shows a wallet, a compact personal accessory used to carry "
            f"cash, cards, and identification. Its exterior features a predominantly "
            f"{cl} finish that reflects a classic, refined style. Wallets are "
            f"crafted from leather, synthetic, or fabric materials and come in bifold, "
            f"trifold, and cardholder designs. This particular piece combines "
            f"practicality with everyday elegance. It is filed under the Accessory "
            f"category in the local database."
        )
    if canonical == "person":
        return (
            f"This image is a portrait photograph of a person named "
            f"{display_name}. The image is dominated by {cl} tones that set the "
            f"mood of the shot. Portrait photos like this capture the likeness, "
            f"expression, and personality of the subject. The composition focuses "
            f"on the upper body and face, allowing clear visual identification. "
            f"It is stored under the Person category in the local database."
        )

    return (
        f"This image shows {display_name.lower()}, an object stored in the local image "
        f"database. Its appearance is dominated by a {cl} tone that helps distinguish "
        f"it visually. The item was added so it can be recognized and matched against "
        f"future uploads. Its color, shape, and texture together form the visual "
        f"signature used during identification. It is kept for reference within the "
        f"local collection."
    )


def main():
    store = ExcelImageStore(DATABASE_PATH)
    images = store.get_all_images()

    if not images:
        print("No images found in the database.")
        return

    print(f"Backfilling {len(images)} images...\n")

    for i, img in enumerate(images, 1):
        filename = img.get("filename")
        object_name = img.get("object_name") or "Item"
        file_path = os.path.join(IMAGES_DIR, filename)

        if not os.path.exists(file_path):
            # File missing on disk: still write a color-agnostic description so
            # the record isn't left blank. Leave the color field untouched.
            canonical = canonical_object(object_name, filename)
            description = build_description(canonical, "natural", object_name)
            store.update_image(image_id=img["image_id"], description=description)
            print(f"[{i}/{len(images)}] {filename}: description only (file missing)")
            continue

        try:
            rgb = dominant_color(file_path)
            color_name, hex_code = nearest_color_name(rgb)
            color_value = f"{color_name} {hex_code}"

            canonical = canonical_object(object_name, filename)
            description = build_description(canonical, color_name, object_name)

            store.update_image(
                image_id=img["image_id"],
                description=description,
                color=color_value,
            )
            print(f"[{i}/{len(images)}] {filename}: color={color_value}")
        except Exception as e:
            print(f"[{i}/{len(images)}] ERROR {filename}: {e}")

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
