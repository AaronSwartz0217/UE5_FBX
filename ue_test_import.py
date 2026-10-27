"""Execute with UnrealEditor-Cmd -ExecutePythonScript=...; no scene changes."""
import json
import os
import shutil
from pathlib import Path
import unreal
import smart_fbx_materials as bridge

bridge.register_menus()

source = os.environ.get('SMART_FBX_TEST_SOURCE', '')
if not source or not Path(source).is_file():
    raise RuntimeError('Set SMART_FBX_TEST_SOURCE to an existing skinned FBX with one material slot and four PBR maps')
source = str(Path(source).resolve())
destination = '/Game/SmartFBX_Verification/BronzeSoldierValidated'
mesh_path = destination + '/SK_' + bridge.asset_id(Path(source).stem)
existing = unreal.load_asset(mesh_path) if unreal.EditorAssetLibrary.does_asset_exist(mesh_path) else None
reports = [bridge.repair_mesh(existing, source)] if existing else bridge.import_fbx(source, destination)
assert reports and reports[0]['materials'], 'No assigned materials'
roles = set(reports[0]['materials'][0]['textures'])
assert {'base_color', 'normal', 'metallic', 'roughness'} <= roles, roles
mesh = unreal.load_asset(reports[0]['mesh'])
assert isinstance(mesh, unreal.SkeletalMesh), 'Skinned sample must keep its skeleton'
assert mesh.get_editor_property('skeleton'), 'Skeleton missing'
assert unreal.EditorAssetLibrary.does_asset_exist(mesh.get_editor_property('skeleton').get_path_name()), 'Skeleton not persisted'
material = mesh.get_editor_property('materials')[0].material_interface
properties = (unreal.MaterialProperty.MP_BASE_COLOR, unreal.MaterialProperty.MP_NORMAL,
              unreal.MaterialProperty.MP_METALLIC, unreal.MaterialProperty.MP_ROUGHNESS)
nodes = [unreal.MaterialEditingLibrary.get_material_property_input_node(material, prop)
         for prop in properties]
assert all(nodes), 'Missing material input connections'
textures = [node.get_editor_property('texture') for node in nodes]
assert len(textures) == 4, 'Expected four material textures'
before_assets = sorted(unreal.EditorAssetLibrary.list_assets(destination, recursive=True))
bridge.repair_mesh(mesh, source)
assert before_assets == sorted(unreal.EditorAssetLibrary.list_assets(destination, recursive=True)), 'Repair duplicated assets'
assert mesh.get_editor_property('materials')[0].material_interface == material, 'Material reference changed'
for texture in textures:
    name = texture.get_name()
    if name.endswith('_normal'):
        assert not texture.srgb
        assert texture.compression_settings == unreal.TextureCompressionSettings.TC_NORMALMAP
        assert texture.flip_green_channel
    elif name.endswith(('_metallic', '_roughness')):
        assert not texture.srgb
    elif name.endswith('_base_color'):
        assert texture.srgb
result = {'engine': unreal.SystemLibrary.get_engine_version(), 'mesh': mesh.get_path_name(),
          'material': material.get_path_name(), 'texture_count': len(textures), 'reports': reports}
path = Path(unreal.Paths.project_saved_dir()) / 'SmartFbxMaterials' / 'verification.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('SMART_FBX_VERIFIED ' + str(path))

# Static-mesh branch: export Epic's test cube, then import with explicit sample maps.
fixture = Path(unreal.Paths.project_saved_dir()).resolve() / 'SmartFbxMaterials' / 'StaticCube.fbx'
export_task = unreal.AssetExportTask()
export_task.object = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
export_task.filename = str(fixture)
export_task.automated = True
export_task.prompt = False
export_task.replace_identical = True
export_task.exporter = unreal.StaticMeshExporterFBX()
assert unreal.Exporter.run_asset_export_task(export_task), 'Static test fixture export failed'
static_destination = '/Game/SmartFBX_Verification/StaticCube'
static_path = static_destination + '/SM_' + bridge.asset_id('StaticCube')
existing_static = unreal.load_asset(static_path) if unreal.EditorAssetLibrary.does_asset_exist(static_path) else None
cfg = bridge.settings()
cfg['overrides'] = reports[0]['materials'][0]['textures']
static_reports = [bridge.repair_mesh(existing_static, str(fixture), cfg)] if existing_static else bridge.import_fbx(str(fixture), static_destination, cfg)
static_mesh = unreal.load_asset(static_reports[0]['mesh'])
assert isinstance(static_mesh, unreal.StaticMesh), 'Static cube imported as wrong type'
assert static_reports[0]['materials'], 'Static mesh material binding missing'
unreal.log('SMART_FBX_STATIC_VERIFIED ' + static_mesh.get_path_name())

# Exercise the public ImportSubsystem hook via a regular import, outside bridge.import_fbx.
for role, image_path in reports[0]['materials'][0]['textures'].items():
    suffix = Path(image_path).suffix
    role_name = 'basecolor' if role == 'base_color' else role
    shutil.copy2(image_path, fixture.parent / ('PBR_' + role_name + suffix))
automatic_path = '/Game/SmartFBX_Verification/AutomaticCube/AutoCube'
if unreal.EditorAssetLibrary.does_asset_exist(automatic_path):
    automatic_mesh = unreal.load_asset(automatic_path)
    bridge._post_import(None, automatic_mesh)
else:
    task = unreal.AssetImportTask()
    task.filename = str(fixture)
    task.destination_path = '/Game/SmartFBX_Verification/AutomaticCube'
    task.destination_name = 'AutoCube'
    task.automated = True
    task.factory = unreal.FbxFactory()
    task.options = unreal.FbxImportUI()
    task.options.automated_import_should_detect_type = False
    task.options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    task.options.import_materials = False
    task.options.import_textures = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    automatic_mesh = next(obj for obj in task.get_objects() if isinstance(obj, unreal.StaticMesh))
assert bridge._get_tag(automatic_mesh.get_material(0), 'Owner') == bridge.OWNER, 'Automatic import hook did not bind material'
unreal.log('SMART_FBX_AUTOMATIC_VERIFIED ' + automatic_mesh.get_path_name())
result['static_mesh'] = static_mesh.get_path_name()
result['automatic_mesh'] = automatic_mesh.get_path_name()
result['tests'] = ['menu_registration', 'skeletal_import', 'skeleton_saved', 'four_pbr_inputs',
                   'srgb_and_compression', 'normal_green', 'repeat_repair_no_duplicates',
                   'static_mesh_import', 'automatic_post_import_callback']
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
