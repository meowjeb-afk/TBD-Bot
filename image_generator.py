"""Generate TBD dictionary card images using official Google GenAI."""
import os
import base64
import logging
import uuid
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
REFERENCE_IMAGE = ROOT_DIR / "assets" / "reference_card.png"
GENERATED_DIR = ROOT_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Cat poses cycle to vary the mascot
CAT_POSES = [
    "lying on its back with paws up in the air, big yellow-green eyes, tongue sticking out, playful",
    "sitting upright looking curious, head tilted, big yellow-green eyes wide open",
    "curled up sleeping peacefully with eyes closed and a tiny smile",
    "stretching with front paws extended forward, butt up in the air, yawning",
    "pouncing/leaping with paws extended, mischievous grin and wide eyes",
    "standing on hind legs reaching upward with curious expression",
]

async def generate_card_image(word: str, definition: str, posted_by: str, pose_index: int = 0) -> str:
    """Generate a TBD-style dictionary card image using official Gemini API."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    # Initialize official Google GenAI Client
    client = genai.Client(api_key=api_key)

    pose = CAT_POSES[pose_index % len(CAT_POSES)]
    
    if not REFERENCE_IMAGE.exists():
        raise FileNotFoundError(f"Missing reference image at {REFERENCE_IMAGE}")

    # Load reference image bytes for Gemini
    with open(REFERENCE_IMAGE, "rb") as f:
        image_bytes = f.read()

    prompt = f"""Create a square dictionary card image in the EXACT same style as the reference image provided.

Match ALL of these visual elements from the reference:
- Dark purple background (#1a0f2e) with subtle paw-print pattern
- Top header section: lighter purple wave shape with the gradient bubble 'TBD' logo (Trauma Beanies Dictionary), surrounded by sparkles, a ball of yarn on the left and a fish bone on the right
- 'today's word entry is...' small italic text below the header
- The featured word in HUGE white handwritten/marker font in quotation marks (centered)
- A 'Posted by:' pill badge with the username inside
- '(n.)' grammatical marker at right
- A decorative squiggly cat-tail line separator
- The definition text below in cute soft purple/lavender color
- An 'Uppies' upvote pill button with an up arrow, and a small share/arrow circle button at the bottom-left
- A purple cat mascot illustration in the bottom-right corner with big yellow-green eyes

REPLACE the text content with:
- Featured word: "{word.upper()}"
- Posted by username: "{posted_by}"
- Definition: "{definition}"

For the cat mascot in the bottom-right, draw it in this pose: {pose}. Keep the cat the same purple color and same art style (big yellow-green eyes, cute round face) as the reference.

Keep everything else (layout, colors, fonts, decorations, paw pattern, header bubble logo) IDENTICAL to the reference image. Square aspect ratio."""

    # Using standard multimodality passing an image and text
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
            prompt
        ]
    )

    # Check if we received an image block back from the multimodal generation
    # Note: If the API model requires image output generation structure, 
    # it normally provides the file bytes directly inside the response parts.
    try:
        # Standard processing if returning generated data strings or files
        if response.candidates and response.candidates[0].content.parts:
            # Look for returning inline image parts if the preview model generates files directly
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    generated_bytes = part.inline_data.data
                    break
            else:
                # If it didn't find inline data, check if the response contains text fallback descriptions
                raise RuntimeError(f"Gemini responded with text instead of drawing an image: {response.text[:200]}")
        else:
            raise RuntimeError("No generation parts returned from Gemini.")
    except Exception as e:
        logger.error(f"Image extract failed: {e}")
        raise e

    file_name = f"{uuid.uuid4().hex}.png"
    out_path = GENERATED_DIR / file_name
    with open(out_path, "wb") as f:
        f.write(generated_bytes)
        
    logger.info(f"Saved generated card image: {file_name} ({len(generated_bytes)} bytes)")
    return file_name
