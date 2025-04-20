
# ADALM Pluto SDR Spectrum Analyzer

**See invisible electromagnetic waves around you!**  
This project turns an **ADALM Pluto SDR** into a **real-time Spectrum Analyzer** using **Python** and **PyQt**, allowing you to visualize Wi-Fi, LTE, GSM, Bluetooth, and other RF signals that are constantly present in our environment.

---

## 📡 See It In Action (Video Demo)

🎬 **Watch the full video demo and tutorial on YouTube**:  

[![Watch the video](https://img.youtube.com/vi/aKFjk-2SaZ8/0.jpg)](https://www.youtube.com/watch?v=aKFjk-2SaZ8)

---

## 🚀 What is this?

Have you ever wondered what the world around you would look like if you could see the invisible electromagnetic waves — like Wi-Fi, LTE, GSM — that are constantly traveling through the air?

In this project, we build a **real-time Spectrum Analyzer using ADALM Pluto SDR and Python**, allowing us to "see" those signals and **explore the electromagnetic spectrum** right from your desk!

---

## ⚙️ How does it work?

- The SDR **sweeps across frequencies**, measuring amplitude of each frequency using a **lock-in amplifier technique**.
- The received signal is **mixed with the SDR's Local Oscillator (RX LO)** to down-convert the desired component to DC.
- A **low-pass filter** extracts the amplitude of that component.
- The process **repeats for every frequency step**, generating a real-time spectrum of everything around you!

---

## 🎯 Features

- ✅ Real-time wideband frequency sweep and visualization
- ✅ **Peak hold** and **threshold-based alerts**
- ✅ **Draggable markers** for easy analysis
- ✅ Highlights known bands (Wi-Fi, LTE, GSM, Bluetooth, etc.)
- ✅ Fully adjustable sweep and filter settings via GUI
- ✅ Data export to CSV


---

## 🛠 Tools & Technologies Used

- [ADALM Pluto SDR](https://www.analog.com/en/design-center/evaluation-hardware-and-software/evaluation-boards-kits/adalm-pluto.html)
- Python 3
- PyQt6 (GUI framework)
- PyQtGraph (real-time graph plotting)
- NumPy & SciPy (signal processing and filtering)

---

## 💾 How to Use

### 1. **Clone the Repository**

```bash
git clone https://github.com/fromconcepttocircuit/ADALM-Pluto-Spectrum-Analyzer.git
cd ADALM-Pluto-Spectrum-Analyzer
```

### 2. **Install Required Python Libraries**

```bash
pip install pyadi-iio numpy scipy pyqt6 pyqtgraph
```

### 3. **Linux Users: Install Additional System Package**

If you're on **Linux**, install this to avoid missing Qt plugin errors:

```bash
sudo apt install libxcb-cursor-dev
```

### 4. **Run the Spectrum Analyzer**

```bash
python spectrum_analyzer.py
```

### 5. **Connect ADALM Pluto SDR**

- Make sure **ADALM Pluto is connected and reachable** at its default IP: `192.168.2.1`.  
- You can adjust the IP address in the code if necessary:

```python
self.sdr = adi.ad9361(uri='ip:192.168.2.1')
```
---

## ⚙️ Adjust Sweep and Settings in GUI

- **Sample Rate (Hz)**: Adjust sampling speed.
- **Cutoff (Hz)**: Set filter cutoff frequency.
- **Sweep Start/Stop (Hz)**: Frequency range to scan.
- **# of Points**: Resolution of the sweep.
- **Threshold (dB)**: Level to trigger alerts.
- **Peak Hold / Markers**: Analyze signals in detail.

---

## ⚠️ Notes

- The IP `192.168.2.1` is the **default address for ADALM Pluto SDR**. Change it in the code if yours is configured differently.
- The GUI may require **PyQt6-specific themes** for proper visualization — adjust as needed.

---

## 📈 Example Signals Detected

- 📶 **Wi-Fi 2.4 GHz & 5 GHz**
- 📱 **LTE / GSM / AWS bands**
- 🎧 **Bluetooth devices**

### ☕ Support My Work  
If you find this project helpful, consider supporting me:  
[Buy Me a Coffee](https://buymeacoffee.com/concepttoco)

---

## 📜 License

This project is licensed under the **MIT License** — feel free to use, modify, and share!

---

## 🙌 Contributions and Feedback

If you try this project and have feedback or improvements, **feel free to open an issue or submit a pull request**. Let's make SDR more accessible together!

---

## 🔗 Connect

- **YouTube Channel**: [From Concept To Circuit](https://www.youtube.com/@fromconcepttocircuit)
- **GitHub**: [https://github.com/fromconcepttocircuit](https://github.com/fromconcepttocircuit)
- More RF & SDR projects coming soon!

---



#ADALMPluto #SpectrumAnalyzer #ElectromagneticWaves #RFSignals #PythonProjects #SDR #WirelessSignals
