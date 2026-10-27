"""UE 5.5+ editor plugin. All generated assets are tagged; user assets are preserved."""
import json
from pathlib import Path
import traceback

import unreal
from smart_fbx_core import asset_id, choose_textures, fbx_summary

OWNER = 'SmartFbxMaterials'
VERSION = '1.0.0'
_busy = False
_subsystem = None


def settings():
    defaults = {'automatic_repair': True, 'flip_normal_green': True,
                'destination': '/Game/SmartFBX', 'source_fbx': '',
                'overrides': {}, 'material_overrides': {}, 'masked': False,
                'two_sided': False}
    path = Path(unreal.Paths.project_saved_dir()) / OWNER / 'settings.json'
    if path.is_file():
        defaults.update(json.loads(path.read_text(encoding='utf-8-sig')))
    return defaults


def _tag(asset, key, value):
    unreal.EditorAssetLibrary.set_metadata_tag(asset, OWNER + '_' + key, str(value))


def _get_tag(asset, key):
    return unreal.EditorAssetLibrary.get_metadata_tag(asset, OWNER + '_' + key)


def _save(asset):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Save failed: ' + asset.get_path_name())


def _owned_existing(path):
    obj = unreal.EditorAssetLibrary.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if obj and _get_tag(obj, 'Owner') != OWNER:
        raise RuntimeError('Refusing to replace a user asset: ' + path)
    return obj


def _import_texture(source, destination, role, cfg):
    name = 'T_' + asset_id(Path(source).name) + '_' + role
    existing = _owned_existing(destination + '/' + name)
    if not existing and unreal.EditorAssetLibrary.does_directory_exist(destination):
        # Interchange may sanitize or ignore destination_name. Resolve by provenance.
        matches = []
        for path in unreal.EditorAssetLibrary.list_assets(destination, recursive=False):
            candidate = unreal.EditorAssetLibrary.load_asset(path)
            if (isinstance(candidate, unreal.Texture2D) and _get_tag(candidate, 'Owner') == OWNER
                    and _get_tag(candidate, 'Source') == str(Path(source).resolve())
                    and (_get_tag(candidate, 'Role') == role
                         or candidate.get_name().endswith('_' + role))):
                matches.append(candidate)
        if len(matches) > 1:
            raise RuntimeError('Multiple generated textures for source and role: ' + source)
        existing = matches[0] if matches else None
    stamp = str(Path(source).stat().st_mtime_ns)
    if existing and _get_tag(existing, 'Source') != str(Path(source).resolve()):
        raise RuntimeError('Texture source collision: ' + source)
    if existing and _get_tag(existing, 'SourceStamp') == stamp:
        texture = existing
    else:
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', source)
        task.set_editor_property('destination_path', destination)
        task.set_editor_property('destination_name', existing.get_name() if existing else name)
        task.set_editor_property('automated', True)
        task.set_editor_property('factory', unreal.TextureFactory())
        task.set_editor_property('replace_existing', bool(existing))
        task.set_editor_property('save', False)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        objects = task.get_objects()
        texture = next((obj for obj in objects if isinstance(obj, unreal.Texture2D)), None)
        if not texture:
            raise RuntimeError('Texture importer returned no Texture2D: ' + source)
    texture.set_editor_property('srgb', role in ('base_color', 'emissive'))
    compression = (unreal.TextureCompressionSettings.TC_NORMALMAP if role == 'normal'
                   else unreal.TextureCompressionSettings.TC_DEFAULT if role in ('base_color', 'emissive')
                   else unreal.TextureCompressionSettings.TC_MASKS)
    texture.set_editor_property('compression_settings', compression)
    if role == 'normal':
        texture.set_editor_property('flip_green_channel', bool(cfg['flip_normal_green']))
    _tag(texture, 'Owner', OWNER)
    _tag(texture, 'Source', str(Path(source).resolve()))
    _tag(texture, 'Role', role)
    _tag(texture, 'SourceStamp', stamp)
    _save(texture)
    return texture


def _build_material(name, textures, destination, cfg):
    asset_name = 'M_' + asset_id(name)
    material = _owned_existing(destination + '/' + asset_name)
    if not material:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name, destination, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError('Cannot create material: ' + asset_name)
    lib = unreal.MaterialEditingLibrary
    lib.delete_all_material_expressions(material)
    lib.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    material.set_editor_property('two_sided', bool(cfg['two_sided']))
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED if cfg['masked'] else unreal.BlendMode.BLEND_OPAQUE)
    scalar_roles = {'metallic': unreal.MaterialProperty.MP_METALLIC,
                    'roughness': unreal.MaterialProperty.MP_ROUGHNESS,
                    'ao': unreal.MaterialProperty.MP_AMBIENT_OCCLUSION}
    property_roles = {'base_color': unreal.MaterialProperty.MP_BASE_COLOR,
                      'normal': unreal.MaterialProperty.MP_NORMAL,
                      'emissive': unreal.MaterialProperty.MP_EMISSIVE_COLOR}
    for index, (role, texture) in enumerate(sorted(textures.items())):
        if role == 'opacity' and not cfg['masked']:
            continue
        expr = lib.create_material_expression(material, unreal.MaterialExpressionTextureSample, -600, index * 220)
        expr.set_editor_property('texture', texture)
        expr.set_editor_property('sampler_type',
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if role == 'normal' else
            unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if role in ('base_color', 'emissive') else
            unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        if role in property_roles:
            if not lib.connect_material_property(expr, 'RGB', property_roles[role]):
                raise RuntimeError('Cannot connect material texture: ' + role)
        elif role in scalar_roles:
            if not lib.connect_material_property(expr, 'R', scalar_roles[role]):
                raise RuntimeError('Cannot connect scalar texture: ' + role)
        elif role == 'opacity':
            lib.connect_material_property(expr, 'R', unreal.MaterialProperty.MP_OPACITY_MASK)
        elif role in ('orm', 'rma'):
            channels = {'orm': (('R', 'ao'), ('G', 'roughness'), ('B', 'metallic')),
                        'rma': (('R', 'roughness'), ('G', 'metallic'), ('B', 'ao'))}
            for channel, target in channels[role]:
                if target not in textures:
                    lib.connect_material_property(expr, channel, scalar_roles[target])
    lib.recompile_material(material)
    _tag(material, 'Owner', OWNER)
    _tag(material, 'Version', VERSION)
    _save(material)
    return material


def source_filename(mesh):
    data = mesh.get_editor_property('asset_import_data')
    if data:
        names = data.extract_filenames()
        return names[0] if names else ''
    return ''


def repair_mesh(mesh, source=None, cfg=None):
    if not isinstance(mesh, (unreal.StaticMesh, unreal.SkeletalMesh)):
        return None
    cfg = cfg or settings()
    source = str(Path(source or source_filename(mesh)).resolve())
    if not Path(source).is_file() or Path(source).suffix.lower() != '.fbx':
        return None
    static = isinstance(mesh, unreal.StaticMesh)
    slots = list(mesh.get_editor_property('static_materials' if static else 'materials'))
    if not slots:
        raise RuntimeError('Mesh has no material slots: ' + mesh.get_path_name())
    folder = mesh.get_path_name().split('.')[0].rsplit('/', 1)[0]
    destination = folder + '/SmartMaterials/' + asset_id(Path(source).stem)
    report = {'mesh': mesh.get_path_name(), 'source': source, 'materials': [], 'warnings': []}
    for index, slot in enumerate(slots):
        name = str(slot.get_editor_property('imported_material_slot_name'))
        if name in ('None', ''):
            name = str(slot.get_editor_property('material_slot_name'))
        overrides = dict(cfg.get('overrides', {}))
        overrides.update(cfg.get('material_overrides', {}).get(name, {}))
        matches, warnings = choose_textures(source, name, len(slots), overrides)
        report['warnings'].extend(warnings)
        if not matches:
            report['warnings'].append('No unambiguous textures for slot ' + name)
            continue
        textures = {role: _import_texture(path, destination + '/Textures', role, cfg)
                    for role, path in matches.items()}
        material = _build_material(name, textures, destination, cfg)
        if static:
            mesh.set_material(index, material)
        else:
            slot.set_editor_property('material_interface', material)
            slots[index] = slot
        report['materials'].append({'slot': index, 'name': name,
                                    'material': material.get_path_name(), 'textures': matches})
    if not static:
        mesh.set_editor_property('materials', slots)
        skeleton = mesh.get_editor_property('skeleton')
        if skeleton:
            _save(skeleton)
    _save(mesh)
    for warning in report['warnings']:
        unreal.log_warning('[SmartFBX] ' + warning)
    log_dir = Path(unreal.Paths.project_saved_dir()) / OWNER
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / (asset_id(Path(source).stem) + '_report.json')).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def import_fbx(filename, destination=None, cfg=None):
    global _busy
    if _busy:
        raise RuntimeError('An import is already active')
    cfg = cfg or settings()
    filename = str(Path(filename).resolve())
    if not Path(filename).is_file() or Path(filename).suffix.lower() != '.fbx':
        raise ValueError('Select an existing FBX file')
    summary = fbx_summary(filename)
    destination = destination or cfg['destination'] + '/' + asset_id(Path(filename).stem)
    if not destination.startswith('/Game/') or '..' in destination or '.' in destination:
        raise ValueError('Destination must be a /Game/ package folder')
    task = unreal.AssetImportTask()
    options = unreal.FbxImportUI()
    skinned = summary['skinned']
    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH if skinned else unreal.FBXImportType.FBXIT_STATIC_MESH)
    options.set_editor_property('import_as_skeletal', skinned)
    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_animations', False)
    options.set_editor_property('create_physics_asset', False)
    if not skinned:
        options.static_mesh_import_data.set_editor_property('combine_meshes', False)
    for key, value in {'filename': filename, 'destination_path': destination,
                       'destination_name': ('SK_' if skinned else 'SM_') + asset_id(Path(filename).stem),
                       'automated': True, 'replace_existing': False, 'save': False,
                       'factory': unreal.FbxFactory(), 'options': options}.items():
        task.set_editor_property(key, value)
    _busy = True
    try:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        meshes = [obj for obj in task.get_objects() if isinstance(obj, (unreal.StaticMesh, unreal.SkeletalMesh))]
        if not meshes:
            raise RuntimeError('FBX import returned no meshes. See Output Log.')
        reports = [repair_mesh(mesh, filename, cfg) for mesh in meshes]
        for obj in task.get_objects():
            _save(obj)
        unreal.log('[SmartFBX] IMPORT_OK ' + json.dumps(reports, ensure_ascii=False))
        return reports
    finally:
        _busy = False


def repair_selected():
    global _busy
    _busy = True
    try:
        return [repair_mesh(obj) for obj in unreal.EditorUtilityLibrary.get_selected_assets()
                if isinstance(obj, (unreal.StaticMesh, unreal.SkeletalMesh))]
    finally:
        _busy = False


def import_dialog():
    # Tk is bundled with Epic's Windows Python distribution. No package installation.
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
            filename = filedialog.askopenfilename(title='Smart FBX Materials', filetypes=[('FBX models', '*.fbx')])
        finally:
            root.destroy()
        if filename:
            import_fbx(filename)
    except Exception:
        unreal.log_error('[SmartFBX] ' + traceback.format_exc())
        unreal.EditorDialog.show_message('Smart FBX Materials', 'Import failed. See Output Log. You can also call smart_fbx_materials.import_fbx(path) in Python.', unreal.AppMsgType.OK)


def _post_import(factory, asset):
    global _busy
    if _busy or not isinstance(asset, (unreal.StaticMesh, unreal.SkeletalMesh)):
        return
    try:
        cfg = settings()
        if cfg['automatic_repair']:
            _busy = True
            repair_mesh(asset, cfg=cfg)
    except Exception:
        unreal.log_warning('[SmartFBX] Automatic repair failed; original mesh retained. ' + traceback.format_exc())
    finally:
        _busy = False


def register_menus():
    menus = unreal.ToolMenus.get()
    menu = menus.extend_menu('LevelEditor.MainMenu.Tools').add_sub_menu(
        OWNER, 'Tools', OWNER, 'Smart FBX Materials')
    for name, label, command in (
            ('Import', 'Import FBX + PBR Materials...', 'import smart_fbx_materials as s; s.import_dialog()'),
            ('Repair', 'Repair Selected Mesh Materials', 'import smart_fbx_materials as s; s.repair_selected()')):
        entry = unreal.ToolMenuEntry(name=OWNER + name, type=unreal.MultiBlockType.MENU_ENTRY)
        entry.set_label(label)
        entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, '', command)
        menu.add_menu_entry('SmartFBX', entry)
    menus.refresh_all_widgets()


def startup():
    global _subsystem
    if _subsystem is not None:
        return
    _subsystem = unreal.get_editor_subsystem(unreal.ImportSubsystem)
    _subsystem.on_asset_post_import.add_callable(_post_import)
    command_line = unreal.SystemLibrary.get_command_line().lower()
    if '-unattended' not in command_line and '-run=' not in command_line:
        register_menus()
    unreal.log('[SmartFBX] Plugin ready ' + VERSION)
