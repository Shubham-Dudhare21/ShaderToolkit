bl_info = {
    "name": "Shader Toolkit",
    "author": "RenderCode Studio",
    "version": (3, 0, 0),
    "blender": (5, 1, 0),
    "location": "Shader Editor",
    "description": "A collection of tools to speed up shader creation and management",
    "category": "Node",
}

# ----------------------------------------------------------
# Core Modules
# ----------------------------------------------------------

from . import Requirements
from . import Utility

# ----------------------------------------------------------
# Feature Modules
# Import the feature modules here to register them
# ----------------------------------------------------------

from . import F_MainMenu
from . import F_submenus

from . import F_CleanUp
from . import F_FixColorSpace
from . import F_GroupTextures
from . import F_NewTextureGroup
from . import F_NewPrincipledShaderGroup

# ----------------------------------------------------------
# Feature Module List
# Write the names of the feature modules in this list to register them
# ----------------------------------------------------------

modules = (
    F_MainMenu,
    F_submenus,
    F_CleanUp,
    F_FixColorSpace,
    F_GroupTextures,
    F_NewTextureGroup,
    F_NewPrincipledShaderGroup,
    
)

# ----------------------------------------------------------
# Register
# ----------------------------------------------------------

def register():
    for module in modules:
        module.register()

# ----------------------------------------------------------
# Unregister
# ----------------------------------------------------------

def unregister():
    for module in reversed(modules):
        module.unregister()

if __name__ == "__main__":
    register()