"""Read-only X11 observations for the private overlay probes."""
import ctypes as C


class Rect(C.Structure):
    _fields_ = [("x", C.c_short), ("y", C.c_short), ("width", C.c_ushort), ("height", C.c_ushort)]


class Attributes(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("width", C.c_int), ("height", C.c_int),
                ("border_width", C.c_int), ("depth", C.c_int), ("visual", C.c_void_p),
                ("root", C.c_ulong), ("class_", C.c_int), ("bit_gravity", C.c_int),
                ("win_gravity", C.c_int), ("backing_store", C.c_int), ("backing_planes", C.c_ulong),
                ("backing_pixel", C.c_ulong), ("save_under", C.c_int), ("colormap", C.c_ulong),
                ("map_installed", C.c_int), ("map_state", C.c_int), ("all_event_masks", C.c_long),
                ("your_event_mask", C.c_long), ("do_not_propagate_mask", C.c_long),
                ("override_redirect", C.c_int), ("screen", C.c_void_p)]


class Button(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
                ("display", C.c_void_p), ("window", C.c_ulong), ("root", C.c_ulong),
                ("subwindow", C.c_ulong), ("time", C.c_ulong), ("x", C.c_int), ("y", C.c_int),
                ("x_root", C.c_int), ("y_root", C.c_int), ("state", C.c_uint),
                ("button", C.c_uint), ("same_screen", C.c_int)]


class Event(C.Union):
    _fields_ = [("button", Button), ("pad", C.c_long * 24)]


def coverage(rectangles):
    """Canonical row intervals: SHAPE returns the union, not the original overlapping run list."""
    rows = {}
    for x, y, w, h in rectangles:
        for row in range(y, y + h):
            rows.setdefault(row, []).append((x, x + w))
    result = {}
    for row, spans in rows.items():
        merged = []
        for lo, hi in sorted(spans):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
            else:
                merged.append((lo, hi))
        result[row] = merged
    return result


class X11:
    def __init__(self, display):
        self.x = C.CDLL("libX11.so.6")
        self.shape = C.CDLL("libXext.so.6")
        for name, args, rest in (
            ("XOpenDisplay", [C.c_char_p], C.c_void_p),
            ("XCloseDisplay", [C.c_void_p], C.c_int),
            ("XDefaultRootWindow", [C.c_void_p], C.c_ulong),
            ("XGetWindowAttributes", [C.c_void_p, C.c_ulong, C.POINTER(Attributes)], C.c_int),
            ("XFetchName", [C.c_void_p, C.c_ulong, C.POINTER(C.c_void_p)], C.c_int),
            ("XFree", [C.c_void_p], C.c_int),
            ("XSendEvent", [C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)], C.c_int),
            ("XFlush", [C.c_void_p], C.c_int),
            ("XCreateSimpleWindow", [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint,
                                     C.c_uint, C.c_ulong, C.c_ulong], C.c_ulong),
            ("XStoreName", [C.c_void_p, C.c_ulong, C.c_char_p], C.c_int),
            ("XChangeWindowAttributes", [C.c_void_p, C.c_ulong, C.c_ulong, C.c_void_p], C.c_int),
            ("XMapWindow", [C.c_void_p, C.c_ulong], C.c_int),
            ("XUnmapWindow", [C.c_void_p, C.c_ulong], C.c_int),
            ("XDestroyWindow", [C.c_void_p, C.c_ulong], C.c_int),
            ("XSync", [C.c_void_p, C.c_int], C.c_int),
            ("XQueryTree", [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                            C.POINTER(C.POINTER(C.c_ulong)), C.POINTER(C.c_uint)], C.c_int),
        ):
            f = getattr(self.x, name)
            f.argtypes, f.restype = args, rest
        self.shape.XShapeGetRectangles.argtypes = [C.c_void_p, C.c_ulong, C.c_int,
                                                   C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.shape.XShapeGetRectangles.restype = C.POINTER(Rect)
        self.shape.XShapeCombineRectangles.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                                      C.c_int, C.POINTER(Rect), C.c_int, C.c_int, C.c_int]
        self.d = self.x.XOpenDisplay(display.encode())
        if not self.d:
            raise RuntimeError("private X display did not open")
        self.root = self.x.XDefaultRootWindow(self.d)

    def close(self):
        self.x.XCloseDisplay(self.d)

    def children(self, win):
        root, parent, count = C.c_ulong(), C.c_ulong(), C.c_uint()
        children = C.POINTER(C.c_ulong)()
        assert self.x.XQueryTree(self.d, win, C.byref(root), C.byref(parent), C.byref(children), C.byref(count))
        result = list(children[:count.value])
        if children:
            self.x.XFree(children)
        return result

    def title(self, win):
        name = C.c_void_p()
        self.x.XFetchName(self.d, win, C.byref(name))
        value = C.string_at(name).decode() if name else ""
        if name:
            self.x.XFree(name)
        return value

    def find(self, title, win=None):
        win = self.root if win is None else win
        if self.title(win) == title:
            return win
        for child in self.children(win):
            found = self.find(title, child)
            if found:
                return found
        return None

    def attrs(self, win):
        attrs = Attributes()
        assert self.x.XGetWindowAttributes(self.d, win, C.byref(attrs))
        return attrs

    def rectangles(self, win, kind):
        count, order = C.c_int(), C.c_int()
        rects = self.shape.XShapeGetRectangles(self.d, win, kind, C.byref(count), C.byref(order))
        result = [(r.x, r.y, r.width, r.height) for r in rects[:count.value]]
        if rects:
            self.x.XFree(rects)
        return result

    def click(self, win, x, y, dx=0, dy=0):
        a = self.attrs(win)
        for kind, px, py in ((4, x, y), (5, x + dx, y + dy)):
            event = Event()
            event.button = Button(kind, 0, 1, self.d, win, self.root, 0, 0, px, py,
                                  a.x + px, a.y + py, 0, 1, 1)
            assert self.x.XSendEvent(self.d, win, 0, 1 << (kind - 2), C.byref(event))
        self.x.XFlush(self.d)

    def check_overlay(self, state):
        win = self.find("DeHulud Combat damage")
        assert win, "overlay title absent"
        attrs = self.attrs(win)
        assert attrs.override_redirect, "overlay is managed"
        assert [attrs.x, attrs.y, attrs.width, attrs.height] == state["geometry"][:4]
        assert (attrs.map_state == 2) == state["mapped"], "map state differs"
        assert self.rectangles(win, 2) == [], "overlay accepts input"
        assert coverage(self.rectangles(win, 0)) == coverage(state["outlines"]), "bounding shape differs"

    def self_check(self):
        """Exercise the observer's ABI against a known window on the owned display."""
        class SetAttributes(C.Structure):
            _fields_ = [("background_pixmap", C.c_ulong), ("background_pixel", C.c_ulong),
                        ("border_pixmap", C.c_ulong), ("border_pixel", C.c_ulong),
                        ("bit_gravity", C.c_int), ("win_gravity", C.c_int), ("backing_store", C.c_int),
                        ("backing_planes", C.c_ulong), ("backing_pixel", C.c_ulong), ("save_under", C.c_int),
                        ("event_mask", C.c_long), ("do_not_propagate_mask", C.c_long),
                        ("override_redirect", C.c_int), ("colormap", C.c_ulong), ("cursor", C.c_ulong)]
        attrs = SetAttributes()
        attrs.override_redirect = 1
        win = self.x.XCreateSimpleWindow(self.d, self.root, 539, 200, 202, 102, 0, 0, 0)
        try:
            self.x.XChangeWindowAttributes(self.d, win, 1 << 9, C.byref(attrs))
            self.x.XStoreName(self.d, win, b"DeHulud Combat damage")
            runs = [(0, 0, 4, 4), (2, 2, 5, 3)]
            rects = (Rect * len(runs))(*(Rect(*r) for r in runs))
            self.shape.XShapeCombineRectangles(self.d, win, 0, 0, 0, rects, len(runs), 0, 0)
            self.shape.XShapeCombineRectangles(self.d, win, 2, 0, 0, None, 0, 0, 0)
            self.x.XSync(self.d, 0)
            state = {"geometry": [539, 200, 202, 102, 2, 1], "mapped": False, "outlines": runs}
            self.check_overlay(state)
            self.x.XMapWindow(self.d, win)
            self.x.XSync(self.d, 0)
            state["mapped"] = True
            self.check_overlay(state)
            self.x.XUnmapWindow(self.d, win)
            self.x.XSync(self.d, 0)
            state["mapped"] = False
            self.check_overlay(state)
        finally:
            self.x.XDestroyWindow(self.d, win)
            self.x.XSync(self.d, 0)
