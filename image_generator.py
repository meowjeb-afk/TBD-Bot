"""Generate TBD dictionary card images by overlaying dynamic text and cycling mascot assets onto a template."""
import logging
import textwrap
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
TEMPLATE_PATH = ROOT_DIR / "assets" / "card_template.png"
ASSETS_DIR = ROOT_DIR / "assets"
GENERATED_DIR = ROOT_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Total number of unique cat images you have in your assets folder
TOTAL_CAT_MASCOTS = 11 

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Overlays custom text and cycles transparent cat mascots onto the template."""
    try:
        logger.info(f"Compiling card for '{word}' using mascot variant {pose_index}")
        
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Missing background template asset at {TEMPLATE_PATH}")

        # 1. Open the blank base template
        img = Image.open(TEMPLATE_PATH).convert("RGBA")
        
        # 2. Dynamically paste the selected cat mascot in the bottom right
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        
        if cat_path.exists():
            # Open the mascot and ensure it keeps its transparency layer intact
            cat_mascot = Image.open(cat_path).convert("RGBA")
            
            # --- MASCOT POSITIONING ---
            cat_x = img.width - cat_mascot.width - 40
            cat_y = img.height - cat_mascot.height - 40
            
            img.alpha_composite(cat_mascot, dest=(cat_x, cat_y))
            logger.info(f"Successfully pasted cat_{cat_num}.png onto layout")
        else:
            logger.warning(f"Mascot asset file not found at {cat_path}, skipping cat layer.")

        # Convert back to RGB so we can draw sharp text and save cleanly
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # 3. Configure text styling
        try:
            # Swap "arialbd.ttf" for a custom asset font if preferred
            font_title = ImageFont.truetype("arialbd.ttf", 52) 
            font_body = ImageFont.truetype("arial.ttf", 24)
            font_meta = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            logger.warning("System fonts failed to load, falling back to basic defaults.")
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
            font_meta = ImageFont.load_default()
            
        # 4. Burn the Text Elements onto the template
        
        # Center the Featured Word horizontally in quotation marks
        word_text = f'"{word.upper()}"'
        w_width = draw.textlength(word_text, font=font_title)
        word_x = (img.width - w_width) // 2
        draw.text((word_x, 420), word_text, fill="#ffffff", font=font_title)
        
        # Draw username directly onto the 'Posted by:' badge field
        draw.text((510, 605), posted_by, fill="#d1c4e9", font=font_meta)
        
        # Wrap and center the definition text block using textwrap
        # width=40 acts as a maximum character threshold per line safely
        lines = textwrap.wrap(definition, width=40)
            
        # Print the lines of definition down the middle section
        y_offset = 700
        for line in lines[:4]:  # Caps rendering to max 4 lines to prevent overflow
            line_w = draw.textlength(line, font=font_body)
            line_x = (img.width - line_w) // 2
            draw.text((line_x, y_offset), line, fill="#b3a2d6", font=font_body)
            y_offset += 36

        # 5. Save out the completed masterpiece
        file_name = f"{uuid.uuid4().hex}.png"
        out_path = GENERATED_DIR / file_name
        img.save(out_path)
        
        return file_name

    except Exception as e:
        logger.error(f"Template system crashed: {e}", exc_info=True)
        raise e
