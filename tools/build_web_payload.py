"""Refresh or check the checked-in pygbag game payload using stdlib only.

Run after editing runtime code/data/assets; the HTML loader is separate.
"""
import argparse
import gzip
import io
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('main.py', 'rules.py', 'menu_ui.py', 'upgrade_ui.py', 'challenges.py', 'records.py')


def payload():
    paths = [ROOT / name for name in MODULES]
    for directory in ('assets', 'data', 'sounds'):
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file()]
    return {'assets/' + p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(paths)}


def check(files):
    with zipfile.ZipFile(ROOT / 'docs/night-survivors.apk') as z, tarfile.open(ROOT / 'docs/night-survivors.tar.gz') as t:
        assert z.testzip() is None, 'ZIP integrity failure'
        assert set(z.namelist()) == set(t.getnames()) == set(files), 'Payload file list differs from runtime sources'
        for name, data in files.items():
            assert z.read(name) == t.extractfile(name).read() == data, f'Stale game payload: {name}'
    print(f'PASS: ZIP and TAR contain all {len(files)} current runtime files, including daily modifiers')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check without changing archives')
    args = parser.parse_args()
    files = payload()
    if not args.check:
        with zipfile.ZipFile(ROOT / 'docs/night-survivors.apk', 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w') as t:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                t.addfile(info, io.BytesIO(data))
        (ROOT / 'docs/night-survivors.tar.gz').write_bytes(buffer.getvalue())
    check(files)


if __name__ == '__main__':
    main()
