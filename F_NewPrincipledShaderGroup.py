import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, CollectionProperty, BoolProperty, EnumProperty

from . import Utility
from .Requirements import TEXTURE_TYPES, OUTPUT_ORDER
from .F_NewTextureGroup import find_texture_files, group_image_nodes


# ----------------------------------------------------------
# Operator: New Principled Shader Group (file browser)
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_NewPrincipledShaderGroupBrowser(Operator):
    """Import textures and create a Principled Shader Group"""
    bl_idname = "shadertoolkit.new_principled_shader_group_browser"
    bl_label = "New Principled Shader Group"
    bl_description = "Import textures and create a Principled Shader Group"
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
        scene = context.scene
        for key in ('shader_toolkit_temp_paths', 'shader_toolkit_temp_suffixes',
                    'shader_toolkit_temp_group_name', 'shader_toolkit_temp_shader_name'):
            if key in scene:
                del scene[key]

        selected_files = [f.name for f in self.files] if self.files else [os.path.basename(self.filepath)]
        folder = self.directory if self.directory else os.path.dirname(self.filepath)

        if not selected_files or not folder:
            self.report({'ERROR'}, "No files selected")
            return {'CANCELLED'}

        texture_files = []
        default_group_name = "TextureGroup"

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

        paths = [fp for fp, _ in texture_files]
        suffixes = [suf for _, suf in texture_files]
        scene['shader_toolkit_temp_paths'] = "||".join(paths)
        scene['shader_toolkit_temp_suffixes'] = "||".join(suffixes)
        scene['shader_toolkit_temp_group_name'] = default_group_name
        scene['shader_toolkit_temp_shader_name'] = f"{default_group_name} BSDF"

        bpy.ops.shadertoolkit.new_principled_shader_group_popup('INVOKE_DEFAULT')
        return {'FINISHED'}


# ----------------------------------------------------------
# Popup Dialog
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_NewPrincipledShaderGroupPopup(Operator):
    """Configure the new Principled Shader Group"""
    bl_idname = "shadertoolkit.new_principled_shader_group_popup"
    bl_label = "New Principled Shader Group Options"
    bl_options = {'REGISTER'}

    group_name: StringProperty(
        name="Texture Group Name",
        description="Name of the internal texture group",
        default=""
    )
    shader_name: StringProperty(
        name="Shader Group Name",
        description="Name of the final shader group",
        default=""
    )
    use_alpha: BoolProperty(
        name="Use Base Color Alpha",
        description="Add an extra 'BC Alpha' output to the texture group",
        default=False
    )
    fix_colors: BoolProperty(
        name="Fix Color Spaces",
        description="Set sRGB for BC/AO, Non-Color for others",
        default=True
    )
    use_vector_input: BoolProperty(
        name="Vector Input",
        description="Expose the Texture Group's Vector input as an input of the Shader Group",
        default=False
    )
    coord_type: EnumProperty(
        name="Texture Coordinate",
        description="Type of texture coordinate node to add inside the Shader Group",
        items=[
            ('UV', "UV Map", "Use UV Map coordinates"),
            ('OBJECT', "Object", "Use Object coordinates"),
            ('GENERATED', "Generated", "Use Generated coordinates"),
            ('NORMAL', "Normal", "Use Normal coordinates"),
            ('CAMERA', "Camera", "Use Camera coordinates"),
            ('WINDOW', "Window", "Use Window coordinates"),
            ('REFLECTION', "Reflection", "Use Reflection coordinates"),
        ],
        default='UV'
    )

    def invoke(self, context, event):
        scene = context.scene
        if 'shader_toolkit_temp_group_name' in scene:
            self.group_name = scene['shader_toolkit_temp_group_name']
        if 'shader_toolkit_temp_shader_name' in scene:
            self.shader_name = scene['shader_toolkit_temp_shader_name']
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "group_name")
        layout.prop(self, "shader_name")
        layout.separator()
        layout.prop(self, "use_alpha")
        layout.prop(self, "fix_colors")
        layout.separator()
        layout.prop(self, "use_vector_input")
        if not self.use_vector_input:
            layout.prop(self, "coord_type")

    def execute(self, context):
        scene = context.scene
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

        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Open Shader Editor")
            return {'CANCELLED'}

        node_tree = space.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}

        # ----------------------------------------------------------
        # 1. Load images and create Image Texture nodes
        # ----------------------------------------------------------
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

        for n in node_tree.nodes:
            n.select = False
        for n in image_nodes:
            n.select = True
        if image_nodes:
            node_tree.nodes.active = image_nodes[-1]

        # ----------------------------------------------------------
        # 2. Create the Texture Group
        # ----------------------------------------------------------
        texture_group_node = group_image_nodes(
            node_tree,
            image_nodes,
            self.group_name.strip(),
            self.use_alpha,
            self.fix_colors
        )

        if not texture_group_node:
            self.report({'ERROR'}, "Failed to create texture group")
            return {'CANCELLED'}

        for n in node_tree.nodes:
            n.select = False
        texture_group_node.select = True
        node_tree.nodes.active = texture_group_node

        # ----------------------------------------------------------
        # 3. Add coordinate nodes and Mapping (if needed)
        # ----------------------------------------------------------
        coord_node = None
        mapping_node = None
        if not self.use_vector_input:
            # Add Texture Coordinate node
            coord_node = node_tree.nodes.new('ShaderNodeTexCoord')
            coord_node.location = (texture_group_node.location.x - 600,
                                   texture_group_node.location.y + 300)

            # Add Mapping node
            mapping_node = node_tree.nodes.new('ShaderNodeMapping')
            mapping_node.location = (texture_group_node.location.x - 400,
                                     texture_group_node.location.y + 300)

            # Choose the output socket from TexCoord based on coord_type
            coord_type = self.coord_type
            if coord_type == 'UV':
                output_socket = coord_node.outputs["UV"]
            elif coord_type == 'OBJECT':
                output_socket = coord_node.outputs["Object"]
            elif coord_type == 'GENERATED':
                output_socket = coord_node.outputs["Generated"]
            elif coord_type == 'NORMAL':
                output_socket = coord_node.outputs["Normal"]
            elif coord_type == 'CAMERA':
                output_socket = coord_node.outputs["Camera"]
            elif coord_type == 'WINDOW':
                output_socket = coord_node.outputs["Window"]
            else:  # REFLECTION
                output_socket = coord_node.outputs["Reflection"]

            # Connect TexCoord -> Mapping -> Texture Group Vector
            node_tree.links.new(output_socket, mapping_node.inputs["Vector"])
            node_tree.links.new(mapping_node.outputs["Vector"], texture_group_node.inputs["Vector"])

        # ----------------------------------------------------------
        # 4. Principled BSDF, Normal Map, Displacement
        # ----------------------------------------------------------
        bsdf_node = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf_node.location = (texture_group_node.location.x + 400,
                              texture_group_node.location.y)

        # Find Material Output
        material_output = None
        for node in node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                material_output = node
                break
        if not material_output:
            material_output = node_tree.nodes.new('ShaderNodeOutputMaterial')
            material_output.location = (texture_group_node.location.x + 800,
                                        texture_group_node.location.y)

        normal_map_node = None
        displacement_node = None
        for output in texture_group_node.outputs:
            if output.name == "Base Color":
                node_tree.links.new(output, bsdf_node.inputs["Base Color"])
            elif output.name == "Roughness":
                node_tree.links.new(output, bsdf_node.inputs["Roughness"])
            elif output.name == "Metallic":
                node_tree.links.new(output, bsdf_node.inputs["Metallic"])
            elif output.name == "Emission":
                node_tree.links.new(output, bsdf_node.inputs["Emission"])
            elif output.name == "Opacity":
                node_tree.links.new(output, bsdf_node.inputs["Alpha"])
            elif output.name == "Normal":
                normal_map_node = node_tree.nodes.new('ShaderNodeNormalMap')
                normal_map_node.location = (texture_group_node.location.x + 200,
                                            texture_group_node.location.y - 300)
                node_tree.links.new(output, normal_map_node.inputs["Color"])
                node_tree.links.new(normal_map_node.outputs["Normal"], bsdf_node.inputs["Normal"])
            elif output.name == "Height":
                displacement_node = node_tree.nodes.new('ShaderNodeDisplacement')
                displacement_node.location = (texture_group_node.location.x + 200,
                                              texture_group_node.location.y - 600)
                node_tree.links.new(output, displacement_node.inputs["Height"])

        # Connect BSDF to Material Output
        node_tree.links.new(bsdf_node.outputs["BSDF"], material_output.inputs["Surface"])
        if displacement_node:
            node_tree.links.new(displacement_node.outputs["Displacement"],
                                material_output.inputs["Displacement"])

        # ----------------------------------------------------------
        # 5. Select all nodes to be grouped
        # ----------------------------------------------------------
        for n in node_tree.nodes:
            n.select = False

        nodes_to_select = [texture_group_node, bsdf_node]
        if coord_node:
            nodes_to_select.append(coord_node)
        if mapping_node:
            nodes_to_select.append(mapping_node)
        if normal_map_node:
            nodes_to_select.append(normal_map_node)
        if displacement_node:
            nodes_to_select.append(displacement_node)

        for n in nodes_to_select:
            n.select = True
        node_tree.nodes.active = bsdf_node

        # ----------------------------------------------------------
        # 6. Group the nodes
        # ----------------------------------------------------------
        try:
            bpy.ops.node.group_make()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to group nodes: {e}")
            return {'CANCELLED'}

        shader_group_node = node_tree.nodes.active
        if not shader_group_node or shader_group_node.type != 'GROUP':
            self.report({'ERROR'}, "Failed to create shader group")
            return {'CANCELLED'}

        # ----------------------------------------------------------
        # 7. If Vector Input is enabled, expose it as a group input
        # ----------------------------------------------------------
        if self.use_vector_input:
            group = shader_group_node.node_tree
            # Check if a Vector input already exists
            has_vector = any(socket.name == "Vector" and socket.in_out == 'INPUT'
                             for socket in group.interface.items_tree)
            if not has_vector:
                # Add a Vector input socket
                group.interface.new_socket(
                    name="Vector",
                    in_out='INPUT',
                    socket_type='NodeSocketVector'
                )
                # Find the internal Texture Group node inside the shader group
                internal_tex_group = None
                for node in group.nodes:
                    if node.type == 'GROUP' and node.node_tree == texture_group_node.node_tree:
                        internal_tex_group = node
                        break
                if internal_tex_group:
                    # Connect the new Vector input to the internal texture group's Vector input
                    group_input_node = None
                    for node in group.nodes:
                        if node.type == 'GROUP_INPUT':
                            group_input_node = node
                            break
                    if group_input_node:
                        group.links.new(
                            group_input_node.outputs["Vector"],
                            internal_tex_group.inputs["Vector"]
                        )

        # Rename and set color tag
        shader_name = self.shader_name.strip()
        if not shader_name:
            shader_name = "PrincipledShader"
        shader_group_node.node_tree.name = shader_name
        shader_group_node.node_tree.color_tag = 'SHADER'
        shader_group_node.label = shader_name

        # ----------------------------------------------------------
        # 8. Hide the Vector input's value field (safe)
        # ----------------------------------------------------------
        if shader_group_node.node_tree:
            # On interface socket
            for item in shader_group_node.node_tree.interface.items_tree:
                if item.name == "Vector" and item.in_out == 'INPUT':
                    try:
                        item.hide_value = True
                    except:
                        pass
                    break
            # Also on the node instance as a fallback
            for inp in shader_group_node.inputs:
                if inp.name == "Vector":
                    try:
                        inp.hide_value = True
                    except:
                        pass
                    break

        # Cleanup temp data
        for key in ('shader_toolkit_temp_paths', 'shader_toolkit_temp_suffixes',
                    'shader_toolkit_temp_group_name', 'shader_toolkit_temp_shader_name'):
            if key in scene:
                del scene[key]

        self.report({'INFO'}, f"Created Principled Shader Group '{shader_name}'")
        return {'FINISHED'}


# ----------------------------------------------------------
# Menu integration
# ----------------------------------------------------------

def draw_new_principled_shader_group_item(self, context):
    self.layout.operator(SHADERTOOLKIT_OT_NewPrincipledShaderGroupBrowser.bl_idname, icon='MATERIAL')


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_OT_NewPrincipledShaderGroupBrowser,
    SHADERTOOLKIT_OT_NewPrincipledShaderGroupPopup,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.SHADERTOOLKIT_MT_Create.append(draw_new_principled_shader_group_item)


def unregister():
    bpy.types.SHADERTOOLKIT_MT_Create.remove(draw_new_principled_shader_group_item)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)