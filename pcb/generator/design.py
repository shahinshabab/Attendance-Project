"""Attendance scanner main board: the circuit as data.

Every component lists its KiCad symbol, footprint, LCSC part and pin -> net connections.
The schematic and PCB are generated from this file, so a connection exists only if it is here.
Pin keys are symbol pin numbers. 'NC' marks a pin that is intentionally unconnected.
See ../README.md (requirements) and ../parts.md (part selection and datasheet checks).
"""

BLOCKS = []      # (title, [refs]) in schematic order
COMPONENTS = {}  # ref -> dict


def block(title):
    BLOCKS.append((title, []))


def part(ref, symbol, value, footprint, lcsc, pins, dnp=False, note=''):
    assert ref not in COMPONENTS, ref
    COMPONENTS[ref] = dict(ref=ref, symbol=symbol, value=value, footprint=footprint, lcsc=lcsc,
                           pins={str(k): v for k, v in pins.items()}, dnp=dnp, note=note)
    BLOCKS[-1][1].append(ref)


R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
RES_LCSC = {'100': 'C22775', '470': 'C23179', '1k': 'C21190', '2.4k': 'C22940', '4.7k': 'C23162', '5.1k': 'C23186',
            '10k': 'C25804', '30k': 'C22984', '100k': 'C25803', '220k': 'C22961'}


def R(ref, value, a, b):
    part(ref, 'Device:R', value, R0603, RES_LCSC[value], {1: a, 2: b})


def C(ref, value, a, b):
    if value == '100n':
        part(ref, 'Device:C', '100nF', C0603, 'C14663', {1: a, 2: b})
    elif value == '1u':
        part(ref, 'Device:C', '1uF', C0603, 'C15849', {1: a, 2: b})
    elif value == '10u':
        part(ref, 'Device:C', '10uF 25V', C0805, 'C15850', {1: a, 2: b})
    elif value == '22u':
        part(ref, 'Device:C', '22uF 25V', C0805, 'C45783', {1: a, 2: b})
    elif value == '470u':
        part(ref, 'Device:C_Polarized', '470uF 35V', 'Capacitor_SMD:CP_Elec_10x10', 'C976030', {1: a, 2: b})
    elif value == '100u':
        part(ref, 'Device:C_Polarized', '100uF 10V', 'Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B', 'C129567', {1: a, 2: b})
    else:
        raise ValueError(value)


def LED(ref, colour, anode, cathode):
    lcsc = {'red': 'C84256', 'green': 'C84260'}[colour]
    part(ref, 'Device:LED', colour, 'LED_SMD:LED_0805_2012Metric', lcsc, {1: cathode, 2: anode})


def SS34(ref, anode, cathode):
    part(ref, 'Device:D_Schottky', 'SS34', 'Diode_SMD:D_SMA', 'C8678', {1: cathode, 2: anode})


def LM66100(ref, vin, vout, ce):
    # Pinout checked against TI SLVSEZ8A: 1 VIN, 2 GND, 3 CE (active low), 4 N/C, 5 ST, 6 VOUT.
    part(ref, 'attendance:LM66100DCKR', 'LM66100', None, 'C2869734',
         {1: vin, 2: 'GND', 3: ce, 4: 'NC', 5: 'GND', 6: vout})


# ---------------------------------------------------------------- power input
block('12 V input: fuse, reverse-polarity and surge protection')
# DC-005 2.0 datasheet: pin 4 = centre pin (+), pin 2 = sleeve (GND), pin 3 = switch.
part('J1', 'attendance:DC-0055.5-2.0MM', 'DC-005 12V', None, 'C16214', {4: 'VIN_JACK', 2: 'GND', 3: 'NC'})
part('F1', 'Device:Polyfuse', '1.5A 24V', 'Fuse:Fuse_1812_4532Metric', 'C32404', {1: 'VIN_JACK', 2: 'VIN_FUSED'})
part('Q1', 'Transistor_FET:AO3401A', 'AO3401A', 'Package_TO_SOT_SMD:SOT-23', 'C15127',
     {3: 'VIN_FUSED', 2: 'VIN', 1: 'Q1_GATE'}, note='Reverse-polarity protection: off when the plug is reversed')
R('R1', '100k', 'Q1_GATE', 'GND')
part('D2', 'Device:D_Zener', 'BZT52C10', 'Diode_SMD:D_SOD-123', 'C173431', {1: 'VIN', 2: 'Q1_GATE'},
     note='Clamps Q1 gate-source to 10 V for inputs up to 24 V')
part('D3', 'Device:D_TVS', 'SMBJ24A', 'Diode_SMD:D_SMB', 'C87268', {1: 'VIN', 2: 'GND'},
     note='Unidirectional: pad 1 (cathode band) to VIN')
C('C1', '470u', 'VIN', 'GND')
C('C2', '100n', 'VIN', 'GND')

block('5 V buck converter (XL1509-5.0, 150 kHz)')
# XL1509 datasheet: 1 VIN, 2 OUTPUT (switch), 3 FEEDBACK, 4 ON/OFF (low = on), 5-8 GND.
part('U3', 'attendance:XL1509-5.0E1', 'XL1509-5.0', None, 'C61063',
     {1: 'VIN', 2: 'SW_BUCK', 3: 'BUCK_5V', 4: 'GND', 5: 'GND', 6: 'GND', 7: 'GND', 8: 'GND'})
SS34('D1', 'GND', 'SW_BUCK')
part('L1', 'attendance:FNR8040S470MT', '68uH', None, 'C168140', {1: 'SW_BUCK', 2: 'BUCK_5V'},
     note='FNR8040S680MT, same 8x8 mm footprint as the 47 uH symbol it reuses')
C('C3', '470u', 'BUCK_5V', 'GND')
C('C4', '22u', 'BUCK_5V', 'GND')
LM66100('U8', 'BUCK_5V', '+5V', 'GND')

block('USB-C 5 V input (power only) and external-power sense')
# TYPE-C 6P: VBUS A9/B9, GND A12/B12, CC1 A5, CC2 B5, shell 7. No data pins exist.
part('J2', 'attendance:TYPE-C6P', 'USB-C power', None, 'C456012',
     {'A9': 'USB_5V', 'B9': 'USB_5V', 'A12': 'GND', 'B12': 'GND', 'A5': 'USB_CC1', 'B5': 'USB_CC2', 7: 'GND'})
R('R2', '5.1k', 'USB_CC1', 'GND')
R('R3', '5.1k', 'USB_CC2', 'GND')
C('C5', '10u', 'USB_5V', 'GND')
LM66100('U10', 'USB_5V', '+5V', 'GND')
SS34('D4', 'BUCK_5V', 'EXT_5V')
SS34('D5', 'USB_5V', 'EXT_5V')
C('C6', '10u', 'EXT_5V', 'GND')
R('R14', '100k', 'EXT_5V', 'MAINS_SENSE')
R('R15', '220k', 'MAINS_SENSE', 'GND')

block('5 V rail and 3.3 V regulator')
C('C7', '100u', '+5V', 'GND')
C('C8', '22u', '+5V', 'GND')
part('U4', 'Regulator_Linear:AMS1117-3.3', 'AMS1117-3.3', 'Package_TO_SOT_SMD:SOT-223-3_TabPin2', 'C6186',
     {1: 'GND', 2: '+3V3', 3: '+5V'})
C('C9', '10u', '+5V', 'GND')
C('C10', '22u', '+3V3', 'GND')
C('C11', '100u', '+3V3', 'GND')
R('R5', '1k', '+3V3', 'LED5_A')
LED('LED5', 'green', 'LED5_A', 'GND')

block('Battery: charger, protection, 5 V boost, switch-over')
# TP4056: 1 TEMP, 2 PROG, 3 GND, 4 VCC, 5 BAT, 6 STDBY, 7 CHRG, 8 CE, 9 EP.
part('U5', 'attendance:TP4056_C725790', 'TP4056', None, 'C725790',
     {1: 'GND', 2: 'TP_PROG', 3: 'GND', 4: 'EXT_5V', 5: 'BAT_P', 6: 'STDBY_N', 7: 'CHRG_N', 8: 'EXT_5V', 9: 'GND'})
R('R6', '2.4k', 'TP_PROG', 'GND')
C('C12', '10u', 'EXT_5V', 'GND')
C('C13', '10u', 'BAT_P', 'GND')
R('R7', '1k', 'EXT_5V', 'LED3_A')
LED('LED3', 'red', 'LED3_A', 'CHRG_N')
R('R8', '1k', 'EXT_5V', 'LED4_A')
LED('LED4', 'green', 'LED4_A', 'STDBY_N')
R('R9', '100k', 'CHRG_N', '+3V3')
part('J3', 'attendance:PH2.0-2P-LT', 'LiPo (PH2.0)', None, 'C722761', {1: 'BAT_P', 2: 'BAT_N', 3: 'NC', 4: 'NC'},
     note='Pin 1 = + : check the battery plug polarity, it varies by seller')
part('J10', 'Connector_Generic:Conn_01x02', 'LiPo pads', 'Connector_Wire:SolderWire-0.5sqmm_1x02_P4.6mm_D0.9mm_OD2.1mm',
     '', {1: 'BAT_P', 2: 'BAT_N'}, dnp=True, note='Solder pads for a directly wired cell')
# DW01A: 1 OD, 2 CS/VM, 3 OC, 4 TD, 5 VCC, 6 GND.  FS8205A: 1 S1, 2/5 D, 3 S2, 4 G2, 6 G1.
part('U6', 'attendance:DW01A_C351410', 'DW01A', None, 'C351410',
     {1: 'DW_OD', 2: 'DW_CS', 3: 'DW_OC', 4: 'NC', 5: 'DW_VCC', 6: 'BAT_N'})
R('R10', '100', 'BAT_P', 'DW_VCC')
C('C14', '100n', 'DW_VCC', 'BAT_N')
R('R11', '1k', 'DW_CS', 'GND')
part('Q3', 'attendance:FS8205A_C2830320', 'FS8205A', None, 'C2830320',
     {1: 'BAT_N', 6: 'DW_OD', 3: 'GND', 4: 'DW_OC', 2: 'FET_DRAIN', 5: 'FET_DRAIN'})
# TPS61023 (TI SLVSF14B): 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 VOUT; VREF 0.595 V -> 220k/30k = 4.96 V.
part('U7', 'attendance:TPS61023DRLR', 'TPS61023', None, 'C919459',
     {1: 'BOOST_FB', 2: 'BAT_P', 3: 'BAT_P', 4: 'GND', 5: 'BOOST_SW', 6: 'BOOST_5V'},
     note='Always enabled (20 uA idle) so the switch-over has no start-up gap')
part('L2', 'attendance:PRS4018-1R0NT', '1uH', None, 'C96152', {1: 'BAT_P', 2: 'BOOST_SW'})
R('R12', '220k', 'BOOST_5V', 'BOOST_FB')
R('R13', '30k', 'BOOST_FB', 'GND')
C('C15', '10u', 'BAT_P', 'GND')
C('C16', '22u', 'BOOST_5V', 'GND')
C('C17', '22u', 'BOOST_5V', 'GND')
LM66100('U9', 'BOOST_5V', '+5V', 'EXT_5V')
R('R16', '100k', 'BAT_P', 'BAT_SENSE')
R('R17', '220k', 'BAT_SENSE', 'GND')
C('C18', '100n', 'BAT_SENSE', 'GND')

# ---------------------------------------------------------------- MCU
block('ESP32-WROOM-32E')
part('U1', 'RF_Module:ESP32-WROOM-32E', 'ESP32-WROOM-32E-N4', 'RF_Module:ESP32-WROOM-32E', 'C701341', {
    1: 'GND', 2: '+3V3', 3: 'EN', 4: 'MAINS_SENSE', 5: 'CHRG_N', 6: 'BAT_SENSE', 7: 'RTC_INT', 8: 'BUZZER',
    9: 'LED_OK', 10: 'BUTTON', 11: 'TAMPER', 12: 'SENSOR_TOUCH', 13: 'TFT_BL', 14: 'NC', 15: 'GND', 16: 'LED_ERR',
    17: 'NC', 18: 'NC', 19: 'NC', 20: 'NC', 21: 'NC', 22: 'NC', 23: 'NC', 24: 'NC', 25: 'IO0', 26: 'TFT_DC',
    27: 'SENSOR_TX', 28: 'SENSOR_RX', 29: 'TFT_CS', 30: 'TFT_SCK', 31: 'TFT_RST', 32: 'NC', 33: 'I2C_SDA',
    34: 'ESP_RXD', 35: 'ESP_TXD', 36: 'I2C_SCL', 37: 'TFT_MOSI', 38: 'GND', 39: 'GND'},
    note='IO2, IO12, IO15 left unconnected (strapping pins); IO6-11 are internal flash')
C('C19', '10u', '+3V3', 'GND')
C('C20', '100n', '+3V3', 'GND')

block('Reset, boot and programming header (no USB on the board)')
R('R18', '10k', '+3V3', 'EN')
C('C21', '1u', 'EN', 'GND')
# TS-1187A: A-B joined, C-D joined; pressing connects A/B to C/D.
part('SW1', 'attendance:TS-1187A-B-A-B', 'RESET', None, 'C318884', {1: 'EN', 2: 'EN', 3: 'GND', 4: 'GND'})
R('R19', '10k', '+3V3', 'IO0')
part('SW2', 'attendance:TS-1187A-B-A-B', 'BOOT', None, 'C318884', {1: 'IO0', 2: 'IO0', 3: 'GND', 4: 'GND'})
# Auto-program (as on Espressif DevKitC): DTR=1,RTS=0 -> reset; DTR=0,RTS=1 -> IO0 low.
part('Q4', 'Transistor_BJT:MMBT3904', 'MMBT3904', 'Package_TO_SOT_SMD:SOT-23', 'C20526', {1: 'Q4_B', 2: 'PROG_RTS', 3: 'EN'})
R('R20', '10k', 'Q4_B', 'PROG_DTR')
part('Q5', 'Transistor_BJT:MMBT3904', 'MMBT3904', 'Package_TO_SOT_SMD:SOT-23', 'C20526', {1: 'Q5_B', 2: 'PROG_DTR', 3: 'IO0'})
R('R21', '10k', 'Q5_B', 'PROG_RTS')
R('R22', '470', 'ESP_TXD', 'PROG_TX')
R('R23', '470', 'ESP_RXD', 'PROG_RX')
part('J9', 'Connector_Generic:Conn_01x06', 'PROG: GND TX RX DTR RTS 3V3', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',
     '', {1: 'GND', 2: 'PROG_TX', 3: 'PROG_RX', 4: 'PROG_DTR', 5: 'PROG_RTS', 6: 'PROG_3V3'}, dnp=True,
     note='Internal; pin 2 is the ESP32 TX (to the adapter RX)')
part('JP1', 'Jumper:SolderJumper_2_Open', 'PROG 3V3', 'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm', '',
     {1: 'PROG_3V3', 2: '+3V3'}, note='Open: never power the board from the adapter')

block('Real-time clock (DS3231M) and I2C')
part('U2', 'Timer_RTC:DS3231MZ', 'DS3231MZ', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', 'C107410',
     {1: 'NC', 2: '+3V3', 3: 'RTC_INT', 4: 'NC', 5: 'GND', 6: 'VBAT_RTC', 7: 'I2C_SDA', 8: 'I2C_SCL'})
C('C22', '100n', '+3V3', 'GND')
C('C23', '100n', 'VBAT_RTC', 'GND')
part('BT1', 'Device:Battery_Cell', 'CR2032', 'Battery:BatteryHolder_Keystone_3034_1x20mm', 'C5213768',
     {1: 'VBAT_RTC', 2: 'GND'}, note='No charging path: CR2032 is not rechargeable')
R('R24', '10k', '+3V3', 'RTC_INT')
R('R25', '4.7k', '+3V3', 'I2C_SDA')
R('R26', '4.7k', '+3V3', 'I2C_SCL')
part('J8', 'Connector_Generic:Conn_01x04', 'I2C', 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical', 'C144395',
     {1: '+3V3', 2: 'GND', 3: 'I2C_SDA', 4: 'I2C_SCL'})

block('Fingerprint sensor (R307 / AS608)')
part('J4', 'attendance:WAFER-MX1.25-6PLB', 'R307 1.25mm', None, 'C3029354',
     {1: 'SENSOR_VCC', 2: 'GND', 3: 'SENSOR_TX', 4: 'SENSOR_RX', 5: 'SENSOR_TOUCH', 6: '+3V3', 7: 'NC', 8: 'NC'},
     note='R307 pinout: 1 +5V, 2 GND, 3 TXD, 4 RXD, 5 touch sense, 6 touch power')
part('J11', 'Connector_Generic:Conn_01x06', 'R307 pads', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical', '',
     {1: 'SENSOR_VCC', 2: 'GND', 3: 'SENSOR_TX', 4: 'SENSOR_RX', 5: 'SENSOR_TOUCH', 6: '+3V3'}, dnp=True,
     note='Solder pads for the loose R307 leads')
part('JP2', 'Jumper:SolderJumper_3_Bridged12', 'SENSOR 5V/3V3', 'Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm', '',
     {1: '+5V', 2: 'SENSOR_VCC', 3: '+3V3'}, note='Default 5 V (R307); 3.3 V only for 3.3 V sensors')
C('C24', '10u', 'SENSOR_VCC', 'GND')

block('1.8" TFT (ST7735) with switchable backlight')
part('J5', 'Connector_Generic:Conn_01x08', 'TFT VCC GND CS RST A0 SDA SCK LED', 'Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical',
     'C42431840', {1: '+5V', 2: 'GND', 3: 'TFT_CS', 4: 'TFT_RST', 5: 'TFT_DC', 6: 'TFT_MOSI', 7: 'TFT_SCK', 8: 'TFT_LED'},
     note='VCC from 5 V: the module has its own 3.3 V regulator')
part('Q2', 'Transistor_FET:AO3401A', 'AO3401A', 'Package_TO_SOT_SMD:SOT-23', 'C15127',
     {2: '+3V3', 3: 'TFT_LED', 1: 'TFT_BL_G'}, note='Backlight switch: on by default, IO14 high turns it off')
R('R27', '1k', 'TFT_BL', 'TFT_BL_G')
R('R28', '100k', 'TFT_BL_G', 'GND')

block('IN/OUT button and case tamper switch')
part('J6', 'Connector_Generic:Conn_01x02', 'BUTTON', 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical', 'C158012',
     {1: 'BUTTON', 2: 'GND'})
R('R29', '10k', '+3V3', 'BUTTON')
part('J7', 'Connector_Generic:Conn_01x02', 'TAMPER', 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical', 'C158012',
     {1: 'TAMPER_IN', 2: 'GND'}, note='Case switch, closed when the case is shut')
R('R30', '10k', '+3V3', 'TAMPER_IN')
R('R31', '1k', 'TAMPER_IN', 'TAMPER')
C('C25', '100n', 'TAMPER', 'GND')

block('Buzzer and status LEDs')
# MLT-8530: + and - on one side (pads 1 and 4), pads 2/3 are dummies.
part('BZ1', 'attendance:MLT-8530', 'MLT-8530', None, 'C94599', {1: '+3V3', 4: 'BZ_N', 2: 'NC', 3: 'NC'})
part('D6', 'Device:D', '1N4148W', 'Diode_SMD:D_SOD-123', 'C81598', {1: '+3V3', 2: 'BZ_N'})
part('Q6', 'Transistor_BJT:MMBT3904', 'MMBT3904', 'Package_TO_SOT_SMD:SOT-23', 'C20526', {1: 'Q6_B', 2: 'GND', 3: 'BZ_N'})
R('R32', '1k', 'BUZZER', 'Q6_B')
R('R33', '1k', 'LED_ERR', 'LED1_A')
LED('LED1', 'red', 'LED1_A', 'GND')
R('R34', '1k', 'LED_OK', 'LED2_A')
LED('LED2', 'green', 'LED2_A', 'GND')

block('Test points and mounting holes')
for ref, net in [('TP1', 'VIN'), ('TP2', '+5V'), ('TP3', '+3V3'), ('TP4', 'GND'), ('TP5', 'BAT_P')]:
    part(ref, 'Connector:TestPoint', net, 'TestPoint:TestPoint_Pad_D1.5mm', '', {1: net}, dnp=True)
for ref in ('H1', 'H2', 'H3', 'H4'):
    part(ref, 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3', '', {}, dnp=True)
