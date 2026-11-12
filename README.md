# 🛡️ ScrollGuard AI

**AI-powered doomscrolling detector.** Watches your webcam while you study — the moment you pick up your phone, it fires an alarm and logs the distraction.

Built with Python 3.12 · PySide6 · YOLOv8 · MediaPipe · SQLite

---

## 🎯 Why this exists

I kept losing hours to "quick phone checks" while studying. Screen-time apps only show you the damage *after* the fact. ScrollGuard uses a webcam + computer vision to intervene **in the moment** — the way a strict study partner would.

The tricky part isn't detecting a phone (YOLO does that trivially). It's distinguishing a **phone lying on your desk** from a **phone you just picked up to scroll**. That's what ScrollGuard's state machine does.

---

## ✨ Features

- **Real-time phone detection** — YOLOv8n running on every 5th frame for 20+ FPS
- **Hand tracking** — MediaPipe Hands (21 landmarks per hand)
- **Proximity analysis** — fingertip-to-phone distance determines if you're holding it
- **7-state machine** — `NO_PHONE → PHONE_DETECTED → PHONE_ON_DESK → HAND_APPROACHING → PHONE_PICKED_UP → POSSIBLE_PHONE_USE → DISTRACTION_CONFIRMED`
- **Loud alarm + voice warnings** — pygame sound loop + gTTS-generated voice lines
- **Pomodoro focus sessions** — 25/50/60/90-min presets, auto-pauses during distractions
- **Analytics** — weekly focus charts, distraction hours, productivity score
- **History** — every distraction logged with timestamp, duration, confidence
- **100% local** — SQLite database, no cloud, no accounts, no telemetry


## 🚀 Quick Start

### Requirements
- Windows 10/11
- Python 3.12
- A webcam
- ~2 GB free disk space (PyTorch + MediaPipe)

### Setup

```bash
# 1. Clone
git clone https://github.com/Satbir004/ScrollGuard-AI.git
cd ScrollGuard-AI

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies (takes 5–10 min; PyTorch is ~800 MB)
pip install -r requirements.txt

# 4. Generate voice warning lines (one-time, needs internet)
python scripts\generate_voice_pack.py

# 5. Run
python main.py