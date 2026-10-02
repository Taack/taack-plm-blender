import bpy, os, requests, uuid, sys, getpass, json, datetime, time, zipfile, subprocess
import hashlib, tempfile

from bpy.props import (StringProperty,
                       PointerProperty,
                       )

from bpy.types import (Panel,
                       PropertyGroup,
                       Operator,
                       )
from io import BytesIO
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
            self.report({"ERROR"}, "Connection failed with an unexpected error: " + str(sys.exc_info()[0]))

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

        print("create_missing_uuid " + obj['taack_id'])

    def compute_file_shaOne(self, filePath):
        sha1 = hashlib.sha1()
        with open(filePath, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha1.update(data)

        return sha1.hexdigest()


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
            plm_file.label = obj.filepath
            if obj.filepath.endswith(".blend"):
                subprocess.run(["blender-thumbnailer", filepath, "taack-preview/br.png"])
                plm_file.filePreview = open("taack-preview/br.png", 'rb').read()
                os.remove("taack-preview/br.png")

            s = os.stat(filepath)
            plm_file.cTimeNs = s.st_ctime_ns
            plm_file.uTimeNs = s.st_mtime_ns
            plm_file.name = obj.name
            plm_file.fileName = filepath
            #plm_file.lastModifiedDate = str(datetime.datetime.strptime(os.path.getctime(bpy.data.filepath), "%a %b %d %H:%M:%S %Y"))
            #plm_file.lastModifiedBy = str(datetime.datetime.strptime(os.path.getctime(bpy.data.filepath), "%a %b %d %H:%M:%S %Y"))
            plm_file.lastModifiedDate = str(datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).strftime(simpleDateFormat))
            plm_file.createdDate = str(datetime.datetime.fromtimestamp(os.path.getctime(filepath)).strftime(simpleDateFormat))
            # plm_file.fileContent = open(filepath, 'rb').read()
            plm_file.sha1hex = self.compute_file_shaOne(filepath)
            self.shaOneMap[plm_file.sha1hex] = filepath
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

        self.shaOneMap = dict()
        deps = bpy.context.evaluated_depsgraph_get()
        filepath_set = set()
        wm = context.window_manager
        progress = 0
        steps = 10 + 2 * len(deps.ids)
        wm.progress_begin(0, steps)
        self.create_missing_uuid(bpy.context.scene, False)
        bpy.ops.wm.save_mainfile()
        filepath_set.add(bpy.data.filepath)
        bucket = PlmBuf.Bucket()
        plm_file = PlmBuf.PlmFile()
        s = os.stat(bpy.data.filepath)
        plm_file.cTimeNs = s.st_ctime_ns
        plm_file.uTimeNs = s.st_mtime_ns
        plm_file.name = bpy.context.active_object.name
        plm_file.fileName = bpy.data.filepath
        plm_file.createdBy = getpass.getuser()
        plm_file.label = os.path.basename(bpy.data.filepath)
        plm_file.id = bpy.context.scene['taack_id']

        bpy.context.scene.render.image_settings.file_format = 'WEBP'
        bpy.context.scene.render.filepath = "taack-preview/br.webp"
        bpy.ops.render.opengl(write_still=True)
        plm_file.filePreview = open("taack-preview/br.webp", 'rb').read()
        os.remove("taack-preview/br.webp")
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
            progress += 1
            wm.progress_update(progress)

        os.rmdir("taack-preview")
        # plm_file.fileContent = open(bpy.data.filepath, 'rb').read()
        plm_file.sha1hex = self.compute_file_shaOne(bpy.data.filepath)
        bucket.plmFiles[plm_file.name].CopyFrom(plm_file)
        self.shaOneMap[plm_file.sha1hex] = bpy.data.filepath

        print(filepath_set)
        if len(filepath_set) == 0:
            self.report({"ERROR"}, "Filset path set is empty")
            return {"CANCELLED"}

        tmp_zip_dir = tempfile.TemporaryDirectory()
        print("tmp_zip_dir: " + tmp_zip_dir.name)
        zip_proto_filename = os.path.join(tmp_zip_dir.name, "tmp-blender-proto-" + str(round(time.time() * 1000)) + ".zip")

        with zipfile.ZipFile(file=zip_proto_filename, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
                             ) as zip_proto_archive:
            zip_proto_archive.writestr("proto.bin", bucket.SerializeToString())

        progress += 10
        wm.progress_update(progress)

        data = {"ajax": 'true'}
        zip_proto_file = open(zip_proto_filename, 'rb')

        taack_prefs = context.preferences.addons[TaackPlmPreferences.bl_idname].preferences
        try:
            r = taackIntranetSession.post(url=taack_prefs.serverUrl + 'plmProto/uploadProto', files={'proto.bin': zip_proto_file}, data=data)

            resp_bytes = BytesIO(r.content).read()
            resp_bucket = PlmBuf.Bucket()
            resp_bucket.ParseFromString(resp_bytes)

            if resp_bucket.status == PlmBuf.ServerStatus.OK_PROTO:
                for serverSha1File in resp_bucket.serverSha1Files:
                    if serverSha1File in self.shaOneMap:
                        progress += 1
                        wm.progress_update(progress)
                        print("Removing:" + self.shaOneMap.pop(serverSha1File) + " from files to upload ... " + serverSha1File)
                    else:
                        print("NO KEY:" + serverSha1File + " ... ")
                nb_items = len(self.shaOneMap.items())
                nb16_interval = nb_items // 16
                print("nbItems: " + str(nb_items))
                if nb_items > 0:
                    for i in range(nb16_interval + 1):
                        zip_files_filename = os.path.join(tmp_zip_dir.name, "tmp-blender-16files" + str(i) + "-" + str(round(time.time() * 1000)) + ".zip")
                        with zipfile.ZipFile(file=zip_files_filename, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
                                             ) as zip_archive:
                            for j in range(16):
                                if len(self.shaOneMap) > 0:
                                    e_sha_one, filename = self.shaOneMap.popitem()
                                    zip_archive.write(filename, e_sha_one)
                                    progress += 1
                                    wm.progress_update(progress)

                        zip_files_file = open(zip_files_filename, 'rb')
                        try:
                            r = taackIntranetSession.post(url=taack_prefs.serverUrl + 'plmProto/uploadZip', files={'proto.bin': zip_files_file}, data=data)
                            resp_bytes = BytesIO(r.content).read()
                            resp_bucket = PlmBuf.Bucket()
                            resp_bucket.ParseFromString(resp_bytes)
                            if resp_bucket.status != PlmBuf.ServerStatus.OK_FILES:
                                self.report({"ERROR"}, "Message does not successfully sent: " + r.json()["message"])
                                return {"CANCELLED"}
                        except Exception as ex:
                            self.report({"ERROR"}, "Server seems to be disconnected ... ")
                            connected = False
                        finally:
                            zip_files_file.close()
                            #os.remove(zip_proto_filename)
                wm.progress_update(steps)
                r = taackIntranetSession.post(url=taack_prefs.serverUrl + 'plmProto/reset', data=data)
                wm.progress_end()
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, "Message does not successfully sent: " + r.json()["message"])
                return {"CANCELLED"}
        except (json.JSONDecodeError, requests.exceptions.ConnectionError) as ex:
            self.report({"ERROR"}, "Server seems to be disconnected ... ")
            connected = False
        finally:
            zip_proto_file.close()
            #os.remove(zip_proto_filename)
            tmp_zip_dir.cleanup()


# class TaackPlmForkRecent(Operator):
#     bl_label = "Duplicate History"
#     bl_idname = "taack.plm_fork_recent"
#     bl_description = "Create a new history for this model"
#
#     def execute(self, context):
#         self.report({"INFO"}, "Forked model, you can upload!")
#         return {"FINISHED"}


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
            op_row_connect.enabled = True
        else:
            op_row_upload.enabled = False
            op_row_connect.enabled = True
        op_row_connect.operator("taack.plm_fork_connect", icon_value=taackIcons["taack_plm"].icon_id)
        op_row_upload.operator("taack.plm_fork_upload", icon="FILE_REFRESH")
        #layout.operator("taack.plm_fork_recent", icon="COPY_ID")


# Register/unregister
classes = (
    TaackPlmPreferences,
    TaackPlmProperties,
    TaackPlmConnect,
    TaackPlmUpload,
    # TaackPlmForkRecent,
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


# pip download protobuf --dest ./wheels
# blender --command extension build
