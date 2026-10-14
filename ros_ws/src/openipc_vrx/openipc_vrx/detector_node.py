"""People and things in the VRX picture, as vision_msgs/Detection2DArray.

Takes the compressed picture vrx_bridge publishes, runs YOLO11n (COCO) in
ONNX on the CPU and publishes what it found with the picture's own stamp,
so the latency correction carries over. Only the newest picture is worked
on: when the model is slower than 30 fps the older ones are dropped rather
than queued, so the detections never fall behind.

The model is not in the repository (YOLO11 weights are AGPL-3.0); make it
with export_model.sh, by default into ~/.cache/openipc_vrx/yolo11n.onnx.
"""

import io
import threading
from pathlib import Path

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

from .detect import COCO, Detector
from .sightings import Sightings

DEFAULT_MODEL = Path.home() / ".cache" / "openipc_vrx" / "yolo11n.onnx"
DEFAULT_LOG = Path.home() / "Videos" / "vrx" / "nalezy"


def annotate(jpeg, found):
    """The picture with a labelled box per detection, as JPEG."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(io.BytesIO(jpeg)).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(16, image.height // 40))
    for name, score, x1, y1, x2, y2 in found:
        color = (255, 60, 60) if name == "person" else (60, 200, 255)
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        label = f"{name} {score:.2f}"
        tx, ty = x1, max(0, y1 - font.size - 6)
        draw.rectangle(draw.textbbox((tx, ty), label, font=font), fill=(0, 0, 0))
        draw.text((tx, ty), label, fill=color, font=font)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=80)
    return out.getvalue()


class DetectorNode(Node):
    def __init__(self):
        super().__init__("vrx_detector")
        p = self.declare_parameter
        prefix = p("prefix", "/openipc_cinewhoop").value.rstrip("/")
        model = p("model", str(DEFAULT_MODEL)).value
        classes = [c for c in p("classes", "").value.split(",") if c.strip()]
        unknown = [c for c in classes if c not in COCO]
        if unknown:
            raise ValueError(f"not COCO classes: {unknown}; use e.g. person,chair,backpack")
        self.annotated = p("publish_annotated", True).value
        # The log of sightings is off unless asked for, also while running:
        #   ros2 param set /vrx_detector log_sightings true
        self.log_dir = p("log_dir", str(DEFAULT_LOG)).value
        self.gone_after = p("gone_after", 3.0).value
        self.log_lock = threading.Lock()
        self.sightings = None
        if p("log_sightings", False).value:
            self.start_log()
        self.add_on_set_parameters_callback(self.on_params)
        if not Path(model).exists():
            raise FileNotFoundError(f"no model at {model}; make it with export_model.sh")
        self.detector = Detector(model, conf=p("confidence", 0.4).value, classes=classes,
                                 threads=p("threads", 0).value)

        self.pub = self.create_publisher(Detection2DArray, f"{prefix}/camera/detections", 10)
        self.image_pub = self.create_publisher(
            CompressedImage, f"{prefix}/camera/detections/image/compressed", qos_profile_sensor_data)
        self.create_subscription(CompressedImage, f"{prefix}/camera/image_raw/compressed",
                                 self.on_image, qos_profile_sensor_data)
        self.latest = None
        self.wake = threading.Event()
        self.done = 0
        self.dropped = 0
        self.seen = {}          # class -> (pictures it was in, best score) since the last report
        threading.Thread(target=self.work, daemon=True).start()
        self.create_timer(10.0, self.report)
        self.get_logger().info(f"model {model}, classes {classes or 'all 80'}; log of sightings "
                               + ("on" if self.sightings else "off (turn on with vrx/log.sh on)"))

    def on_image(self, msg):
        if self.latest is not None:
            self.dropped += 1
        self.latest = msg
        self.wake.set()

    def work(self):
        while rclpy.ok():
            self.wake.wait(1.0)
            self.wake.clear()
            msg, self.latest = self.latest, None
            if msg is None:
                continue
            found = self.detector(bytes(msg.data))
            if not rclpy.ok():
                return          # shutting down while the model ran
            self.publish(msg, found)
            self.log_sightings(msg, found)
            self.done += 1
            for name in {f[0] for f in found}:
                best = max(f[1] for f in found if f[0] == name)
                n, b = self.seen.get(name, (0, 0.0))
                self.seen[name] = (n + 1, max(b, best))

    def publish(self, msg, found):
        out = Detection2DArray()
        out.header = msg.header
        for name, score, x1, y1, x2, y2 in found:
            d = Detection2D()
            d.header = msg.header
            d.bbox.center.position.x = (x1 + x2) / 2
            d.bbox.center.position.y = (y1 + y2) / 2
            d.bbox.size_x = x2 - x1
            d.bbox.size_y = y2 - y1
            h = ObjectHypothesisWithPose()
            h.hypothesis.class_id = name
            h.hypothesis.score = score
            d.results.append(h)
            out.detections.append(d)
        self.pub.publish(out)
        if self.annotated and self.image_pub.get_subscription_count():
            img = CompressedImage()
            img.header = msg.header
            img.format = "jpeg"
            img.data = annotate(bytes(msg.data), found)
            self.image_pub.publish(img)

    def start_log(self):
        with self.log_lock:
            if self.sightings is None:
                self.sightings = Sightings(self.log_dir, gone_after=self.gone_after)
                self.get_logger().info(f"log of sightings on: {self.sightings.path}")

    def stop_log(self):
        with self.log_lock:
            if self.sightings is not None:
                self.sightings.close()
                self.get_logger().info(f"log of sightings off, written {self.sightings.path}")
                self.sightings = None

    def on_params(self, params):
        for prm in params:
            if prm.name == "log_sightings":
                if prm.value:
                    self.start_log()
                else:
                    self.stop_log()
        return SetParametersResult(successful=True)

    def log_sightings(self, msg, found):
        jpeg = bytes(msg.data)

        def snapshot(path):
            path.write_bytes(annotate(jpeg, found))

        with self.log_lock:
            if self.sightings is None:
                return
            events = self.sightings.update(found, self.detector.last_size[0], snapshot)
        for e in events:
            self.get_logger().info(f"{e['udalost']}: {e['co']} x{e['pocet']} ({e['jistota']}, {e['kde_v_obraze']})"
                                   + (f", {e['trvani_s']} s" if e["trvani_s"] else ""))

    def report(self):
        seen = ", ".join(f"{name} in {n} of {self.done} (best {b:.2f})"
                         for name, (n, b) in sorted(self.seen.items(), key=lambda kv: -kv[1][0]))
        self.get_logger().info(f"last 10 s: {seen or 'nothing'}; "
                               f"{self.done / 10:.1f} pictures/s, {self.dropped} skipped as stale")
        self.done = self.dropped = 0
        self.seen = {}

    def destroy_node(self):
        self.stop_log()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
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
