#!/usr/bin/env bash
set -euo pipefail

paper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$paper_dir/.." && pwd)"
build_dir="$repo_dir/tmp/pdfs/camera-ready"
output_dir="$repo_dir/output/pdf"
mkdir -p "$build_dir" "$output_dir"
cd "$paper_dir"

# Fail if the vendored official style files were changed accidentally.
python3 - <<'PY'
import hashlib
from pathlib import Path

expected = {
    'acl.sty': '19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de',
    'acl_natbib.bst': '6fbb306202290f4b68e74ac1460a8b27398500cb6dfeb4492e74c457eae7cd1e',
}
for name, digest in expected.items():
    actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f'{name} differs from the pinned official ACL file')
PY

for pass in 1 2 3; do
  if ! pdflatex -interaction=nonstopmode -halt-on-error -file-line-error \
      -output-directory="$build_dir" camera_ready.tex > "$build_dir/build-pass-$pass.txt"; then
    tail -n 60 "$build_dir/build-pass-$pass.txt"
    exit 1
  fi
done

# Do not deliver a PDF with unresolved references or overflowing text.
python3 - <<'PY'
from pathlib import Path
import re
log = Path('../tmp/pdfs/camera-ready/camera_ready.log').read_text()
if re.search(r'Overfull \\[hv]box|LaTeX Warning:|Package .* Warning:', log):
    raise SystemExit('Inspect the final LaTeX log: warning or overfull box found')
PY

cp "$build_dir/camera_ready.pdf" "$output_dir/eval-pair-matrix-camera-ready.pdf"
printf 'Built %s\n' "$output_dir/eval-pair-matrix-camera-ready.pdf"
