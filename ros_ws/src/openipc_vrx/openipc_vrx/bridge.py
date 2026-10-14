"""Bring what the Walksnail VRX Pro hands the ground PC over USB into ROS 2.

There is no computer on the drone, so everything comes down the Walksnail
radio and out of the VRX's USB-C:

- the picture: the VRX's whole screen, OSD included, as the VRX's own MJPEG,
  published without decoding as sensor_msgs/CompressedImage,
- the lidar scan the flight controller writes into the OSD (scan_osd.lua),
  as sensor_msgs/LaserScan on the same topic the simulation uses,
- the VRX's and, when it is on USB, the Lite+'s info and temperature over
  the OTRA protocol, as diagnostic_msgs/DiagnosticArray.

Stamps are the arrival time minus `latency_ms`, which `vrx.py --latency`
measures; the picture is that much older than its arrival.

Where the scan comes from is `scan_source`: "" is off, "msp:tcp:HOST:PORT"
or "msp:/dev/ttyX" reads MSP DisplayPort (SITL, or the flight controller's
UART tapped with SERIAL_PASS). Reading the characters out of the picture
itself is not done yet: it needs the Walksnail OSD font seen in the UVC
picture, which needs the Lite+ wired to the flight controller.
"""

import threading
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Duration
from sensor_msgs.msg import CameraInfo, CompressedImage, LaserScan

from . import osdscan, otra, scan
from .uvc import UvcReader


def load_camera_info(path):
    """A camera_calibration YAML (ROS format) as CameraInfo."""
    import yaml

    with open(path) as f:
        c = yaml.safe_load(f)
    info = CameraInfo()
    info.width = c["image_width"]
    info.height = c["image_height"]
    info.distortion_model = c.get("distortion_model", "plumb_bob")
    info.d = [float(x) for x in c["distortion_coefficients"]["data"]]
    info.k = [float(x) for x in c["camera_matrix"]["data"]]
    info.r = [float(x) for x in c.get("rectification_matrix", {"data": [1, 0, 0, 0, 1, 0, 0, 0, 1]})["data"]]
    info.p = [float(x) for x in c["projection_matrix"]["data"]]
    return info


class VrxBridge(Node):
    def __init__(self):
        super().__init__("vrx_bridge")
        p = self.declare_parameter
        self.prefix = p("prefix", "/openipc_cinewhoop").value.rstrip("/")
        device = p("device", "").value or None
        self.camera_frame = p("camera_frame", "camera_optical_frame").value
        self.scan_frame = p("scan_frame", "front_lidar_link").value
        self.latency = Duration(nanoseconds=int(p("latency_ms", 0.0).value * 1e6))
        camera_info_file = p("camera_info_file", "").value
        scan_source = p("scan_source", "").value
        self.temp_period = p("temperature_period", 2.0).value
        self.warn_c = p("warn_c", 75).value
        self.alarm_c = p("alarm_c", 85).value

        self.image_pub = self.create_publisher(
            CompressedImage, f"{self.prefix}/camera/image_raw/compressed", qos_profile_sensor_data)
        self.info_pub = None
        self.camera_info = None
        if camera_info_file:
            self.camera_info = load_camera_info(camera_info_file)
            self.info_pub = self.create_publisher(
                CameraInfo, f"{self.prefix}/camera/camera_info", qos_profile_sensor_data)
        else:
            self.get_logger().warn("no camera_info_file: camera_info is not published until the "
                                   "camera is calibrated through the VRX")
        self.scan_pub = self.create_publisher(LaserScan, f"{self.prefix}/scan/front", qos_profile_sensor_data)
        self.diag_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)

        self.frames = 0
        self.uvc = UvcReader(device, self.on_frame, log=self.get_logger().info)
        if scan_source:
            threading.Thread(target=self.read_scan, args=(scan_source,), daemon=True).start()
        threading.Thread(target=self.poll_devices, daemon=True).start()

    def stamp(self, arrived):
        """ROS time the content was captured: arrival minus the measured latency."""
        age = Duration(nanoseconds=int((time.monotonic() - arrived) * 1e9))
        return (self.get_clock().now() - age - self.latency).to_msg()

    def on_frame(self, jpeg, arrived):
        msg = CompressedImage()
        msg.header.stamp = self.stamp(arrived)
        msg.header.frame_id = self.camera_frame
        msg.format = "jpeg"
        msg.data = jpeg
        self.image_pub.publish(msg)
        if self.info_pub:
            self.camera_info.header = msg.header
            self.info_pub.publish(self.camera_info)
        self.frames += 1

    def read_scan(self, source):
        if not source.startswith("msp:"):
            self.get_logger().error(f"scan_source {source!r}: only msp:... is supported so far")
            return
        spec = source[4:]
        while rclpy.ok():
            try:
                read = osdscan.open_msp(spec)
            except OSError as e:
                self.get_logger().warn(f"scan source {spec}: {e}, retrying")
                time.sleep(2)
                continue
            self.get_logger().info(f"reading the OSD scan from {spec}")
            dp, asm = osdscan.DisplayPort(), osdscan.Assembler()
            last = None
            while rclpy.ok():
                try:
                    data = read()
                except OSError:
                    data = b""
                if not data:
                    break
                for screen in dp.feed(data):
                    codes = asm.add(osdscan.frame_from_screen(screen))
                    if codes is None:
                        continue
                    now = time.monotonic()
                    self.publish_scan(codes, now, 0.0 if last is None else now - last)
                    last = now
            time.sleep(1)

    def publish_scan(self, codes, arrived, period):
        msg = LaserScan()
        msg.header.stamp = self.stamp(arrived)
        msg.header.frame_id = self.scan_frame
        msg.angle_min = scan.ANGLE_MIN
        msg.angle_max = scan.ANGLE_MAX
        msg.angle_increment = scan.INCREMENT
        msg.time_increment = 0.0      # a turn arrives whole, sectors are not timed
        msg.scan_time = period
        msg.range_min = scan.RANGE_MIN
        msg.range_max = scan.RANGE_MAX
        msg.ranges = scan.ranges_from_codes(codes)
        self.scan_pub.publish(msg)

    def poll_devices(self):
        while rclpy.ok():
            array = DiagnosticArray()
            array.header.stamp = self.get_clock().now().to_msg()
            for name, path in otra.find_ports().items():
                try:
                    info = otra.info(path)
                except OSError:
                    info = None
                status = DiagnosticStatus()
                status.name = f"vrx_bridge: {name}"
                status.hardware_id = path
                if info is None:
                    status.level = DiagnosticStatus.STALE
                    status.message = "no answer"
                else:
                    t = info["temp_c"]
                    status.level = (DiagnosticStatus.ERROR if t >= self.alarm_c
                                    else DiagnosticStatus.WARN if t >= self.warn_c
                                    else DiagnosticStatus.OK)
                    status.message = f"{t} °C" + (" overheating" if t >= self.alarm_c else "")
                    status.values = [KeyValue(key=k, value=str(v)) for k, v in info.items() if v != ""]
                array.status.append(status)
            video = DiagnosticStatus()
            video.name = "vrx_bridge: picture"
            video.hardware_id = self.uvc.device or ""
            video.level = DiagnosticStatus.OK if self.uvc.connected else DiagnosticStatus.WARN
            video.message = "streaming" if self.uvc.connected else "no picture from the VRX"
            video.values = [KeyValue(key="frames", value=str(self.frames))]
            array.status.append(video)
            self.diag_pub.publish(array)
            time.sleep(self.temp_period)

    def destroy_node(self):
        self.uvc.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VrxBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
