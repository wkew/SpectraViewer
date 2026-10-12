# Architecture and scientific boundaries

## Design intent

The interface should remain responsive while expensive I/O and processing run in
bounded background jobs. Opening a 200-spectrum session must not require 200
transients, FFT outputs, or complete CoreMS object graphs in memory.

The initial technology direction is Python with PySide6/Qt and PyQtGraph. The
existing prototype uses NumPy/SciPy; CoreMS integration is a next step. These are
working choices to evaluate, not a requirement to preserve an underperforming
implementation.

## Separation of responsibilities

| Layer | Responsibility |
|---|---|
| Readers | Format detection, metadata, transient/profile access, and source provenance |
| Scientific adapter | CoreMS integration, processing parameters, validated calibration, peaks and annotations |
| Processing workers | Bounded jobs, progress/cancellation, intermediate lifetime and memory accounting |
| Storage and session | File-backed profiles, cache versioning, compact peak tables and lazy spectrum access |
| View preparation | Viewport selection, appropriate resolution, mass coordinates and display transforms |
| Desktop interface | File/session navigation, plots, inspection tools, exports and interaction state |

Future reader adapters should accommodate both the new TIMS-FTICR format and
timsTOF data without embedding vendor-specific assumptions in plotting code.
Use CoreMS readers where available and appropriate vendor-library adapters where
needed. Existing integration experience can inform this work; no such adapter is
included yet. Preserve relevant metadata for later mobility support, but do not
make mobility analysis a prerequisite for spectrum viewing.

## Memory and rendering

- Retain only the intermediate arrays needed by the current processing stage.
- Use process lifetime to reclaim retained native allocations where necessary;
  deleting Python references alone does not ensure that RSS drops immediately.
- Limit concurrent processing by measured peak memory, including FFT workspace
  and zero filling. Do not launch one large FFT job per open spectrum.
- Keep full-resolution profiles on disk and load/map only what is needed.
- Use a hierarchy of min/max envelopes with original extrema indices for overview
  display. Retrieve original samples for detailed zoom and analytical operations.
- For uniform FFT grids, store intensities against frequency-bin indices with
  grid metadata. Generate mass coordinates only for the requested region.
- Cache keys must include source identity, processing parameters, algorithm/cache
  version, and relevant calibration dependencies. Define eviction and disk budgets.

The current envelope cache is built in frequency-bin space. It preserves block
extrema, not every peak or peak shape, and is not a per-pixel mass-axis reduction.
Synthetic calibration currently uses m/z = A/f; this must not be treated as a
validated instrument calibration.

## Scientific correctness

Display simplification is never an analytical input. Peak picking, mass-distance
measurements, recalibration, and matching must use authoritative samples or
validated peak tables, not reduced plot vertices. Label units and calibration
state explicitly and retain processing provenance in exports.

Internal recalibration normally updates the coordinate mapping and dependent peak
masses/annotations without repeating the FFT. Reuse frequency-domain summaries
only when the mapping remains valid and monotonic across the selected domain.
Instrument frequency conventions and calibration equations need real fixtures.

A display threshold is separate from noise estimation and peak-picking criteria.
Likewise, normalized or vertically offset traces are display transformations;
retain original intensities for analysis and export.

Formula/isotope tools should report candidate evidence and ambiguity. IsoSpecPy
is a candidate theoretical-pattern backend; experimental matching still requires
explicit charge/adduct handling, tolerances, resolving power, overlap handling,
and validation. Broad automated formula-assignment workflows are outside the
initial viewer scope.
