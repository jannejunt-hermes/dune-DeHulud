"""Overlay observations inside the private compositor created by test_overlay_gui.py."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import selectors
import shlex
import socket

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from overlay_x11 import X11


def wait_for(predicate, description):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        found = predicate()
        if found is not None:
            return found
        time.sleep(.005)
    raise AssertionError("timed out: " + description)


def read_events(path):
    events = []
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # a trace writer may still be appending the final line
    return events


def state(view, geometry, module):
    outlines, fills = module.overlay_rects(view, geometry[4], geometry[5])
    return {"geometry": list(geometry), "mapped": not view.empty(),
            "outlines": [list(r) for r in outlines], "fills": [list(r) for r in fills]}


def socket_snapshot(pid):
    """Classify the observed sockets of this probe's child, never another process."""
    base = Path("/proc") / str(pid)
    inodes = []
    for p in (base / "fd").iterdir():
        try:
            target = str(p.readlink())
        except FileNotFoundError:
            continue  # /proc may include the enumeration's own already-closed directory descriptor
        if target.startswith("socket:["):
            inodes.append(target[8:-1])
    assert inodes, "no display socket observed"
    unix = {line.split()[6] for line in (base / "net/unix").read_text().splitlines()[1:]}
    assert set(inodes) <= unix, "a non-Unix socket is open"
    for table in ("tcp", "tcp6", "udp", "udp6", "raw", "raw6"):
        for line in (base / ("net/" + table)).read_text().splitlines()[1:]:
            assert line.split()[9] not in inodes, "an IP socket is open"
    if pid == os.getpid():
        number = os.environ["DISPLAY"][1:].split(".")[0]
        expected = "/tmp/.X11-unix/X" + number
        for p in (base / "fd").iterdir():
            try:
                target = str(p.readlink())
            except FileNotFoundError:
                continue
            if target.startswith("socket:["):
                with socket.socket(fileno=os.dup(int(p.name))) as connection:
                    peer = connection.getpeername()
                    if isinstance(peer, bytes):
                        peer = peer.decode()
                    assert peer.lstrip("\0") == expected, (peer, expected)
    return len(inodes)


def shipped_sockets(x, out):
    """Runs only in the newly-mounted PID namespace: production scans see no owner processes."""
    assert os.getpid() == 1, "production probes require the private PID namespace"
    commands = [("plain", [os.environ["DEHULUD_SOCKET_PLAIN_BIN"]], "DeHulud"),
                ("combat", [os.environ["DEHULUD_SOCKET_COMBAT_BIN"]], "DeHulud Combat")]
    try:
        import tkinter  # noqa: F401
    except ImportError:
        out["python_skip"] = "this Python has no tkinter"
    else:
        commands.append(("python", [sys.executable, "-B", str(Path(__file__).resolve().parent.parent / "dehulud_combat.py")],
                         "DeHulud Combat"))
    counts = {}
    for name, argv, title in commands:
        with (Path(os.environ["TMPDIR"]) / (name + "-socket.log")).open("w") as log:
            child = subprocess.Popen(argv, stdout=log, stderr=log)
            try:
                wait_for(lambda: x.find(title), name + " production window")
                counts[name] = []
                for _ in range(3):
                    counts[name].append(socket_snapshot(child.pid))
                    time.sleep(.05)
            finally:
                child.terminate()
                child.wait(timeout=5)
                wait_for(lambda: True if x.find(title) is None else None, name + " window closed")
    out["socket_counts"] = counts


def rust_reads(no_shape):
    tmp = Path(os.environ["TMPDIR"]) / ("no-shape" if no_shape else "shape")
    tmp.mkdir()
    (tmp / "cfg").mkdir()
    ctl, trace = tmp / "control", tmp / "trace"
    fin, fout = tmp / "in", tmp / "out"
    for p in (fin, fout):
        os.mkfifo(p, 0o600)
    inp = os.open(fin, os.O_RDWR)
    output = os.open(fout, os.O_RDWR | os.O_NONBLOCK)
    keys = ["pid=child", "poll_ms=100", "scan_ms=0", "trace=" + str(trace), "no_shape=" + str(int(no_shape))]

    def control(extra=()):
        replacement = ctl.with_suffix(".tmp")
        replacement.write_text("\n".join(keys + list(extra)) + "\n")
        replacement.replace(ctl)

    control()
    fake = Path(__file__).resolve().parent / "fake_game.py"
    script = "exec " + shlex.join([sys.executable, "-B", str(fake), "DuneSandbox-Win64-Shipping.exe",
                                   "--build", "26592269", "--damage"]) + " <" + shlex.quote(str(fin)) + " >" + shlex.quote(str(fout))
    log = (tmp / "stderr").open("w")
    child = subprocess.Popen([os.environ["DEHULUD_OVERLAY_BIN"], "--launch", "/bin/sh", "-c", script],
                             env=dict(os.environ, DEHULUD_TEST_SOURCE=str(ctl), XDG_CONFIG_HOME=str(tmp / "cfg")),
                             stderr=log, stdout=log)
    try:
        selector = selectors.DefaultSelector()
        selector.register(output, selectors.EVENT_READ)
        assert selector.select(10), "fake game metadata absent"
        info = json.loads(os.read(output, 65536).decode().splitlines()[0])
        selector.close()
        control(["base=" + str(info["base"]), "size=" + str(info["size"])])

        def polls():
            es = read_events(trace)
            return es if len([e for e in es if e.get("event") == "poll" and e.get("build")]) >= 2 else None

        es = wait_for(polls, "fake game reads")
        reads = [e for e in es if e.get("event") == "read"]
        assert reads and any(e.get("event") == "poll" and e.get("percent") == 42 for e in es)
        expected_enabled = {"worm"} if no_shape else {"worm", "damage_taken", "damage_dealt"}
        assert all(set(e["enabled"]) == expected_enabled for e in es if e.get("event") == "poll")
        ticks = [e for e in es if e.get("event") == "tick"]
        assert ticks and all((e["overlay"] is None) == no_shape for e in ticks)
        assert all(set(e["enabled"]) == {"worm", "damage_taken", "damage_dealt"} for e in ticks)
        for feature in ("damage_taken", "damage_dealt"):
            overlapping = [e for e in reads for lo, hi in info["damage"]["feature_ranges"][feature]
                           if e["address"] < hi and lo < e["address"] + e["size"]]
            assert bool(overlapping) != no_shape, (feature, no_shape, overlapping)
        sockets = socket_snapshot(child.pid)
        control(["base=" + str(info["base"]), "size=" + str(info["size"]), "stop=1"])
        os.write(inp, b"exit\n")
        assert child.wait(timeout=10) == 0
        log.flush()
        stderr = (tmp / "stderr").read_text()
        assert stderr.count("damage numbers need the X SHAPE extension") == int(no_shape), stderr
        return {"no_shape": no_shape, "reads": len(reads), "sockets": sockets}
    finally:
        os.write(inp, b"exit\n")
        control(["stop=1"])
        if child.poll() is None:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        os.close(inp)
        os.close(output)
        log.close()


def rust_probe(x, out):
    import dehulud_combat as m
    tmp = Path(os.environ["TMPDIR"])
    trace, ctl = tmp / "trace.jsonl", tmp / "control"
    lines = ["trace=" + str(trace), "poll_ms=250", "step=0",
             "reading=on foot|42|0.425||||/",
             "reading=on foot|42|0.425|||37|120/40",
             "reading=on foot|42|0.425|||999999|0.49/2.5",
             "reading=Unsupported game version|||||-|-"]

    def set_control(*extra):
        p = ctl.with_suffix(".tmp")
        p.write_text("\n".join(lines + list(extra)) + "\n")
        p.replace(ctl)

    def events():
        return read_events(trace)

    set_control()
    log = (tmp / "rust.log").open("w")
    child = subprocess.Popen([os.environ["DEHULUD_OVERLAY_BIN"]],
                             env=dict(os.environ, DEHULUD_TEST_SOURCE=str(ctl)), stdout=log, stderr=log)
    try:
        seen, view, last_poll, shape_checks = 0, m.Overlay(), None, 0

        def next_tick():
            nonlocal seen, last_poll, shape_checks
            evs = wait_for(lambda: events() if any(e.get("event") == "tick" for e in events()[seen:]) else None,
                           "overlay tick")
            while seen < len(evs):
                e = evs[seen]
                seen += 1
                if e.get("event") == "poll":
                    last_poll = e
                    taken = None if e["taken"] is None else tuple(v for v in e["taken"] if v is not None)
                    dealt = None if e["dealt"] is None else tuple(() if v is None else (v,) for v in e["dealt"])
                    r = m.Reading(e["status"], e["percent"], e["fraction"], hint=e["hint"], detail=e["detail"],
                                  taken=taken, dealt=dealt)
                    view.step(r, frozenset(e["enabled"]))
                if e.get("event") == "reset":
                    view.reset(e["feature"])
                if e.get("event") == "tick":
                    actual = e["overlay"]
                    expected = state(view, m.overlay_geometry((0, 0, 1280, 800)), m)
                    assert actual == expected, (last_poll, actual, expected)
                    x.check_overlay(actual)
                    shape_checks += 1
                    return e
            raise AssertionError("missing tick")

        e = next_tick()
        assert not e["overlay"]["mapped"]
        set_control("step=1")
        e = next_tick()
        assert e["overlay"]["mapped"]
        for _ in range(5):
            e = next_tick()
        assert not e["overlay"]["mapped"], "numbers did not expire"
        set_control("step=2")
        e = next_tick()
        assert e["overlay"]["mapped"]
        set_control("step=3")
        e = next_tick()
        assert not e["overlay"]["mapped"], "untrustworthy reading did not clear"
        out["socket_count"] = socket_snapshot(child.pid)
        connects = [e["addr"] for e in events() if e.get("event") == "connect"]
        assert connects and all(a.startswith(("/tmp/.X11-unix/X", "@/tmp/.X11-unix/X")) for a in connects), connects
        win = x.find("DeHulud Combat")
        assert win
        a = x.attrs(win)
        assert a.height == 62
        heights = [a.height]
        # A Gray-code walk visits all eight switch combinations; one header click per transition.
        for at, expected in ((10, 38), (80, 38), (10, 62), (150, 62), (10, 18), (80, 38), (10, 62), (150, 62)):
            old = len(events())
            before = x.attrs(win)
            x.click(win, at, 9)
            wait_for(lambda: True if any(e.get("event") == "switched" for e in events()[old:]) else None,
                     "header switch")
            a = x.attrs(win)
            assert a.height == expected, (at, a.height, expected)
            assert (a.x, a.y) == (before.x, before.y)
            cfg = json.loads((Path(os.environ["XDG_CONFIG_HOME"]) / "dehulud-combat/config.json").read_text())
            switched = next(e for e in events()[old:] if e.get("event") == "switched")
            for key in m.FEATURES:
                assert cfg[key] == (key in switched["enabled"]), (cfg, switched)
            heights.append(a.height)
        before = x.attrs(win)
        old = len(events())
        x.click(win, 10, 9, 23, 17)
        wait_for(lambda: True if any(e.get("event") == "moved" for e in events()[old:]) else None, "drag")
        a = x.attrs(win)
        assert (a.x, a.y) == (before.x + 23, before.y + 17)
        out.update(shape_checks=shape_checks, heights=heights)
    finally:
        set_control("stop=1")
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        log.close()


def python_probe(x, out):
    import tkinter as tk
    import dehulud_combat as m
    from types import SimpleNamespace

    class Meter:
        reading = m.Reading("on foot", 42, .425, taken=(), dealt=((), ()))

        def poll(self, enabled):
            return self.reading

    meter = Meter()
    cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "dehulud-combat/config.json"
    w = m.Window(tk, meter, str(cfg))
    try:
        w.root.update()
        heights, checks = [w.root.winfo_height()], 0
        empty = meter.reading
        hit = m.Reading("on foot", 42, .425, taken=(37,), dealt=((120,), (40,)))
        readings = [empty, hit] + [empty] * 5 + [hit, m.Reading("Unsupported game version")]
        expected_maps = [False, True, True, True, True, True, False, True, False]
        for r, expected_map in zip(readings, expected_maps):
            meter.reading = r
            w.tick()
            w.root.update()
            out.setdefault("windows", []).append({"shaped": w.overlay.xid, "queried": x.find(m.OVERLAY_TITLE),
                                                    "mapped": w.overlay_state()["mapped"]})
            x.check_overlay(w.overlay_state())
            assert w.overlay_state()["mapped"] == expected_map, "numbers did not map, expire, or clear"
            text = [w.canvas.itemcget(item, "text") for item in w.canvas.find_all()
                    if w.canvas.type(item) == "text"]
            assert not {"TAKEN", "HEALTH", "SHIELD"}.intersection(text), text
            checks += 1
        out["socket_count"] = socket_snapshot(os.getpid())
        for at, expected in ((10, 38), (80, 38), (10, 62), (150, 62), (10, 18), (80, 38), (10, 62), (150, 62)):
            pos = w.pos
            ev = SimpleNamespace(x=at, y=9, x_root=pos[0] + at, y_root=pos[1] + 9)
            w._press(ev)
            w._release(ev)
            w.root.update()
            assert w.root.winfo_height() == expected
            assert w.pos == pos
            saved = m.load_config(str(cfg))
            assert all(saved[k] == (k in w.enabled) for k in m.FEATURES)
            heights.append(w.root.winfo_height())
        pos = w.pos
        w._press(SimpleNamespace(x=10, y=9, x_root=pos[0] + 10, y_root=pos[1] + 9))
        w._release(SimpleNamespace(x=33, y=26, x_root=pos[0] + 33, y_root=pos[1] + 26))
        assert w.pos == (pos[0] + 23, pos[1] + 17)
        out.update(shape_checks=checks, heights=heights)
    finally:
        w.quit()


def main(mode, result, before):
    out = {"failures": []}
    try:
        # The compositor may remove TMPDIR from the session it starts.
        os.environ["TMPDIR"] = str(Path(result).parent)
        display = os.environ.get("DISPLAY", "")
        number = display[1:].split(".")[0] if display.startswith(":") else ""
        assert number and "X" + number not in before.split(","), "refused pre-existing display"
        x = X11("unix/:" + number)
        try:
            if mode == "harness":
                x.self_check()
                out.update(shape_checks=3)
            elif mode == "rust-reads":
                out["read_log"] = [rust_reads(False), rust_reads(True)]
            elif mode == "socket-inner":
                shipped_sockets(x, out)
            elif mode == "sockets":
                subprocess.run(["unshare", "--user", "--map-root-user", "--pid", "--fork", "--mount-proc",
                                sys.executable, "-B", __file__, "socket-inner", result, before], check=True, timeout=30)
                return
            else:
                (rust_probe if mode == "rust" else python_probe)(x, out)
        finally:
            x.close()
    except Exception:
        out["failures"].append(traceback.format_exc())
    Path(result).write_text(json.dumps(out))


if __name__ == "__main__":
    main(*sys.argv[1:])
