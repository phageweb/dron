"""The VRX picture with the detector's boxes, in a web browser.

rqt_image_view needs PyQt5, which the dev shell lacks, so this serves the
picture as an MJPEG stream on http://localhost:8090 instead, with what the
detector found and the VRX and VTX temperatures next to it. Standard
library HTTP only, like lidar/lidar_web.py.

It shows the detector's annotated picture when the detector runs (the
detector only draws its boxes while someone subscribes), else the plain one.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from diagnostic_msgs.msg import DiagnosticArray
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from vision_msgs.msg import Detection2DArray

PAGE = """<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><title>VRX</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #111; color: #eee; font: 15px system-ui, sans-serif; }
  main { display: flex; flex-wrap: wrap; gap: 12px; padding: 12px; }
  img { flex: 1 1 640px; max-width: 100%; height: auto; background: #000; border-radius: 6px; }
  aside { flex: 0 1 280px; }
  h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: #999; margin: 14px 0 6px; }
  .row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #222; }
  .ok { color: #8f8; } .warn { color: #fd4; } .err { color: #f55; font-weight: 700; } .dim { color: #888; }
</style></head><body><main>
<img src="/stream" alt="VRX picture">
<aside>
  <h2>Nalezeno</h2><div id="found" class="dim">…</div>
  <h2>Teploty</h2><div id="temps" class="dim">…</div>
  <h2>Obraz</h2><div id="pic" class="dim">…</div>
</aside></main>
<script>
const level = l => ["ok", "warn", "err", "dim"][l] ?? "dim";
async function tick() {
  try {
    const s = await (await fetch("/status")).json();
    document.getElementById("found").innerHTML = s.found.length
      ? s.found.map(f => `<div class="row"><span>${f.name}</span><span>${f.score.toFixed(2)}</span></div>`).join("")
      : '<span class="dim">nic</span>';
    document.getElementById("temps").innerHTML = s.temps.length
      ? s.temps.map(t => `<div class="row"><span>${t.name}</span><span class="${level(t.level)}">${t.message}</span></div>`).join("")
      : '<span class="dim">žádné zařízení na USB</span>';
    document.getElementById("pic").textContent = `${s.fps.toFixed(1)} snímků/s, ${s.source}`;
  } catch (e) {
    document.getElementById("pic").textContent = "uzel neběží";
  }
}
setInterval(tick, 1000); tick();
</script></body></html>
"""


class WebView(Node):
    def __init__(self):
        super().__init__("vrx_web_view")
        p = self.declare_parameter
        prefix = p("prefix", "/openipc_cinewhoop").value.rstrip("/")
        port = p("port", 8090).value
        bind = p("bind", "127.0.0.1").value
        self.annotated_topic = f"{prefix}/camera/detections/image/compressed"
        self.raw_topic = f"{prefix}/camera/image_raw/compressed"

        self.cond = threading.Condition()
        self.jpeg = None
        self.seq = 0
        self.last_annotated = 0.0
        self.times = []
        self.source = "čekám na obraz"
        self.found = []
        self.temps = []

        self.create_subscription(CompressedImage, self.annotated_topic,
                                 lambda m: self.on_image(m, True), qos_profile_sensor_data)
        self.create_subscription(CompressedImage, self.raw_topic,
                                 lambda m: self.on_image(m, False), qos_profile_sensor_data)
        self.create_subscription(Detection2DArray, f"{prefix}/camera/detections", self.on_found, 10)
        self.create_subscription(DiagnosticArray, "/diagnostics", self.on_diag, 10)

        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/":
                    body = PAGE.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/status":
                    body = json.dumps(node.status()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    seen = -1
                    try:
                        while rclpy.ok():
                            with node.cond:
                                node.cond.wait_for(lambda: node.seq != seen, timeout=1.0)
                                if node.seq == seen or node.jpeg is None:
                                    continue
                                seen, jpeg = node.seq, node.jpeg
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                             + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                                             + jpeg + b"\r\n")
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                else:
                    self.send_error(404)

        self.server = ThreadingHTTPServer((bind, port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.get_logger().info(f"open http://{'localhost' if bind == '127.0.0.1' else bind}:{port}")

    def on_image(self, msg, annotated):
        now = time.monotonic()
        if annotated:
            self.last_annotated = now
        elif now - self.last_annotated < 1.0:
            return              # the detector's boxed picture is coming, show that
        with self.cond:
            self.jpeg = bytes(msg.data)
            self.seq += 1
            self.source = "s rámečky" if annotated else "bez rozpoznávání"
            self.times.append(now)
            while self.times and now - self.times[0] > 2.0:
                self.times.pop(0)
            self.cond.notify_all()

    def on_found(self, msg):
        self.found = [{"name": d.results[0].hypothesis.class_id, "score": d.results[0].hypothesis.score}
                      for d in msg.detections if d.results]

    def on_diag(self, msg):
        temps = []
        for s in msg.status:
            if not s.name.startswith("vrx_bridge: ") or s.name.endswith("picture"):
                continue
            lvl = s.level[0] if isinstance(s.level, (bytes, bytearray)) else int(s.level)
            temps.append({"name": s.name.split(": ", 1)[1], "message": s.message, "level": lvl})
        self.temps = temps

    def status(self):
        with self.cond:
            fps = (len(self.times) - 1) / (self.times[-1] - self.times[0]) if len(self.times) > 1 else 0.0
            source = self.source
        return {"found": self.found, "temps": self.temps, "fps": fps, "source": source}

    def destroy_node(self):
        self.server.shutdown()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = WebView()
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
