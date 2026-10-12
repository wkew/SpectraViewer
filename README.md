# SpectraViewer

A desktop graphical application for fast, memory-conscious mass spectrum viewing,
comparison, inspection, and lightweight annotation, with FTICR as the initial focus.

## Why this project exists

Reviewing many large, high-resolution spectra should be practical on an individual
workstation. SpectraViewer aims to provide a responsive alternative to Bruker
DataAnalysis for everyday review, using less memory and avoiding dependence on
available DataAnalysis seats. Changes to vendor licensing motivate an application
that can be installed wherever routine spectrum inspection is needed.

The immediate goal is to **demonstrate better responsiveness and lower memory use
on representative review workflows**, while preserving scientifically meaningful
peak information. A direct comparison with vendor software remains to be done;
this repository does not yet establish a performance advantage.

SpectraViewer is a viewer with basic processing tools, not a comprehensive data
processing suite. It should reuse scientific functionality from CoreMS wherever
practical instead of developing a competing processing framework.

## Scope and priorities

| Area | Direction |
|---|---|
| Spectrum review | Multiple open spectra, overlays and stacks, zoom/pan, full view, and selection |
| Basic processing | Apodization, zero filling, FFT, frequency-to-m/z conversion, basic peak picking and noise estimation |
| Inspection | Mass-distance measurements, internal mass recalibration, and display thresholds |
| Lightweight annotation | Basic formula candidates and isotope-pattern matching, with explicit uncertainty |
| Export | Spectrum images and peak lists with processing/calibration provenance |
| Initial scale | Up to 64M transient samples per spectrum; sessions with approximately 200 spectra |
| Future formats | New TIMS-FTICR data format and Bruker timsTOF data |
| Deferred | Ion mobility visualization and analysis, comprehensive identification workflows, and large automated processing pipelines |

FTICR is the principal large-data design case. Future TIMS-FTICR and timsTOF readers
should build on CoreMS support and existing experience integrating Bruker libraries.
They are planned integrations, not implemented readers. Mobility-specific work is
explicitly deferred and should follow the capabilities developed in CoreMS.

## Current status

**Early performance prototype, not a production application.** The repository
contains a synthetic transient generator, a NumPy/SciPy processing benchmark, a
file-backed multiresolution cache, and a working Qt spectrum viewer.

The viewer currently supports zoom, pan, full view, overlays, stacks, and PNG
export. Its 1–200 traces are scaled copies of one profile. CoreMS integration,
vendor import, validated instrument calibration, peak picking, recalibration
fitting, and annotation are not yet implemented.

Initial measurements include an actual 67,108,864-sample transform and offscreen Qt
painting. They support further development but do not establish the performance
of CoreMS, 200 independent files, or real instrument data. See
[measured results](RESULTS.md) and [benchmark methods and commands](docs/BENCHMARK.md).

## Run the prototype

Python 3.10+ and a desktop environment are required for the interactive viewer.
The prototype has been tested on Linux/Python 3.12; Windows and macOS validation
is planned.

```bash
git clone https://github.com/wkew/SpectraViewer.git
cd SpectraViewer
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python prepare_demo.py
python viewer.py
```

The demo generates a small 1M-sample dataset locally. Large generated binaries are
excluded from version control. For correctness checks and the full benchmark:

```bash
python check_correctness.py
python run_suite.py --points 67108864 --repeats 3 --pad-factors 1 2 --out local_run
```

Use a fresh output directory. The recorded 2× zero-filled processing run peaked
near 4 GiB; allow approximately 8 GiB available RAM and several GiB of disk for
the full suite. Read timings include OS-cache effects.

## Development direction

Start with Python, Qt/PySide6, PyQtGraph, NumPy/SciPy, and a small CoreMS adapter.
Keep scientific processing separate from the renderer, use compact arrays and
file-backed caches, and bound background work by available memory. Consider Rust
or alternative rendering backends only for measured bottlenecks.

- [Architecture and scientific boundaries](docs/ARCHITECTURE.md)
- [Roadmap and performance acceptance plan](docs/ROADMAP.md)
- [Prototype methods and limitations](docs/BENCHMARK.md)
- [Recorded benchmark results](RESULTS.md)

Project licensing has not yet been selected. Dependency and vendor-library terms
must be reviewed before distributing an installer; Bruker libraries are not
bundled in this repository.
