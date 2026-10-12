"""Small deterministic checks against direct numerical references, including tails."""
import json
from pathlib import Path
import tempfile
import numpy as np
from scipy import fft
from benchmark import build_pyramid, Spectrum


def main():
    rng = np.random.default_rng(7)
    # Non-power-of-two length exercises partial blocks through the hierarchy.
    values = rng.random(100_003)
    values[12_345] = 1000  # a narrow isolated spike must survive overview rendering
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        np.save(folder/'profile.npy', values)
        levels = build_pyramid(folder, len(values))
        for lev in levels:
            block = lev['block']
            ii = np.load(folder/f'index_{block}.npy')
            vv = np.load(folder/f'value_{block}.npy')
            for g in range(len(ii)):
                reference = values[g*block:min((g+1)*block, len(values))]
                assert vv[g].min() == reference.min()
                assert vv[g].max() == reference.max()
                np.testing.assert_array_equal(values[ii[g]], vv[g])
                assert ii[g, 0] <= ii[g, 1]
        meta = dict(sample_rate_hz=2_000_000, fft_points=2*len(values), calibration_a=1e8,
                    max_intensity=1000, levels=levels)
        (folder/'spectrum.json').write_text(json.dumps(meta))
        s = Spectrum(folder)
        x, y, detail = s.read_view(100, 1e6, 100)
        assert 1000 in y and detail['level_block'] > 1
        assert np.all(np.diff(x) >= 0)
        target = s.a / ((12345+1)*s.df)
        x, y, detail = s.read_view(target-.001, target+.001, 1600)
        assert detail['level_block'] == 1 and 1000 in y
        np.testing.assert_allclose(y, values[np.rint(s.a/x/s.df).astype(int)-1], rtol=0, atol=0)
        # Move spike close to a partial summary-block edge and verify preservation.
        for span in (100, 5000, 15000, 30000):
            lo_bin, hi_bin = 12344, min(len(values)-1, 12345+span)
            low, high = s.a/((hi_bin+1)*s.df), s.a/((lo_bin+1)*s.df)
            xx, yy, _ = s.read_view(low, high, 10)
            assert 1000 in yy
    # Check blockwise Hann against canonical window, and FFT vs explicit DFT.
    raw = rng.normal(size=64)
    actual = raw.copy()
    for start in range(0, 64, 7):
        end = min(start+7, 64)
        actual[start:end] *= .5-.5*np.cos(2*np.pi*np.arange(start, end)/63)
    np.testing.assert_allclose(actual, raw*np.hanning(64), atol=2e-15)
    n = 128
    expected = np.exp(-2j*np.pi*np.outer(np.arange(n//2+1), np.arange(64))/n) @ actual
    np.testing.assert_allclose(fft.rfft(actual, n=n), expected, atol=1e-12)
    print('PASS: all hierarchy extrema, original indices, tail blocks, peak visibility,')
    print('      zoom samples, m/z mapping, symmetric Hann and zero-padded FFT reference.')


if __name__ == '__main__': main()
