import bpy
from bpy.types import Operator, Menu
from bpy.props import StringProperty, BoolProperty

from . import Utility
from .Requirements import TEXTURE_TYPES, OUTPUT_ORDER


# ----------------------------------------------------------
# Operator: Group Textures (with dialog & link preservation)
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_GroupTextures(Operator):
    """Group selected Image Texture nodes into a Texture Group"""
    bl_idname = "shadertoolkit.group_textures"
    bl_label = "Group Textures"
    bl_description = "Group selected Image Texture nodes into a single Texture Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty(
        name="Group Name",
        description="Name of the new texture group",
        default=""
    )
    use_alpha: BoolProperty(
        name="Use Base Color Alpha",
        description="Add an extra 'BC Alpha' output from Base Color's alpha channel",
        default=False
    )
    fix_colors: BoolProperty(
        name="Fix Color Spaces",
        description="Automatically set sRGB for Base Color and AO, Non‑Color for others",
        default=True
    )

    def invoke(self, context, event):
        selected = context.selected_nodes
        image_nodes = [n for n in selected if n.type == 'TEX_IMAGE' and n.image]
        if not image_nodes:
            self.report({'WARNING'}, "Select at least one Image Texture node")
            return {'CANCELLED'}
        self.image_nodes = image_nodes

        # Default group name from first texture
        first_img = image_nodes[0].image
        parsed = Utility.ParseTextureFilename(first_img.name)
        self.group_name = parsed.get("TextureName", "TextureGroup")

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "group_name")
        layout.prop(self, "use_alpha")
        layout.prop(self, "fix_colors")

    def execute(self, context):
        if not self.image_nodes:
            self.report({'WARNING'}, "No Image Texture nodes selected")
            return {'CANCELLED'}

        node_tree = context.space_data.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}

        # ----------------------------------------------------------
        # 1. Store all data from selected image nodes (before deletion)
        # ----------------------------------------------------------
        node_data = []  # list of dicts with image, image_name, tex_type, display_name, links
        for img_node in self.image_nodes:
            img = img_node.image
            img_name = img.name
            parsed = Utility.ParseTextureFilename(img_name)
            tex_type = parsed.get("TextureType", "").upper()
            display_name = TEXTURE_TYPES.get(tex_type, tex_type.capitalize())

            # Store outgoing links
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

        # ----------------------------------------------------------
        # 2. Fix color spaces if requested (on the image data blocks)
        # ----------------------------------------------------------
        if self.fix_colors:
            for data in node_data:
                tex_type = data['tex_type']
                img = data['image']
                if tex_type in TEXTURE_TYPES and (tex_type == "BC" or tex_type == "AO"):
                    target_cs = 'sRGB'
                else:
                    target_cs = 'Non-Color'
                if img.colorspace_settings.name != target_cs:
                    img.colorspace_settings.name = target_cs

        # ----------------------------------------------------------
        # 3. Prepare textures for group creation (unique types)
        # ----------------------------------------------------------
        unique_textures = {}
        for data in node_data:
            display_name = data['display_name']
            if display_name not in unique_textures:
                unique_textures[display_name] = (data['image'], data['tex_type'])

        # ----------------------------------------------------------
        # 4. Create the node group data block
        # ----------------------------------------------------------
        group_name = self.group_name.strip()
        if not group_name:
            group_name = "TextureGroup"
        if group_name in bpy.data.node_groups:
            group_name = bpy.data.node_groups.new(group_name, 'ShaderNodeTree').name
        group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
        group.color_tag = 'TEXTURE'

        # Add Vector input
        vector_socket = group.interface.new_socket(
            name="Vector",
            in_out='INPUT',
            socket_type='NodeSocketVector'
        )
        vector_socket.hide_value = True

        # Internal nodes: Group Input and Group Output
        group_input = group.nodes.new("NodeGroupInput")
        group_input.location = (-1000, 0)
        group_output = group.nodes.new("NodeGroupOutput")
        group_output.location = (600, 0)

        # Map display_name -> internal texture node
        internal_nodes = {}
        y_offset = 0
        for display_name, (img, suffix) in unique_textures.items():
            tex_node = group.nodes.new("ShaderNodeTexImage")
            tex_node.image = img
            tex_node.label = display_name
            tex_node.name = display_name
            tex_node.location = (-400, y_offset)
            y_offset -= 300

            # Connect shared vector
            group.links.new(
                group_input.outputs["Vector"],
                tex_node.inputs["Vector"]
            )
            internal_nodes[display_name] = tex_node

        # ----------------------------------------------------------
        # 5. Create output sockets in the order of OUTPUT_ORDER
        # ----------------------------------------------------------
        present = set(unique_textures.keys())
        if self.use_alpha and "Base Color" in present:
            present.add("BC Alpha")

        output_index = 0
        for out_name in OUTPUT_ORDER:
            if out_name not in present:
                continue
            # Socket type
            if out_name in {"Roughness", "Metallic", "Height", "Opacity", "BC Alpha"}:
                socket_type = 'NodeSocketFloat'
            else:
                socket_type = 'NodeSocketColor'

            group.interface.new_socket(
                name=out_name,
                in_out='OUTPUT',
                socket_type=socket_type
            )

            # Connect from internal node
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

        # ----------------------------------------------------------
        # 6. Replace selected image nodes with the group node
        # ----------------------------------------------------------
        avg_x = sum(n.location.x for n in self.image_nodes) / len(self.image_nodes)
        avg_y = sum(n.location.y for n in self.image_nodes) / len(self.image_nodes)

        group_node = node_tree.nodes.new("ShaderNodeGroup")
        group_node.node_tree = group
        group_node.location = (avg_x, avg_y)
        group_node.label = group_name
        group_node.width = 250

        # Remove original image nodes
        for node in self.image_nodes:
            node_tree.nodes.remove(node)

        # ----------------------------------------------------------
        # 7. Restore outgoing links to the new group outputs
        # ----------------------------------------------------------
        output_sockets = {sock.name: sock for sock in group_node.outputs}

        for data in node_data:
            display_name = data['display_name']
            links = data['links']
            for from_sock, to_sock in links:
                # Determine target socket name on the group node
                if from_sock.name == "Alpha" and display_name == "Opacity":
                    target_name = "Opacity"
                elif from_sock.name == "Alpha" and display_name == "Base Color" and self.use_alpha:
                    target_name = "BC Alpha"
                elif from_sock.name == "Color":
                    target_name = display_name
                else:
                    # Unsupported socket – skip
                    continue

                target_sock = output_sockets.get(target_name)
                if target_sock:
                    node_tree.links.new(target_sock, to_sock)

        self.report({'INFO'}, f"Created texture group '{group_name}' with {len(unique_textures)} textures")
        return {'FINISHED'}


# ----------------------------------------------------------
# Add to "Create" submenu
# ----------------------------------------------------------

def draw_group_textures_item(self, context):
    self.layout.operator(SHADERTOOLKIT_OT_GroupTextures.bl_idname, icon='NODETREE')


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_OT_GroupTextures,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.SHADERTOOLKIT_MT_Create.append(draw_group_textures_item)


def unregister():
    bpy.types.SHADERTOOLKIT_MT_Create.remove(draw_group_textures_item)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)