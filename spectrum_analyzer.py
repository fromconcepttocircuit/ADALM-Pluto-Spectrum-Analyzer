import sys
import numpy as np
import adi
import time
from scipy.signal import (firwin, lfilter, kaiserord, find_peaks)
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QLabel, QFileDialog, QStatusBar,
    QLineEdit
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCursor

##############################################################################
# DraggableTextItem for markers
##############################################################################
class DraggableTextItem(pg.TextItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)
        self.dragging = False
        self.initial_pos = None
        self.hover = False

    def hoverEnterEvent(self, event):
        self.hover = True
        QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

    def hoverLeaveEvent(self, event):
        self.hover = False
        QApplication.restoreOverrideCursor()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.hover:
            self.dragging = True
            QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)
            self.initial_pos = event.scenePos() - self.scenePos()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self.dragging and self.initial_pos is not None:
            new_pos = event.scenePos() - self.initial_pos
            view_pos = self.parentItem().mapFromScene(new_pos)
            self.setPos(view_pos)
            event.accept()
        else:
            event.ignore()

    def mouseClickEvent(self, event):
        event.ignore()

##############################################################################
# FIR filter design function
##############################################################################
def design_filter(sample_rate, cutoff_hz=400e3):
    """
    Designs a low-pass FIR filter using a Kaiser window.
    - sample_rate: in Hz
    - cutoff_hz: cutoff frequency in Hz
    """
    nyq_rate = sample_rate / 2.0
    # Transition width for the filter
    width = 10e3 / nyq_rate
    ripple_db = 180
    N_filt, beta_filt = kaiserord(ripple_db, width)
    b_filt = firwin(N_filt, cutoff_hz / nyq_rate, window=('kaiser', beta_filt))
    return b_filt

##############################################################################
# MainWindow for the GUI
##############################################################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SDR Frequency Sweep (DIY RF Detector)")
        self.setGeometry(100, 100, 1400, 900)

        # ------------------------
        # Default SDR parameters
        # ------------------------
        self.sample_rate = 1.0e6   # 1 MHz default
        self.rf_bw = 1.0e6        # 1 MHz default (same as sample_rate)
        self.cutoff_hz = 400e3    # 400 kHz default

        # Sweep parameters
        self.sweep_start = 100e6
        self.sweep_stop = 6e9
        self.sweep_steps = 2000

        # Create and configure the SDR (RX only)
        self.sdr = adi.ad9361(uri='ip:192.168.2.1')
        self.sdr.sample_rate = int(self.sample_rate)
        self.sdr.rx_lo = int(2.25e9)  # default center freq
        self.sdr.rx_rf_bandwidth = int(self.rf_bw)
        self.sdr.rx_buffer_size = 4192 * 8
        self.sdr.gain_control_mode_chan0 = 'manual'
        self.sdr.rx_hardwaregain_chan0 = 60
        self.sdr.rx_hardwaregain_chan1 = 60

        # Lock-in low-pass filter
        self.b_filt = design_filter(self.sample_rate, self.cutoff_hz)

        # Frequencies for sweep
        self.frequencies = np.linspace(self.sweep_start, self.sweep_stop, self.sweep_steps)

        # Data storage for each sweep + peak hold
        self.num_samples = self.sdr.rx_buffer_size
        self.num_reads = 1
        self.buffer_clear_reads = 1
        self.delay_time = 0.01

        self.freq_list = []         # frequencies in GHz
        self.amp_list = []          # amplitude in dB
        self.peak_hold_data = {}    # freq -> max amplitude (dB)
        self.sweep_index = 0
        self.sweep_complete = False
        self.pause_counter = 0
        self.is_paused = False

        # Known bands (we will selectively plot only the ones in range)
        self.all_known_bands = {
            "LTE 700": (0.699, 0.76),
            "GSM 850": (0.869, 0.894),
            "GSM 1900": (1.93, 1.99),
            "AWS (LTE 1700/2100)": (1.71, 2.155),
            "Wi-Fi 2.4 GHz": (2.4, 2.5),
            "Bluetooth": (2.4, 2.4835),
            "Wi-Fi 5 GHz": (5.0, 5.9),
        }
        # We'll keep references to band regions & labels so we can remove them
        self.regions_and_labels = []

        # Build the GUI layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # -----------------------------------------------------
        # Control panel (top row) for user interaction
        # -----------------------------------------------------
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)

        # Pause/Resume
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_button)

        # Clear Markers
        self.clear_markers_button = QPushButton("Clear Markers")
        self.clear_markers_button.clicked.connect(self.clear_all_markers)
        control_layout.addWidget(self.clear_markers_button)

        # Save Data
        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        control_layout.addWidget(self.save_button)

        # Reset Peak Hold
        self.reset_peak_button = QPushButton("Reset Peak Hold")
        self.reset_peak_button.clicked.connect(self.reset_peak_hold)
        control_layout.addWidget(self.reset_peak_button)

        # Threshold text box
        self.threshold_label = QLabel("Alert Threshold (dB):")
        control_layout.addWidget(self.threshold_label)
        self.threshold_edit = QLineEdit("-20")
        control_layout.addWidget(self.threshold_edit)

        # Current Frequency Label
        self.freq_label = QLabel("Current Frequency: N/A")
        control_layout.addWidget(self.freq_label)

        main_layout.addWidget(control_panel)

        # -----------------------------------------------------
        # Second row for real-time parameter changes
        # -----------------------------------------------------
        param_panel = QWidget()
        param_layout = QHBoxLayout(param_panel)

        # Text box #1: "Sample Rate (Hz)"
        param_layout.addWidget(QLabel("Sample Rate (Hz):"))
        self.sr_edit = QLineEdit(str(int(self.sample_rate)))
        param_layout.addWidget(self.sr_edit)

        # Text box #2: "Cutoff Frequency"
        param_layout.addWidget(QLabel("Cutoff (Hz):"))
        self.cutoff_edit = QLineEdit(str(int(self.cutoff_hz)))
        param_layout.addWidget(self.cutoff_edit)

        # New text box: Sweep Start
        param_layout.addWidget(QLabel("Sweep Start (Hz):"))
        self.sweep_start_edit = QLineEdit(str(int(self.sweep_start)))
        param_layout.addWidget(self.sweep_start_edit)

        # New text box: Sweep Stop
        param_layout.addWidget(QLabel("Sweep Stop (Hz):"))
        self.sweep_stop_edit = QLineEdit(str(int(self.sweep_stop)))
        param_layout.addWidget(self.sweep_stop_edit)

        # New text box: Sweep Steps
        param_layout.addWidget(QLabel("# of Points:"))
        self.sweep_steps_edit = QLineEdit(str(int(self.sweep_steps)))
        param_layout.addWidget(self.sweep_steps_edit)

        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_sdr_settings)
        param_layout.addWidget(self.apply_button)

        main_layout.addWidget(param_panel)

        # -----------------------------------------------------
        # Plot: Amplitude vs Frequency
        # -----------------------------------------------------
        self.amplitude_plot = pg.PlotWidget(title="Amplitude vs Frequency")
        self.amplitude_plot.setBackground('w')
        self.amplitude_plot.setLabel('left', "Amplitude", units='dB')
        self.amplitude_plot.setLabel('bottom', "Frequency", units='GHz')
        self.amplitude_plot.getAxis('left').setPen(pg.mkPen('k'))
        self.amplitude_plot.getAxis('bottom').setPen(pg.mkPen('k'))
        self.amplitude_plot.showGrid(x=True, y=True)
        main_layout.addWidget(self.amplitude_plot)

        # Curves
        self.amplitude_curve = self.amplitude_plot.plot(pen=pg.mkPen('b', width=2))
        self.peak_curve = self.amplitude_plot.plot(pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine))

        # Crosshair
        self.vLine_amp = pg.InfiniteLine(angle=90, movable=False)
        self.hLine_amp = pg.InfiniteLine(angle=0, movable=False)
        self.amplitude_plot.addItem(self.vLine_amp, ignoreBounds=True)
        self.amplitude_plot.addItem(self.hLine_amp, ignoreBounds=True)

        self.amplitude_plot.scene().sigMouseMoved.connect(self.mouse_moved_amp)
        self.amplitude_plot.plotItem.scene().sigMouseClicked.connect(self.mouse_clicked_amp)
        self.amplitude_markers = []

        # Add known-band overlays (initial)
        self.add_known_bands()

        # -----------------------------------------------------
        # Status bar for real-time messages
        # -----------------------------------------------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # -----------------------------------------------------
        # Timer for continuous updates
        # -----------------------------------------------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)

    ##########################################################################
    # Known bands: only show those within sweep range
    ##########################################################################
    def add_known_bands(self):
        """
        Remove any old band items, then add new ones that overlap
        the current sweep range.
        """
        # First remove existing bands/labels
        for region, label in self.regions_and_labels:
            self.amplitude_plot.removeItem(region)
            self.amplitude_plot.removeItem(label)
        self.regions_and_labels.clear()

        sweep_min_ghz = self.sweep_start / 1e9
        sweep_max_ghz = self.sweep_stop / 1e9

        y_offset_step = 5
        i = 0
        for band_name, (start, stop) in self.all_known_bands.items():
            # Skip if no overlap
            if stop < sweep_min_ghz or start > sweep_max_ghz:
                continue

            # Clamp region to the intersection with sweep range
            region_start = max(start, sweep_min_ghz)
            region_stop = min(stop, sweep_max_ghz)

            region = pg.LinearRegionItem(
                values=(region_start, region_stop),
                movable=False,
                brush=(200, 200, 0, 50)
            )
            self.amplitude_plot.addItem(region)

            text = pg.TextItem(text=band_name, color='m', anchor=(0.5, 1))
            x_center = (region_start + region_stop) / 2.0
            # Position label near top of current Y-axis range
            y_range = self.amplitude_plot.plotItem.viewRange()[1]  # (y_min, y_max)
            y_top = y_range[1]
            text.setPos(x_center, y_top - i * y_offset_step)
            self.amplitude_plot.addItem(text)

            self.regions_and_labels.append((region, text))
            i += 1

    ##########################################################################
    # Function to extract amplitude using the current FIR filter
    ##########################################################################
    def extract_amplitude(self, rx_signal):
        filtered_signal = lfilter(self.b_filt, 1.0, rx_signal)
        amplitude = np.abs(filtered_signal)
        return np.mean(amplitude)

    ##########################################################################
    # Mouse & Marker logic
    ##########################################################################
    def mouse_moved_amp(self, pos):
        if self.amplitude_plot.sceneBoundingRect().contains(pos):
            mouse_point = self.amplitude_plot.plotItem.vb.mapSceneToView(pos)
            self.vLine_amp.setPos(mouse_point.x())
            self.hLine_amp.setPos(mouse_point.y())
            self.status.showMessage(
                f"Frequency: {mouse_point.x():.2f} GHz, Amplitude: {mouse_point.y():.1f} dB"
            )

    def find_nearest_point(self, x, y, data_x, data_y):
        if not data_x or not data_y:
            return None, None
        distances = np.sqrt((np.array(data_x) - x)**2 + (np.array(data_y) - y)**2)
        nearest_idx = np.argmin(distances)
        return data_x[nearest_idx], data_y[nearest_idx]

    def mouse_clicked_amp(self, event):
        if event.button() == pg.QtCore.Qt.MouseButton.LeftButton and self.freq_list:
            # If the user clicked on a DraggableTextItem, skip
            if hasattr(event, 'currentItem') and isinstance(event.currentItem, DraggableTextItem):
                event.accept()
                return
            pos = event.scenePos()
            view = self.amplitude_plot.plotItem.vb
            mouse_point = view.mapSceneToView(pos)
            nearest_x, nearest_y = self.find_nearest_point(
                mouse_point.x(), mouse_point.y(),
                self.freq_list, self.amp_list
            )
            if nearest_x is not None:
                scatter = pg.ScatterPlotItem(
                    pos=[(nearest_x, nearest_y)],
                    symbol='o',
                    brush=pg.mkBrush(255, 165, 0, 255),
                    size=10,
                    pen=pg.mkPen(None)
                )
                label = DraggableTextItem(
                    text=f'({nearest_x:.6f} GHz,\n {nearest_y:.1f} dB)',
                    color=(0, 0, 0),
                    anchor=(0, -1),
                    border=pg.mkPen(color=(200, 200, 200)),
                    fill=pg.mkBrush('white')
                )
                label.setPos(nearest_x, nearest_y)
                self.amplitude_plot.addItem(scatter)
                self.amplitude_plot.addItem(label)
                self.amplitude_markers.append((scatter, label))
                print(f"Added amplitude marker at {nearest_x:.6f} GHz, {nearest_y:.1f} dB")

    ##########################################################################
    # Button callbacks
    ##########################################################################
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_button.setText("Resume" if self.is_paused else "Pause")

    def clear_all_markers(self):
        for scatter, label in self.amplitude_markers:
            self.amplitude_plot.removeItem(scatter)
            if label is not None:
                self.amplitude_plot.removeItem(label)
        self.amplitude_markers.clear()
        print("All markers cleared")

    def save_data(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Data", "", "CSV Files (*.csv)")
        if filename:
            data = np.column_stack((self.freq_list, self.amp_list))
            header = "Frequency_GHz,Amplitude_dB"
            np.savetxt(filename, data, delimiter=",", header=header)
            print(f"Data saved to {filename}")

    def reset_peak_hold(self):
        self.peak_hold_data.clear()
        self.peak_curve.setData([], [])
        print("Peak hold data reset")

    def apply_sdr_settings(self):
        """
        Parses user input and updates:
          - sample_rate & RF bandwidth
          - cutoff frequency
          - sweep_start, sweep_stop, sweep_steps
        Then re-initializes the sweep data and restarts it.
        """
        try:
            # Parse sample rate (also used for RF bandwidth)
            sr_val = float(self.sr_edit.text())
            self.sdr.sample_rate = int(sr_val)
            self.sdr.rx_rf_bandwidth = int(sr_val)
            self.sample_rate = sr_val
            self.rf_bw = sr_val

            # Parse cutoff frequency
            cutoff_val = float(self.cutoff_edit.text())
            self.cutoff_hz = cutoff_val
            self.b_filt = design_filter(self.sample_rate, self.cutoff_hz)

            # Parse sweep start, stop, and steps
            sweep_start_val = float(self.sweep_start_edit.text())
            sweep_stop_val = float(self.sweep_stop_edit.text())
            sweep_steps_val = int(self.sweep_steps_edit.text())

            self.sweep_start = sweep_start_val
            self.sweep_stop = sweep_stop_val
            self.sweep_steps = sweep_steps_val
            self.frequencies = np.linspace(self.sweep_start, self.sweep_stop, self.sweep_steps)

            # -------------------------------------------
            # REMOVE existing markers from the plot
            # -------------------------------------------
            for scatter, label in self.amplitude_markers:
                self.amplitude_plot.removeItem(scatter)
                if label is not None:
                    self.amplitude_plot.removeItem(label)
            self.amplitude_markers.clear()

            # Reset data for a fresh sweep
            self.freq_list.clear()
            self.amp_list.clear()
            self.peak_hold_data.clear()
            self.amplitude_curve.setData([], [])
            self.peak_curve.setData([], [])
            self.sweep_index = 0
            self.sweep_complete = False

            # Update X-axis range to new sweep
            sweep_min_ghz = self.sweep_start / 1e9
            sweep_max_ghz = self.sweep_stop / 1e9
            self.amplitude_plot.setXRange(sweep_min_ghz, sweep_max_ghz)

            # Re-draw known frequency bands
            self.add_known_bands()

            self.status.showMessage("SDR settings & sweep parameters updated successfully", 2000)
            print(f"Applied new settings: SR={sr_val}, Cutoff={cutoff_val}, "
                  f"Sweep=({self.sweep_start/1e6} MHz to {self.sweep_stop/1e6} MHz), "
                  f"Steps={self.sweep_steps}")
        except Exception as e:
            self.status.showMessage(f"Error: {e}", 3000)
            print("Error updating SDR settings:", e)

    ##########################################################################
    # Main update loop
    ##########################################################################
    def update_plot(self):
        if self.is_paused:
            return

        # Sweep in progress
        if not self.sweep_complete and self.sweep_index < len(self.frequencies):
            freq = self.frequencies[self.sweep_index]
            self.sdr.rx_lo = int(freq)
            time.sleep(self.delay_time)
            self.freq_label.setText(f"Current Frequency: {freq/1e9:.2f} GHz")

            # Clear RX buffer
            for _ in range(self.buffer_clear_reads):
                self.sdr.rx()

            # Accumulate signals
            accumulated_signal = np.zeros(self.num_samples * self.num_reads, dtype=np.complex64)
            for j in range(self.num_reads):
                rx_signal = self.sdr.rx()[0]
                # Arbitrary scaling factor
                accumulated_signal[j*self.num_samples:(j+1)*self.num_samples] = (rx_signal / 2**12) * 5.5

            # Compute amplitude (dB)
            amp_lin = self.extract_amplitude(accumulated_signal)
            amp_db = 20 * np.log10(amp_lin)
            freq_ghz = freq / 1e9

            self.freq_list.append(freq_ghz)
            self.amp_list.append(amp_db)

            # Update peak hold
            key = round(freq_ghz, 5)
            if key in self.peak_hold_data:
                self.peak_hold_data[key] = max(self.peak_hold_data[key], amp_db)
            else:
                self.peak_hold_data[key] = amp_db

            # Update main amplitude curve
            self.amplitude_curve.setData(self.freq_list, self.amp_list)

            # Update peak hold curve
            sorted_keys = sorted(self.peak_hold_data.keys())
            peak_vals = [self.peak_hold_data[k] for k in sorted_keys]
            self.peak_curve.setData(sorted_keys, peak_vals)

            # Threshold-based alert
            try:
                threshold = float(self.threshold_edit.text())
            except ValueError:
                threshold = -20  # fallback

            # If amplitude > threshold and outside known bands
            if amp_db > threshold and not any(
                start <= freq_ghz <= stop for start, stop in self.all_known_bands.values()
            ):
                scatter = pg.ScatterPlotItem(
                    pos=[(freq_ghz, amp_db)],
                    symbol='o',
                    brush=pg.mkBrush(255, 0, 0, 255),
                    size=12,
                    pen=pg.mkPen(None)
                )
                self.amplitude_plot.addItem(scatter)
                self.amplitude_markers.append((scatter, None))
                self.status.showMessage(
                    f"Alert: High amplitude at {freq_ghz:.2f} GHz: {amp_db:.1f} dB", 2000
                )

            self.sweep_index += 1
            self.status.showMessage(f"Sweeping: {freq_ghz:.2f} GHz, Amplitude: {amp_db:.1f} dB")
            print(f"Freq: {freq/1e6:.2f} MHz, Amp: {amp_db:.2f} dB")

        # Sweep just finished
        elif not self.sweep_complete:
            self.sweep_complete = True
            self.pause_counter = 0

            # Auto-detect peaks after the sweep
            if len(self.amp_list) > 0:
                try:
                    threshold = float(self.threshold_edit.text())
                except ValueError:
                    threshold = -20
                arr_amp = np.array(self.amp_list)
                peaks, _ = find_peaks(arr_amp, height=threshold)
                for idx in peaks:
                    freq_val = self.freq_list[idx]
                    amp_val = self.amp_list[idx]
                    scatter = pg.ScatterPlotItem(
                        pos=[(freq_val, amp_val)],
                        symbol='t',
                        brush=pg.mkBrush(0, 0, 255, 255),
                        size=14,
                        pen=pg.mkPen(None)
                    )
                    self.amplitude_plot.addItem(scatter)
                    self.amplitude_markers.append((scatter, None))
                    print(f"Auto-detected peak at {freq_val:.2f} GHz, {amp_val:.1f} dB")

        # Pause between sweeps, then reset
        else:
            self.pause_counter += 1
            if self.pause_counter >= 50:
                # Clear markers
                for scatter, label in self.amplitude_markers:
                    self.amplitude_plot.removeItem(scatter)
                    if label is not None:
                        self.amplitude_plot.removeItem(label)
                self.amplitude_markers.clear()

                # Reset for new sweep
                self.freq_list.clear()
                self.amp_list.clear()
                self.sweep_index = 0
                self.sweep_complete = False
                print("Starting new sweep")


##############################################################################
# Main entry point
##############################################################################
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    try:
        sys.exit(app.exec())
    finally:
        # Clean up SDR buffer
        main_window.sdr.rx_destroy_buffer()