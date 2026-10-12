#!/usr/bin/env python3
"""Run stages in fresh processes; keep one profile per padding factor, all timing logs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--points', type=int, default=2**26)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--pad-factors', type=int, nargs='+', choices=(1, 2, 4), default=[1, 2])
    parser.add_argument('--frames', type=int, default=12)
    parser.add_argument('--out', type=Path, default=Path('local_run'))
    parser.add_argument('--raw', type=Path, help='Reuse an existing generated raw folder')
    args = parser.parse_args()
    if args.repeats < 1: parser.error('--repeats must be positive')
    root = Path(__file__).resolve().parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = args.raw.resolve() if args.raw else out/'raw'
    def run(*cmd): subprocess.run([sys.executable, '-u', *map(str, cmd)], check=True)
    if args.raw:
        meta = json.loads((raw/'raw.json').read_text())
        if meta['points'] != args.points: parser.error('--points does not match reused raw data')
    else:
        run(root/'benchmark.py', 'generate', raw, '--points', args.points)
    for pad in args.pad_factors:
        for rep in range(args.repeats):
            dest = out/f'pad{pad}_run{rep+1}'
            run(root/'benchmark.py', 'process', raw, dest, '--pad-factor', pad)
            shutil.copy2(dest/'processing.json', out/f'processing_pad{pad}_run{rep+1}.json')
            if rep: shutil.rmtree(dest)  # only our newly generated intermediate directory
    first = args.pad_factors[0]
    run(root/'viewer.py', out/f'pad{first}_run1', '--benchmark', '--frames', args.frames,
        '--output', out/'display')
    print(f'Completed. Results: {out}')
    print(f'Interactive viewer: python viewer.py "{out / f"pad{first}_run1"}"')


if __name__ == '__main__': main()
