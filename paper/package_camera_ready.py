#!/usr/bin/env python3
"""Create local, explicit-file-list camera-ready and reproducibility archives."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/release'


def paper_files():
    names = {'paper/' + n for n in (
        'camera_ready.tex', 'main_body.tex', 'appendix_content.tex',
        'references.tex', 'acl.sty', 'acl_natbib.bst', 'build_camera_ready.sh',
        'ACL_STYLE_PROVENANCE.md', 'README.md', 'CAMERA_READY_STATUS.md')}
    for source in ('main_body.tex', 'appendix_content.tex'):
        text = (ROOT / 'paper' / source).read_text()
        for image in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', text):
            names.add('paper/' + image)
        for table in re.findall(r'\\input\{([^}]+)\}', text):
            names.add('paper/' + table + ('' if table.endswith('.tex') else '.tex'))
    return names


def write_archive(filename, names, readme):
    manifest = {}
    with zipfile.ZipFile(OUT / filename, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(name)
            content = path.read_bytes()
            manifest[name] = hashlib.sha256(content).hexdigest()
            archive.writestr(name, content)
        archive.writestr('PACKAGE_README.md', readme)
        manifest['PACKAGE_README.md'] = hashlib.sha256(readme.encode()).hexdigest()
        archive.writestr('SHA256SUMS.json', json.dumps(manifest, indent=2) + '\n')
    return {'file': filename, 'files': len(manifest),
            'bytes': (OUT / filename).stat().st_size,
            'sha256': hashlib.sha256((OUT / filename).read_bytes()).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = paper_files()
    packages = [write_archive('eval-pair-matrix-camera-ready-source.zip', source,
        '# Camera-ready LaTeX sources\n\nFrom this extracted directory run '
        '`bash paper/build_camera_ready.sh`. Requires Python 3 and pdfLaTeX. '
        'The build verifies official ACL style hashes and writes '
        '`output/pdf/eval-pair-matrix-camera-ready.pdf`. '
        'Only referenced figures/tables and the final manuscript are included.\n')]
    inventory = json.loads((ROOT / 'paper/audit/paired_audit_report.json').read_text())
    names = source | set(inventory['files']) | {
        'README.md', 'pyproject.toml', 'paper/REPRODUCIBILITY.md',
        'paper/requirements-analysis.txt', 'paper/package_camera_ready.py',
        'paper/behavior_paired_sensitivity.py',
        'data/exp/3provider_300.manifest.json', 'data/exp/exp-300.manifest.json',
        'paper/tables/behavior_paired_sensitivity.json',
        'paper/tables/behavior_paired_sensitivity.tex',
        'paper/reference_metadata_check.json'}
    names |= {str(p.relative_to(ROOT)) for p in (ROOT / 'src').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    names |= {'paper/audit/' + n for n in (
        'README.md', 'paired_audit.py', 'paired_audit_report.json',
        'paired_verdicts.csv', 'behavior_stratified.py',
        'behavior_stratified_report.json', 'build_cell_review_queue.py',
        'cell_review_queue.json', 'cell_review_queue.csv',
        'cell_review_progress.json', 'cell_review_summary.md',
        'cell_audit_findings.json', 'cell_audit_findings.md',
        'judge_cost.py', 'judge_usage.jsonl', 'judge_usage_manifest.json')}
    packages.append(write_archive('eval-pair-matrix-reproducibility.zip', names,
        '# Reproducibility package\n\nSee `paper/REPRODUCIBILITY.md` for '
        'saved-data analysis commands and expected results. These commands '
        'make no model calls. The source pool, labeled generations, verdicts, '
        'human audit inputs, prompts/schemas, and usage-only ledger are included. '
        'Each packaged file is hashed in `SHA256SUMS.json`. '
        'Upstream data provenance and terms continue to apply.\n'))
    (OUT / 'release-manifest.json').write_text(json.dumps(packages, indent=2)+'\n')
    for p in packages:
        print(p['file'], p['files'], 'files,', p['bytes'], 'bytes')


if __name__ == '__main__':
    main()
