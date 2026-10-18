import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('candidate_host',Path(__file__).resolve().parents[1]/'ci/candidate-host.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class CandidateHost(unittest.TestCase):
    def select(self,entry):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'contract.json').write_text(json.dumps({'clients':{'python':entry}}))
            return module.candidate_requirement(directory)
    def test_stable_fallback(self):
        self.assertIsNone(self.select({'repository':'licensebox/python','release':'v0.1.0'}))
    def test_exact_public_candidate(self):
        self.assertEqual(self.select({'repository':'licensebox/python','candidate_ref':'a'*40}),'licensebox @ git+https://github.com/licensebox/python.git@'+'a'*40)
    def test_invalid_refs_and_other_repositories_rejected(self):
        for ref in [None,True,'main','v0.1.0','a'*39,'a'*41,'A'*40,'https://example.invalid/repo','a'*40+'; command']:
            with self.subTest(ref=ref),self.assertRaises(ValueError):self.select({'repository':'licensebox/python','candidate_ref':ref})
        with self.assertRaises(ValueError):self.select({'repository':'other/python','candidate_ref':'a'*40})
