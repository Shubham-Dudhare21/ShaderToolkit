# F_Cleanup.py
import bpy
from bpy.types import Operator, Menu


# ----------------------------------------------------------
# Operator: Purge Unused Data
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_PurgeUnusedData(Operator):
    """Open the Purge Unused Data dialog (File > Clean Up)"""
    bl_idname = "shadertoolkit.purge_unused_data"
    bl_label = "Purge Unused Data..."
    bl_description = "Open the Purge Unused Data dialog (File > Clean Up > Purge Unused Data)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.outliner.orphans_purge('INVOKE_DEFAULT')
        return {'FINISHED'}


# ----------------------------------------------------------
# Operator: Manage Unused Data
# ----------------------------------------------------------

class SHADERTOOLKIT_OT_ManageUnusedData(Operator):
    """Open the Manage Unused Data list dialog (File > Clean Up)"""
    bl_idname = "shadertoolkit.manage_unused_data"
    bl_label = "Manage Unused Data..."
    bl_description = "Open the Manage Unused Data list dialog (File > Clean Up > Manage Unused Data)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.outliner.orphans_manage('INVOKE_DEFAULT')
        return {'FINISHED'}


# ----------------------------------------------------------
# Menu: CleanUp submenu
# ----------------------------------------------------------

class SHADERTOOLKIT_MT_CleanUp(Menu):
    bl_label = "CleanUp"
    bl_idname = "SHADERTOOLKIT_MT_CleanUp"

    def draw(self, context):
        layout = self.layout
        layout.operator(SHADERTOOLKIT_OT_PurgeUnusedData.bl_idname, icon='FILE_BLEND')
        layout.operator(SHADERTOOLKIT_OT_ManageUnusedData.bl_idname, icon='FILE_BLEND')


# ----------------------------------------------------------
# Registration (no appending – the main menu references this class)
# ----------------------------------------------------------

classes = (
    SHADERTOOLKIT_OT_PurgeUnusedData,
    SHADERTOOLKIT_OT_ManageUnusedData,
    SHADERTOOLKIT_MT_CleanUp,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)