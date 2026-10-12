# Measured results — 12 October 2026

Actual synthetic-data runs in this Linux environment. This is a SciPy/Qt baseline, not a CoreMS benchmark.

## Workload and method

67,108,864 int32 transient samples (256 MiB), 48 damped off-bin sine waves plus Gaussian noise; double-precision Hann/real FFT/magnitude. Three fresh-process repetitions per padding factor. No other benchmark workload ran concurrently during these reported repetitions. The 64M synthesis took 49.38 s and is excluded from processing timings.

Environment: Python 3.12.14; NumPy 2.3.5; SciPy 1.17.0; PyQtGraph 0.14.0; Qt 6.12.0. Container memory limit 8 GiB; CPU quota equivalent to 8 cores. SciPy FFT workers=1. Host CPU model not reliably identified here.

Read timings are influenced by the OS page cache. They do **not** establish cold-storage throughput. Write timings are file/mmap operations, not durable-storage guarantees.

## Processing time

| Stage | 64M FFT, median s | 128M FFT (2× padding), median s |
|---|---:|---:|
| binary load int32 | 0.050 | 0.051 |
| convert to float64 release int32 | 0.062 | 0.065 |
| hann window in place chunked | 0.723 | 0.746 |
| real fft | 2.308 | 5.080 |
| release transient | 0.007 | 0.005 |
| magnitude to disk release complex | 0.525 | 1.056 |
| build multiresolution cache | 0.135 | 0.238 |

**1× padding:** median sum of measured processing stages 3.83 s; FFT range 2.26–2.36 s; maximum OS high-water RSS 2095 MiB (2.05 GiB). Stage sums exclude startup, imports, report writing, and inter-stage garbage collection/instrumentation.

**2× padding:** median sum of measured processing stages 7.39 s; FFT range 5.05–5.37 s; maximum OS high-water RSS 4143 MiB (4.05 GiB). Stage sums exclude startup, imports, report writing, and inter-stage garbage collection/instrumentation.

The no-padding profile is 256 MiB; all display hierarchy levels together are approximately 21.3 MiB. With 2× padding those sizes roughly double. Reopening the cached spectrum maps files and reads metadata; it does not eagerly read the profile. No full frequency or m/z array is stored.

Memory dropped after deleting arrays, but the process retained roughly 512 MiB above its starting RSS in the unpadded case and roughly 1 GiB with 2× padding. The exact allocator/backend cause was not diagnosed. This is not by itself proof of a leak; a short-lived processing worker ensures its remaining address space is reclaimed.

## Display timing

Actual forced CPU painting into an 1800×1000 Qt image. Each row summarizes 12 timed updates after a warm-up. These are not monitor FPS measurements. Each trace has its own prepared arrays and plot object, but all traces are scaled copies of **one profile** and share source pages. This is not 200 independent-file I/O or a 200-spectrum memory benchmark.

| View | Traces | Prepare ms | Submit ms | Paint ms | Total median ms | Total p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| overlay, full | 1 | 0.1 | 0.4 | 3.0 | 3.5 | 4.9 |
| overlay, full | 20 | 1.3 | 1.8 | 8.4 | 11.4 | 13.1 |
| overlay, full | 200 | 11.9 | 16.0 | 55.8 | 84.4 | 89.7 |
| overlay, region | 200 | 9.5 | 16.7 | 46.5 | 73.2 | 75.8 |
| overlay, peak | 200 | 4.6 | 17.7 | 55.7 | 78.0 | 95.7 |
| stack, full | 1 | 0.1 | 0.4 | 3.2 | 3.7 | 5.4 |
| stack, full | 20 | 1.4 | 2.0 | 7.4 | 10.7 | 12.6 |
| stack, full | 200 | 13.5 | 17.3 | 48.1 | 80.0 | 88.7 |
| stack, region | 200 | 10.3 | 16.6 | 44.2 | 71.4 | 78.3 |
| stack, peak | 200 | 4.8 | 17.5 | 54.1 | 78.0 | 118.6 |

Display-process OS peak RSS: 209.4 MiB. At full view the cache supplied approximately 3,064 points per trace, around 613,000 points total for 200 traces. The narrow-window benchmark used approximately 3,879 original samples per trace.

## Correctness and runnable preview

Passed checks against direct references for every min/max block in a non-power-of-two fixture, original extrema indices, partial tail blocks, partial viewport boundaries, preservation of a single narrow spike, exact samples on zoom, mass mapping, symmetric Hann apodization, and zero-padded FFT vs explicit DFT. All 48 generated tone frequencies were recovered within 0.55 FFT bins in each large run. These are numerical sanity checks, not vendor-equivalence or scientific validation of a real FTICR workflow.

The **1M-sample** demo was also opened in the desktop viewer using offscreen Qt; the controls were exercised for 200 stacked traces, full view, peak zoom, and PNG output. The original downloadable prototype included the captures. This repository retains the JSON reports; running `python viewer.py --smoke-test results/preview` after demo setup recreates desktop captures, and the benchmark command recreates the full-size render images.

## What the experiment supports

The Python-controlled numerical baseline can handle a real 64M transform in seconds here, while memory remains bounded by one processing job. Cached rendering of 200 curves is feasible, although roughly 80 ms redraws are below a 60 Hz interaction target. Most display time is submission/painting rather than fetching and calibrating the compact view arrays.

This supports continuing with Python plus a compact file-backed rendering layer. It does not establish CoreMS performance or 200 independent-spectrum performance. The next consequential test is a CoreMS adapter and genuinely distinct, dense spectra on lab storage; batching drawing objects or a GPU renderer are candidates if drawing remains dominant.

All raw timing samples and environment metadata are retained in JSON alongside this report. The large input and profile files are not bundled; `run_suite.py` regenerates them.
