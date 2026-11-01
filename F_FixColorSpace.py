import bpy
from bpy.types import Operator, Menu

from . import Utility
from .Requirements import TEXTURE_TYPES


# ----------------------------------------------------------
# Helper: Recursively collect Image Texture nodes
# ----------------------------------------------------------

def get_image_textures(node_tree):
    """Return all TEX_IMAGE nodes from a node tree, recursing into groups."""
    images = []
    for node in node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            images.append(node)
        elif node.type == 'GROUP' and node.node_tree:
            images.extend(get_image_textures(node.node_tree))
    return images


# ----------------------------------------------------------
# Operator: Fix Color Space
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_FixColorSpace(Operator):
    """Set color space of selected Image Textures (and inside selected Groups) based on texture type in filename"""
    bl_idname = "shadertoolkit.fix_color_space"
    bl_label = "Fix Color Space"
    bl_description = "Automatically set correct color space for image textures (BC/AO → sRGB, others → Non‑Color)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            self.report({'WARNING'}, "No Shader Editor active")
            return {'CANCELLED'}

        node_tree = space.edit_tree
        if not node_tree:
            self.report({'WARNING'}, "No node tree in active editor")
            return {'CANCELLED'}

        selected = context.selected_nodes
        if not selected:
            self.report({'WARNING'}, "No nodes selected")
            return {'CANCELLED'}

        # Collect all image nodes (including those inside selected groups)
        image_nodes = []
        for node in selected:
            if node.type == 'TEX_IMAGE' and node.image:
                image_nodes.append(node)
            elif node.type == 'GROUP' and node.node_tree:
                image_nodes.extend(get_image_textures(node.node_tree))

        if not image_nodes:
            self.report({'INFO'}, "No Image Texture nodes found in selection")
            return {'CANCELLED'}

        fixed_count = 0
        for img_node in image_nodes:
            img = img_node.image
            if not img:
                continue

            # Use the image name (always set to the filename when loaded)
            img_name = img.name

            # Parse using the dictionary helper
            parsed = Utility.ParseTextureFilename(img_name)
            tex_type = parsed.get("TextureType", "").upper()

            # Debug: print to console
            print(f"[FixColorSpace] Image: {img_name}, parsed type: '{tex_type}'")

            # Determine target color space
            # Base Color (BC) and Ambient Occlusion (AO) → sRGB
            if tex_type in TEXTURE_TYPES and (tex_type == "BC" or tex_type == "AO"):
                target_cs = 'sRGB'
            else:
                target_cs = 'Non-Color'

            if img.colorspace_settings.name != target_cs:
                img.colorspace_settings.name = target_cs
                fixed_count += 1
                print(f"  -> changed to {target_cs}")
            else:
                print(f"  -> already {target_cs}")

        self.report({'INFO'}, f"Fixed color space for {fixed_count} image(s)")
        return {'FINISHED'}


# ----------------------------------------------------------
# Menu: Fix Color Space submenu
# ----------------------------------------------------------

class SHADERTOOLKIT_MT_FixColorSpace(Menu):
    bl_label = "Fix Color Space"
    bl_idname = "SHADERTOOLKIT_MT_FixColorSpace"

    def draw(self, context):
        layout = self.layout
        layout.operator(SHADERTOOLKIT_OT_FixColorSpace.bl_idname, icon='COLOR')


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_OT_FixColorSpace,
    SHADERTOOLKIT_MT_FixColorSpace,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)