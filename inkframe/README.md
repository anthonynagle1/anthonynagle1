# InkFrame

A slim, battery-powered, portrait e-ink art frame.

- **Screen:** Pimoroni Inky Impression 13.3" (E Ink Spectra 6, 1200×1600 portrait)
- **Computer:** Raspberry Pi Zero 2 WH
- **Battery:** PiSugar 3 (1200 mAh, with a wake-up clock)

**How it works:** the frame spends almost all its time **fully powered off**. E-ink keeps the
picture with no power. The PiSugar's clock wakes the Pi on a schedule. The Pi then shows the
next picture, sets the next alarm and powers off again. Each wake takes about 90 seconds.

**To add pictures:** press the PiSugar button. The frame stays awake for 10 minutes. Open
`http://inkframe.local` on your phone, on the same Wi-Fi, to upload pictures and change
settings. While the charger is plugged in, the frame stays awake.

---

## Setup guide

### 1. Flash the SD card (on your computer, ~15 min)
1. Install **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)**.
2. Choose **Raspberry Pi Zero 2 W** → **Raspberry Pi OS Lite (64-bit)** → your microSD card.
3. Click **Edit settings** and set:
   - Hostname: `inkframe`
   - A username and password
   - Your **Wi-Fi name and password**
   - On the **Services** tab, turn on **SSH** (password login).
4. Write the card, then put it in the Pi.

### 2. Test on your desk before building the frame
1. Plug the Inky screen **straight onto the Pi's pins** for now, with no ribbon cable yet.
2. Sit the Pi on top of the PiSugar 3. Its spring pins touch the bottom of the Pi.
3. Plug a USB-C charger into the PiSugar and press its button to turn on.
4. Wait ~2 minutes for the first boot.

### 3. Connect to the Pi
On a Mac (Terminal) or Windows (PowerShell):
```
ssh yourusername@inkframe.local
```

### 4. Install InkFrame
```
sudo apt-get install -y git
git clone https://github.com/anthonynagle1/anthonynagle1.git
cd anthonynagle1/inkframe
sudo ./install.sh
```
This takes 15–30 minutes on a Pi Zero, mostly installing Python packages.

### 5. Install the PiSugar software
Use PiSugar's official installer and choose **PiSugar 3** when asked:
```
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
```
If that link has changed, follow the current instructions at
<https://github.com/PiSugar/pisugar-power-manager-rs>.

Then reboot:
```
sudo reboot
```

### 6. Check it works
- After ~1 minute the screen shows a **welcome page** with the web address.
- Open **http://inkframe.local** on your phone and upload a few pictures.
- **If a picture is upside down:** go to Settings → *Picture upside down?* → switch to Rotation B.
- **Test sleeping:** unplug the charger, then tap **Sleep now**. The Pi powers off and the
  picture stays on screen. It wakes on its own at the "Next picture" time shown on the page.
- In the PiSugar web page (`http://inkframe.local:8421`), check that the battery reads correctly.

### 7. Build the slim frame
1. Measure the **visible screen area** and have a mat cut to that size, or cut it yourself.
   Make it ~2 mm smaller on each side so the screen's edge stays hidden.
2. Put in this order: glass → mat → screen, face down. Hold the screen in place with small
   pieces of **VHB tape** on its border. Never press on the middle of the screen.
3. Connect the **40-pin male-to-female ribbon cable**. Its female end goes onto the Pi's pins
   and its male end goes into the Inky's socket. Line up pin 1 on both ends (look for the
   coloured stripe on the cable).
4. Cut a hole in the backing board where the Pi and PiSugar will sit. Mount them flat with
   M2.5 standoffs, side by side with the screen board. Nothing should be stacked.
5. Leave the **PiSugar button and USB-C charging port** reachable from the back or the bottom
   edge, for example through a small notch in the backing board.
6. Close the frame and hang it.

---

## Battery life (estimates)

| Picture changes | Approx. time per charge |
|---|---|
| Once a day | 1–2 months |
| Every 8 hours | 3–5 weeks |
| Every 4 hours (default) | 2–3 weeks |

Quiet hours (default 10 PM–7 AM) skip refreshes overnight. Below 15% battery, a small "please
charge" note appears in the corner of the picture.

## Troubleshooting

| Problem | Fix |
|---|---|
| `inkframe.local` doesn't load | Press the PiSugar button and wait 1 minute, then try again. On some Android phones, use the Pi's IP address from your router instead. |
| Screen never updates | Check the logs with `ssh` and then `journalctl -u inkframe -e`. Make sure SPI is on and `dtoverlay=spi0-0cs` is in `/boot/firmware/config.txt`. |
| Frame never wakes up by itself | In the PiSugar web page (port 8421), check that the clock time is correct and an alarm is set. |
| Colours look dull or harsh | Change *Colour strength* in Settings (default 0.5). |

## For developers

Run it on any computer without the hardware. It writes `preview.png` instead of using the
screen, and never sleeps:
```
pip install pillow flask pytest
INKFRAME_DATA=./data python -m inkframe --preview --port 8000
python -m pytest
```
