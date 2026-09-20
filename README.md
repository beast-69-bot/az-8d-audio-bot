# 🎧 AZ 8D Audio & Video Studio Bot (@azmusicstudiobot)

A production-ready Telegram Bot built with Python, NumPy/SciPy psychoacoustic DSP, and FFmpeg for transforming regular songs into **320kbps 8D Spatial Audio** and **Full HD 1080p Audio-Reactive Visualizer Videos**.

---

## ✨ Features

- 🎧 **8D Spatial Audio**: 360-degree continuous binaural orbit around the head with anchored mono sub-bass (<110Hz).
- 🌀 **16D Spatial Audio**: Dual counter-rotating frequency bands (vocals vs instruments).
- 🌌 **Slowed + Reverb**: Deep nostalgic daycore / chillwave vibe.
- ⚡ **Sped Up / Nightcore**: High-energy dance tempo with transient pitch boost.
- 💣 **Extreme Bass Boost**: Sub-harmonic 45–80Hz boost with zero digital clipping.
- 🎬 **Full HD 1080p Video Visualizers**:
  - 〰️ Smooth Center Wave
  - 📊 Spectrum Equalizer Bars
  - 🪞 Mirrored Dual Frequency
  - 🌈 Neon Cyber Glow
  - 🌀 3D Stereo Orbit Scope
- 🖼️ **Custom Wallpaper Support**: Allows users to upload custom background images.
- 🚀 **EBU R128 Loudness Normalization**: Mastered to `-14.0 LUFS` and `-1.0 dBTP`.
- ⚡ **Threaded Processing Queue**: Non-blocking asynchronous execution.

---

## 🚀 Quick Setup & Deployment

### 1. Requirements
- Python 3.10+
- FFmpeg installed and available on `PATH`

### 2. Installation
```bash
git clone https://github.com/beast-69-bot/az-8d-audio-bot.git
cd az-8d-audio-bot
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and set your token:
```bash
cp .env.example .env
```

### 4. Run the Bot
```bash
python bot.py
```

---

## 🛠️ Systemd Service (Linux Server / GCP Deployment)

```ini
[Unit]
Description=AZ 8D Audio Studio Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/az-8d-audio-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
