import tempfile
import unittest
from pathlib import Path

from scripts.install_analyze import COMMAND, install


class AnalyzeCommandTests(unittest.TestCase):
    def test_install_retry_and_remove_preserve_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = root/'settings.json'; settings.write_text('{"synthetic":"keep"}')
            target = Path(install(root))
            self.assertEqual(target.read_text(), COMMAND)
            self.assertEqual(install(root), str(target))
            install(root, uninstall=True)
            self.assertFalse(target.exists())
            self.assertEqual(settings.read_text(), '{"synthetic":"keep"}')

    def test_existing_command_and_competing_install_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'skills/analyze/SKILL.md'; target.parent.mkdir(parents=True)
            target.write_text('Unrelated command')
            with self.assertRaisesRegex(ValueError, 'unrelated'):
                install(folder)
            with self.assertRaises(ValueError):
                install(folder, uninstall=True)
            self.assertEqual(target.read_text(), 'Unrelated command')
            target.unlink()
            pending = target.with_suffix('.installing'); pending.write_text('Competing installer')
            with self.assertRaises(FileExistsError):
                install(folder)
            self.assertEqual(pending.read_text(), 'Competing installer')

    def test_plugin_has_one_developer_entrypoint_and_internal_support_skills(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root/'skills').glob('*/SKILL.md'):
            self.assertIn('user-invocable: false', path.read_text().split('---', 2)[1])
        self.assertIn('ally-session-analyzer:analyze', COMMAND)
        self.assertIn('$ARGUMENTS', COMMAND)
        self.assertIn('disable-model-invocation: true', COMMAND)
