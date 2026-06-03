"""Generate TBD dictionary card images by overlaying dynamic text onto a 2364x1773 template."""
import os
import base64
import asyncio
import logging
import textwrap
import uuid
import random
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
import httpx  # Ensure 'httpx' is in your requirements.txt!

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
ANCHOR_WORD       = (522, 726) 
ANCHOR_USERNAME   = (1105, 1514)  
ANCHOR_DEFINITION = (288, 1128) 
ANCHOR_CAT        = (1371, 741)

# Design Constants
PALE_PURPLE = "#DCD0FF"
DARK_PURPLE = "#2E1A47"  # Fill color for the word text
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

async def upload_to_github(local_file_path: Path) -> str | None:
    """Uploads a locally generated image directly to your GitHub repository."""
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    
    if not token or not repo:
        logger.warning("GitHub auto-archive skipped: GITHUB_TOKEN or GITHUB_REPO not configured on Render.")
        return None

    filename = local_file_path.name
    github_api_url = f"https://api.github.com/repos/{repo}/contents/generated_cards/{filename}"
    
    try:
        with open(local_file_path, "rb") as f:
            encoded_content = base64.b64encode(f.read()).decode("utf-8")
            
        payload = {
            "message": f"🤖 Bot Auto-Archive: Saved/Updated dictionary card {filename}",
            "content": encoded_content,
            "branch": "main"  
        }
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(github_api_url, json=payload, headers=headers)
            if response.status_code in [201, 200]:
                logger.info(f"✨ Successfully backed up {filename} to GitHub!")
                return response.json()["content"]["download_url"]
            else:
                logger.error(f"GitHub upload failed ({response.status_code}): {response.text}")
                return None
    except Exception as e:
        logger.error(f"Failed to push asset to GitHub: {e}", exc_info=True)
        return None

def _sync_draw_card(word: str, definition: str, posted_by: str, pose_index: int, filename: str) -> str:
    """Pure synchronous canvas operations shifted out of the main execution thread loop."""
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

    # Draw Word with Stroke (Centered at 1182px)
    word_text = f"“{word.upper()}”"
    w_w = draw.textlength(word_text, font=font_title)
    draw.text(
        (1182 - (w_w / 2), ANCHOR_WORD[1]), 
        word_text, 
        fill=DARK_PURPLE,        
        font=font_title, 
        stroke_width=6,          
        stroke_fill=PALE_PURPLE  
    )

    # Draw Username
    draw_mixed_font_text(
        draw, ANCHOR_USERNAME, posted_by, font_meta, FONT_META_PATH, font_fallback, fill=PALE_PURPLE
    )

    # Draw Definition
    wrapped_def = textwrap.wrap(definition, width=40)
    curr_y = ANCHOR_DEFINITION[1]
    for line in wrapped_def:
        draw.text((ANCHOR_DEFINITION[0], curr_y), line, fill=PALE_PURPLE, font=font_body)
        curr_y += 60

    # Mascot Layer
    cat_num = pose_index % TOTAL_CAT_MASCOTS
    cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
    if cat_path.exists():
        cat_mascot = Image.open(cat_path).convert("RGBA")
        img.paste(cat_mascot, ANCHOR_CAT, cat_mascot)

    # Optimized Fast Save
    output_path = GENERATED_DIR / filename
    img.save(output_path, "PNG", compress_level=1, optimize=False)
    return filename

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = None) -> tuple[str, str | None]:
    """Asynchronous wrapper that runs drawing work in a thread and pushes backups to GitHub."""
    try:
        random.seed(time.time())
        if pose_index is None:
            pose_index = random.randint(0, TOTAL_CAT_MASCOTS - 1)

        filename = f"{uuid.uuid4()}.png"
        output_path = GENERATED_DIR / filename

        # Offload blocking drawing work to thread pool
        await asyncio.to_thread(_sync_draw_card, word, definition, posted_by, pose_index, filename)
        
        # Trigger GitHub background upload execution
        github_url = await upload_to_github(output_path)
        
        # Returns BOTH paths so the bot can stream files locally and save the URL links
        return filename, github_url

    except Exception as e:
        logger.error(f"Image generation core routine failed: {e}", exc_info=True)
        raise e
