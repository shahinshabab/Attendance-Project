# Commissioning and operating notes

## What is implemented

- R307 two-scan enrollment, matching, protected deletion, and capacity query via USB.
- Four-pin OLED status and IN/OUT mode; optional GPIO25 push button. Mode is persisted in ESP32 preferences.
- USB attendance forwarding or standalone Wi-Fi HTTPS delivery.
- Two Wi-Fi networks in Wi-Fi mode: the office network sent from the dashboard (first priority, saved in the ESP32's flash) and a fallback phone hotspot compiled into the firmware (`FALLBACK_WIFI_SSID`/`PASSWORD` in `config.h`).
- Server-requested enrollment: the dashboard asks the scanner to enroll a staff member; the slot is chosen by the server and bound automatically on success.
- Flash-backed queue (up to 500 events by default), repeated delivery until an exact acknowledgment, stable random event identities, and server-side idempotency. Same-finger scans have a ten-second device debounce and require removal between scans.
- Staff add/update/deactivate, device-specific slot assignment, attendance listing by office date, and CSV export.

## Important behavior

**Time:** data uses UTC and displays in Asia/Kolkata by default. The bridge syncs the ESP32 from the computer clock; Wi-Fi mode uses NTP. Ensure the computer/server clocks are correct. The ESP32 has no battery-backed clock in this build. A scan before clock sync after power loss has `occurred_at=null`; the dashboard flags it `received_only`. Its displayed date is the server receive date and is not evidence of the actual scan date. Events already queued without a clock are never silently assigned a made-up capture time. Add a battery-backed RTC if accurate offline time through power loss is a requirement.

**Offline queue:** a saved device event is persisted before delivery, and is removed only after acknowledgment. First-time filesystem provisioning is explicit via `device.ps1 init-storage`; a mount failure never automatically formats existing records. A full/unavailable queue displays `NOT SAVED` and does not silently discard the oldest records. Queue write protection cannot guarantee survival during arbitrary electrical failure; test power-loss recovery on the actual board. Enrollment temporarily pauses scanning/delivery; HTTP requests can pause the scan loop for several seconds during an outage. A corrupt queued file blocks delivery and needs maintenance instead of silent deletion.

**Assignments:** enroll a fresh sensor slot, create the employee, bind the slot, and only then start live scans. Old unmapped scans remain unmapped after a new assignment; no guessed historical reassignment occurs. Slot bindings are deliberately not reassigned to another employee. Drain all queued events before deleting a template. Deletion removes the template from the sensor, but retains historical server assignments. Do not reuse the deleted slot for a different employee. Future slot lifecycle/version management will be needed if slots must be recycled.

**Inactive staff:** deactivation marks the staff record inactive in reports; it does not erase their fingerprint or reject scans. Explicitly delete their sensor template through USB after draining the queue. Attendance is evidence collection rather than a door-access control decision.

**IN / OUT:** staff choose the mode before scanning. This is a shared terminal mode, visible on OLED and preserved through resets. The starter records scans; it does not derive hours, late marks, shifts, or payroll automatically. Missing and duplicated human scans still require review. The dashboard displays up to 500 records per request by default, with an API maximum of 10,000; CSV is limited to the most recent 100,000 matching records. Reports beyond that need pagination before use at that scale.

**USB trust:** enrollment/deletion/time/acknowledgment commands use physical USB access without additional authentication. Keep the installed scanner enclosure and USB port under office control. Never expose its serial port over an unauthenticated network tunnel. Device API keys authenticate the sender; they do not prove a live finger was present against someone with firmware/physical access.

**Sensor variants:** confirm the actual sensor capacity and default 57600 baud. The firmware uses slots 1 through capacity minus one, and limits server slot values to 1000. Empty-slot detection depends on R307 returning the documented invalid-template status; verify this during commissioning. Do not force overwrite on a communication failure. No full-sensor erase command is exposed by this project.

**Wi-Fi recovery:** the scanner tries the saved office Wi-Fi for 20 seconds, then the fallback hotspot for 20 seconds, and repeats. While on the hotspot it retries the office network every 5 minutes. When the office password or network changes: turn on a phone hotspot with the fallback name/password (2.4 GHz, the phone needs internet), wait for the dashboard to show the scanner on "Fallback hotspot", enter the new office Wi-Fi under Scanner & Wi-Fi, and the scanner saves it and switches within about 10 seconds. Then turn the hotspot off. The dashboard shows the last office failure reason (`network not found`, `wrong password or rejected`). Scans are queued on the device throughout and sent once it is online. Entering a new password while the old one still works makes the scanner switch immediately, so update it once the router has changed. The office password is stored unencrypted in the server database and in the ESP32's flash, and is never returned by the admin API. Enterprise (802.1X) and captive-portal networks are not supported.

**Server enrollment:** one enrollment at a time per scanner. The scanner shows the staff name and waits 2 minutes for the first placement and 60 seconds for the second. Pressing the IN/OUT button during enrollment cancels it. Scanning is paused during an enrollment. A failed attempt leaves its slot unused forever; just request again.

## Hardware acceptance sequence

1. Check power rails and UART levels, then connect USB and identify the actual non-Bluetooth COM port.
2. Build/upload firmware and provision event storage once. Confirm sensor readiness, OLED display, and `pending=0` using STATUS.
3. Enroll a test finger, check occupied-slot refusal, map it to a test employee, scan IN, select OUT, wait ten seconds and scan OUT.
4. Confirm both server rows and exported local times. Test an unknown finger produces no attendance.
5. Stop the server, capture several scans, power-cycle the board, restart the server/bridge and confirm queued events arrive once. Events captured after reboot without clock sync must show `received_only`.
6. For standalone Wi-Fi, verify real server certificate validation, reconnect after Wi-Fi loss, recovery after server downtime, and queue behavior with the actual office network.

Office use also needs your agreed staff enrollment/retention process, backups, enclosure, stable power, server monitoring, and tested recovery. These depend on your office and server setup.

## Windows builds in this folder

The full OneDrive/project path caused `CreateProcess: No such file or directory` while launching the ESP32 compiler. The build wrapper uses the existing Windows 8.3 short path to this same folder for PlatformIO and its tool cache; it does not move source files or create a drive mapping. Use `scripts/device.ps1 build` instead of a bare PlatformIO invocation. If a different Windows installation has 8.3 names disabled and hits the same command-length limit, use a shorter project/tool-cache path on that machine.
