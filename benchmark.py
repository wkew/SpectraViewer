#!/usr/bin/env python3
"""Synthetic FTICR numerical and display benchmark. See README.md for scope."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gc
import json
import math
import os
from pathlib import Path
import platform
import threading
import time

import numpy as np
import psutil
import scipy
from scipy import fft

MIB = 2**20
CHUNK = 2**20


def environment():
    info = dict(platform=platform.platform(), python=platform.python_version(),
                numpy=np.__version__, scipy=scipy.__version__,
                logical_cpus=os.cpu_count(), host_ram_gib=psutil.virtual_memory().total/2**30)
    for name in ('memory.max', 'cpu.max'):
        p = Path('/sys/fs/cgroup') / name
        if p.exists():
            info['cgroup_' + name] = p.read_text().strip()
    return info


class Recorder:
    """Sample process RSS every 5 ms, including native NumPy/FFT/Qt allocations.

    Stage peaks are sampled absolute RSS, NOT allocated bytes or exact maxima.
    OS peak RSS is recorded separately where available. Includes mmap residency.
    """
    def __init__(self):
        # Some containers expose host /proc but namespace-local getpid().
        # /proc/self remains correct in that case.
        if Path('/proc/self/statm').exists():
            self.rss = lambda: int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        else:
            process = psutil.Process()
            self.rss = lambda: process.memory_info().rss
        self.rows = []

    @contextmanager
    def stage(self, name, **extra):
        gc.collect()
        start_rss = self.rss()
        peak = [start_rss]
        stop = threading.Event()
        def sample():
            while not stop.wait(.005):
                peak[0] = max(peak[0], self.rss())
        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        cpu0, t0 = time.process_time(), time.perf_counter()
        try:
            yield
        finally:
            elapsed, cpu = time.perf_counter()-t0, time.process_time()-cpu0
            end_rss = self.rss()
            stop.set()
            thread.join()
            row = dict(stage=name, seconds=elapsed, cpu_seconds=cpu,
                       rss_start_mib=start_rss/MIB, rss_end_mib=end_rss/MIB,
                       sampled_peak_rss_mib=max(peak[0], end_rss)/MIB, **extra)
            self.rows.append(row)
            print(json.dumps(row), flush=True)

    def report(self, path, **extra):
        peak = None
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak /= MIB if platform.system() == 'Darwin' else 1024
        except ImportError:
            pass
        payload = dict(environment=environment(), os_peak_rss_mib=peak,
                       stages=self.rows, **extra)
        Path(path).write_text(json.dumps(payload, indent=2))
        return payload


def generate(folder, points, tones=48, seed=42):
    """Write little-endian int32 damped sine mixtures, without an N x tones array."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'transient.i32').exists():
        raise FileExistsError('Use a fresh directory; generator will not overwrite raw data.')
    rng = np.random.default_rng(seed)
    fs, calibration_a = 2_000_000., 100_000_000.
    frequencies = rng.uniform(60_000, 780_000, tones)  # deliberately off FFT bins
    amplitudes = 10 ** rng.uniform(-2, 0, tones)
    phases = rng.uniform(0, 2*np.pi, tones)
    decay_s = points/fs * 1.5
    noise_sigma = .02
    scale = (2**29) / (amplitudes.sum()+10*noise_sigma)
    rec = Recorder()
    with rec.stage('generate_sine_mixture_and_write', samples=points, tones=tones):
        with (folder/'transient.i32').open('wb') as stream:
            for start in range(0, points, CHUNK):
                size = min(CHUNK, points-start)
                t = (np.arange(size, dtype=np.float64)+start)/fs
                y = np.zeros(size)
                for f, a, phase in zip(frequencies, amplitudes, phases):
                    y += a*np.sin(2*np.pi*f*t+phase)
                y *= np.exp(-t/decay_s)
                y += rng.normal(0, noise_sigma, size)
                quantized = np.rint(y*scale)
                assert np.max(np.abs(quantized)) < np.iinfo(np.int32).max
                quantized.astype('<i4').tofile(stream)
    meta = dict(points=points, sample_rate_hz=fs, calibration_a=calibration_a,
                calibration_model='synthetic m/z = A / f; not a vendor calibration',
                seed=seed, tones=tones, frequencies_hz=frequencies.tolist(),
                amplitudes=amplitudes.tolist(), phases=phases.tolist(),
                noise_sigma=noise_sigma, decay_seconds=decay_s, adc_scale=scale,
                raw_dtype='<i4', generation='chunked direct sine summation plus Gaussian noise')
    (folder/'raw.json').write_text(json.dumps(meta, indent=2))
    rec.report(folder/'generation.json', config=meta)


def extrema_rows(values, indices):
    """Choose min/max from each row, output in original index order."""
    row = np.arange(len(values))
    amin, amax = np.argmin(values, axis=1), np.argmax(values, axis=1)
    ia, ib = indices[row, amin], indices[row, amax]
    va, vb = values[row, amin], values[row, amax]
    order = ia <= ib
    return (np.column_stack((np.where(order, ia, ib), np.where(order, ib, ia))),
            np.column_stack((np.where(order, va, vb), np.where(order, vb, va))))


def build_pyramid(folder, count):
    """64-bin leaf summaries, then 4:1 levels; exact extrema, including tail bins."""
    folder = Path(folder)
    profile = np.load(folder/'profile.npy', mmap_mode='r')
    block = 64
    levels = []
    groups = math.ceil(count/block)
    oi = np.lib.format.open_memmap(folder/f'index_{block}.npy', mode='w+',
                                 dtype=np.int64, shape=(groups, 2))
    ov = np.lib.format.open_memmap(folder/f'value_{block}.npy', mode='w+',
                                 dtype=np.float64, shape=(groups, 2))
    for g in range(0, groups, CHUNK//block):
        end = min(g+CHUNK//block, groups)
        lo, hi = g*block, min(end*block, count)
        vals = np.array(profile[lo:hi])
        pad = (end-g)*block-len(vals)
        # Last block may be shorter. Duplicating its final sample preserves extrema.
        if pad:
            vals = np.pad(vals, (0, pad), mode='edge')
        vals = vals.reshape(-1, block)
        local_min, local_max = vals.argmin(axis=1), vals.argmax(axis=1)
        first, last = np.minimum(local_min, local_max), np.maximum(local_min, local_max)
        rows = np.arange(end-g)
        base = np.arange(g, end)*block
        oi[g:end] = np.column_stack((base+first, base+last))
        ov[g:end] = np.column_stack((vals[rows, first], vals[rows, last]))
    oi.flush(); ov.flush()
    levels.append(dict(block=block, groups=groups))
    del oi, ov, profile
    while groups > 512:
        prev_i = np.load(folder/f'index_{block}.npy', mmap_mode='r')
        prev_v = np.load(folder/f'value_{block}.npy', mmap_mode='r')
        new_groups = math.ceil(groups/4)
        new_block = block*4
        oi = np.lib.format.open_memmap(folder/f'index_{new_block}.npy', mode='w+',
                                     dtype=np.int64, shape=(new_groups, 2))
        ov = np.lib.format.open_memmap(folder/f'value_{new_block}.npy', mode='w+',
                                     dtype=np.float64, shape=(new_groups, 2))
        for start in range(0, new_groups, 32768):
            end = min(start+32768, new_groups)
            ii = np.array(prev_i[start*4:min(end*4, groups)]).reshape(-1)
            vv = np.array(prev_v[start*4:min(end*4, groups)]).reshape(-1)
            pad = (end-start)*8-len(ii)
            if pad:
                ii = np.pad(ii, (0, pad), mode='edge')
                vv = np.pad(vv, (0, pad), mode='edge')
            a, b = extrema_rows(vv.reshape(-1, 8), ii.reshape(-1, 8))
            oi[start:end], ov[start:end] = a, b
        oi.flush(); ov.flush()
        del oi, ov, prev_i, prev_v
        block, groups = new_block, new_groups
        levels.append(dict(block=block, groups=groups))
    return levels


def process(folder, out, pad_factor=1):
    folder, out = Path(folder), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out/'profile.npy').exists():
        raise FileExistsError('Use a fresh output directory.')
    raw_meta = json.loads((folder/'raw.json').read_text())
    n = raw_meta['points']
    nfft = n*pad_factor
    assert (folder/'transient.i32').stat().st_size == n*4
    rec = Recorder()
    with rec.stage('binary_load_int32', bytes=n*4, cache_state='uncontrolled OS page cache'):
        raw = np.fromfile(folder/'transient.i32', dtype='<i4')
    with rec.stage('convert_to_float64_release_int32'):
        transient = raw.astype(np.float64)
        del raw
    with rec.stage('hann_window_in_place_chunked'):
        for start in range(0, n, CHUNK):
            end = min(start+CHUNK, n)
            window = np.arange(start, end, dtype=np.float64)
            window *= 2*np.pi/(n-1)
            np.cos(window, out=window)
            window *= -.5
            window += .5
            transient[start:end] *= window
        del window
    with rec.stage('real_fft', fft_points=nfft, pad_factor=pad_factor):
        # n= requests zero-padding within the backend. Does NOT guarantee in-place.
        transformed = fft.rfft(transient, n=nfft, workers=1, overwrite_x=True)
    with rec.stage('release_transient'):
        del transient
        gc.collect()
    count = len(transformed)-1  # exclude DC, which cannot map to finite m/z
    with rec.stage('magnitude_to_disk_release_complex', profile_bins=count):
        profile = np.lib.format.open_memmap(out/'profile.npy', mode='w+',
                                          dtype=np.float64, shape=(count,))
        max_intensity = 0.
        for start in range(0, count, CHUNK):
            end = min(start+CHUNK, count)
            np.absolute(transformed[start+1:end+1], out=profile[start:end])
            max_intensity = max(max_intensity, float(np.max(profile[start:end])))
        profile.flush()
        del profile, transformed
        gc.collect()
    with rec.stage('build_multiresolution_cache'):
        levels = build_pyramid(out, count)
    meta = dict(raw_meta, fft_points=nfft, profile_bins=count, pad_factor=pad_factor,
                profile_dtype='float64', processing='symmetric Hann, SciPy rfft, unnormalized magnitude',
                dc_excluded=True, max_intensity=max_intensity, levels=levels)
    (out/'spectrum.json').write_text(json.dumps(meta, indent=2))
    with rec.stage('validate_synthetic_peak_positions'):
        validation = validate_peaks(out)
    rec.report(out/'processing.json', config=meta, validation=validation,
               limitations=['SciPy numerical baseline; no CoreMS calls',
                            'OS page cache uncontrolled: not a cold disk benchmark',
                            '5 ms RSS sampling can miss very short-lived allocations',
                            'flush timing is not guaranteed durable storage latency'])


class Spectrum:
    """File-backed profile and lazily mapped summaries; no full m/z array."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.meta = json.loads((self.folder/'spectrum.json').read_text())
        self.profile = np.load(self.folder/'profile.npy', mmap_mode='r')
        self.levels = {}
        self.df = self.meta['sample_rate_hz']/self.meta['fft_points']
        self.a = self.meta['calibration_a']

    def read_view(self, mz_low, mz_high, width=1600):
        if not 0 < mz_low < mz_high or width < 1:
            raise ValueError('Expected positive ordered m/z limits and positive width.')
        n = len(self.profile)
        # Include neighbours for a continuous curve at both viewport boundaries.
        lo = max(0, min(n, math.floor(self.a/mz_high/self.df)-2))
        hi = max(0, min(n, math.ceil(self.a/mz_low/self.df)+1))
        count = hi-lo
        selected = None
        if count > width*4:
            for lev in self.meta['levels']:
                selected = lev['block']
                if 2*math.ceil(count/selected) <= width*4:
                    break
        if selected is None:
            idx = np.arange(lo, hi, dtype=np.int64)
            y = np.array(self.profile[lo:hi])
        else:
            if selected not in self.levels:
                self.levels[selected] = (
                    np.load(self.folder/f'index_{selected}.npy', mmap_mode='r'),
                    np.load(self.folder/f'value_{selected}.npy', mmap_mode='r'))
            ii, vv = self.levels[selected]
            g0, g1 = math.ceil(lo/selected), hi//selected
            # Use summaries only for complete blocks. Read partial edge blocks
            # from raw data so boundary peaks are never silently omitted.
            edge_idx = []
            edge_y = []
            intervals = [(lo, hi)] if g1 <= g0 else [(lo, g0*selected), (g1*selected, hi)]
            for start, end in intervals:
                if end > start:
                    v = self.profile[start:end]
                    imin, imax = int(v.argmin()), int(v.argmax())
                    offsets = sorted((imin, imax))
                    edge_idx.extend(start+k for k in offsets)
                    edge_y.extend(float(v[k]) for k in offsets)
            if g1 > g0:
                idx = np.concatenate((ii[g0:g1].reshape(-1), np.array(edge_idx, dtype=np.int64)))
                y = np.concatenate((vv[g0:g1].reshape(-1), edge_y))
                order = np.argsort(idx, kind='stable')
                idx, y = idx[order], y[order]
            else:
                idx, y = np.array(edge_idx, dtype=np.int64), np.array(edge_y)
        x = self.a / ((idx.astype(np.float64)+1)*self.df)
        # Frequency increases, mass decreases; plotting arrays are ascending m/z.
        return x[::-1].copy(), y[::-1].copy(), dict(level_block=selected or 1, points=len(x))


def validate_peaks(folder):
    s = Spectrum(folder)
    errors = []
    for freq in s.meta['frequencies_hz']:
        k = int(round(freq/s.df))-1
        lo, hi = max(0, k-4), min(len(s.profile), k+5)
        found = lo+int(s.profile[lo:hi].argmax())
        errors.append(abs((found+1)*s.df-freq)/s.df)
    # Synthetic fixture uses isolated, strong tones. Nearest-bin error should < .55.
    passed = max(errors) < .55
    if not passed:
        raise AssertionError(f'Peak check failed: worst error {max(errors):.3f} bins')
    return dict(tones_checked=len(errors), max_frequency_error_bins=max(errors),
                tolerance_bins=.55, passed=passed)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    g = sub.add_parser('generate')
    g.add_argument('folder')
    g.add_argument('--points', type=int, default=2**26)
    g.add_argument('--tones', type=int, default=48)
    g.add_argument('--seed', type=int, default=42)
    r = sub.add_parser('process')
    r.add_argument('folder'); r.add_argument('out')
    r.add_argument('--pad-factor', type=int, choices=(1, 2, 4), default=1)
    a = p.parse_args()
    if a.command == 'generate':
        if a.points < 1024 or a.tones < 1:
            p.error('Use at least 1024 points and one tone.')
        generate(a.folder, a.points, a.tones, a.seed)
    else:
        process(a.folder, a.out, a.pad_factor)


if __name__ == '__main__':
    main()
