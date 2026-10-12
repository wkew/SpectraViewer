# Roadmap and performance acceptance plan

## 1. Establish the numerical and display baseline

The initial synthetic prototype and recorded results are included. It generates
damped sine waves plus noise, loads int32 binary data, applies a Hann window,
computes an optionally zero-filled FFT, stores magnitudes, and renders cached
views. Numerical and cache checks cover narrow peaks and detailed zoom.

Remaining baseline work: independent spectra, denser signals, representative
storage, and interactive measurements on target workstations. The current
200-trace test reuses one profile and must not be described as a 200-file test.

## 2. Prove representative FTICR review performance

Introduce a CoreMS adapter and real FTICR fixtures with known acquisition and
calibration metadata. Compare numerical output to trusted references. Implement
bounded asynchronous processing and independent-spectrum sessions before drawing
conclusions about production memory use or responsiveness.

Measure SpectraViewer and Bruker DataAnalysis on the same workstation, source
files, processing settings, and review actions where equivalent operations are
available. Record application/dependency versions, CPU, RAM, storage, point counts,
zero filling, spectrum density, and how cold/warm cache states are established.
If an operation has no equivalent, report it separately.

| Measurement | Required evidence |
|---|---|
| Load and processing | Separate binary I/O, preparation, FFT, magnitude/calibration and cache generation |
| Session opening | Independent spectra at increasing counts up to approximately 200; cold and cached reopening |
| Memory | Peak and steady-state RSS for the UI and all workers; mapped resident pages and disk-cache size |
| Navigation | Preparation, submission, painting and end-to-end interaction latency; median and p95 with sufficient repetitions |
| Scientific fidelity | Reference FFT/calibration checks, narrow-peak preservation, full-resolution measurements and intensity range |
| Resource recovery | Repeated open/close, cancellation and failed-job cleanup without unbounded resource growth |

Cached navigation below 100 ms is an initial target, not a guarantee. Agree a
practical memory budget for the target hardware. Demonstrate lower memory use
and faster representative review operations than DataAnalysis before claiming
those advantages, and report regressions and workload boundaries as well as wins.

## 3. Deliver the focused desktop workflow

Build independent file/session management, selection, linked zoom, overlays and
stacks. Add peak picking/noise estimation, mass distances, internal recalibration,
peak-list export and lightweight formula/isotope annotations incrementally.
Keep expensive work cancellable and provide progress and understandable errors.
Validate Windows and macOS alongside Linux and make installation reproducible.

## 4. Extend format support

Add readers for the new TIMS-FTICR data format and Bruker timsTOF data, using
CoreMS capabilities and established Bruker-library integration experience.
Confirm reader availability, supported format variants, calibration metadata and
redistribution terms during implementation. These formats are planned, not
currently supported.

Mobility visualization and analysis remain a later phase, aligned with CoreMS
development. Neither mobility nor a comprehensive processing suite should delay
the initial FTICR review application.

## Scope discipline

Optimize measured bottlenecks before replacing the scientific stack. Evaluate
render batching, alternate renderers, or targeted native/Rust components when
measurements justify them. Keep reproducible benchmark reports and small
redistributable fixtures in git; generate large datasets locally.
