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
    """Generates a dictionary card mapped to specific coordinate constraints."""
    try:
        logger.info(f"Compiling card for '{word}'")

        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Template not found at {TEMPLATE_PATH}")
        
        # 1. Load Template in RGB mode to ensure vivid color fidelity
        img = Image.open(TEMPLATE_PATH).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 2. Load Fonts with sizes tuned to your layout
        try:
            font_title = ImageFont.truetype(str(FONT_TITLE_PATH), 70)
            font_body = ImageFont.truetype(str(FONT_BODY_PATH), 30)
            font_meta = ImageFont.truetype(str(FONT_META_PATH), 22)
            font_intro = ImageFont.truetype(str(FONT_BODY_PATH), 22)
        except Exception:
            font_title = font_body = font_meta = font_intro = ImageFont.load_default()

        # 3. PRECISE PLACEMENT MAPPING
        
        # A. Intro sub-header (Top box)
        intro_text = "today's word entry is..."
        i_w = draw.textlength(intro_text, font=font_intro)
        draw.text(((img.width - i_w) / 2, 335), intro_text, fill="#ffffff", font=font_intro)

        # B. Main Featured Word (Word entry space)
        word_text = f"“{word.upper()}”"
        w_w = draw.textlength(word_text, font=font_title)
        draw.text(((img.width - w_w) / 2, 420), word_text, fill="#ffffff", font=font_title)

        # C. User metadata (Middle stripe)
        draw.text((370, 595), "Posted by:", fill="#ffffff", font=font_meta)
        draw.text((495, 595), posted_by, fill="#ffffff", font=font_meta)

        # D. Definition Area (Left-bottom box, width-constrained)
        wrapped_def = textwrap.wrap(definition, width=35)
        d_y = 690 
        for line in wrapped_def:
            draw.text((60, d_y), line, fill="#d1d1d1", font=font_body)
            d_y += 45

        # E. Mascot Placement (Bottom-right box)
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_mascot = Image.open(cat_path).convert("RGBA")
            cat_mascot.thumbnail((250, 250)) 
            img.paste(cat_mascot, (680, 680), cat_mascot)

        # 4. Save with high-quality settings
        filename = f"{uuid.uuid4()}.png"
        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", quality=100)
        
        return filename

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        raise e
