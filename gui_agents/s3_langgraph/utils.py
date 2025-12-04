

import io
import pyautogui
from PIL.Image import Resampling
from io import BytesIO

MAX_DIM_SIZE = 2400 # UI-TRAS 最大分辨率

def scale_screen_dimensions(width: int, height: int, max_dim_size: int):
    scale_factor = min(max_dim_size / width, max_dim_size / height, 1)
    safe_width = int(width * scale_factor)
    safe_height = int(height * scale_factor)
    return safe_width, safe_height

def screenshot() -> BytesIO:
    """Take a screenshot of the current screen.

    Returns:
        bytes: The screenshot image in PNG format as BufferedReader.
    """
    shot = pyautogui.screenshot()
    scaled_width, scaled_height = scale_screen_dimensions(
        shot.width, shot.height, max_dim_size=MAX_DIM_SIZE
    )
    shot = shot.resize((scaled_width, scaled_height), Resampling.LANCZOS)
    buffered = io.BytesIO()
    shot.save(buffered, format="PNG")
    return buffered

if __name__ == "__main__":
    from PIL.Image import Image, open
    img = screenshot()
    Image.show(open(img))