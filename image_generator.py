"""Generate TBD dictionary card images by overlaying dynamic text and cycling mascot assets onto a template."""
import logging
import textwrap
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

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

TOTAL_CAT_MASCOTS = 18

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Generates a high-quality dictionary card with wrapped definition and mascot."""
    try:
        logger.info(f"Compiling card for '{word}'")

        # 1. Load Template and convert to RGB (Ensures colors are vivid and not washed out)
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Template not found at {TEMPLATE_PATH}")
        
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 2. Load Fonts
        try:
            # Adjust these sizes to fit your specific template dimensions
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 70)
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 30)
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 22)
        except Exception:
            font_title = font_body = font_meta = ImageFont.load_default()

        # 3. Draw Main Word (Centered)
        # Using double quotes for the f-string to correctly handle curly quotes
        word_text = f"“{word.upper()}”"
        w_w = draw.textlength(word_text, font=font_title)
        draw.text(((img.width - w_w) / 2, 100), word_text, fill="#FFFFFF", font=font_title)

        # 4. Draw Definition (Wrapped, Left-aligned)
        # Wrapping to ~40 characters per line
        wrapped_lines = textwrap.wrap(definition, width=45)
        y_text = 220
        for line in wrapped_lines:
            draw.text((60, y_text), line, fill="#D1D1D1", font=font_body)
            y_text += 40

        # 5. Draw "Posted by" (Bottom)
        draw.text((60, 500), f"Posted by: {posted_by}", fill="#888888", font=font_meta)

        # 6. Paste Mascot (Optional)
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            # Paste with mask to maintain transparency
            img.paste(cat_mascot, (400, 300), cat_mascot)

        # 7. Save result
        filename = f"{uuid.uuid4()}.png"
        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", quality=100)
        
        return filename

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        raise e
