# Nokia 3210 (2024) → Voice → Claude Pipeline

**Date:** 2026-11-19  
**Goal:** Use Nokia 3210 (2024) with Jio SIM as a remote voice input device to capture ideas and send them to Claude, with responses readable on laptop.

---

## Device Constraints

- Nokia 3210 (2024), Series 30+ OS
- Jio SIM (VoLTE, 4G LTE)
- No WiFi, no apps, no smartphone
- Communication channels available: **GSM voice calls** and **SMS only**
- Bluetooth 5.0 present but only useful within ~10m range

---

## Architecture Options

### Option A — Cloud path (Nokia away from laptop)

```
Nokia speaks → Jio VoLTE call → cloud phone number
→ server records call audio
→ Whisper STT (transcription)
→ Claude / Gemini API (AI response)
→ response stored in file / DB
→ user reads response on laptop later
```

**Phone number services compared:**

| Service | Cost | Voice | Latency | Setup | India Nokia |
|---|---|---|---|---|---|
| Missed-call trigger (Twilio trial) | $0 (unanswered = not billed) | No — ring count = command | Instant | Low | Yes |
| CallCentric free DID | $0 (60 min/month) | Yes | 15–30s | Medium | Yes (international rate) |
| Truecaller voicemail | $0 | Yes | Manual only | None | Yes (calls Indian mobile) |
| Oracle VM + VoIP.ms | $0 VM + ~₹70/month DID | Yes | 15–30s | High | Yes |
| Twilio $15 trial | $0 to start, ~₹100/month after | Yes | 15–30s | Low | Yes |
| Google Voice | $0 | Yes (voicemail only) | 2–5 min | Low | No (needs US account) |
| IPKall | Likely dead | — | — | — | — |

**Recommended cloud stack (free to start):**
```
Twilio $15 trial (no card needed)
→ Cloudflare Tunnel (free, permanent URL)
→ Flask webhook server on laptop
→ Whisper STT
→ Gemini Flash API (free tier, 1500 req/day)
→ response saved to text file
```

When Twilio trial ends: migrate to Oracle Cloud Always Free VM + CallCentric free DID or VoIP.ms (~₹70/month DID).

---

### Option B — SIM800L module on laptop (recommended, zero call cost)

Nokia calls the SIM800L's Jio SIM (Jio-to-Jio = free on many plans). Laptop receives and processes the call locally.

**Hardware required (~₹500–700 total):**

| Part | Price | Purpose |
|---|---|---|
| SIM800L module | ₹200–400 | GSM modem |
| CP2102 USB-UART adapter | ₹80–150 | UART → USB to laptop |
| 18650 battery + holder | ₹150–200 | Power (USB alone insufficient) |
| 3.5mm male-male audio cable | ₹50 | Route call audio to laptop mic input |
| 100Ω + 470Ω resistors | ₹5 | Audio voltage divider |

**Wiring:**

```
18650 (3.7V)
  (+) ──────────────── SIM800L VCC
  (–) ──────────────── SIM800L GND ──── CP2102 GND

CP2102 (USB side → laptop)
  TXD ──────────────── SIM800L RXD
  RXD ──────────────── SIM800L TXD
  GND ──── (shared with battery GND above)
  ⚠ DO NOT connect CP2102 VCC to SIM800L VCC

Audio (call voice → laptop mic input)
  SIM800L SPK+ ── 100Ω ── 3.5mm tip
  SIM800L SPK- ── 470Ω ── 3.5mm sleeve/GND
                           └── laptop 3.5mm mic jack
```

**Why 18650 and not USB power:**  
SIM800L transmits in bursts at up to 2A peak. Laptop USB delivers 500–900mA. Undervoltage during burst causes random resets and dropped calls.

**Software flow:**
```
Nokia calls Jio SIM in SIM800L
→ CP2102 COM port on Windows sees: RING + CLIP (caller ID)
→ Windows Python sends AT command: ATA (answer)
→ Call audio: SIM800L SPK pins → voltage divider → 3.5mm → laptop mic input
→ Python records mic input (pyaudio / sounddevice)
→ Nokia hangs up → Python stops recording
→ Whisper transcribes WAV file
→ Claude / Gemini API processes the idea
→ Response saved to dated text file
→ User reads response on laptop
```

**Laptop must be on** for Option B to work. Option A (cloud path) works when laptop is off.

---

## WSL2 / Windows Notes

- CP2102 USB-UART shows as COM3/COM4/etc in Windows Device Manager
- WSL2 cannot access COM ports natively — needs `usbipd-win` or run handler in Windows Python
- Aura already runs via Windows Python (`%LOCALAPPDATA%\Aura\venv\Scripts\python.exe`) — use the same interpreter for SIM800L handler
- Audio recording from 3.5mm mic input works natively on Windows via `pyaudio` or `sounddevice`

**Quick test after wiring:**
```python
import serial
s = serial.Serial('COM4', 9600, timeout=1)  # adjust COM number
s.write(b'AT\r\n')
print(s.readline())  # expected: b'OK\r\n'
```

---

## AI Backend Options (free tiers)

| Service | Free tier | Quality | Notes |
|---|---|---|---|
| Gemini 1.5 Flash | 1500 req/day, 1M tokens/min | Good | Best free option |
| Groq (LLaMA 3.3 70B) | 14,400 req/day | Very good | Fastest inference |
| Claude API | No free tier | Best | Needs Anthropic API key (paid) |
| Ollama (local) | Free, unlimited | Good | Runs on laptop, no internet needed |

---

## Next Steps

1. **Buy hardware:** SIM800L module, CP2102, 18650 battery from Amazon/Robu.in
2. **Wire per diagram above**
3. **Test serial connection** with quick test script
4. **Build Python handler:** answer call → record audio → Whisper → Gemini → save response
5. **Integrate with Aura** (`aura remote` module) or run as standalone service
6. **Optional cloud fallback:** Twilio trial for when laptop is off

---

## Alternative: Remove Nokia 3210 from the Picture

Without the Nokia 3210, the GSM call path and all its complexity (AT commands, audio routing, phone numbers, billing) disappears. Easier options exist.

### Option 1 — ESP32 + INMP441 microphone (~₹450) ★ Recommended

This is the exact YouTube ESP32 voice project pattern.

```
Press button on ESP32
→ records voice via I2S microphone to memory
→ release button → sends WAV file over WiFi to laptop Flask server
→ Whisper STT on laptop
→ Claude / Gemini API processes idea
→ response saved to dated text file
→ user reads on laptop
```

- No phone number, no SIM, no call cost
- Works anywhere with WiFi (home, office)
- Away from WiFi: add a Jio MiFi router (~₹500) as hotspot, ESP32 connects to it
- **Total cost: ₹450 hardware only, or ₹950 with MiFi for away-from-home use**

**Parts:**
| Part | Price |
|---|---|
| ESP32 DevKit | ₹250–350 |
| INMP441 I2S microphone module | ₹100–150 |
| Push button + wires | ₹20 |

### Option 2 — XIAO ESP32-S3 Sense (~₹800)

Onboard microphone, no extra parts. Smaller than a matchbox. Same WiFi + WAV send flow.

### Option 3 — Raspberry Pi Zero 2W (~₹1500)

Full Linux, runs Python directly, USB mic. Overkill for simple voice capture but most flexible.

### Option 4 — Cheap Android phone (~₹3000–5000)

Termux + Python. Sends audio over WiFi or mobile data. Telegram bot or HTTP POST to server. Most capable but highest cost.

### Option 5 — Laptop mic + hotkey (zero cost)

Aura already does this locally (Ctrl+Alt+J → speak). Only gap: not usable when physically away from laptop.

### Comparison

| Option | Cost | Away from WiFi | Complexity | Matches YouTube projects |
|---|---|---|---|---|
| ESP32 + INMP441 | ₹450 | Need MiFi (₹500) | Low | Yes, exactly |
| XIAO ESP32-S3 Sense | ₹800 | Need MiFi | Very low | Yes |
| Nokia 3210 + SIM800L | ₹500–700 + call cost | Yes (GSM) | High | No |
| Cheap Android | ₹3000+ | Uses mobile data | Medium | Partially |
| Laptop mic only | ₹0 | No (at laptop) | None | N/A |

**Verdict:** ESP32 + INMP441 + home WiFi = ₹450, buildable in a weekend. Add ₹500 Jio MiFi for away-from-home use. Nokia/SIM800L path only makes sense if you already own the Nokia and want zero extra hardware spend.

---

## References

- SIM800L datasheet AT command reference: `AT+CLIP=1` (caller ID), `ATA` (answer), `ATH` (hang up)
- Whisper: `openai/whisper` (open source, runs locally)
- Gemini Flash free tier: `generativelanguage.googleapis.com`
- Oracle Cloud Always Free: 4 ARM CPUs, 24 GB RAM, free forever
- CallCentric free DID: 60 inbound minutes/month, US number
- Cloudflare Tunnel: free permanent HTTPS tunnel with named tunnel + domain
