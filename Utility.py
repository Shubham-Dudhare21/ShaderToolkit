from .Requirements import *

import bpy
import os
import re


# ----------------------------------------------------------
# TextureName_TextureType_Resolution
# Rule : the text befor first underscore is the texture name,
# the text after the first underscore (till the second underscore if present) is the texture type,
# if second underscore is present, text after it is the resolution.
# ----------------------------------------------------------
import os


def ParseTextureFilename(filepath):
    """
    Parses a texture filename using the format:
        TextureName_TextureType_Resolution.ext
    Rules:
        - Text before the first '_'      -> TextureName
        - Text after the first '_'       -> TextureType
        - Text after the second '_'      -> Resolution (optional)
    Examples:
        Brick_BC.png
        -> {
            "TextureName": "Brick",
            "TextureType": "BC",
            "Resolution": ""
        }
        Brick_BC_4K.png
        -> {
            "TextureName": "Brick",
            "TextureType": "BC",
            "Resolution": "4K"
        }
        Wood_Rough_8K.exr
        -> {
            "TextureName": "Wood",
            "TextureType": "Rough",
            "Resolution": "8K"
        }
    """

    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    parts = name.split("_")
    result = {
        "TextureName": "",
        "TextureType": "",
        "Resolution": "",
    }

    if len(parts) >= 1:
        result["TextureName"] = parts[0]

    if len(parts) >= 2:
        result["TextureType"] = parts[1]

    if len(parts) >= 3:
        result["Resolution"] = "_".join(parts[2:])

    return result