"""Compare visible Cppcheck diagnostics with a reviewed legacy inventory.

The baseline records unresolved findings; it does not suppress analyzer output
or certify old findings as safe. New diagnostics and incomplete scans fail CI.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

FATAL = {'syntaxError', 'internalError', 'internalAstError', 'cppcheckError',
         'unknownMacro', 'preprocessorErrorDirective'}


def diagnostics(report, root):
    raw = report.read_bytes()
    if len(raw) > 16 * 1024 * 1024 or b'<!DOCTYPE' in raw.upper():
        raise ValueError('Invalid or oversized analyzer XML')
    tree = ET.fromstring(raw)
    if tree.tag != 'results' or tree.find('errors') is None or tree.find('cppcheck') is None:
        raise ValueError('Incomplete Cppcheck report')
    root = root.resolve()
    findings, information = [], []
    for error in tree.find('errors'):
        if error.get('id') in FATAL:
            raise ValueError('Analyzer could not complete: ' + error.get('id'))
        if error.get('severity') == 'information':
            information.append(error.get('id'))
            continue
        locations, source_checksums = [], {}
        for location in error.findall('location'):
            path = Path(location.get('file', '').replace('\\', '/'))
            absolute = (root / path).resolve()
            relative = absolute.relative_to(root).as_posix()
            lines = absolute.read_text(encoding='utf-8').splitlines()
            source_checksums[relative] = hashlib.sha256(
                '\n'.join(line.strip() for line in lines if line.strip()).encode()).hexdigest()
            line = int(location.get('line', '0'))
            if not 1 <= line <= len(lines):
                raise ValueError('Invalid diagnostic source location')
            locations.append({'file': relative, 'code': lines[line - 1].strip()})
        if not locations:
            raise ValueError('Diagnostic lacks a reviewable source location')
        finding = {'id': error.get('id'), 'severity': error.get('severity'),
                   'message': error.get('msg'), 'locations': locations}
        finding['fingerprint'] = hashlib.sha256(json.dumps(finding, sort_keys=True).encode()).hexdigest()
        finding['source_checksums'] = source_checksums
        findings.append(finding)
    return tree.find('cppcheck').get('version'), findings, Counter(information)


def compare(version, findings, baseline):
    if baseline.get('schema') != 1 or baseline.get('cppcheck_version') != version:
        raise ValueError('Analyzer version/baseline changed; explicit review required')
    entries = baseline['findings']
    for entry in entries:
        if entry.get('disposition') not in ('FALSE_POSITIVE', 'NEEDS_INVESTIGATION') or not entry.get('reason'):
            raise ValueError('Baseline entry lacks a review disposition/reason')
        if entry['severity'] == 'error' and entry['disposition'] != 'FALSE_POSITIVE':
            raise ValueError('Unresolved analyzer errors cannot be baselined')
    known = Counter(entry['fingerprint'] for entry in entries)
    current = Counter(finding['fingerprint'] for finding in findings)
    new = current - known
    exceptions = {entry['fingerprint']: entry for entry in entries if entry['disposition'] == 'FALSE_POSITIVE'}
    for finding in findings:
        exception = exceptions.get(finding['fingerprint'])
        if exception and (not exception.get('source_checksums') or
                          exception['source_checksums'] != finding.get('source_checksums')):
            new[finding['fingerprint']] += 1
    return new, known - current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--progress', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        commands = json.loads(args.commands.read_text())
        expected = len({row['file'] for row in commands})
        totals = re.findall(r'(\d+)/(\d+) files checked', args.progress.read_text())
        if not expected or not any(int(done) == int(total) == expected for done, total in totals):
            raise ValueError('Analyzer did not confirm every compilation unit')
        version, findings, information = diagnostics(args.report, args.root)
        baseline = json.loads(args.baseline.read_text())
        new, resolved = compare(version, findings, baseline)
        print(json.dumps({'cppcheck': version, 'translation_units': expected,
                          'diagnostics': len(findings), 'information': dict(information),
                          'new': [f for f in findings if f['fingerprint'] in new],
                          'baseline_entries_no_longer_reported': sum(resolved.values())}, indent=2))
        return 1 if new else 0
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as error:
        print('Static analysis incomplete: ' + str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
