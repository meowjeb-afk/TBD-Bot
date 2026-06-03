"""Generate TBD dictionary card images by overlaying dynamic text onto a 2364x1773 template."""
import logging
import textwrap
import uuid
import random
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

logger = logging.getLogger(__name__)

# Directory setup
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
TEMPLATE_PATH = ASSETS_DIR / "card_template.png"
GENERATED_DIR = ROOT_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Font Setup
FONT_TITLE_PATH = ASSETS_DIR / "title_font.ttf"
FONT_BODY_PATH = ASSETS_DIR / "body_font.ttf"
FONT_META_PATH = ASSETS_DIR / "meta_font.ttf"
FONT_FALLBACK_PATH = ASSETS_DIR / "notosans_fallback.ttf"

TOTAL_CAT_MASCOTS = 11

# Updated Coordinates for 2364x1773
# These anchors must be calibrated against your clean background template
ANCHOR_WORD       = (425, 694) 
ANCHOR_USERNAME   = (1105, 1514)  
ANCHOR_DEFINITION = (324, 1006) 
ANCHOR_CAT        = (1371, 741)

# Design Constants
PALE_PURPLE = "#DCD0FF"
TARGET_SIZE = (2364, 1773)

def has_glyph(font_path: Path, glyph: str) -> bool:
    try:
        font = TTFont(str(font_path))
        for table in font['cmap'].tables:
            if ord(glyph) in table.cmap:
                return True
        return False
    except Exception:
        return False

def draw_mixed_font_text(draw, position, text, primary_font, primary_path, fallback_font, fill):
    x, y = position
    for char in text:
        if has_glyph(primary_path, char) or not FONT_FALLBACK_PATH.exists():
            current_font = primary_font
        else:
            current_font = fallback_font
        draw.text((x, y), char, fill=fill, font=current_font)
        x += draw.textlength(char, font=current_font)

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = None) -> str:
    try:
        random.seed(time.time())
        if pose_index is None:
            pose_index = random.randint(0, TOTAL_CAT_MASCOTS - 1)

        # Load, convert, and force canvas resize
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        if img.size != TARGET_SIZE:
            img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
            
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 150)
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 50)
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 40)
            font_fallback = ImageFont.truetype(str(FONT_FALLBACK_PATH), 40)
        except Exception:
            font_title = font_body = font_meta = font_fallback = ImageFont.load_default()

        # 1. Draw Word (Centered horizontally at 1182px)
        word_text = f"“{word.upper()}”"
        w_w = draw.textlength(word_text, font=font_title)
        draw.text((1182 - (w_w / 2), ANCHOR_WORD[1]), word_text, fill=PALE_PURPLE, font=font_title)

        # 2. Draw Username (Label is now baked into the template, drawing only the name)
        draw_mixed_font_text(
            draw, ANCHOR_USERNAME, posted_by, font_meta, FONT_META_PATH, font_fallback, fill=PALE_PURPLE
        )

        # 3. Draw Definition
        wrapped_def = textwrap.wrap(definition, width=40)
        curr_y = ANCHOR_DEFINITION[1]
        for line in wrapped_def:
            draw.text((ANCHOR_DEFINITION[0], curr_y), line, fill=PALE_PURPLE, font=font_body)
            curr_y += 60

        # 4. Mascot
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            img.paste(cat_mascot, ANCHOR_CAT, cat_mascot)

        filename = f"{uuid.uuid4()}.png"
        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", optimize=True)
        
        return filename

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        raise e
