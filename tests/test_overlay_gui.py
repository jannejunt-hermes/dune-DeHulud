"""Overlay integration on a private Xwayland output; never the caller's display."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class OverlayGui(unittest.TestCase):
    def run_probe(self, mode):
        missing = [name for name in ("kwin_wayland", "Xwayland", "dbus-run-session") if not shutil.which(name)]
        if missing:
            self.skipTest("private display tools absent: " + ", ".join(missing))
        if mode == "python":
            try:
                import tkinter  # noqa: F401
            except ImportError:
                self.skipTest("this Python has no tkinter")
        binary = os.environ.get("DEHULUD_OVERLAY_BIN")
        if mode == "rust" and not binary:
            self.skipTest("run from cargo test --features test-source for the Rust window")
        with tempfile.TemporaryDirectory(prefix="overlay-gui-") as tmp:
            tmp = Path(tmp)
            dirs = {k: tmp / k for k in ("home", "run", "cfg", "data", "cache", "state")}
            for d in dirs.values():
                d.mkdir(mode=0o700)
            before = sorted(os.listdir("/tmp/.X11-unix")) if os.path.isdir("/tmp/.X11-unix") else []
            result = tmp / "result.json"
            app = tmp / "app.sh"
            args = [sys.executable, "-B", str(HERE / "overlay_probe.py"), mode, str(result), ",".join(before) or "-"]
            app.write_text("#!/bin/sh\nexec " + shlex.join(args) + " >" + shlex.quote(str(tmp / "probe.log")) + " 2>&1\n")
            app.chmod(0o700)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "TMPDIR": str(tmp),
                   "HOME": str(dirs["home"]), **{"XDG_" + k + "_HOME": str(dirs[v]) for k, v in
                   (("CONFIG", "cfg"), ("DATA", "data"), ("CACHE", "cache"), ("STATE", "state"))},
                   "XDG_RUNTIME_DIR": str(dirs["run"])}
            if binary:
                env["DEHULUD_OVERLAY_BIN"] = binary
            with (tmp / "kwin.log").open("w") as log:
                subprocess.run(["dbus-run-session", "--", "kwin_wayland", "--virtual", "--xwayland",
                                "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities", "--socket",
                                "overlay-test", "--width", "1280", "--height", "800", "--exit-with-session", str(app)],
                               env=env, stdout=log, stderr=log, timeout=120, check=False)
            logs = "\n".join(p.read_text()[-6000:] for p in (tmp / "probe.log", tmp / "kwin.log") if p.exists())
            self.assertTrue(result.exists(), logs)
            data = json.loads(result.read_text())
            self.assertEqual(data.get("failures"), [], logs + repr(data))
            self.assertGreaterEqual(data["shape_checks"], 3)
            if mode != "harness":
                self.assertEqual(data["heights"], [62, 38, 38, 62, 62, 18, 38, 62, 62])

    def test_python_window(self):
        self.run_probe("python")

    def test_x11_observer_on_owned_display(self):
        self.run_probe("harness")

    def test_rust_window(self):
        self.run_probe("rust")


if __name__ == "__main__":
    unittest.main()
