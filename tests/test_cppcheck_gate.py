from pathlib import Path
import tempfile
import unittest
from cppcheck_gate import compare, diagnostics


class CppcheckGateTests(unittest.TestCase):
    def test_baseline_preserves_multiplicity_and_rejects_new_finding(self):
        entry = {'fingerprint': 'a', 'severity': 'warning',
                 'disposition': 'NEEDS_INVESTIGATION', 'reason': 'Legacy evidence retained for review'}
        baseline = {'schema': 1, 'cppcheck_version': '2.13.0', 'findings': [entry]}
        self.assertFalse(compare('2.13.0', [entry], baseline)[0])
        self.assertEqual(compare('2.13.0', [entry, entry], baseline)[0]['a'], 1)
        with self.assertRaises(ValueError):
            compare('2.14.0', [entry], baseline)
        entry['severity'] = 'error'
        with self.assertRaises(ValueError):
            compare('2.13.0', [entry], baseline)

    def test_fingerprint_tracks_code_not_line_number(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, report = root / 'test.cpp', root / 'results.xml'
            def scan(line):
                report.write_text('<results><cppcheck version="2.13.0"/><errors>'
                                  '<error id="test" severity="warning" msg="sample">'
                                  f'<location file="test.cpp" line="{line}"/></error></errors></results>')
                return diagnostics(report, root)[1][0]['fingerprint']
            source.write_text('int x;\n')
            before = scan(1)
            source.write_text('// moved\nint x;\n')
            self.assertEqual(before, scan(2))
            source.write_text('// moved\nint y;\n')
            self.assertNotEqual(before, scan(2))

    def test_false_positive_requires_unchanged_reviewed_source(self):
        entry = {'fingerprint': 'a', 'severity': 'error', 'disposition': 'FALSE_POSITIVE',
                 'reason': 'Reviewed guarded path', 'source_checksums': {'test.cpp': 'original'}}
        baseline = {'schema': 1, 'cppcheck_version': '2.13.0', 'findings': [entry]}
        self.assertFalse(compare('2.13.0', [entry], baseline)[0])
        changed = dict(entry, source_checksums={'test.cpp': 'changed guard'})
        self.assertTrue(compare('2.13.0', [changed], baseline)[0])

    def test_incomplete_reports_and_paths_outside_root_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / 'results.xml'
            for content in ('<results>', '<results/>',
                            '<results><cppcheck/><errors><error id="syntaxError"/></errors></results>',
                            '<results><cppcheck/><errors><error severity="warning"><location file="../outside" line="1"/></error></errors></results>',
                            '<!DOCTYPE x><results><cppcheck/><errors/></results>'):
                report.write_text(content)
                with self.assertRaises(Exception):
                    diagnostics(report, root)


if __name__ == '__main__':
    unittest.main()
