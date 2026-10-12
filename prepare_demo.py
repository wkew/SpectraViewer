#!/usr/bin/env python3
"""Generate the small demo locally, reusing a completed dataset on later runs."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    raw, spectrum = root/'demo'/'raw', root/'demo'/'spectrum'
    if (spectrum/'spectrum.json').exists() and (spectrum/'profile.npy').exists():
        print('Demo already prepared. Run: python viewer.py')
        return
    if not (raw/'raw.json').exists():
        subprocess.run([sys.executable, str(root/'benchmark.py'), 'generate',
                        str(raw), '--points', '1048576'], check=True)
    subprocess.run([sys.executable, str(root/'benchmark.py'), 'process',
                    str(raw), str(spectrum)], check=True)
    print('Demo ready. Run: python viewer.py')


if __name__ == '__main__':
    main()
