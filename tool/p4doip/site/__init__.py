"""Builder for the public GitHub Pages site (anonymised; see docs/site-design.md).

It reads only git-tracked files, through one gate (`inputs.Inputs.read_input`), cleans every piece of free
text on the way in (exact dates reduced to month and year, identifiers masked) and scans every file it wrote
on the way out (`gate.scan_dir`). Run it with `python -m p4doip.site build --root <tree> --out <dir>`.
"""
