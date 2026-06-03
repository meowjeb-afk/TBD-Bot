"""Generate TBD dictionary card images by overlaying dynamic text and cycling mascot assets onto a template."""
import logging
import textwrap
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
TEMPLATE_PATH = ASSETS_DIR / "card_template.png"
GENERATED_DIR = ROOT_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Define paths for your custom fonts
FONT_TITLE_PATH = ASSETS_DIR / "title_font.ttf"
FONT_BODY_PATH = ASSETS_DIR / "body_font.ttf"
FONT_META_PATH = ASSETS_DIR / "meta_font.ttf"

# Robust fallback font for crazy unicode characters/symbols (e.g., Google Noto Sans)
FONT_FALLBACK_PATH = ASSETS_DIR / "notosans_fallback.ttf" 

TOTAL_CAT_MASCOTS = 18 

def has_glyph(font_path: Path, glyph: str) -> bool:
    """Checks if a font file contains the rendering glyph for a specific character."""
    try:
        font = TTFont(str(font_path))
        for table in font['cmap'].tables:
            if ord(glyph) in table.cmap:
                return True
        return False
    except Exception:
        return False

def draw_mixed_font_text(draw, position, text, primary_font, primary_path, fallback_font, fill):
    """
    Draws text character-by-character. If the primary font lacks the character,
    it falls back to the robust unicode font automatically.
    """
    x, y = position
    for char in text:
        # Determine which font has the character
        if has_glyph(primary_path, char) or not FONT_FALLBACK_PATH.exists():
            current_font = primary_font
        else:
            current_font = fallback_font
            
        # Draw the single character
        draw.text((x, y), char, fill=fill, font=current_font)
        
        # Move the cursor forward by the width of that character
        x += draw.textlength(char, font=current_font)

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Overlays custom text and cycles transparent cat mascots onto the template."""
    try:
        logger.info(f"Compiling card for '{word}' using mascot variant {pose_index}")
        
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Missing background template asset at {TEMPLATE_PATH}")

        img = Image.open(TEMPLATE_PATH).convert("RGBA")
        
        # Mascot Setup
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            cat_x = img.width - cat_mascot.width - 40
            cat_y = img.height - cat_mascot.height - 40
            img.alpha_composite(cat_mascot, dest=(cat_x, cat_y))

        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Load Fonts
        try:
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 52) 
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 24)
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 20)
            
            # Load fallback font at the exact same size as the metadata font
            font_fallback = ImageFont.truetype(str(FONT_FALLBACK_PATH), 20)
        except IOError as e:
            logger.warning(f"Fonts failed to load ({e}), using defaults.")
            font_title = font_body = font_meta = font_fallback = ImageFont.load_default()
            
        # 1. Draw Title Word
        word_text = f'"{word.upper()}"'
        w_width = draw.textlength(word_text, font=font_title)
        word_x = (img.width - w_width) // 2
        draw.text((word_x, 420), word_text, fill="#ffffff", font=font_title)
        
        # 2. Draw Username (Using our new unicode-safe handler!)
        # Adjust (510, 605) to perfectly position the starting character inside your layout badge
        draw_mixed_font_text(
            draw=draw, 
            position=(510, 605), 
            text=posted_by, 
            primary_font=font_meta, 
            primary_path=FONT_META_PATH, 
            fallback_font=font_fallback, 
            fill="#d1c4e9"
        )
        
        # 3. Wrap and Draw Definition
        lines = textwrap.wrap(definition, width=40)
        y_offset = 700
        for line in lines[:4]:
            line_w = draw.textlength(line, font=font_body)
            line_x = (img.width - line_w) // 2
            draw.text((line_x, y_offset), line, fill="#b3a2d6", font=font_body)
            y_offset += 36

        file_name = f"{uuid.uuid4().hex}.png"
        out_path = GENERATED_DIR / file_name
        img.save(out_path)
        
        return file_name

    except Exception as e:
        logger.error(f"Template system crashed: {e}", exc_info=True)
        raise e
