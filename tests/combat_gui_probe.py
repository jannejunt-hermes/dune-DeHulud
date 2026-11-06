"""Runs INSIDE the owned compositor started by test_combat_gui.py. Builds DeHulud Combat's real window with a
scripted meter.

argv: <result.json> <comma-separated X sockets that existed before the compositor started, or '-'>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def overlay_on_server(w, xs):
    """The overlay window as the X server sees it, through the program's own X SHAPE connection."""
    import ctypes
    import dehulud_combat as dehulud
    st, ov = w.overlay_state(), w.overlay
    x11, xext, dpy, xid = xs.x11, xs.xext, xs.dpy, ov.xid
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XSync(dpy, 0)

    class Attrs(ctypes.Structure):                  # XWindowAttributes
        _fields_ = [(n, ctypes.c_int) for n in ("x", "y", "width", "height", "border_width", "depth")] + [
            ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong), ("class_", ctypes.c_int),
            ("bit_gravity", ctypes.c_int), ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
            ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong), ("save_under", ctypes.c_int),
            ("colormap", ctypes.c_ulong), ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
            ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
            ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
            ("screen", ctypes.c_void_p)]
    a = Attrs()
    x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Attrs)]
    x11.XGetWindowAttributes(dpy, xid, ctypes.byref(a))
    xext.XShapeGetRectangles.restype = ctypes.POINTER(dehulud._XRectangle)
    xext.XShapeGetRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    x11.XFree.argtypes = [ctypes.c_void_p]

    def region(kind):
        n, order = ctypes.c_int(0), ctypes.c_int(0)
        r = xext.XShapeGetRectangles(dpy, xid, kind, ctypes.byref(n), ctypes.byref(order))
        rects = [(r[i].x, r[i].y, r[i].width, r[i].height) for i in range(n.value)]
        if r:
            x11.XFree(r)
        return n.value, cover(rects)

    def cover(rects):
        return sorted({(x, y) for rx, ry, rw, rh in rects for x in range(rx, rx + rw) for y in range(ry, ry + rh)})
    n_input, _ = region(dehulud.SHAPE_INPUT)
    _, bounding = region(dehulud.SHAPE_BOUNDING)
    return {"state": st, "title": ov.top.title(), "frame_is_mapped_window": ov.xid == int(ov.top.wm_frame(), 16),
            "override_redirect": bool(a.override_redirect), "viewable": a.map_state == 2,
            "rootxy": [ov.top.winfo_rootx(), ov.top.winfo_rooty()], "size": [a.width, a.height],
            "input_rects": n_input, "bounding_is_outlines": bounding == cover(st["outlines"])}


def main(result_path, before):
    display = os.environ.get("DISPLAY", "")
    number = display[1:].split(".")[0] if display.startswith(":") else ""
    if not number or "X" + number in before.split(","):     # never the session's own display
        with open(result_path, "w") as f:
            json.dump({"refused": display}, f)
        return 3
    import tkinter
    from tkinter import messagebox
    import dehulud_combat as dehulud

    readings = iter([dehulud.Reading("on foot", 42, 0.425, taken=(37,), dealt=((120,), (40,))),
                     dehulud.Reading("Unsupported game version", detail="PE timestamp 1700000000", hint="PE 1700000000"),
                     dehulud.Reading("vehicle", 100, 1.0),
                     dehulud.Reading("no permission", detail="FIX: sudo sysctl", hint=dehulud.MENU_HINT)])

    class Meter:
        def poll(self, enabled):
            return next(readings)

    cfg_path = os.path.join(os.environ["XDG_CONFIG_HOME"], "dehulud-combat", "config.json")
    w = dehulud.Window(tkinter, Meter(), cfg_path)
    w.root.update()
    out = {"title": w.root.title(), "screen": w.root.winfo_screen(), "topmost": int(w.root.attributes("-topmost")),
           "frameless": bool(w.root.overrideredirect()), "size": [w.root.winfo_width(), w.root.winfo_height()],
           "shown": []}
    xs = w.overlay.xs if w.overlay else None
    out["overlay_unmapped_at_start"] = bool(w.overlay) and not w.overlay.top.winfo_ismapped()
    for i in range(4):
        w.tick()
        w.root.update()
        if i == 0:
            out["overlay"] = overlay_on_server(w, xs)
        c = w.canvas
        out["shown"].append([c.itemcget(w.pct, "text"), c.itemcget(w.status, "text"), c.itemcget(w.fill, "fill"),
                             c.itemcget(w.hint, "text")])
        out.setdefault("boxes", []).append({k: c.bbox(getattr(w, k)) for k in ("pct", "status", "hint")})
    shown = []
    messagebox.showinfo = lambda title, message, **kw: shown.append(message)
    w.show_help()
    out["help"] = shown[0] if shown else None

    class Ev:
        def __init__(self, x, y):
            self.x_root, self.y_root = x, y
            self.x, self.y = x - w.pos[0], y - w.pos[1]
    x0, y0 = w.pos
    w._press(Ev(x0 + 80, y0 + 9))                        # a click on the Taken switch
    w._release(Ev(x0 + 81, y0 + 10))
    w.root.update()
    out["after_click"] = {"config": dehulud.load_config(cfg_path), "pos": list(w.pos),
                          "size": [w.root.winfo_width(), w.root.winfo_height()]}
    x0, y0 = w.pos
    w._press(Ev(x0 + 4, y0 + 2))
    w._drag(Ev(100, 100))
    w._drag(Ev(134, 72))
    w._release(Ev(134, 72))
    out["after_drag"] = dehulud.load_config(cfg_path)
    w.frame_var.set(True)
    w.toggle_frame()
    w.root.update()
    out["after_frame"] = dehulud.load_config(cfg_path)
    w.reset_position()
    out["after_reset"] = dehulud.load_config(cfg_path)
    for _ in range(6):                                  # the numbers age out: unmapped
        w.tick()
        w.root.update()
    out["overlay_after"] = {"mapped": w.overlay_state()["mapped"], "ismapped": bool(w.overlay.top.winfo_ismapped())}
    w.quit()
    try:
        out["destroyed"] = not w.root.winfo_exists()
    except tkinter.TclError:
        out["destroyed"] = True
    with open(result_path, "w") as f:
        json.dump(out, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
