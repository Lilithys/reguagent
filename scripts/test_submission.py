"""Validate the actual deliverable in isolation, including the complete demo CLI."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from package_submission import build_submission,PACKAGE


class SubmissionTests(unittest.TestCase):
    def test_bundle_is_reproducible_and_contains_only_reviewable_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp,'first.zip');second=Path(tmp,'second.zip')
            build_submission(first);build_submission(second)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names=[n.removeprefix(PACKAGE+'/') for n in archive.namelist()]
                self.assertIn('.env.example',names)
                for name in names:
                    self.assertNotIn(name.split('/')[0],('.env.local','.venv','.git','runs','backups','CODEX_CONTEXT.md','TODO.md'))
                    self.assertFalse(name.endswith(('.pdf','.sqlite3','.pyc','.DS_Store')))
                manifest=json.loads(archive.read(PACKAGE+'/SUBMISSION_MANIFEST.json'))
                for name,sha in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(PACKAGE+'/'+name)).hexdigest(),sha)

    def test_extracted_bundle_runs_complete_demo_without_site_packages_or_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp,'submission.zip');build_submission(archive)
            with zipfile.ZipFile(archive) as bundle:bundle.extractall(tmp)
            root=Path(tmp,PACKAGE)
            # Isolate imports and disable site-packages: no SDKs or source checkout.
            result=subprocess.run([sys.executable,'-I','-S','scripts/demo.py'],cwd=root,
                capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            summary=json.loads((root/'runs/demo/summary.json').read_text())
            self.assertEqual(summary['mode'],'scripted_replay')
            self.assertEqual(summary['api_requests_attempted'],0)
            self.assertTrue(all(summary['checks'].values()))
            self.assertEqual(summary['energy_coverage']['missing_borrower_count'],3500)
            self.assertEqual(summary['actions'][0]['status'],'verified')
            self.assertTrue((root/'runs/demo/report.md').is_file())
            self.assertTrue((root/'runs/demo/audit.json').is_file())


if __name__=='__main__':unittest.main()
