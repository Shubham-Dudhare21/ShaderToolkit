import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, CollectionProperty, BoolProperty

from . import Utility
from .Requirements import TEXTURE_TYPES, OUTPUT_ORDER


# ----------------------------------------------------------
# Helper: find all textures with same base name in folder
# ----------------------------------------------------------

def find_texture_files(folder: str, base_name: str) -> list:
    """
    Scan a folder for texture files matching base_name_<suffix>.<ext>.
    Returns a list of (file_path, suffix) for recognised suffixes.
    """
    results = []
    for f in os.listdir(folder):
        file_path = os.path.join(folder, f)
        if not os.path.isfile(file_path):
            continue
        name, ext = os.path.splitext(f)
        ext = ext.lstrip('.').lower()
        if ext not in {'png', 'jpg', 'jpeg', 'tif', 'tiff', 'exr', 'hdr', 'tga', 'bmp', 'psd'}:
            continue
        parsed = Utility.ParseTextureFilename(name)
        if parsed.get("TextureName") == base_name and parsed.get("TextureType", "").upper() in TEXTURE_TYPES:
            results.append((file_path, parsed.get("TextureType", "").upper()))
    return results


# ----------------------------------------------------------
# Helper: group a list of image nodes into a texture group
# ----------------------------------------------------------

def group_image_nodes(node_tree, image_nodes, group_name, use_alpha, fix_colors):
    """Groups Image Texture nodes into a Texture Group, returns the group node."""
    if not image_nodes:
        return None

    # 1. Store outgoing links and data
    node_data = []
    for img_node in image_nodes:
        img = img_node.image
        img_name = img.name
        parsed = Utility.ParseTextureFilename(img_name)
        tex_type = parsed.get("TextureType", "").upper()
        display_name = TEXTURE_TYPES.get(tex_type, tex_type.capitalize())

        links = []
        for output in img_node.outputs:
            for link in output.links:
                links.append((link.from_socket, link.to_socket))

        node_data.append({
            'image': img,
            'image_name': img_name,
            'tex_type': tex_type,
            'display_name': display_name,
            'links': links,
        })

    # 2. Fix color spaces if requested
    if fix_colors:
        for data in node_data:
            tex_type = data['tex_type']
            img = data['image']
            if tex_type in TEXTURE_TYPES and (tex_type == "BC" or tex_type == "AO"):
                target_cs = 'sRGB'
            else:
                target_cs = 'Non-Color'
            if img.colorspace_settings.name != target_cs:
                img.colorspace_settings.name = target_cs

    # 3. Prepare unique textures per type
    unique_textures = {}
    for data in node_data:
        display_name = data['display_name']
        if display_name not in unique_textures:
            unique_textures[display_name] = (data['image'], data['tex_type'])

    # 4. Create the node group data block
    if group_name in bpy.data.node_groups:
        group_name = bpy.data.node_groups.new(group_name, 'ShaderNodeTree').name
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group.color_tag = 'TEXTURE'

    # Vector input
    vector_socket = group.interface.new_socket(
        name="Vector",
        in_out='INPUT',
        socket_type='NodeSocketVector'
    )
    vector_socket.hide_value = True

    # Internal nodes
    group_input = group.nodes.new("NodeGroupInput")
    group_input.location = (-1000, 0)
    group_output = group.nodes.new("NodeGroupOutput")
    group_output.location = (600, 0)

    internal_nodes = {}
    y_offset = 0
    for display_name, (img, suffix) in unique_textures.items():
        tex_node = group.nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        tex_node.label = display_name
        tex_node.name = display_name
        tex_node.location = (-400, y_offset)
        y_offset -= 300

        group.links.new(
            group_input.outputs["Vector"],
            tex_node.inputs["Vector"]
        )
        internal_nodes[display_name] = tex_node

    # 5. Create outputs in order
    present = set(unique_textures.keys())
    if use_alpha and "Base Color" in present:
        present.add("BC Alpha")

    output_index = 0
    for out_name in OUTPUT_ORDER:
        if out_name not in present:
            continue
        if out_name in {"Roughness", "Metallic", "Height", "Opacity", "BC Alpha"}:
            socket_type = 'NodeSocketFloat'
        else:
            socket_type = 'NodeSocketColor'

        group.interface.new_socket(
            name=out_name,
            in_out='OUTPUT',
            socket_type=socket_type
        )

        if out_name == "BC Alpha":
            base_node = internal_nodes.get("Base Color")
            if base_node:
                group.links.new(
                    base_node.outputs["Alpha"],
                    group_output.inputs[output_index]
                )
        else:
            node = internal_nodes.get(out_name)
            if node:
                output_socket = "Alpha" if out_name == "Opacity" else "Color"
                group.links.new(
                    node.outputs[output_socket],
                    group_output.inputs[output_index]
                )
        output_index += 1

    # 6. Replace selected image nodes with group node
    avg_x = sum(n.location.x for n in image_nodes) / len(image_nodes)
    avg_y = sum(n.location.y for n in image_nodes) / len(image_nodes)

    group_node = node_tree.nodes.new("ShaderNodeGroup")
    group_node.node_tree = group
    group_node.location = (avg_x, avg_y)
    group_node.label = group_name
    group_node.width = 250

    for node in image_nodes:
        node_tree.nodes.remove(node)

    # 7. Restore outgoing links
    output_sockets = {sock.name: sock for sock in group_node.outputs}

    for data in node_data:
        display_name = data['display_name']
        for from_sock, to_sock in data['links']:
            if from_sock.name == "Alpha" and display_name == "Opacity":
                target_name = "Opacity"
            elif from_sock.name == "Alpha" and display_name == "Base Color" and use_alpha:
                target_name = "BC Alpha"
            elif from_sock.name == "Color":
                target_name = display_name
            else:
                continue
            target_sock = output_sockets.get(target_name)
            if target_sock:
                node_tree.links.new(target_sock, to_sock)

    return group_node


# ----------------------------------------------------------
# Operator: File Browser (select textures)
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_NewTextureGroupBrowser(Operator):
    """Import textures from disk and create a new Texture Group"""
    bl_idname = "shadertoolkit.new_texture_group_browser"
    bl_label = "New Texture Group"
    bl_description = "Import textures and create a Texture Group"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')
    filter_image: BoolProperty(default=True)
    filter_folder: BoolProperty(default=True)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # Store selected file info in a temporary property on the scene
        scene = context.scene
        # Clear previous stored data
        if hasattr(scene, 'shader_toolkit_temp_files'):
            del scene.shader_toolkit_temp_files

        selected_files = [f.name for f in self.files] if self.files else [os.path.basename(self.filepath)]
        folder = self.directory if self.directory else os.path.dirname(self.filepath)

        if not selected_files or not folder:
            self.report({'ERROR'}, "No files selected")
            return {'CANCELLED'}

        # Determine texture files to use
        texture_files = []
        base_name = None

        if len(selected_files) == 1:
            filename = selected_files[0]
            parsed = Utility.ParseTextureFilename(filename)
            base_name = parsed.get("TextureName")
            if not base_name:
                self.report({'ERROR'}, "Selected file does not follow naming convention")
                return {'CANCELLED'}
            found = find_texture_files(folder, base_name)
            if not found:
                self.report({'ERROR'}, f"No matching textures for '{base_name}' in {folder}")
                return {'CANCELLED'}
            texture_files = found
            default_group_name = base_name
        else:
            for fname in selected_files:
                file_path = os.path.join(folder, fname)
                if not os.path.isfile(file_path):
                    continue
                parsed = Utility.ParseTextureFilename(fname)
                tex_type = parsed.get("TextureType", "").upper()
                if tex_type in TEXTURE_TYPES:
                    texture_files.append((file_path, tex_type))
            if not texture_files:
                self.report({'ERROR'}, "None of the selected files match the naming convention")
                return {'CANCELLED'}
            first_parsed = Utility.ParseTextureFilename(os.path.basename(texture_files[0][0]))
            default_group_name = first_parsed.get("TextureName", "TextureGroup")

        # Store the files and folder in a custom property on the scene
        # We'll store as a string list, but we need to pass them to the popup operator
        # Use a simple list on the scene: we'll store file paths and suffixes
        temp_data = []
        for fp, suffix in texture_files:
            temp_data.append((fp, suffix))

        # Store in a custom property (list of strings) – but we can't store tuples easily.
        # Instead, we'll store two separate lists: paths and suffixes.
        # Or we can store as a single string with a delimiter.
        # Let's store as a JSON-like string, but simpler: we'll store as a string list with separator.
        # For simplicity, we'll just store the full file paths and then parse suffixes again.
        # Actually, we already have the suffix; we can store them as a single string with a delimiter.
        # We'll use a custom property on the scene: 'shader_toolkit_temp_paths' as a string.
        paths = [fp for fp, _ in texture_files]
        suffixes = [suf for _, suf in texture_files]
        scene['shader_toolkit_temp_paths'] = "||".join(paths)
        scene['shader_toolkit_temp_suffixes'] = "||".join(suffixes)
        scene['shader_toolkit_temp_group_name'] = default_group_name

        # Now open the popup operator
        bpy.ops.shadertoolkit.new_texture_group_popup('INVOKE_DEFAULT')
        return {'FINISHED'}


# ----------------------------------------------------------
# Operator: Popup Dialog + Grouping
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_NewTextureGroupPopup(Operator):
    """Configure the new Texture Group"""
    bl_idname = "shadertoolkit.new_texture_group_popup"
    bl_label = "New Texture Group Options"
    bl_options = {'REGISTER'}

    group_name: StringProperty(
        name="Group Name",
        description="Name of the texture group",
        default=""
    )
    use_alpha: BoolProperty(
        name="Use Base Color Alpha",
        description="Add an extra 'BC Alpha' output",
        default=False
    )
    fix_colors: BoolProperty(
        name="Fix Color Spaces",
        description="Set sRGB for BC/AO, Non-Color for others",
        default=True
    )

    def invoke(self, context, event):
        # Pre-fill group name from stored data
        scene = context.scene
        if 'shader_toolkit_temp_group_name' in scene:
            self.group_name = scene['shader_toolkit_temp_group_name']
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "group_name")
        layout.prop(self, "use_alpha")
        layout.prop(self, "fix_colors")

    def execute(self, context):
        scene = context.scene
        # Retrieve stored file data
        paths_str = scene.get('shader_toolkit_temp_paths', '')
        suffixes_str = scene.get('shader_toolkit_temp_suffixes', '')
        if not paths_str or not suffixes_str:
            self.report({'ERROR'}, "No texture data found")
            return {'CANCELLED'}

        paths = paths_str.split("||")
        suffixes = suffixes_str.split("||")
        if len(paths) != len(suffixes):
            self.report({'ERROR'}, "Invalid texture data")
            return {'CANCELLED'}

        # Ensure we have a node editor
        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Open Shader Editor")
            return {'CANCELLED'}

        node_tree = space.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}

        # Load images and create Image Texture nodes
        image_nodes = []
        for i, fp in enumerate(paths):
            if not os.path.isfile(fp):
                continue
            img = bpy.data.images.load(fp, check_existing=True)
            node = node_tree.nodes.new('ShaderNodeTexImage')
            node.image = img
            node.location = (0, -300 * len(image_nodes))
            image_nodes.append(node)

        if not image_nodes:
            self.report({'ERROR'}, "No valid image files")
            return {'CANCELLED'}

        # Deselect all, select new nodes
        for n in node_tree.nodes:
            n.select = False
        for n in image_nodes:
            n.select = True
        if image_nodes:
            node_tree.nodes.active = image_nodes[-1]

        # Create the group
        group_node = group_image_nodes(
            node_tree,
            image_nodes,
            self.group_name.strip(),
            self.use_alpha,
            self.fix_colors
        )

        # Clean up temp data
        for key in ('shader_toolkit_temp_paths', 'shader_toolkit_temp_suffixes', 'shader_toolkit_temp_group_name'):
            if key in scene:
                del scene[key]

        if group_node:
            self.report({'INFO'}, f"Created texture group '{self.group_name}'")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to create group")
            return {'CANCELLED'}


# ----------------------------------------------------------
# Add to "Create" submenu
# ----------------------------------------------------------

def draw_new_texture_group_item(self, context):
    self.layout.operator(SHADERTOOLKIT_OT_NewTextureGroupBrowser.bl_idname, icon='FILE_NEW')


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_OT_NewTextureGroupBrowser,
    SHADERTOOLKIT_OT_NewTextureGroupPopup,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.SHADERTOOLKIT_MT_Create.append(draw_new_texture_group_item)


def unregister():
    bpy.types.SHADERTOOLKIT_MT_Create.remove(draw_new_texture_group_item)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)