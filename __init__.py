import bpy

from bpy.props import (StringProperty,
                       PointerProperty,
                       )

from bpy.types import (Panel,
                       PropertyGroup,
                       Operator,
                       Panel,
                       )

class TaackPlmProperties(PropertyGroup):
    serverUrl: StringProperty(name="ServerUrl", description="Server URL")
    username: StringProperty(name="Username", description="Username on the server")
    password: StringProperty(name="Password", subtype="PASSWORD", description="Password ...")


class TaackPlmUpload(Operator):
    bl_label = "Taack PLM Upload"
    bl_idname = "taack.plm_fork_upload"
    bl_description = "Upload saved model to the server"

    def execute(self, context):
        scene = context.scene
        taack_tool = scene.taack_tool

        self.report({"INFO"}, "Uploaded model to server: " + taack_tool.serverUrl)
        self.report({"INFO"}, "With user: " + taack_tool.username)
        return {"FINISHED"}


class TaackPlmForkRecent(Operator):
    bl_label = "Taack PLM Fork Recent"
    bl_idname = "taack.plm_fork_recent"
    bl_description = "Create a new history for this model"

    def execute(self, context):
        self.report({"INFO"}, "Forked model, you can upload!")
        return {"FINISHED"}


# Panel: where the button appears
class TAACK_PT_panel(Panel):
    bl_label = "Taack PLM Addon Panel"
    bl_idname = "TAACK_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "History"


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        taack_tool = scene.taack_tool

        layout.prop(taack_tool, "serverUrl")
        layout.prop(taack_tool, "username")
        layout.prop(taack_tool, "password")
        layout.separator()
        layout.operator("taack.plm_fork_upload")
        layout.operator("taack.plm_fork_recent")


# Register/unregister
classes = (
    TaackPlmProperties,
    TaackPlmUpload,
    TaackPlmForkRecent,
    TAACK_PT_panel,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.taack_tool = PointerProperty(type=TaackPlmProperties)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.taack_tool

if __name__ == "__main__":
    register()
