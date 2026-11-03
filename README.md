# Office fingerprint attendance

This folder is the project workspace for an **ESP32 development board (ESP-WROOM-32), R307 UART fingerprint sensor, and 128 × 64 four-pin I²C OLED**. Open `Attendance.code-workspace` in VS Code or open this folder directly.

The ESP32 is the implemented board. A standard Raspberry Pi Pico has no built-in Wi-Fi and needs different firmware; the supplied ESP32 firmware must not be flashed to a Pico. Pico W is a separate Wi-Fi-capable alternative, also requiring a port.

## Your deployed server

The dashboard/API is live at **https://attendance.shahinanalytics.com**, deployed through SSH alias `Attendance-Server`. Enter this computer's `ADMIN_API_KEY` value from `.env` in the dashboard. HTTPS, authentication, and automatic service startup have been checked. See [server details](docs/SERVER.md).

The board runs in **Wi-Fi mode** and talks to that server directly (see Connection modes below). The office Wi-Fi and fingerprint enrollment are both managed from the dashboard.

The USB connection on COM3 was verified and attendance firmware was uploaded after a full original-flash backup. Event storage was initialized and verified. The sensor (1000-slot capacity) and OLED (0x3C) were detected after shared-ground correction, but subsequent checks showed intermittent/missing communication; full power-cycle and wiring inspection are pending. Staff member Shabab (EMP001) exists on the server, but fingerprint enrollment has not succeeded and no slot is assigned. The steps below also cover running an optional local development server and provisioning another board. Do not reinitialize storage during routine firmware updates.

## Start here

1. Read [the wiring guide](docs/WIRING.md) and open [the labelled wiring diagram](docs/wiring.png) ([editable SVG](docs/wiring.svg)). Wire with USB unplugged. Use GPIO numbers, not physical header positions.
2. In PowerShell, from this folder, run:

   ```powershell
   .\scripts\setup.ps1
   .\scripts\start-server.ps1
   ```

   If your shell blocks scripts, run a command with `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1` (process-specific; no permanent system policy change needed). Setup creates `.venv`, installs dependencies, generates independent random admin/device keys in `.env`, and copies the firmware configuration. Both secret files are git-ignored.
3. Open **http://127.0.0.1:8765**. Open `.env` locally, copy the `ADMIN_API_KEY` value into the dashboard, and click Connect. Do not share that key.
4. Connect the ESP32 development board with a **USB data cable**. In a second PowerShell window:

   ```powershell
   .\scripts\device.ps1 list
   .\scripts\device.ps1 build
   .\scripts\device.ps1 upload -Port COM3
   # FIRST INSTALL ONLY: creates the event filesystem; erases pending device scans.
   .\scripts\device.ps1 init-storage -Port COM3
   .\scripts\device.ps1 status -Port COM3
   ```

   Your board was detected as **Silicon Labs CP210x, COM3** during setup. Confirm it with `list` each time; Windows can change the port number. Do not choose a Bluetooth COM port. Close any serial monitor before uploading or opening the USB bridge. Upload replaces the board's current program. If uploading stalls at Connecting, hold BOOT, tap EN, then release BOOT when writing starts. Do not run `init-storage` during normal updates; pending scans survive ordinary firmware uploads when the partition layout is unchanged.
5. Create a staff member in the dashboard, for example `EMP001`. Enroll their fingerprint into a fresh slot:

   ```powershell
   .\scripts\device.ps1 enroll -Port COM3 -Slot 1
   ```

   Follow the OLED/terminal prompts: place finger, remove, place the same finger again. Enrollment takes place on the sensor; it does not create a server staff record. Assign device `office-01`, slot `1`, to `EMP001` in the dashboard. Remove the finger before starting attendance. Verify that a second enrollment into an occupied slot is refused on your particular sensor before enrolling the office.
6. Start the USB bridge:

   ```powershell
   .\scripts\device.ps1 bridge -Port COM3
   ```

   Scan, then click Refresh in the dashboard. The OLED's **Saved on device** means the scan is queued in flash; the terminal's **Saved** means the server accepted it. Staff must select IN or OUT before scanning. The optional button toggles the mode and the OLED shows it. With the bridge stopped you can also run:

   ```powershell
   .\scripts\device.ps1 out -Port COM3
   .\scripts\device.ps1 bridge -Port COM3
   ```

   Mode survives resets. Run `device.ps1 in` or use the button to switch back. There is no automatic IN/OUT alternation, which could produce wrong records after a missed scan.

## Connection modes

**USB to this computer:** the ESP32 uses USB serial for enrollment and attendance. `tools/device.py` synchronizes the clock and forwards queued events. The local server and bridge both need to run. The computer can also forward to your internet server:

```powershell
.\scripts\device.ps1 bridge -Port COM3 -Server https://attendance.your-domain.example
```

Use the same device ID and device key on this computer and the remote server. The bridge never uses the admin key and validates normal HTTPS certificates.

**Standalone Wi-Fi to server (current setup):** the scanner connects straight to https://attendance.shahinanalytics.com without this computer. Office Wi-Fi is entered in the dashboard (Scanner & Wi-Fi). If it stops working, turn on a phone hotspot with the fallback name/password built into the firmware; the scanner connects through it, picks up the new office Wi-Fi from the dashboard, and switches back. No firmware change is needed. Enroll staff from the dashboard (Enroll a fingerprint): the scanner shows their name and the slot is assigned automatically. USB stays available for maintenance commands. Do not run the USB attendance bridge for a Wi-Fi board. See [server setup](docs/SERVER.md) and [operations](docs/OPERATIONS.md).

## Project layout

| Path | Purpose |
| --- | --- |
| `firmware/` | PlatformIO Arduino ESP32 firmware and hardware configuration |
| `backend/` | FastAPI service, SQLite database, and local dashboard |
| `tools/device.py` | USB bridge and physical enrollment/maintenance commands |
| `tools/firmware_config.py` | Writes the Wi-Fi-mode `config.h` (device key, server URL, root CAs, fallback hotspot) |
| `scripts/` | Windows setup, build, upload, and start commands |
| `docs/` | Wiring diagram, deployment notes, API and operating limits |
| `tests/` | API authentication, retries, date handling, and bridge acknowledgment tests |
| `.env` | Local server keys/configuration, excluded from Git |
| `data/` | Local database, excluded from Git |

Run checks with `.\.venv\Scripts\python.exe -m pytest -q`. The firmware dependencies and ESP32 platform are pinned in `platformio.ini`. Python installation versions are recorded in `requirements-lock.txt` after local verification; install that file to reproduce the tested environment.

This is a working project foundation for hardware commissioning. Hardware operation, fingerprint compatibility, and internet deployment must be verified with your actual board, sensor, display, and server before office use. See [operating notes](docs/OPERATIONS.md) for clock, queue, enrollment, and reporting limits.
