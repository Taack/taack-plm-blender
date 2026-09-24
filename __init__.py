import bpy, os, requests, uuid

from bpy.props import (StringProperty,
                       PointerProperty,
                       )

from bpy.types import (Panel,
                       PropertyGroup,
                       Operator,
                       Panel,
                       )

import bpy.utils.previews

taackIcons = bpy.utils.previews.new()
taackIntranetSession = requests.session()
connected = None

class TaackPlmProperties(PropertyGroup):
    serverUrl: StringProperty(name="ServerUrl", description="Server URL")
    username: StringProperty(name="Username", description="Username on the server")
    password: StringProperty(name="Password", subtype="PASSWORD", description="Password ...")


class TaackPlmConnect(Operator):
    bl_label = "Connect"
    bl_idname = "taack.plm_fork_connect"
    bl_description = "Connect to the server"

    def execute(self, context):
        scene = context.scene
        taack_tool = scene.taack_tool

        global connected

        data = {"username": taack_tool.username, "password": taack_tool.password, "ajax": 'true'}
        try:
            r = taackIntranetSession.post(url=taack_tool.serverUrl + 'login/authenticate', data=data, timeout=5)
            if r.json()["success"]:
                connected = True
                self.report({"INFO"}, "Connected to server: " + taack_tool.serverUrl)
            else:
                self.report({"ERROR"}, "Connection failed: " + r.json()["message"])
                connected = False
        except:
            self.report({"ERROR"}, "Connection failed with an unexpected error: " + sys.exc_info()[0])

        # context.area.tag_redraw()
        return {"FINISHED"}


class TaackPlmUpload(Operator):
    bl_label = "Upload To Server"
    bl_idname = "taack.plm_fork_upload"
    bl_description = "Upload saved model to the server"

    def execute(self, context):
        scene = context.scene
        taack_tool = scene.taack_tool

        return {"FINISHED"}


class TaackPlmForkRecent(Operator):
    bl_label = "Duplicate History"
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
    bl_category = "Taack PLM"


    def draw(self, context):
        print("DRAWWWWW " + str(connected))
        layout = self.layout
        scene = context.scene
        taack_tool = scene.taack_tool

        layout.prop(taack_tool, "serverUrl")
        layout.prop(taack_tool, "username")
        layout.prop(taack_tool, "password")
        layout.separator()
        op_row_upload = layout.row()
        op_row_connect = layout.row()
        if connected:
            op_row_upload.enabled = True
            op_row_connect.enabled = False
        else:
            op_row_upload.enabled = False
            op_row_connect.enabled = True
        op_row_connect.operator("taack.plm_fork_connect", icon_value=taackIcons["taack_plm"].icon_id)
        op_row_upload.operator("taack.plm_fork_upload", icon="FILE_REFRESH")
        layout.operator("taack.plm_fork_recent", icon="COPY_ID")


# Register/unregister
classes = (
    TaackPlmProperties,
    TaackPlmConnect,
    TaackPlmUpload,
    TaackPlmForkRecent,
    TAACK_PT_panel,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.taack_tool = PointerProperty(type=TaackPlmProperties)
    addon_dir = os.path.dirname(__file__)
    icon_path = os.path.join(addon_dir, "taackPLM.png")
    taackIcons.load("taack_plm", icon_path, 'IMAGE')


def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.taack_tool
    bpy.utils.previews.remove(taackIcons)

if __name__ == "__main__":
    register()
