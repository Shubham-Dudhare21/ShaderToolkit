import bpy
from bpy.types import Operator, Menu


# ----------------------------------------------------------
# Main Shader Toolkit Menu
# ----------------------------------------------------------

class SHADERTOOLKIT_MT_Menu(Menu):
    bl_label = "Shader Toolkit"
    bl_idname = "SHADERTOOLKIT_MT_Menu"

    def draw(self, context):
        layout = self.layout
        layout.menu("SHADERTOOLKIT_MT_Create", icon='ADD')
        layout.menu("SHADERTOOLKIT_MT_CleanUp", icon='FILE_BLEND')
        layout.menu("SHADERTOOLKIT_MT_Replace", icon='FILE_REFRESH')
        layout.menu("SHADERTOOLKIT_MT_FixColorSpace", icon='COLOR')   # <-- changed to valid icon


# ----------------------------------------------------------
# Append to the node editor Add menu (Shift+A)
# ----------------------------------------------------------

def draw_menu(self, context):
    self.layout.separator()
    self.layout.menu(SHADERTOOLKIT_MT_Menu.bl_idname, icon='NODETREE')

_menu_appended = False


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_MT_Menu,
)


def register():
    global _menu_appended
    for cls in classes:
        bpy.utils.register_class(cls)
    if not _menu_appended:
        bpy.types.NODE_MT_add.append(draw_menu)
        _menu_appended = True


def unregister():
    global _menu_appended
    if _menu_appended:
        bpy.types.NODE_MT_add.remove(draw_menu)
        _menu_appended = False
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)