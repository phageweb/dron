"""Build and check an AIO candidate without modifying the source project.

Run through aktualizuj_desku.sh --auto (KiCad's own Python). Exit status:
0 = connected, no unexpected ERC/parity or DRC errors; 2 = incomplete;
1 = failed tool or invalid candidate. Reports and the best board are retained.
This is a development check, not a fabrication release.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from kontrola import better, firmware_errors, net_pins, reference_diff, summarize, valid

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
ROOT = SOURCE.parent.parent


class Build:
    def __init__(self, args):
        self.args = args
        self.out = args.output.resolve()
        self.project = self.out / "project"
        self.logs = self.out / "logs"
        self.reports = self.out / "reports"
        self.board = self.project / "aio.kicad_pcb"
        self.history = []
        self.exceptions = json.loads((HERE / "vyjimky.json").read_text())
        self.number = 0
        self.result = {"profile": args.profile, "source": str(args.source.resolve()), "steps": self.history,
                       "started": datetime.now(timezone.utc).isoformat(), "status": "running"}

    def save(self):
        (self.out / "result.json").write_text(json.dumps(self.result, indent=2, ensure_ascii=False) + "\n")

    def run(self, label, command, env=None):
        self.number += 1
        log = self.logs / f"{self.number:03}-{label}.log"
        print(f"[{self.number}] {label}", flush=True)
        start = time.monotonic()
        item = dict(step=label, command=[str(c) for c in command], log=str(log))
        self.history.append(item)
        self.save()
        try:
            with log.open("w") as f:
                done = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT,
                                      env={**os.environ, **(env or {})}, timeout=self.args.timeout)
            item["returncode"] = done.returncode
            if done.returncode:
                raise RuntimeError(f"{label}: exit {done.returncode}; {log}\n{log.read_text()[-2500:]}")
        except subprocess.TimeoutExpired:
            item["timeout"] = True
            raise RuntimeError(f"{label}: timeout after {self.args.timeout}s; {log}") from None
        finally:
            item["seconds"] = round(time.monotonic() - start, 2)
            self.save()

    def script(self, name, *args, **kwargs):
        self.run(name, [sys.executable, HERE / name, *map(str, args)], **kwargs)

    def prepare(self):
        # Refuse reuse, including symlinks: do not mix a previous run's reports
        # or overwrite a user-selected project directory.
        self.out.mkdir(parents=True, exist_ok=False)
        self.project.mkdir()
        self.logs.mkdir()
        self.reports.mkdir()
        src = self.args.source.resolve()
        for name in ("aio.kicad_pcb", "aio.kicad_pro", "aio.kicad_dru", "fp-lib-table", "sym-lib-table"):
            shutil.copy2(src / name, self.project / name)
        for pattern in ("*.kicad_sch", "*.kicad_sym"):
            for p in src.glob(pattern):
                shutil.copy2(p, self.project / p.name)
        shutil.copy2(src / "NAVRH.md" if (src / "NAVRH.md").exists() else SOURCE / "NAVRH.md",
                     self.project / "NAVRH.md")
        for name in ("lib.pretty", "hwdef"):
            shutil.copytree(src / name, self.project / name)
        self.result["source_sha256"] = hashlib.sha256((src / "aio.kicad_pcb").read_bytes()).hexdigest()
        self.run("version", ["kicad-cli", "version"])
        self.result["kicad"] = (self.logs / "001-version.log").read_text().strip()

    def erc(self, label):
        path = self.reports / f"{label}.erc.json"
        self.run("erc-" + label, ["kicad-cli", "sch", "erc", "--format", "json", "-o", path,
                                 self.project / "aio.kicad_sch"])
        return json.loads(path.read_text())

    def drc(self, label):
        path = self.reports / f"{label}.drc.json"
        self.run("drc-" + label, ["kicad-cli", "pcb", "drc", "--schematic-parity", "--refill-zones",
                                 "--save-board", "--format", "json", "-o", path, self.board])
        return json.loads(path.read_text())

    def audit(self, label):
        netlist = self.reports / f"{label}.netlist.xml"
        self.run("netlist-" + label, ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
                                     "-o", netlist, self.project / "aio.kicad_sch"])
        pins = net_pins(netlist)
        result = dict(pins=pins, reference_differences=reference_diff(pins),
                      firmware_errors=firmware_errors(pins, (self.project / "hwdef/Pavo20AIO/hwdef.dat").read_text()))
        (self.reports / f"{label}.pinout.json").write_text(json.dumps(result, indent=2) + "\n")
        self.result[label + "_pinout"] = result
        if result["firmware_errors"]:
            raise RuntimeError("Schematic/hwdef mismatch: " + "; ".join(result["firmware_errors"]))
        if (label != "source" or self.args.route_only) and self.args.profile == "micoair-v2" and result["reference_differences"]:
            raise RuntimeError("Generated schematic does not match the MicoAir V2 reference")

    def route(self, erc, baseline):
        best = self.out / "best.kicad_pcb"
        shutil.copy2(self.board, best)
        score = baseline
        # Pin migrations may have removed a BGA escape. Rebuild missing escapes
        # before routing, but keep the previous board if DRC rejects them.
        try:
            self.script("vyved_bga.py", self.board)
            escaped = summarize(self.drc("escape"), erc, self.exceptions)
            if valid(escaped) and escaped["unconnected"] <= score["unconnected"]:
                score = escaped
                shutil.copy2(self.board, best)
            else:
                shutil.copy2(best, self.board)
        except BaseException:
            shutil.copy2(best, self.board)
            raise
        first = self.out / "priority.txt"
        first.write_text("")
        env = {"TRASUJ_PRVNI": str(first), "TRASUJ_OKNO": "8", "TRASUJ_UZLY": "2500000"}
        for i in range(self.args.passes):
            label = f"route-{i + 1}"
            try:
                if i:  # First try the remaining connections, then try a fresh route order.
                    self.script("trasuj.py", self.board, "--smaz")
                    self.drc(label + "-cleared")
                self.script("trasuj.py", self.board, env=env)
                drc = self.drc(label)
                candidate = summarize(drc, erc, self.exceptions)
                accepted = better(candidate, score)
                self.history[-1].update(score=candidate, accepted=accepted)
                print(f"  {candidate['unconnected']} unconnected, {candidate['drc_errors']} DRC errors; "
                      f"{'accepted' if accepted else 'restoring best'}", flush=True)
                if accepted:
                    score = candidate
                    shutil.copy2(self.board, best)
                else:
                    shutil.copy2(best, self.board)
                nets = sorted({re.search(r"\[(.*?)\]", u["items"][0]["description"]).group(1)
                               for u in drc["unconnected_items"]})
                first.write_text("\n".join(nets) + "\n")
                if not score["unconnected"]:
                    break
            except BaseException:
                shutil.copy2(best, self.board)
                raise
            finally:
                self.save()
        # Stitching can disconnect a plane or cause a clearance error too. Check
        # and roll it back with exactly the same gate as normal routing.
        try:
            self.script("prosij.py", self.board)
            drc = self.drc("stitch")
            candidate = summarize(drc, erc, self.exceptions)
            if valid(candidate) and candidate["unconnected"] <= score["unconnected"]:
                shutil.copy2(self.board, best)
            else:
                shutil.copy2(best, self.board)
        except BaseException:
            shutil.copy2(best, self.board)
            raise

    def execute(self):
        self.prepare()
        try:
            self.audit("source")
            erc = self.erc("source")
            baseline = summarize(self.drc("source"), erc, self.exceptions)
            self.result["source_score"] = baseline
            shutil.copy2(self.board, self.out / "source.kicad_pcb")
            if self.args.route_only:
                if valid(baseline):
                    self.route(erc, baseline)
            elif not self.args.check:
                self.script("gen_aio.py", self.project, "--profile", self.args.profile)
                self.audit("generated")
                erc = self.erc("generated")
                self.script("aktualizuj_desku.py", self.board, "--disconnect-changed")
                self.script("rozmisti.py", self.board)
                ready = summarize(self.drc("prepared"), erc, self.exceptions)
                self.result["prepared_score"] = ready
                # Do not automatically delete inherited ESC copper to silence a
                # failed placement or pin reassignment. Preserve the candidate
                # and the exact violations for the next design iteration.
                if valid(ready) and not self.args.prepare_only:
                    self.route(erc, ready)
            final_drc = self.drc("final")
            self.run("tables", [sys.executable, SOURCE / "tabulky.py", self.project, "--profile", self.args.profile])
            final = summarize(final_drc, erc, self.exceptions)
            self.result["final_score"] = final
            self.result["status"] = ("invalid" if not valid(final) else
                                     "incomplete" if final["unconnected"] else "connected")
            self.result["improved"] = better(final, baseline)
            self.result["fabrication_ready"] = False  # rotations, SI, power and manufacturing review still needed
            self.save()
            rows = ["# Výsledek automatického běhu AIO", "",
                    f"Profil: `{self.args.profile}`. Stav: **{self.result['status']}**.", "",
                    "| Kontrola | Vstup | Výstup |", "| --- | ---: | ---: |"]
            for key in ("drc_errors", "unconnected", "unexpected_erc", "unexpected_parity"):
                rows.append(f"| {key} | {baseline[key]} | {final[key]} |")
            rows += ["", "Zdrojový projekt se nezměnil. Kandidát: `project/aio.kicad_pcb`.",
                     "Detaily: `result.json`, `reports/`, `logs/`. Výsledek není uvolněním do výroby.", "",
                     "## Nespojené spoje", ""]
            for u in final_drc["unconnected_items"]:
                rows.append("- " + " → ".join(i["description"] for i in u["items"]))
            (self.out / "REPORT.md").write_text("\n".join(rows) + "\n")
            print(f"{self.result['status']}: {final}; reports: {self.out}", flush=True)
            return 1 if not valid(final) else 2 if final["unconnected"] else 0
        except (Exception, KeyboardInterrupt) as error:
            self.result.update(status="failed", error=str(error))
            self.save()
            print(f"FAILED: {error}\nResults retained: {self.out}", file=sys.stderr)
            return 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=SOURCE)
    p.add_argument("--output", type=Path, default=ROOT / "build/aio" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    p.add_argument("--profile", choices=("current", "micoair-v2"), default="current")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check a copy of the source, without generation/routing")
    mode.add_argument("--route-only", action="store_true", help="route an already generated project, without regenerating it")
    mode.add_argument("--prepare-only", action="store_true", help="generate, sync and place; do not route")
    p.add_argument("--passes", type=int, default=2, help="routing attempts; actual DRC selects the best result")
    p.add_argument("--timeout", type=int, default=1800, help="seconds per subprocess")
    args = p.parse_args()
    if args.passes < 0 or args.timeout <= 0:
        p.error("passes must be nonnegative and timeout positive")
    if args.check and args.profile != "current":
        p.error("--check validates existing files; use --prepare-only to generate a profile")
    if args.output.resolve().is_relative_to(args.source.resolve()):
        p.error("output must be outside the source project")
    if args.output.exists():
        p.error("output directory already exists; choose a new run directory")
    return Build(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
