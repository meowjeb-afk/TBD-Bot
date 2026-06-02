"""Generate TBD dictionary card images by overlaying dynamic text and cycling mascot assets onto a template."""
import logging
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
TOTAL_CAT_MASCOTS = 16 

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
            # If your template is roughly 1000x1000 pixels:
            # This places the cat near the bottom right. You can adjust these coordinates 
            # (X, Y) slightly so your different cats sit perfectly on the card!
            cat_x = img.width - cat_mascot.width - 40
            cat_y = img.height - cat_mascot.height - 40
            
            img.alpha_composite(cat_mascot, dest=(cat_x, cat_y))
            logger.info(f"Successfully pasted {f'cat_{cat_num}.png'} onto layout")
        else:
            logger.warning(f"Mascot asset file not found at {cat_path}, skipping cat layer.")

        # Convert back to RGB so we can draw sharp text and save cleanly as a standard image
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # 3. Configure text styling
        try:
            # Pro-tip: If you put a cute handwritten .ttf font in assets, swap "arialbd.ttf" for it!
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
        # Adjust '420' up or down to align perfectly within your quotation area
        draw.text((word_x, 420), word_text, fill="#ffffff", font=font_title)
        
        # Draw username directly onto the 'Posted by:' badge field
        # Adjust '510, 605' to line up inside your custom badge shape
        draw.text((510, 605), posted_by, fill="#d1c4e9", font=font_meta)
        
        # Wrap and center the definition text block
        max_chars_per_line = 40
        words = definition.split()
        lines = []
        current_line = []
        
        for w in words:
            current_line.append(w)
            if len(" ".join(current_line)) > max_chars_per_line:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [w]
        if current_line:
            lines.append(" ".join(current_line))
            
        # Print the lines of definition down the middle section
        y_offset = 700
        for line in lines[:4]:
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
