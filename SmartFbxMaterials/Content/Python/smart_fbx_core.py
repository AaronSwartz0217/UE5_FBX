"""Engine-independent, bounded and deterministic texture matching. No source writes."""
import hashlib
import os
from pathlib import Path
import re
import struct

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.bmp', '.exr'}
ALIASES = {
    'base_color': ('basecolor', 'base_color', 'albedo', 'diffuse', 'tripo_rgb', '_rgb', '_color', '颜色', '底色'),
    'normal': ('normal', '_n', '_nor', '法线'),
    'roughness': ('roughness', '_rough', '_r', '粗糙'),
    'metallic': ('metallic', 'metalness', '_metal', '_m', '金属'),
    'ao': ('ambientocclusion', 'occlusion', '_ao', '环境遮蔽'),
    'emissive': ('emissive', 'emission', '_emit', '自发光'),
    'opacity': ('opacity', '_alpha', '透明'),
    'orm': ('_orm', '_arm', 'occlusionroughnessmetallic'),
    'rma': ('_rma', 'roughnessmetallicao'),
}


def asset_id(name):
    readable = re.sub(r'[^a-zA-Z0-9_]+', '_', name).strip('_')[:48] or 'Asset'
    return readable + '_' + hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]


def texture_role(path):
    name = Path(path).stem.lower()
    for role in ('orm', 'rma', 'normal', 'roughness', 'metallic', 'ao', 'emissive', 'opacity', 'base_color'):
        for alias in ALIASES[role]:
            if alias.startswith('_'):
                if re.search(re.escape(alias) + r'(?:$|[_\- .])', name):
                    return role
            elif alias in name:
                return role
    return None


def scan_textures(fbx, max_depth=3, max_files=4096):
    root = Path(fbx).resolve().parent
    found = []
    count = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not Path(directory, d).is_symlink())
        if len(Path(directory).relative_to(root).parts) >= max_depth:
            dirs[:] = []
        for filename in sorted(files):
            count += 1
            if count > max_files:
                raise ValueError('Texture search exceeds {} files; use a dedicated asset folder'.format(max_files))
            path = Path(directory, filename)
            if not path.is_symlink() and path.suffix.lower() in EXTENSIONS:
                found.append(str(path))
    return found


def choose_textures(fbx, material_name='', material_count=1, overrides=None):
    """Refuse ambiguity; a single shared texture set is safe only for one material."""
    candidates = scan_textures(fbx)
    chosen, warnings = {}, []
    for role in ALIASES:
        override = (overrides or {}).get(role)
        if override:
            path = Path(override)
            if not path.is_absolute():
                path = Path(fbx).parent / path
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                raise ValueError('Invalid {} override: {}'.format(role, path))
            chosen[role] = str(path.resolve())
            continue
        matches = [p for p in candidates if texture_role(p) == role]
        specific = [p for p in matches if material_name and material_name.lower() in Path(p).stem.lower()]
        if specific:
            matches = specific
        elif material_count > 1:
            if matches:
                warnings.append('{}: no material-specific match for {}'.format(material_name, role))
            continue
        if len(matches) == 1:
            chosen[role] = matches[0]
        elif len(matches) > 1:
            warnings.append('{}: ambiguous {}; use explicit overrides'.format(material_name, role))
    return chosen, warnings


def fbx_summary(filename):
    """Read FBX object labels and skin presence without loading large mesh arrays."""
    result = {'materials': [], 'textures': [], 'skinned': False, 'version': None}
    with open(filename, 'rb') as stream:
        header = stream.read(27)
        if not header.startswith(b'Kaydara FBX Binary'):
            stream.seek(0)
            if os.fstat(stream.fileno()).st_size > 64 * 1024 * 1024:
                raise ValueError('ASCII FBX exceeds 64 MiB diagnostic limit; convert to binary FBX')
            text = stream.read().decode('utf-8', errors='replace')
            if not re.search(r';\s*FBX|FBXHeaderExtension\s*:', text):
                raise ValueError('Not a recognized FBX file')
            result['materials'] = re.findall(r'Material:\s*\d+,\s*"Material::([^"\r\n]+)"', text)
            result['textures'] = re.findall(r'(?:RelativeFilename|FileName|Filename):\s*"([^"\r\n]+)"', text)
            result['skinned'] = bool(re.search(r'Deformer:\s*\d+,[^\r\n]*"Skin"', text))
            return result
        version = struct.unpack('<I', header[23:27])[0]
        result['version'] = version
        wide = version >= 7500
        header_size = 25 if wide else 13
        fmt = '<QQQB' if wide else '<IIIB'
        file_size = os.fstat(stream.fileno()).st_size

        def node(depth=0):
            if depth > 64:
                raise ValueError('FBX nesting too deep')
            data = stream.read(header_size)
            if len(data) != header_size:
                return False
            end, count, prop_len, name_len = struct.unpack(fmt, data)
            if not end:
                return False
            if end > file_size or end <= stream.tell() or count > 1000000:
                raise ValueError('Invalid FBX node boundary')
            name = stream.read(name_len).decode('utf-8', errors='replace')
            prop_end = stream.tell() + prop_len
            props = []
            for _ in range(count):
                kind = stream.read(1)
                sizes = {b'Y': 2, b'C': 1, b'I': 4, b'F': 4, b'D': 8, b'L': 8}
                if kind in sizes:
                    stream.seek(sizes[kind], 1)
                elif kind in (b'S', b'R'):
                    size = struct.unpack('<I', stream.read(4))[0]
                    if kind == b'S' and size < 65536:
                        props.append(stream.read(size).decode('utf-8', errors='replace'))
                    else:
                        stream.seek(size, 1)
                elif kind in (b'f', b'd', b'l', b'i', b'b', b'c'):
                    _, _, size = struct.unpack('<III', stream.read(12))
                    stream.seek(size, 1)
                else:
                    stream.seek(prop_end)
                    break
            stream.seek(prop_end)
            if name == 'Material' and props:
                result['materials'].append(props[0].split('\x00')[0].removeprefix('Material::'))
            if name in ('RelativeFilename', 'FileName', 'Filename'):
                result['textures'].extend(props)
            if name == 'Deformer' and 'Skin' in props:
                result['skinned'] = True
            while stream.tell() < end - header_size:
                if not node(depth + 1):
                    break
            stream.seek(end)
            return True

        while stream.tell() < file_size - header_size:
            if not node():
                break
    return result
