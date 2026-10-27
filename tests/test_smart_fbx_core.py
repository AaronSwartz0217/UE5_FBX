import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'SmartFbxMaterials/Content/Python'))
import smart_fbx_core as core


class MatchingTests(unittest.TestCase):
    def test_tripo_nested_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp, '青铜.fbx')
            model.touch()
            folder = Path(tmp, '青铜')
            folder.mkdir()
            for name in ('tripo_rgb_uuid.jpg', 'tripo_normal_uuid.jpg', '青铜_metallic.JPEG', '青铜_roughness.JPEG'):
                (folder / name).touch()
            matches, warnings = core.choose_textures(model)
            self.assertEqual(set(matches), {'base_color', 'normal', 'metallic', 'roughness'})
            self.assertFalse(warnings)

    def test_ambiguous_does_not_pick_random_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp, 'a.fbx')
            for name in ('a_basecolor.png', 'b_basecolor.png'):
                Path(tmp, name).touch()
            matches, warnings = core.choose_textures(model)
            self.assertNotIn('base_color', matches)
            self.assertTrue(warnings)

    def test_multiple_materials_require_specific_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'tripo_rgb_uuid.jpg').touch()
            matches, warnings = core.choose_textures(Path(tmp, 'a.fbx'), 'Wood', 2)
            self.assertFalse(matches)
            self.assertTrue(warnings)

    def test_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'anything.png').touch()
            matches, _ = core.choose_textures(Path(tmp, 'a.fbx'), overrides={'metallic': 'anything.png'})
            self.assertEqual(Path(matches['metallic']).name, 'anything.png')

    def test_missing_override_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                core.choose_textures(Path(tmp, 'a.fbx'), overrides={'normal': 'missing.png'})

    def test_packed_and_short_suffix(self):
        self.assertEqual(core.texture_role('Bronze_ORM.png'), 'orm')
        self.assertEqual(core.texture_role('Bronze_RMA.png'), 'rma')
        self.assertEqual(core.texture_role('Bronze_N.png'), 'normal')
        self.assertIsNone(core.texture_role('terrain_noise.png'))

    def test_unicode_ids_do_not_collide(self):
        self.assertNotEqual(core.asset_id('铜机械小兵'), core.asset_id('铜械将军'))

    def test_ascii_fbx_skin_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'skin.fbx')
            path.write_text('; FBX 7.4\nMaterial: 4, "Material::Bronze", "" {}\nDeformer: 7, "Deformer::skin", "Skin" {}', encoding='utf-8')
            summary = core.fbx_summary(path)
            self.assertTrue(summary['skinned'])
            self.assertEqual(summary['materials'], ['Bronze'])

    def test_invalid_fbx_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'invalid.fbx')
            path.write_bytes(b'not a model')
            with self.assertRaises(ValueError):
                core.fbx_summary(path)


if __name__ == '__main__':
    unittest.main()
