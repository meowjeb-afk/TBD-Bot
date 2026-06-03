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

FONT_TITLE_PATH = ASSETS_DIR / "title_font.ttf"
FONT_BODY_PATH = ASSETS_DIR / "body_font.ttf"
FONT_META_PATH = ASSETS_DIR / "meta_font.ttf"
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
    """Draws text character-by-character, swinging to fallback fonts for Unicode styles."""
    x, y = position
    for char in text:
        if has_glyph(primary_path, char) or not FONT_FALLBACK_PATH.exists():
            current_font = primary_font
        else:
            current_font = fallback_font
            
        draw.text((x, y), char, fill=fill, font=current_font)
        x += draw.textlength(char, font=current_font)

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Overlays custom text and cycles transparent cat mascots onto the template."""
    try:
        logger.info(f"Compiling card for '{word}' using mascot variant {pose_index}")
        
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Missing background template asset at {TEMPLATE_PATH}")

        # 1. Open template as RGBA to keep original digital color spaces accurate
        img_rgba = Image.open(TEMPLATE_PATH).convert("RGBA")
        
        # 2. Dynamically paste the selected cat mascot
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            # Anchor cat directly into the bottom-right corner safely
            cat_x = img_rgba.width - cat_mascot.width - 25
            cat_y = img_rgba.height - cat_mascot.height - 25
            img_rgba.alpha_composite(cat_mascot, dest=(cat_x, cat_y))

        # FIX COLOR SATURATION: Composite the RGBA canvas over an empty solid background 
        # instead of a raw destructive .convert("RGB") call.
        img = Image.new("RGB", img_rgba.size, (0, 0, 0))
        img.paste(img_rgba, (0, 0), img_rgba)
        
        draw = ImageDraw.Draw(img)
        
        # 3. Configure Fonts
        try:
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 52) 
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 28)  # Bumped up slightly for readability
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 22)  # Fits nicely in the pill badge
            font_fallback = ImageFont.truetype(str(FONT_FALLBACK_PATH), 22)
        except IOError:
            logger.warning("Fonts failed to load, falling back to basic defaults.")
            font_title = font_body = font_meta = font_fallback = ImageFont.load_default()
            
        # 4. Burn Text Elements (Corrected Coordinates)
        
        # Title Word - Placed cleanly in the open upper sector below the logo wave
        word_text = f'"{word.upper()}"'
        w_width = draw.textlength(word_text, font=font_title)
        word_x = (img.width - w_width) // 2
        draw.text((word_x, 320), word_text, fill="#ffffff", font=font_title)
        
        # Definition Block - Centered right in the primary dark container area
        lines = textwrap.wrap(definition, width=42)
        y_offset = 450
        for line in lines[:5]:
            line_w = draw.textlength(line, font=font_body)
            line_x = (img.width - line_w) // 2
            draw.text((line_x, y_offset), line, fill="#b3a2d6", font=font_body)
            y_offset += 40

        # Username - Placed perfectly inside the "Posted by:" layout capsule badge shape
        # X: 485 places it right next to the "Posted by:" inner text
        # Y: 602 centers it vertically within the bounds of that specific badge line
        draw_mixed_font_text(
            draw=draw, 
            position=(485, 602), 
            text=posted_by, 
            primary_font=font_meta, 
            primary_path=FONT_META_PATH, 
            fallback_font=font_fallback, 
            fill="#ffffff"
        )

        # 5. Save output
        file_name = f"{uuid.uuid4().hex}.png"
        out_path = GENERATED_DIR / file_name
        img.save(out_path)
        
        return file_name

    except Exception as e:
        logger.error(f"Template system crashed: {e}", exc_info=True)
        raise e
