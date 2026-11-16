"""Rotate the normalized base still, never a repeatedly encoded derivative."""
import io
from PIL import Image


def rotate_still(base, quarter_turns):
    turns = quarter_turns % 4
    if not turns:
        return base
    with Image.open(io.BytesIO(base)) as image:
        operation = {1: Image.Transpose.ROTATE_270, 2: Image.Transpose.ROTATE_180, 3: Image.Transpose.ROTATE_90}[turns]
        rotated = image.transpose(operation).convert('RGB')
        output = io.BytesIO()
        rotated.save(output, 'JPEG', quality=85)
        return output.getvalue()
