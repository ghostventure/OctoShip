import json
import tempfile
import unittest
from pathlib import Path

from octoship import project_recipes
from octoship.core import OctoShipError


class ProjectRecipeTests(unittest.TestCase):
    def test_catalog_contains_208_distinct_entries_and_outputs(self):
        self.assertEqual(len(project_recipes.RECIPES), 208)
        paths = [project_recipes.render_recipe(key)[0] for key in project_recipes.RECIPES]
        self.assertGreater(len(set(paths)), 20)
        outputs = [(path, data) for key in project_recipes.RECIPES for path, data in [project_recipes.render_recipe(key)]]
        self.assertEqual(len(outputs), len(set(outputs)))
        for key in project_recipes.RECIPES:
            path, data = project_recipes.render_recipe(key, 'Demo', 'Example summary')
            self.assertFalse(Path(path).is_absolute())
            self.assertTrue(data)
            self.assertNotIn(b'{project}', data)
            if path.endswith('.json'):
                json.loads(data)

    def test_all_208_recipes_create_the_previewed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            for index, key in enumerate(project_recipes.RECIPES):
                root = Path(folder) / str(index)
                root.mkdir()
                relative, expected = project_recipes.render_recipe(key, 'Demo Project', 'A sample')
                target = project_recipes.create_recipe(root, key, 'Demo Project', 'A sample')
                self.assertEqual(target, root / relative, key)
                self.assertEqual(target.read_bytes(), expected, key)

    def test_output_path_sanitizes_user_project_name(self):
        with tempfile.TemporaryDirectory() as folder:
            relative, _ = project_recipes.render_recipe('flatpak_manifest', '../escape')
            self.assertNotIn('..', Path(relative).parts)
            target = project_recipes.create_recipe(folder, 'flatpak_manifest', '../escape')
            self.assertTrue(target.resolve().is_relative_to(Path(folder).resolve()))

    def test_project_fields_are_substituted(self):
        _path, data = project_recipes.render_recipe('readme', 'Demo App', 'Useful helper')
        self.assertIn(b'# Demo App', data)
        self.assertIn(b'Useful helper', data)

    def test_create_is_atomic_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = project_recipes.create_recipe(folder, 'readme', 'Demo')
            self.assertEqual(path.read_bytes(), project_recipes.render_recipe('readme', 'Demo')[1])
            with self.assertRaises(OctoShipError):
                project_recipes.create_recipe(folder, 'readme', 'Changed')
            self.assertIn(b'# Demo', path.read_bytes())

    def test_rejects_unknown_recipe_and_bad_root(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OctoShipError):
                project_recipes.render_recipe('../README.md')
            with self.assertRaises(OctoShipError):
                project_recipes.create_recipe(Path(folder) / 'missing', 'readme')

    def test_refuses_symlink_traversal(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            Path(folder, '.github').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OctoShipError):
                project_recipes.create_recipe(folder, 'ci_python')
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_refuses_symlink_ancestors_of_project_folder(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            link = Path(folder) / 'linked-root'
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OctoShipError):
                project_recipes.create_recipe(link, 'readme')
            self.assertEqual(list(Path(outside).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
