"""Tests supplied but NOT run in the handoff's unavailable local runtime."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('archive_reference_files.py')


class ArchiveTests(unittest.TestCase):
    def run_tool(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / '中文素材.bin'
            data = bytes(range(256)) * 12288 + b'end-of-reference'
            source.write_bytes(data)
            archive = root / 'archive'
            self.run_tool('pack', source, archive, '--chunk-mib', 1)
            manifest = json.loads((archive / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(len(manifest['parts']), 4)
            self.run_tool('verify', archive)
            output = root / 'restored.bin'
            self.run_tool('unpack', archive, output)
            self.assertEqual(output.read_bytes(), data)
            self.assertEqual(source.read_bytes(), data)
            self.run_tool('unpack', archive, output, success=False)
            self.run_tool('pack', source, archive, success=False)
            part = archive / manifest['parts'][0]['file']
            corrupted = bytearray(part.read_bytes())
            corrupted[0] ^= 1
            part.write_bytes(corrupted)
            self.run_tool('verify', archive, success=False)
            bad_output = root / 'bad.bin'
            self.run_tool('unpack', archive, bad_output, success=False)
            self.assertFalse(bad_output.exists())
            self.assertEqual(source.read_bytes(), data)

    def test_unsafe_manifest_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.bin'
            source.write_bytes(b'example')
            archive = root / 'archive'
            self.run_tool('pack', source, archive)
            path = archive / 'manifest.json'
            obj = json.loads(path.read_text(encoding='utf-8'))
            obj['parts'][0]['file'] = '../source.bin'
            path.write_text(json.dumps(obj), encoding='utf-8')
            self.run_tool('verify', archive, success=False)


if __name__ == '__main__':
    unittest.main()
