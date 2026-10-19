"""MicoAir743v2-AIO-45A reference; deliberately not the older 35 A AIO.

Pinout: https://micoair.com/flightcontroller_micoair743v2_aio_45a/
Firmware: external/ardupilot/.../hwdef/MicoAir743v2/hwdef.dat (pinned locally).
This is a functional reference, not a reconstruction of its undocumented copper.
"""
import re

# Logical board signal -> MCU GPIO. ICM42688 takes the BMI088 accelerometer's
# SPI2 CS/DRDY; this is our adaptation, not a claim about MicoAir's fitted IMU.
PINS = {
    "MOTOR1": "PE14", "MOTOR2": "PE13", "MOTOR3": "PE11", "MOTOR4": "PE9",
    "IMU_SPI.SCK": "PB3", "IMU_SPI.MISO": "PB4", "IMU_SPI.MOSI": "PD6",
    "IMU_CS": "PA15", "IMU_INT": "PB7",
    "IMU2_SCK": "PD3", "IMU2_MISO": "PC2", "IMU2_MOSI": "PC3",
    "IMU2_CS": "PD4", "IMU2_INT": "PC14",
    "GPS_TX": "PD8", "GPS_RX": "PD9", "RC_TX": "PC6", "RC_RX": "PC7",
    "LIDAR_TX": "PB5", "UART5_TX": "PB6", "UART8_TX": "PE1", "UART8_RX": "PE0",
    "UART1_TX": "PA9", "UART1_RX": "PA10", "VTX_TX": "PA2", "VTX_RX": "PA3",
    "FLOW_TX": "PA0", "FLOW_RX": "PA1", "EXT_SCL": "PB8", "EXT_SDA": "PB9",
    "SCL": "PB10", "SDA": "PB11", "VBAT_SENSE": "PC0", "ESC_CURRENT": "PC1",
    "USB_DM": "PA11", "USB_DP": "PA12", "SWDIO": "PA13", "SWCLK": "PA14",
    "SD_CK": "PC12", "SD_CMD": "PD2", "SD_D0": "PC8", "SD_D1": "PC9",
    "SD_D2": "PC10", "SD_D3": "PC11", "LED_R": "PE3", "LED_G": "PE2", "LED_B": "PE4",
    "BUZZER": "PD15", "PWM5": "PB1", "LIDAR_PWM": "PB0", "PWM7": "PD12",
    "VTX_EN": "PD13", "PWM9": "PE5", "PWM10": "PE6", "PWM11": "PD14",
}
ALIASES = {"UART3_TX": "UART5_TX", "UART7_TX": "UART8_TX", "UART7_RX": "UART8_RX"}
SERIAL_ORDER = "OTG1 USART1 USART2 USART3 UART4 UART5 USART6 UART7 UART8"


def gpio(name):
    """KiCad calls the analog-switch pins PC2_C/PC3_C; hwdef calls them PC2/PC3."""
    match = re.match(r"P[A-K]\d+", name)
    return match.group() if match else name


def remap(balls, pin_names):
    by_pin = {gpio(name): ball for ball, name in pin_names.items()}
    out = {ball: net for ball, net in balls.items() if ALIASES.get(net, net) not in PINS}
    for net, pin in PINS.items():
        ball = by_pin[pin]
        if ball in out and out[ball] is not None:
            raise ValueError(f"{net}/{pin} would replace {out[ball]} at {ball}")
        out[ball] = net
    return out


def hwdef(text):
    """Render the reference variant from our board's hwdef, keeping its electrical calibration."""
    text = re.sub(r"SERIAL_ORDER[^\n]*", "SERIAL_ORDER  " + SERIAL_ORDER, text)
    start, end = text.index("# order of UARTs"), text.index("# SWD")
    uarts = "\n".join(f"{pin:4} {bus}_{direction:2} {bus}" for bus, tx, rx in (
        ("USART1", "PA9", "PA10"), ("USART2", "PA2", "PA3"), ("USART3", "PD8", "PD9"),
        ("UART4", "PA0", "PA1"), ("UART5", "PB6", "PB5"), ("USART6", "PC6", "PC7"),
        ("UART7", "PE8", "PE7"), ("UART8", "PE1", "PE0"))
        for pin, direction in ((tx, "TX"), (rx, "RX")))
    text = text[:start] + ("# UART order/pins follow MicoAir743v2-AIO-45A.\n"
        "# SERIAL3 GPS; SERIAL5 LD06; SERIAL6 RC; SERIAL8 Bluetooth pads.\n"
        "SERIAL_ORDER  " + SERIAL_ORDER + "\n\nPA11 OTG_FS_DM OTG1\nPA12 OTG_FS_DP OTG1\n\n"
        + uarts + "\n\n") + text[end:]
    start, end = text.index("# SPI2 -"), text.index("# IMUs:")
    text = text[:start] + """# SPI2: our ICM42688 on the reference BMI088 accel CS/DRDY pins.
PD3 SPI2_SCK SPI2
PC2 SPI2_MISO SPI2
PC3 SPI2_MOSI SPI2
PD4 ICM42688_CS CS
PC14 DRDY1_ICM42688 INPUT

# SPI3: BMI270, same pins as MicoAir743v2-AIO-45A.
PB3 SPI3_SCK SPI3
PB4 SPI3_MISO SPI3
PD6 SPI3_MOSI SPI3
PA15 BMI270_CS CS
PB7 DRDY3_BMI270 INPUT

SPIDEV icm42688 SPI2 DEVID1 ICM42688_CS MODE3 2*MHZ 16*MHZ
SPIDEV bmi270 SPI3 DEVID1 BMI270_CS MODE3 1*MHZ 10*MHZ

""" + text[end:]
    return "# Generated reference variant by gen/micoair.py; verify IMU rotations after placement.\n" + text
