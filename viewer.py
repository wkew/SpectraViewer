#!/usr/bin/env python3
"""Qt spectrum viewer and offscreen render benchmark; scaled-copy stress fixture."""
import argparse
import gc
import json
import os
from pathlib import Path
import time

import numpy as np
from benchmark import Recorder, Spectrum


def prepare(spectrum, count, lo, hi, width, mode):
    """Query each trace separately, including mass conversion; unique output arrays.

    All traces share one source profile and OS cache. Gains differ. This measures
    rendering/data preparation, NOT 200 independent spectra or independent I/O.
    """
    output = []
    detail = None
    for i in range(count):
        x, y, detail = spectrum.read_view(lo, hi, width)
        y /= spectrum.meta['max_intensity']
        y *= .8+.4*(i+1)/(count+1)
        if mode == 'stack':
            y += i*1.3
        output.append((x, y))
    return output, detail


def qt_imports():
    global QtCore, QtGui, QtWidgets, pg
    from PySide6 import QtCore, QtGui, QtWidgets
    import pyqtgraph as pg
    pg.setConfigOptions(antialias=False, background='#101925', foreground='#d7e3ec')


def make_plot(count, width=1800, height=1000):
    plot = pg.PlotWidget()
    plot.resize(width, height)
    plot.setLabel('bottom', 'm/z')
    plot.setLabel('left', 'Relative intensity / stack offset')
    plot.showGrid(x=True, y=True, alpha=.12)
    plot.getPlotItem().hideButtons()
    plot.disableAutoRange()
    colors = ['#45c9df', '#b8a5ff', '#ffa86b', '#68d5a5', '#f18abb']
    curves = [plot.plot(pen=pg.mkPen(colors[i % len(colors)], width=1)) for i in range(count)]
    return plot, curves


def paint(plot, width=1800, height=1000):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtGui.QColor('#101925'))
    painter = QtGui.QPainter(image)
    try:
        plot.render(painter)
    finally:
        painter.end()
    return image


def render_benchmark(folder, output, counts=(1, 20, 200), frames=12):
    qt_imports()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    rec = Recorder()
    with rec.stage('open_metadata_and_memory_maps'):
        spectrum = Spectrum(folder)
    target = spectrum.a / spectrum.meta['frequencies_hz'][int(np.argmax(spectrum.meta['amplitudes']))]
    cases = [('full', 125., 2000.), ('region', max(125., target-20), min(2000., target+20)),
             ('peak', target-.015, target+.015)]
    rows = []
    for mode in ('overlay', 'stack'):
        for count in counts:
            plot, curves = make_plot(count)
            plot.ensurePolished()
            plot.show()
            app.processEvents()
            # Lay out the widget and prime font caches. No screen/GPU timing claim.
            paint(plot)
            for case, lo, hi in cases:
                samples = []
                plot.setTitle(f'FTICR benchmark | {count} scaled copies | {mode} | {case}')
                app.processEvents()
                with rec.stage(f'{mode}_{count}_{case}', frames=frames):
                    for frame in range(frames+1):  # exclude one warm-up per case
                        delta = (hi-lo)*.0001*(frame % 5)
                        low, high = lo+delta, hi+delta
                        t0 = time.perf_counter()
                        data, detail = prepare(spectrum, count, low, high, 1700, mode)
                        t1 = time.perf_counter()
                        for curve, (x, y) in zip(curves, data):
                            curve.setData(x, y)
                        plot.setXRange(low, high, padding=0)
                        plot.setYRange(-.03, count*1.3 if mode == 'stack' else 1.25, padding=0)
                        t2 = time.perf_counter()
                        image = paint(plot)
                        t3 = time.perf_counter()
                        if frame:
                            samples.append(dict(prepare_ms=(t1-t0)*1000,
                                                submit_ms=(t2-t1)*1000,
                                                paint_ms=(t3-t2)*1000,
                                                total_ms=(t3-t0)*1000))
                    if (count == 200 and case == 'full') or (count == 1 and case == 'peak'):
                        image.save(str(out/f'{mode}_{count}_{case}.png'))
                stats = {}
                for key in samples[0]:
                    a = [s[key] for s in samples]
                    stats[key] = dict(median=float(np.median(a)), p95=float(np.percentile(a, 95)))
                rows.append(dict(mode=mode, traces=count, view=case, viewport=[lo, hi],
                                 points_per_trace=detail['points'], level_block=detail['level_block'],
                                 statistics=stats, samples=samples))
                print(json.dumps({k:v for k,v in rows[-1].items() if k != 'samples'}), flush=True)
            del curves, data, image
            plot.close()
            plot.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
            gc.collect()
    rec.report(out/'display.json', results=rows, qt=QtCore.qVersion(), pyqtgraph=pg.__version__,
               render_size=[1800, 1000], frames_per_case=frames,
               fixture='200 individually prepared/scaled copies of ONE file-backed spectrum',
               limitations=['Shared source pages: does not benchmark 200 independent-file I/O',
                            'Offscreen CPU QImage painting; not measured monitor FPS or GPU performance',
                            'Timing excludes PNG encoding and screenshot writing',
                            'Sequential synchronous preparation; no background UI queue in this prototype'])


def launch(folder, smoke_test=None):
    qt_imports()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    spectrum = Spectrum(folder)
    window = QtWidgets.QMainWindow()
    window.setWindowTitle('FTICR bench | synthetic spectrum review')
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    title = QtWidgets.QLabel('FTICR / spectrum review prototype')
    title.setStyleSheet('font-size:22px; font-weight:600; padding:10px')
    layout.addWidget(title)
    note = QtWidgets.QLabel('Synthetic data • 1 source spectrum • up to 200 scaled-copy traces • cached extrema / exact samples on zoom')
    layout.addWidget(note)
    controls = QtWidgets.QHBoxLayout()
    count = QtWidgets.QSpinBox(); count.setRange(1, 200); count.setValue(20)
    mode = QtWidgets.QComboBox(); mode.addItems(['overlay', 'stack'])
    full = QtWidgets.QPushButton('Full view')
    peak = QtWidgets.QPushButton('Strongest peak')
    export = QtWidgets.QPushButton('Export PNG…')
    controls.addWidget(QtWidgets.QLabel('Traces')); controls.addWidget(count)
    for widget in (mode, full, peak, export): controls.addWidget(widget)
    controls.addStretch()
    layout.addLayout(controls)
    plot, initial_curves = make_plot(0)
    layout.addWidget(plot, 1)
    status = QtWidgets.QLabel('Mouse wheel: zoom • drag: pan • right click: plot controls')
    layout.addWidget(status)
    curves = []
    timer = QtCore.QTimer(); timer.setSingleShot(True); timer.setInterval(25)
    def redraw():
        t0 = time.perf_counter()
        while len(curves) < count.value():
            i = len(curves)
            curves.append(plot.plot(pen=pg.mkPen(pg.intColor(i, hues=20), width=1)))
        while len(curves) > count.value():
            plot.removeItem(curves.pop())
        lo, hi = plot.viewRange()[0]
        if lo <= 0: return
        data, detail = prepare(spectrum, count.value(), lo, hi, max(100, plot.width()-100), mode.currentText())
        for curve, (x, y) in zip(curves, data): curve.setData(x, y)
        plot.setYRange(-.03, count.value()*1.3 if mode.currentText() == 'stack' else 1.25, padding=0)
        status.setText(f'{detail["points"]:,} displayed points/trace | summary block {detail["level_block"]:,} | '
                       f'prepare + submit {(time.perf_counter()-t0)*1000:.1f} ms (excludes paint) | wheel: zoom, drag: pan')
    def schedule(*_): timer.start()
    timer.timeout.connect(redraw)
    plot.getViewBox().sigXRangeChanged.connect(schedule)
    plot.getViewBox().sigResized.connect(schedule)
    count.valueChanged.connect(schedule); mode.currentTextChanged.connect(schedule)
    full.clicked.connect(lambda: plot.setXRange(125, 2000, padding=0))
    target = spectrum.a/spectrum.meta['frequencies_hz'][int(np.argmax(spectrum.meta['amplitudes']))]
    half_width = 20*spectrum.df*target**2/spectrum.a
    peak.clicked.connect(lambda: plot.setXRange(target-half_width, target+half_width, padding=0))
    def save_image():
        dest, _ = QtWidgets.QFileDialog.getSaveFileName(window, 'Export plot', 'spectrum.png', 'PNG (*.png)')
        if dest: plot.grab().save(dest)
    export.clicked.connect(save_image)
    window.setCentralWidget(panel); window.resize(1400, 850)
    window.show(); plot.setXRange(125, 2000, padding=0); redraw()
    if smoke_test:
        output = Path(smoke_test); output.mkdir(parents=True, exist_ok=True)
        def exercise_stack():
            count.setValue(200); mode.setCurrentText('stack'); full.click()
        def capture_stack():
            assert len(curves) == 200
            window.grab().save(str(output/'viewer_200_stack.png'))
            count.setValue(1); mode.setCurrentText('overlay'); peak.click()
        def capture_peak():
            assert len(curves) == 1
            window.grab().save(str(output/'viewer_peak.png'))
            print('PASS: desktop viewer startup, 200-trace stack, full view, peak zoom, screenshot export.')
            app.quit()
        QtCore.QTimer.singleShot(100, exercise_stack)
        QtCore.QTimer.singleShot(700, capture_stack)
        QtCore.QTimer.singleShot(1300, capture_peak)
    app.exec()
    # Dispose Qt-owned graphics while QApplication is still alive; relying on
    # Python interpreter shutdown can destroy the objects in an unsafe order.
    timer.stop()
    timer.timeout.disconnect()
    plot.getViewBox().sigXRangeChanged.disconnect(schedule)
    plot.getViewBox().sigResized.disconnect(schedule)
    plot.clear()
    curves.clear()
    window.close()
    window.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', nargs='?', default=str(Path(__file__).parent/'demo'/'spectrum'))
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--output', default='display_results')
    parser.add_argument('--frames', type=int, default=12)
    parser.add_argument('--smoke-test', metavar='OUTPUT_DIR', help='Exercise controls offscreen and exit')
    args = parser.parse_args()
    if args.frames < 1: parser.error('--frames must be positive')
    if args.benchmark:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        render_benchmark(args.folder, args.output, frames=args.frames)
    else:
        if args.smoke_test: os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        launch(args.folder, args.smoke_test)
