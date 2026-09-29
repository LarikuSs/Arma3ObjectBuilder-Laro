import traceback
import os
import re
import struct

import bpy
import mathutils

from .. import get_icon
from ..utilities import generic as utils
from ..utilities import lod as lodutils
from ..utilities import compat as computils
from ..io import import_p3d


# ---------------------------------------------------------------------------
# NH Proxy Tool integration
# ---------------------------------------------------------------------------
# The functions below are intentionally kept equivalent to the original
# NH Proxy Tool implementation. They are integrated into A3OB's existing
# Proxies panel without changing the proxy creation algorithm.

KEY = "cray_source_p3d"


def _nh_norm(p):
    if not p:
        return ""
    try:
        p = bpy.path.abspath(str(p))
    except Exception:
        p = str(p)
    return os.path.normpath(p)


def _nh_stripnum(s):
    s = (s or "").strip()
    while re.search(r"\.\d{3}$", s):
        s = re.sub(r"\.\d{3}$", "", s)
    return s


def _nh_basename_key(s):
    s = _nh_stripnum(os.path.basename(str(s).replace("\\", "/")))
    if s.lower().endswith(".p3d"):
        s = s[:-4]
    return s.lower()


def _nh_findp3d(root, key):
    root = _nh_norm(root)
    if not root or not os.path.isdir(root) or not key:
        return []

    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [x for x in dn if x not in {".git", "__pycache__"}]
        for f in fn:
            if f.lower().endswith(".p3d") and _nh_basename_key(f) == key:
                out.append(os.path.join(dp, f))

    out.sort(key=lambda x: (len(x), x.lower()))
    return out


def _nh_name_candidates(o):
    seen = set()

    def add(v):
        k = _nh_basename_key(v)
        if k and k not in seen:
            seen.add(k)
            return k

    for item in (o, getattr(o, "instance_collection", None)):
        if item:
            k = add(getattr(item, "name", ""))
            if k:
                yield k

    p = getattr(o, "parent", None)
    while p:
        k = add(getattr(p, "name", ""))
        if k:
            yield k

        inst = getattr(p, "instance_collection", None)
        if inst:
            k = add(getattr(inst, "name", ""))
            if k:
                yield k

        p = getattr(p, "parent", None)

    for c in getattr(o, "users_collection", []) or []:
        k = add(getattr(c, "name", ""))
        if k:
            yield k


def _nh_tagged_paths(o):
    out = []

    def add(item):
        if item is None:
            return
        try:
            p = item.get(KEY, "")
            if p:
                out.append(_nh_norm(p))
        except Exception:
            pass

    add(o)

    try:
        add(o.instance_collection)
    except Exception:
        pass

    p = getattr(o, "parent", None)
    while p:
        add(p)
        try:
            add(p.instance_collection)
        except Exception:
            pass
        p = getattr(p, "parent", None)

    for c in getattr(o, "users_collection", []) or []:
        add(c)

    return out


def _nh_resolve_nh(o, root):
    # Kept from the original NH Proxy Tool:
    # resolve the selected asset's own name first.
    for k in _nh_name_candidates(o):
        ms = _nh_findp3d(root, k)
        if len(ms) == 1:
            return ms[0]
        if len(ms) > 1:
            return None, f"{k}.p3d has {len(ms)} matches"

    # Fallback to the explicit NH source tag.
    candidates = set(_nh_name_candidates(o))
    for p in _nh_tagged_paths(o):
        if not candidates or _nh_basename_key(p) in candidates:
            return p

    return None, "NH source P3D could not be resolved"


def _nh_islod(o):
    try:
        return bool(o.a3ob_properties_object.is_a3_lod)
    except Exception:
        return False


def _nh_isproxy(o):
    try:
        return bool(o.a3ob_properties_object_proxy.is_a_proxy)
    except Exception:
        return False


def _nh_lodfilename(o):
    for raw in (
        getattr(o, "name", ""),
        getattr(getattr(o, "data", None), "name", "")
    ):
        n = _nh_stripnum(raw)
        if n.lower().endswith(".p3d"):
            return n
    return ""


def _nh_proxy_mesh():
    # Kept from the original NH Proxy Tool.
    m = bpy.data.meshes.get("NH_ProxyTool_A3OB_Proxy")
    if not m:
        m = bpy.data.meshes.new("NH_ProxyTool_A3OB_Proxy")
        m.from_pydata(
            [(0.0, 0.0, 0.0), (0.0, 0.0, 2.0), (0.0, 1.0, 0.0)],
            [],
            [(0, 1, 2)]
        )
        m.update(calc_edges=True)
    return m


def _nh_nextidx(parent):
    used = set()

    for o in bpy.data.objects:
        if o.parent != parent:
            continue
        try:
            if o.a3ob_properties_object_proxy.is_a_proxy:
                used.add(int(o.a3ob_properties_object_proxy.proxy_index))
        except Exception:
            pass

    i = 1
    while i in used:
        i += 1
    return i


def _nh_arma_path(p):
    p = _nh_norm(p).replace("/", "\\")
    if p.lower().startswith("p:\\"):
        return p

    while p.startswith("\\"):
        p = p[1:]

    return "P:\\" + p


def _nh_setproxy(pr, path, i):
    try:
        pg = pr.a3ob_properties_object_proxy
    except Exception as e:
        raise RuntimeError("A3OB is not enabled.") from e

    pg.is_a_proxy = True
    pg.proxy_path = _nh_arma_path(path)
    pg.proxy_index = i
    pr.display_type = "WIRE"
    pr.show_name = True
    pr.name = f"proxy: {os.path.splitext(os.path.basename(path))[0]} {i}"
    pr.data.name = pr.name

    try:
        pr.a3ob_properties_object.is_a_lod = False
    except Exception:
        pass


def _nh_create_proxy(source, target, path):
    # IMPORTANT: this is the original NH Proxy Tool creation logic.
    # Do not replace with A3OB's generic create_proxy() utility: the NH tool
    # intentionally preserves the source world transform and then parents
    # the new proxy to the selected target LOD.
    col = (
        target.users_collection[0]
        if target.users_collection
        else bpy.context.scene.collection
    )
    pr = bpy.data.objects.new("NH Proxy", _nh_proxy_mesh())
    col.objects.link(pr)

    # Preserve the exact world transform of the placed NH asset/extracted LOD.
    # Parent is assigned without altering that world transform.
    pr.matrix_world = source.matrix_world.copy()
    pr.parent = target
    try:
        pr.matrix_parent_inverse = target.matrix_world.inverted()
    except Exception:
        pass

    i = _nh_nextidx(target)
    _nh_setproxy(pr, path, i)
    pr["nh_proxy_source_object"] = source.name
    pr["nh_proxy_source_p3d"] = _nh_arma_path(path)
    return pr


class A3OB_ProxyCreateSettings(bpy.types.PropertyGroup):
    target_lod: bpy.props.PointerProperty(
        name="Target LOD",
        type=bpy.types.Object
    )
    p3d_root: bpy.props.StringProperty(
        name="P3D Search Root",
        subtype="DIR_PATH",
        default="P:\\"
    )
    delete_originals: bpy.props.BoolProperty(
        name="Delete originals",
        default=True
    )


class A3OB_OT_proxy_create(bpy.types.Operator):
    """Convert selected NH assets / extracted A3OB LODs to A3OB proxies."""

    bl_idname = "a3ob.proxy_create"
    bl_label = "Create Proxy"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        settings = context.scene.a3ob_proxy_create_settings
        target = settings.target_lod

        if not target:
            self.report({"ERROR"}, "Choose Target LOD first.")
            return {"CANCELLED"}

        if not _nh_islod(target):
            self.report({"ERROR"}, "Target must be an A3OB LOD object.")
            return {"CANCELLED"}

        sources = []
        bad = []

        for o in list(context.selected_objects):
            if o == target or _nh_isproxy(o):
                continue

            if _nh_islod(o):
                n = _nh_lodfilename(o)
                if not n:
                    bad.append(o.name + ": P3D filename not found")
                    continue

                ms = _nh_findp3d(
                    settings.p3d_root,
                    _nh_basename_key(n)
                )

                if len(ms) == 1:
                    sources.append((o, ms[0]))
                elif not ms:
                    bad.append(o.name + ": " + n + " not found")
                else:
                    bad.append(
                        o.name + ": " + n + " has multiple matches"
                    )
            else:
                r = _nh_resolve_nh(o, settings.p3d_root)

                if isinstance(r, tuple):
                    bad.append(o.name + ": " + r[1])
                elif r:
                    sources.append((o, r))
                else:
                    bad.append(o.name + ": NH source P3D not found")

        if not sources:
            self.report({"ERROR"}, "No convertible selected objects found.")
            return {"CANCELLED"}

        made = []
        failed = []

        for o, p in sources:
            try:
                made.append((o, _nh_create_proxy(o, target, p)))
            except Exception as e:
                failed.append(o.name + ": " + str(e))

        if settings.delete_originals:
            for o, _ in made:
                if o.name in bpy.data.objects:
                    try:
                        bpy.data.objects.remove(o, do_unlink=True)
                    except Exception:
                        pass

        bpy.ops.object.select_all(action="DESELECT")

        for _, p in made:
            p.select_set(True)

        if made:
            context.view_layer.objects.active = made[-1][1]

        issues = bad + failed

        if issues:
            self.report(
                {"WARNING"},
                f"Created {len(made)} proxies; {len(issues)} skipped/failed. "
                f"{issues[0]}"
            )
        else:
            self.report(
                {"INFO"},
                f"Created {len(made)} A3OB proxies."
            )

        return {"FINISHED"}


class A3OB_OT_proxy_browse_root(bpy.types.Operator):
    """Choose the root folder used to find source P3D files."""

    bl_idname = "a3ob.proxy_browse_root"
    bl_label = "Browse P3D Root"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        context.scene.a3ob_proxy_create_settings.p3d_root = self.directory
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class A3OB_OT_proxy_realign_ocs(bpy.types.Operator):
    """Realign the proxy object coordinate system with proxy directions"""
    
    bl_idname = "a3ob.proxy_realign_ocs"
    bl_label = "Realign Coordinate System"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.mode == 'OBJECT' and len(context.selected_objects) == 1 and obj.type == 'MESH' and obj.a3ob_properties_object_proxy.is_a3_proxy
    
    def execute(self, context):
        obj = context.active_object
        import_p3d.transform_proxy(obj)
            
        return {'FINISHED'}


class A3OB_OT_proxy_align(bpy.types.Operator):
    """Align the proxy object to another selected object"""
    
    bl_idname = "a3ob.proxy_align"
    bl_label = "Align To Object"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        selected = context.selected_objects
        
        if not obj or len(selected) != 2:
            return False
            
        selected.remove(obj)
        return obj.mode == 'OBJECT' and selected[0] and selected[0].mode == 'OBJECT' and selected[0].a3ob_properties_object_proxy.is_a3_proxy
    
    def execute(self, context):
        obj = context.active_object
        selected = context.selected_objects.copy()
        selected.remove(obj)
        proxy = selected[0]
        
        proxy.matrix_world = obj.matrix_world
        proxy.scale = mathutils.Vector((1, 1, 1))
                    
        return {'FINISHED'}


class A3OB_OT_proxy_align_object(bpy.types.Operator):
    """Align an object to a selected proxy object"""
    
    bl_idname = "a3ob.proxy_align_object"
    bl_label = "Align To Proxy"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        selected = context.selected_objects
        
        if not obj or len(selected) != 2:
            return False
            
        selected.remove(obj)
        return obj.mode == 'OBJECT' and obj.a3ob_properties_object_proxy.is_a3_proxy and selected[0] and selected[0].mode == 'OBJECT'
    
    def execute(self, context):
        proxy = context.active_object
        selected = context.selected_objects.copy()
        selected.remove(proxy)
        obj = selected[0]
        
        obj.matrix_world = proxy.matrix_world
        obj.scale = mathutils.Vector((1, 1, 1))
                    
        return {'FINISHED'}


class A3OB_OT_proxy_extract(bpy.types.Operator):
    """Import 1st LOD of proxy model in place of proxy object"""

    bl_idname = "a3ob.proxy_extract"
    bl_label = "Extract Proxy"
    bl_options = {'REGISTER', 'UNDO'}

    enclose: bpy.props.BoolProperty()
    groupby: bpy.props.EnumProperty(default='NONE', items=(('NONE', "", ""),))
    additional_data_allowed: bpy.props.BoolProperty(default=True)
    additional_data: bpy.props.EnumProperty(
        options = {'ENUM_FLAG'},
        items = (
            ('NORMALS', "", ""),
            ("FLAGS", "", ""),
            ('PROPS', "", ""),
            ('MASS', "", ""),
            ('SELECTIONS', "", ""),
            ('UV', "", ""),
            ('MATERIALS', "", "")
        ),
        default = {'NORMALS', 'PROPS', 'MASS', 'SELECTIONS', 'UV', 'MATERIALS'}
    )
    validate_meshes: bpy.props.BoolProperty(default=True)
    proxy_action: bpy.props.EnumProperty(items=(('SEPARATE', "", ""),), default='SEPARATE')
    first_lod_only: bpy.props.BoolProperty(default=True)
    translate_selections: bpy.props.BoolProperty()
    cleanup_empty_selections: bpy.props.BoolProperty()
    sections: bpy.props.EnumProperty(items=(("PRESERVE", "", ""),), default="PRESERVE")
    absolute_paths: bpy.props.BoolProperty(default=True)
    filepath: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        selected = context.selected_objects
        if not selected:
            return False

        # Extract can operate on one or several selected proxies.
        # Every selected object must be a valid P3D proxy with an existing .p3d file.
        for obj in selected:
            if obj.type != 'MESH' or not obj.a3ob_properties_object_proxy.is_a3_proxy:
                return False

            path = utils.abspath(obj.a3ob_properties_object_proxy.proxy_path)
            if not os.path.exists(path) or os.path.splitext(path)[1].lower() != '.p3d':
                return False

        return True

    def execute(self, context):
        proxy_objects = context.selected_objects.copy()
        extracted = 0
        failed = 0

        # read_file() clears the current selection, so keep our own copy above.
        for proxy_object in proxy_objects:
            self.filepath = utils.abspath(proxy_object.a3ob_properties_object_proxy.proxy_path)

            try:
                with open(self.filepath, "rb") as file:
                    lod_objects = import_p3d.read_file(self, context, file)

                imported_object = lod_objects[0]
                imported_object.matrix_world = proxy_object.matrix_world
                imported_object.name = os.path.basename(self.filepath)
                imported_object.data.name = os.path.basename(self.filepath)

                bpy.data.meshes.remove(proxy_object.data)
                extracted += 1

            except struct.error:
                failed += 1
                self.report({'ERROR'}, "Unexpected EndOfFile: %s (check the logs in the system console)" % self.filepath)
                traceback.print_exc()
            except Exception as ex:
                failed += 1
                self.report({'ERROR'}, "%s (check the logs in the system console)" % ex)
                traceback.print_exc()

        if failed == 0:
            self.report({'INFO'}, "Successfully extracted %d prox%s (check the logs in the system console)" %
                        (extracted, "y" if extracted == 1 else "ies"))
        else:
            self.report({'WARNING'}, "Extracted %d prox%s, %d failed (check the logs in the system console)" %
                        (extracted, "y" if extracted == 1 else "ies", failed))

        return {'FINISHED'}


class A3OB_OT_proxy_copy(bpy.types.Operator):
    """Copy proxy to LOD objects"""
    
    bl_idname = "a3ob.proxy_copy"
    bl_label = "Copy Proxy"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.mode == 'OBJECT' and len(context.selected_objects) == 1 and obj.type == 'MESH' and obj.a3ob_properties_object_proxy.is_a3_proxy
    
    def invoke(self, context, event):
        scene_props = context.scene.a3ob_proxies
        scene_props.lod_objects.clear()
        
        object_pool = context.scene.objects
        
        proxy_object = context.active_object
        parent_object = proxy_object.parent
        
        for obj in context.scene.objects:
            if obj.type != 'MESH' or not obj.a3ob_properties_object.is_a3_lod or obj.parent != None or obj == parent_object:
                continue
            
            object_props = obj.a3ob_properties_object
            
            item = scene_props.lod_objects.add()
            item.name = obj.name
            item.lod = lodutils.format_lod_name(int(object_props.lod), object_props.resolution)
            
            scene_props.lod_objects_index = len(scene_props.lod_objects) - 1
            
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        scene_props = context.scene.a3ob_proxies
        layout = self.layout
        split = layout.split(factor=0.5)
        split.label(text="Object Name")
        split.label(text="LOD Type")
        layout.template_list("A3OB_UL_lod_objects_selector", "A3OB_proxies_copy", scene_props, "lod_objects", scene_props, "lod_objects_index")
    
    def execute(self, context):
        proxy_object = context.active_object
        scene = context.scene
        scene_props = scene.a3ob_proxies
        
        target_objects = [scene.objects[item.name] for item in scene_props.lod_objects if item.enabled]
        
        for obj in target_objects:
            new_proxy = proxy_object.copy()
            new_proxy.data = proxy_object.data.copy()
            
            obj.users_collection[0].objects.link(new_proxy)
            new_proxy.matrix_parent_inverse = obj.matrix_world.inverted()
            new_proxy.parent = obj
        
        return {'FINISHED'}


class A3OB_OT_proxy_copy_all(bpy.types.Operator):
    """Copy all proxies from a LOD object to another"""
    
    bl_idname = "a3ob.proxy_copy_all"
    bl_label = "Copy Proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    keep_transform: bpy.props.BoolProperty(
        name = "Keep Transformation",
        description = "Keep the visual world space transformations",
        default = True
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        selected = [item for item in context.selected_objects if item.type == 'MESH' and item.mode == 'OBJECT' and item != obj and item.a3ob_properties_object.is_a3_lod]
        
        return obj and obj.type == 'MESH' and obj.mode == 'OBJECT' and obj.a3ob_properties_object.is_a3_lod and len(selected) == 1
    
    def execute(self, context):
        target = context.active_object
        source = [item for item in context.selected_objects if item.type == 'MESH' and item.mode == 'OBJECT' and item != target][0]
        proxies = [item for item in source.children if item.type == 'MESH' and item.a3ob_properties_object_proxy.is_a3_proxy]
        
        for item in proxies:
            new_proxy = item.copy()
            new_proxy.data = item.data.copy()
            target.users_collection[0].objects.link(new_proxy)
            ctx = {
                "selected_editable_objects": [new_proxy]
            }
            if self.keep_transform:
                computils.call_operator_ctx(bpy.ops.object.parent_clear, ctx, type='CLEAR_KEEP_TRANSFORM')
                ctx.update({
                    "active_object": target,
                    "selected_objects": [target, new_proxy],
                    "selected_editable_objects": [target, new_proxy]
                })
                computils.call_operator_ctx(bpy.ops.object.parent_set, ctx, type='OBJECT', keep_transform=True)
            else:
                computils.call_operator_ctx(bpy.ops.object.parent_clear, ctx)
                ctx.update({
                    "active_object": target,
                    "selected_objects": [target, new_proxy],
                    "selected_editable_objects": [target, new_proxy]
                })
                computils.call_operator_ctx(bpy.ops.object.parent_set, ctx, type='OBJECT')
        
        return {'FINISHED'}


class A3OB_OT_proxy_transfer(bpy.types.Operator):
    """Transfer proxies to a different LOD object"""
    
    bl_idname = "a3ob.proxy_transfer"
    bl_label = "Transfer Proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    keep_transform: bpy.props.BoolProperty(
        name = "Keep Transformation",
        description = "Keep the visual world space transformations",
        default = True
    )
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        selected = [item for item in context.selected_objects if item.type == 'MESH' and item.mode == 'OBJECT' and item != obj and item.a3ob_properties_object.is_a3_lod]
        
        return obj and obj.type == 'MESH' and obj.mode == 'OBJECT' and obj.a3ob_properties_object.is_a3_lod and len(selected) == 1
    
    def execute(self, context):
        target = context.active_object
        source = [item for item in context.selected_objects if item.type == 'MESH' and item.mode == 'OBJECT' and item != target][0]
        proxies = [item for item in source.children if item.type == 'MESH' and item.a3ob_properties_object_proxy.is_a3_proxy]
        
        for item in proxies:
            ctx = {
                "selected_editable_objects": [item]
            }
            if self.keep_transform:
                computils.call_operator_ctx(bpy.ops.object.parent_clear, ctx, type='CLEAR_KEEP_TRANSFORM')
                ctx.update({
                    "active_object": target,
                    "selected_objects": [target, item],
                    "selected_editable_objects": [target, item]
                })
                computils.call_operator_ctx(bpy.ops.object.parent_set, ctx, type='OBJECT', keep_transform=True)
            else:
                computils.call_operator_ctx(bpy.ops.object.parent_clear, ctx)
                ctx.update({
                    "active_object": target,
                    "selected_objects": [target, item],
                    "selected_editable_objects": [target, item]
                })
                computils.call_operator_ctx(bpy.ops.object.parent_set, ctx, type='OBJECT')
        
        return {'FINISHED'}
    

class A3OB_PT_proxies(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Object Builder"
    bl_label = "Proxies"
    bl_options = {'DEFAULT_CLOSED'}

    doc_url = "https://mrcmodding.gitbook.io/arma-3-object-builder/tools/proxies"
    
    @classmethod
    def poll(cls, context):
        return True
        
    def draw_header(self, context):
        utils.draw_panel_header(self)
        
    def draw(self, context):
        layout = self.layout
        
        col_align = layout.column(align=True)
        col_align.operator("a3ob.proxy_align", icon_value=get_icon("op_proxy_align"))
        col_align.operator("a3ob.proxy_align_object", icon_value=get_icon("op_proxy_align_object"))
        layout.operator("a3ob.proxy_realign_ocs", icon_value=get_icon("op_proxy_realign"))
        layout.operator("a3ob.proxy_extract", icon_value=get_icon("op_proxy_extract"))

        scene_props = context.scene.a3ob_proxy_create_settings
        box = layout.box()
        box.label(text="Create Proxy")
        box.prop(scene_props, "target_lod", text="Target")
        row = box.row(align=True)
        row.prop(scene_props, "p3d_root", text="P3D Root")
        row.operator("a3ob.proxy_browse_root", text="", icon="FILE_FOLDER")
        box.prop(scene_props, "delete_originals")
        box.operator("a3ob.proxy_create", icon="CONSTRAINT")

        col_move = layout.column(align=True)
        col_move.operator("a3ob.proxy_copy", icon_value=get_icon("op_proxy_copy"))
        col_move.operator("a3ob.proxy_copy_all", icon_value=get_icon("op_proxy_copy_all"))
        col_move.operator("a3ob.proxy_transfer", icon_value=get_icon("op_proxy_transfer"))


class A3OB_UL_lod_objects_selector(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.name)
        row.label(text=item.lod)


classes = (
    A3OB_ProxyCreateSettings,
    A3OB_OT_proxy_align,
    A3OB_OT_proxy_align_object,
    A3OB_OT_proxy_realign_ocs,
    A3OB_OT_proxy_extract,
    A3OB_OT_proxy_create,
    A3OB_OT_proxy_browse_root,
    A3OB_OT_proxy_copy,
    A3OB_OT_proxy_copy_all,
    A3OB_OT_proxy_transfer,
    A3OB_PT_proxies,
    A3OB_UL_lod_objects_selector
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.a3ob_proxy_create_settings = bpy.props.PointerProperty(
        type=A3OB_ProxyCreateSettings
    )

    print("\t" + "UI: Proxies")


def unregister():
    if hasattr(bpy.types.Scene, "a3ob_proxy_create_settings"):
        del bpy.types.Scene.a3ob_proxy_create_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("\t" + "UI: Proxies")
