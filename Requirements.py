# ----------------------------------------------------------
# Addon Constants
# ----------------------------------------------------------

ADDON_NAME = "Shader Toolkit"

GROUP_NAME = "Texture Group"

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tga",
    ".tif",
    ".tiff",
    ".bmp",
    ".exr",
}

TEXTURE_TYPES = {
    "BC": "Base Color",
    "BASECOLOR": "Base Color",
    "ALBEDO": "Base Color",
    "D": "Base Color",
    "DIFFUSE": "Base Color",
    "COL": "Base Color",
    "aBC": "Base Color",

    "R": "Roughness",
    "ROUGHNESS": "Roughness",
    "ROUGH": "Roughness",

    "M": "Metallic",
    "METALLIC": "Metallic",
    "MET": "Metallic",

    "N": "Normal",
    "NORMAL": "Normal",
    "NRM": "Normal",
    "NOR": "Normal",

    "AO": "Ambient Occlusion",

    "H": "Height",
    "HEIGHT": "Height",
    "DISP": "Height",
    "DISPLACEMENT": "Height",

    "OP": "Opacity",
    "OPACITY": "Opacity",
    "ALPHA": "Opacity",

    "E": "Emission",
    "EMISSION": "Emission",
}

OUTPUT_ORDER = [
    "Opacity",
    "Base Color",
    "BC Alpha",
    "Ambient Occlusion",
    "Metallic",
    "Roughness",
    "Emission",
    "Normal",
    "Height",
]