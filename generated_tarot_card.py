"""Script to render the visual concept of THE LEVEL 10 tarot card as a standalone image."""
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont

def generate_level_10_card(mascot_image_path: str, output_path: str):
    # 1. Canvas Setup (Tall 1000x1600 tarot ratio)
    canvas_size = (1000, 1600)
    img = Image.new("RGB", canvas_size, color="#0F091A") # Deep midnight gothic purple
    draw = ImageDraw.Draw(img)

    # 2. Intricate Double Borders matching the framing layout
    draw.rectangle([(30, 30), (970, 1570)], outline="#2E1A47", width=6)
    draw.rectangle([(45, 45), (955, 1555)], outline="#DCD0FF", width=3)

    # 3. Load Fonts (Falling back to default if your ttf assets aren't local)
    try:
        font_card_title = ImageFont.truetype("assets/title_font.ttf", 65)
        font_meaning = ImageFont.truetype("assets/body_font.ttf", 36)
    except IOError:
        print("Warning: Custom fonts not found. Using default fallback fonts.")
        font_card_title = font_meaning = ImageFont.load_default()

    # 4. Draw Header Title
    card_name = "THE LEVEL 10"
    title_w = draw.textlength(card_name, font=font_card_title)
    draw.text((500 - (title_w / 2), 90), card_name, fill="#DCD0FF", font=font_card_title)

    # 5. Draw Central Illustration Frame Box
    frame_box = [(150, 220), (850, 920)]
    draw.rectangle(frame_box, fill="#1A1126", outline="#2E1A47", width=4)

    # 6. Process and Center the Mascot Image (1000063046.png)
    mascot_path = Path(mascot_image_path)
    if mascot_path.exists():
        cat_img = Image.open(mascot_path).convert("RGBA")
        
        # Crop or resize the mascot to fit cleanly inside the 700x700 frame window
        # For a tarot frame, we'll scale it to fit nicely while maintaining aspect ratio
        cat_img.thumbnail((650, 650), Image.Resampling.LANCZOS)
        
        # Calculate centering offsets inside the frame coordinates
        frame_center_x = 500
        frame_center_y = 570 # Center of the 220 to 920 vertical block
        
        paste_x = frame_center_x - (cat_img.width // 2)
        paste_y = frame_center_y - (cat_img.height // 2)
        
        img.paste(cat_img, (paste_x, paste_y), cat_img)
    else:
        print(f"Error: Could not find the file '{mascot_image_path}'. Drawing placeholder text instead.")
        draw.text((400, 540), "[ Mascot Art Missing ]", fill="#4A3B63", font=font_meaning)

    # 7. Draw Divination Meaning Text Block (Bottom Third)
    meaning_text = (
        "Peak existence achieved. You have reached the absolute zenith of power, "
        "authority, and immaculate vibes. There are no higher levels; you are "
        "officially vibrating at max capacity. Walk through the server with your chest out!"
    )
    
    # Separation line accent
    draw.line([(200, 970), (800, 970)], fill="#2E1A47", width=2)
    
    wrapped_text = textwrap.wrap(meaning_text, width=38)
    curr_y = 1010
    
    for line in wrapped_text:
        line_w = draw.textlength(line, font=font_meaning)
        draw.text((500 - (line_w / 2), curr_y), line, fill="#EAE6FF", font=font_meaning)
        curr_y += 55

    # 8. Save the final image masterpiece
    img.save(output_path, "PNG", compress_level=1)
    print(f"Success! Your custom tarot card has been saved to: {output_path}")

if __name__ == "__main__":
    # Point this to wherever 1000063046.png is sitting on your computer
    generate_level_10_card("1000063046.png", "the_level_10_tarot.png")
