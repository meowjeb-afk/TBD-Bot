"""Generate TBD dictionary card images by overlaying dynamic text and cycling mascot assets onto a template."""
import logging
import textwrap
import uuid
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

TOTAL_CAT_MASCOTS = 18

# Anchor Coordinates for 2048x1676 Template
ANCHOR_INTRO      = (1024, 300) 
ANCHOR_WORD       = (1024, 450) 
ANCHOR_USERNAME   = (650, 600)  
ANCHOR_DEFINITION = (120, 750)  
ANCHOR_CAT        = (1450, 750) 

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

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    try:
        logger.info(f"Compiling card for '{word}'")
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Scaled font sizes for high-res 2048px canvas
        try:
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 120)
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 50)
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 40)
            font_intro = ImageFont.truetype(str(FONT_BODY_PATH), 40)
            font_fallback = ImageFont.truetype(str(FONT_FALLBACK_PATH), 40)
        except Exception:
            font_title = font_body = font_meta = font_intro = font_fallback = ImageFont.load_default()

        # A. Intro (Centered)
        intro_text = "today's word entry is..."
        i_w = draw.textlength(intro_text, font=font_intro)
        draw.text((ANCHOR_INTRO[0] - (i_w / 2), ANCHOR_INTRO[1]), intro_text, fill="#ffffff", font=font_intro)

        # B. Main Word (Centered)
        word_text = f"“{word.upper()}”"
        w_w = draw.textlength(word_text, font=font_title)
        draw.text((ANCHOR_WORD[0] - (w_w / 2), ANCHOR_WORD[1]), word_text, fill="#ffffff", font=font_title)

        # C. Username (Clean, aligned to button)
        draw_mixed_font_text(draw, ANCHOR_USERNAME, posted_by, font_meta, FONT_META_PATH, font_fallback, fill="#ffffff")

        # D. Definition (Wrapped)
        wrapped_def = textwrap.wrap(definition, width=40)
        curr_y = ANCHOR_DEFINITION[1]
        for line in wrapped_def:
            draw.text((ANCHOR_DEFINITION[0], curr_y), line, fill="#d1d1d1", font=font_body)
            curr_y += 60

        # E. Mascot (Resized for high-res)
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            cat_mascot.thumbnail((400, 400))
            img.paste(cat_mascot, ANCHOR_CAT, cat_mascot)

        filename = f"{uuid.uuid4()}.png"
        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", quality=100)
        return filename

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        raise e
