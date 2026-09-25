import bpy, os, requests, uuid, sys

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

class TaackPlmPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__ if __package__ else os.path.splitext(os.path.basename(__file__))[0]

    serverUrl: StringProperty(
        name="Server URL",
        description="The Server URL Address",
        default="http://localhost:9442/"
    )
    username: StringProperty(
        name="Username",
        description="Username",
        default="admin"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Global configuration :")
        layout.prop(self, "serverUrl")
        layout.prop(self, "username")



class TaackPlmProperties(PropertyGroup):
    password: StringProperty(
        name="Password",
        subtype="PASSWORD",
        description="Password ..."
    )


class TaackPlmConnect(Operator):
    bl_label = "Connect"
    bl_idname = "taack.plm_fork_connect"
    bl_description = "Connect to the server"

    def execute(self, context):
        scene = context.scene
        taack_props = scene.taack_props
        taack_prefs = context.preferences.addons[TaackPlmPreferences.bl_idname].preferences
        global connected

        data = {"username": taack_prefs.username, "password": taack_props.password, "ajax": 'true'}
        try:
            r = taackIntranetSession.post(url=taack_prefs.serverUrl + 'login/authenticate', data=data, timeout=5)
            if r.json()["success"]:
                connected = True
                self.report({"INFO"}, "Connected to server: " + taack_prefs.serverUrl)
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

    def __init__(self):
        self.avoidLoop = None
        self.uuidVersion = None
        self.docLabelsForked = None
        self.forkMode = 'Active'


    def create_missing_uuid(self, obj, force):
        if force:
            obj['taack_id'] = str(uuid.uuid4())
        else :
            if 'taack_id' not in obj :
                obj['taack_id'] = str(uuid.uuid4())
            else:
                obj['taack_id'] = obj['taack_id'] + '/' + str(uuid.uuid4())
        linked_objects = iter(obj.children)
        for l in linked_objects:
            self.create_link_protobuf(l, force)

    def create_bucket_protobuf(self, obj):
        print("createBucketProtobuf")
        self.avoidLoop = []
        d = bpy.data
        c = bpy.context
        if d.filepath != "":
            bucket = PlmBuf.Bucket()
            self.create_missing_uuid(c.active_object, False)
            bpy.ops.wm.save_as_mainfile(d.filepath)
            create_doc_protobuf(c.active_object, bucket)
            return bucket
        else:
            self.report({"INFO"}, "Save the file before uploading !")

        linked_objects = iter(obj.children)
        for l in linked_objects:
            self.create_bucket_protobuf(l)

        return None

    def create_doc_protobuf(self, obj, bucket):
        print("createDocProtobuf " + obj.name)
        try:
            if self.avoidLoop.count(obj.name) > 0:
                return None
            self.avoidLoop.append(obj.name)
            plm_file = PlmBuf.PlmFile()
            s = os.stat(obj.filepath)
            plm_file.cTimeNs = s.st_ctime_ns
            plm_file.uTimeNs = s.st_mtime_ns
            plm_file.name = obj.name

            plm_file.id = obj['taack_id']
            print("plmFile.id " + plm_file.id)

            plm_file.label = obj.Label
            plm_file.comment = obj.Comment
            plm_file.fileName = os.path.basename(obj.filepath)
            plm_file.createdDate = obj.CreationDate
            plm_file.createdBy = bpy.context.preferences.filepaths.author
            plm_file.lastModifiedDate = os.path.getctime(obj.filepath)
            plm_file.lastModifiedBy = os.path.getctime(obj.filepath)
            linked_objects = iter(obj.children)
            for l in linked_objects:
                lp = self.create_link_protobuf(l, bucket)
                if lp is not None:
                    plm_file.externalLink.append(lp)

            plm_file.fileContent = open(obj.filepath, 'rb').read()
            bucket.plmFiles[plm_file.name].CopyFrom(plm_file)
        except:
            self.report({"ERROR"}, "Error creating protobuf file !")

        return obj.name

    def create_link_protobuf(self, obj, bucket):
        print("createLinkProtobuf " + obj.name)
        try:
            plm_link = PlmBuf.PlmLink()
            plm_link.linkedObject = obj.name
            plm_link.linkClaimChild = False
            plm_link.linkCopyOnChange = PlmBuf.PlmLink.LinkCopyOnChangeEnum.Disabled
            plm_link.linkTransform = False
            f = create_doc_protobuf(obj.LinkedObject.Document, bucket)
            if f is None:
                return None
            plm_link.plmFile = f
            bucket.links[obj.name].CopyFrom(plm_link)
        except:
            raise ValueError("createLinkProtobuf Error")

        return obj.name

    def execute(self, context):
        print("Execute TaackPlmUpload")
        scene = context.scene
        taack_props = scene.taack_props

        deps = bpy.context.evaluated_depsgraph_get()
        filsetpathSet = set()
        filsetpathSet.add(bpy.data.filepath)
        for obj in deps.ids:
            print(str(obj))
            # For images and so on ...
            if hasattr(obj, 'filepath') and not obj.filepath in filsetpathSet:
                filsetpathSet.add(obj.filepath)

            if obj.library and not obj.library.filepath in filsetpathSet:
                filsetpathSet.add(obj.library.filepath)

        print(filsetpathSet)

        return {"FINISHED"}
    #     scene = context.scene
    # if not connected:
    #     self.report({"ERROR"}, "Not connected to the server")
    #     return False
    #
    # b = self.create_bucket_protobuf()
    # f = open("bl_proto", 'wb')
    # f.write(b.SerializeToString())
    # f.close()
    # data = {"ajax": 'true'}
    # f2 = open("bl_proto", 'rb')
    # r = self.po.taackIntranetSession.post(url=self.po.url + 'plm/uploadProto', files={'proto.bin': f2}, data=data)
    # f2.close()
    #
    # if r.json()["success"]:
    #     return True
    # else:
    #     self.report({"ERROR"}, "Message does not successfully sent: " + r.json()["message"])
    #     return False


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
        layout = self.layout
        scene = context.scene
        taack_props = scene.taack_props

        # layout.prop(taack_props, "serverUrl")
        # layout.prop(taack_props, "username")
        layout.prop(taack_props, "password")
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
    TaackPlmPreferences,
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

    bpy.types.Scene.taack_props = PointerProperty(type=TaackPlmProperties)
    addon_dir = os.path.dirname(__file__)
    icon_path = os.path.join(addon_dir, "taackPLM.png")
    taackIcons.load("taack_plm", icon_path, 'IMAGE')


def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.taack_props
    bpy.utils.previews.remove(taackIcons)

if __name__ == "__main__":
    register()
