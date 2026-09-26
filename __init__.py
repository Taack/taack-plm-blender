import bpy, os, requests, uuid, sys, getpass, json, datetime

from bpy.props import (StringProperty,
                       PointerProperty,
                       )

from bpy.types import (Panel,
                       PropertyGroup,
                       Operator,
                       Panel,
                       )

import bpy.utils.previews

try:
    from . import freecad_plm_pb2 as PlmBuf
except:
    import freecad_plm_pb2 as PlmBuf


taackIcons = bpy.utils.previews.new()
taackIntranetSession = requests.session()
connected = None
simpleDateFormat="%Y-%m-%dT%H:%M:%SZ"

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

    def create_missing_uuid(self, obj, force):
        uuid4 = str(uuid.uuid4())
        if force:
            obj['taack_id'] = uuid4
        else :
            if 'taack_id' not in obj :
                obj['taack_id'] = uuid4
            else:
                obj['taack_id'] = obj['taack_id'] + '/' + uuid4

        print("create_missing_uuid " + obj['taack_id'])

    def create_link_protobuf(self, rootpath, obj, bucket):
        print("createLinkProtobuf " + obj.name)
        try:
            filepath = os.path.join(rootpath, obj.filepath.replace('//', ''))
            if not os.path.exists(filepath):
                self.report({"WARNING"}, "File does not exist " + filepath)
                return None
            plm_link = PlmBuf.PlmLink()
            plm_link.linkedObject = obj.name
            plm_link.linkClaimChild = False
            plm_link.linkCopyOnChange = PlmBuf.PlmLink.LinkCopyOnChangeEnum.Disabled
            plm_link.linkTransform = False
            plm_file = PlmBuf.PlmFile()
            plm_file.id = obj['taack_id']
            s = os.stat(filepath)
            plm_file.cTimeNs = s.st_ctime_ns
            plm_file.uTimeNs = s.st_mtime_ns
            plm_file.name = obj.name
            plm_file.fileName = os.path.basename(filepath)
            #plm_file.lastModifiedDate = str(datetime.datetime.strptime(os.path.getctime(bpy.data.filepath), "%a %b %d %H:%M:%S %Y"))
            #plm_file.lastModifiedBy = str(datetime.datetime.strptime(os.path.getctime(bpy.data.filepath), "%a %b %d %H:%M:%S %Y"))
            plm_file.lastModifiedDate = str(datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).strftime(simpleDateFormat))
            plm_file.createdDate = str(datetime.datetime.fromtimestamp(os.path.getctime(filepath)).strftime(simpleDateFormat))
            plm_file.fileContent = open(filepath, 'rb').read()
            plm_link.plmFile = obj.name
            bucket.links[obj.name].CopyFrom(plm_link)
            bucket.plmFiles[plm_file.name].CopyFrom(plm_file)
        except:
            raise ValueError("createLinkProtobuf Error")

        return obj.name

    def execute(self, context):
        print("Execute TaackPlmUpload")
        global connected
        if not connected:
            self.report({"ERROR"}, "Not connected to the server")
            return {"CANCELLED"}

        deps = bpy.context.evaluated_depsgraph_get()
        filepath_set = set()
        self.create_missing_uuid(bpy.context.active_object, False)
        filepath_set.add(bpy.data.filepath)
        bucket = PlmBuf.Bucket()
        plm_file = PlmBuf.PlmFile()
        s = os.stat(bpy.data.filepath)
        plm_file.cTimeNs = s.st_ctime_ns
        plm_file.uTimeNs = s.st_mtime_ns
        plm_file.name = bpy.context.active_object.name
        plm_file.fileName = os.path.basename(bpy.data.filepath)
        plm_file.createdBy = getpass.getuser()
        plm_file.id = bpy.context.active_object['taack_id']
        plm_file.lastModifiedDate = str(datetime.datetime.fromtimestamp(os.path.getmtime(bpy.data.filepath)).strftime(simpleDateFormat))
        plm_file.createdDate = str(datetime.datetime.fromtimestamp(os.path.getctime(bpy.data.filepath)).strftime(simpleDateFormat))

        for obj in deps.ids:
            print(str(obj))
            # For images and so on ...
            if hasattr(obj, 'filepath') and not obj.filepath in filepath_set:
                filepath_set.add(obj.filepath)
                self.create_missing_uuid(obj, False)
                linkName = self.create_link_protobuf(os.path.dirname(bpy.data.filepath), obj, bucket)
                if linkName is not None:
                    plm_file.externalLink.append(linkName)
                else:
                    print("linkName1: None ... for " + obj.name)


            if obj.library and not obj.library.filepath in filepath_set:
                filepath_set.add(obj.library.filepath)
                self.create_missing_uuid(obj.library, False)
                linkName = self.create_link_protobuf(os.path.dirname(bpy.data.filepath), obj.library, bucket)
                if linkName is not None:
                    plm_file.externalLink.append(linkName)
                else:
                    print("linkName2: None ... for " + obj.name)

        plm_file.fileContent = open(bpy.data.filepath, 'rb').read()
        bucket.plmFiles[plm_file.name].CopyFrom(plm_file)

        print(filepath_set)
        if len(filepath_set) == 0:
            self.report({"ERROR"}, "Filset path set is empty")
            return {"CANCELLED"}

        f = open("bl_proto", 'wb')
        f.write(bucket.SerializeToString())
        f.close()
        data = {"ajax": 'true'}
        f2 = open("bl_proto", 'rb')

        taack_prefs = context.preferences.addons[TaackPlmPreferences.bl_idname].preferences
        try:
            r = taackIntranetSession.post(url=taack_prefs.serverUrl + 'plm/uploadProto', files={'proto.bin': f2}, data=data)
            f2.close()
            if r.json()["success"]:
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, "Message does not successfully sent: " + r.json()["message"])
                return {"CANCELLED"}
        except (json.JSONDecodeError, requests.exceptions.ConnectionError) as ex:
            self.report({"ERROR"}, "Server seems to be disconnected ... ")
            connected = False


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
