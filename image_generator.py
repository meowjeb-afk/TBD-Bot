"""Generate TBD dictionary card images locally using Python Pillow. Fully free, no API keys needed."""
import logging
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
GENERATED_DIR = ROOT_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Generates a TBD-style dictionary card image completely locally."""
    try:
        logger.info(f"Generating card locally for word: {word}")
        
        # 1. Create canvas with your exact theme color: Dark Purple (#1a0f2e)
        # 600x600 pixels square layout
        img = Image.new("RGB", (600, 600), color="#1a0f2e")
        draw = ImageDraw.Draw(img)
        
        # 2. Try loading fonts, gracefully falling back to defaults if not installed on system
        try:
            font_title = ImageFont.truetype("arial.ttf", 40)
            font_body = ImageFont.truetype("arial.ttf", 22)
            font_meta = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            logger.warning("Preferred fonts not found, falling back to system defaults.")
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
            font_meta = ImageFont.load_default()
            
        # 3. Draw TBD Header Banner Layout
        # Lighter purple top header background bar
        draw.rectangle([(0, 0), (600, 80)], fill="#2d1b4e")
        draw.text((30, 25), "🔮 Trauma Beanies Dictionary (TBD)", fill="#fff", font=font_meta)
        
        # 4. Draw Content Elements
        draw.text((40, 110), "today's word entry is...", fill="#9d8bbd", font=font_meta)
        
        # Featured Word in massive white text
        draw.text((40, 140), f'"{word.upper()}"', fill="#ffffff", font=font_title)
        
        # (n.) Grammatical marker at the right
        draw.text((520, 155), "(n.)", fill="#9d8bbd", font=font_body)
        
        # Decorative squiggly separator line
        draw.line([(40, 210), (560, 210)], fill="#4e3180", width=3)
        
        # 5. Wrap and draw the Definition text cleanly
        max_chars = 45
        wrapped_lines = [definition[i:i+max_chars] for i in range(0, len(definition), max_chars)]
        
        y_offset = 240
        for line in wrapped_lines[:8]: # Cap lines to ensure it fits perfectly
            draw.text((40, y_offset), line.strip(), fill="#d1c4e9", font=font_body)
            y_offset += 32
            
        # 6. Draw Footer UI Badges (Pill Badges)
        # Posted By pill container
        draw.rounded_rectangle([(40, 520), (240, 560)], radius=10, fill="#2d1b4e")
        draw.text((55, 530), f"👤 {posted_by}", fill="#fff", font=font_meta)
        
        # Uppies / Vote pill container on the right
        draw.rounded_rectangle([(440, 520), (560, 560)], radius=10, fill="#4e3180")
        draw.text((460, 530), "🔺 Uppies", fill="#fff", font=font_meta)

        # 7. Save output file
        file_name = f"{uuid.uuid4().hex}.png"
        out_path = GENERATED_DIR / file_name
        img.save(out_path)
        
        logger.info(f"Successfully generated local asset card: {file_name}")
        return file_name

    except Exception as e:
        logger.error(f"Local drawing engine error: {e}", exc_info=True)
        raise e
