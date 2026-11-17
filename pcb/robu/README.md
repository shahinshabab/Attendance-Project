# Robu pre-production board (planned)

This folder will hold a simpler pre-production board: an ESP32 plus the basic parts it needs, with the
other functions (display, fingerprint sensor, clock, power, buzzer) added as plug-in modules bought from
robu.in. The design has not started yet.

The full assembled main board (70 x 150 mm, front-side assembly at JLCPCB, Standard PCBA) lives in
`../attendance-board` and is tagged `jlcpcb-production-v0.2`. Its order files are generated into
`../production-jlcpcb/` (git-ignored).

Generated output for this board will go to `robu/production/` (git-ignored).
