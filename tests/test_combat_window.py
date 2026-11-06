"""DeHulud Combat's window: switches (config keys, flags, header clicks), layout, the damage overlay's window
(shapes, map state, drawing, the X SHAPE layer) and the enabled set handed to the poll. The windows are driven
through a stand-in for tkinter that records what is drawn and a stand-in for the X SHAPE connection, so these
run without a display; tests/test_combat_gui.py builds the real Tk windows on a private display."""
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from support import FakeGame, FakeSource, GameTest
import dehulud_combat as dehulud

ALL = dehulud.ALL
TAKEN, DEALT = "damage_taken", "damage_dealt"
DEFAULTS = {"x": None, "y": None, "frame": False, "worm": True, "damage_taken": True, "damage_dealt": True}
HEIGHTS = {(False, False, False): 18, (True, False, False): 62, (False, True, False): 38,
           (False, False, True): 38, (True, True, False): 62, (True, False, True): 62,
           (False, True, True): 38, (True, True, True): 62}


def features(worm, taken, dealt):
    return frozenset(f for f, on in zip(dehulud.FEATURES, (worm, taken, dealt)) if on)


class ConfigKeys(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "dehulud", "config.json")

    def write(self, text):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            f.write(text)

    def test_defaults_are_on(self):
        self.assertEqual(dehulud.load_config(self.path), DEFAULTS)
        self.write('{"x": 5, "y": 6}')                   # a file from before the switches existed
        self.assertEqual(dehulud.load_config(self.path), dict(DEFAULTS, x=5, y=6))

    def test_each_key_is_read_on_its_own(self):
        self.write('{"worm": false, "damage_taken": true, "damage_dealt": false}')
        self.assertEqual(dehulud.load_config(self.path), dict(DEFAULTS, worm=False, damage_dealt=False))

    def test_damaged_values_give_the_default_for_that_key_only(self):
        for bad in ('"false"', "0", "1", "null", "[]", "{}", '"no"'):
            self.write('{"worm": %s, "damage_taken": false, "damage_dealt": %s}' % (bad, bad))
            self.assertEqual(dehulud.load_config(self.path), dict(DEFAULTS, damage_taken=False), bad)

    def test_saved_file(self):
        self.assertTrue(dehulud.save_config(self.path, dict(DEFAULTS, x=1, y=2, damage_taken=False)))
        with open(self.path) as f:
            text = f.read()
        self.assertEqual(text, '{"x": 1, "y": 2, "frame": false, "worm": true, "damage_taken": false, '
                               '"damage_dealt": true}')
        self.assertEqual(dehulud.load_config(self.path), dict(DEFAULTS, x=1, y=2, damage_taken=False))


class Flags(unittest.TestCase):
    def test_each_flag(self):
        for flag, key in (("--no-worm", "worm"), ("--no-taken", TAKEN), ("--no-dealt", DEALT)):
            self.assertEqual(dehulud.parse_args([flag]), (False, None, frozenset([key])))
        self.assertEqual(dehulud.parse_args(["--no-dealt", "--no-worm"]),
                         (False, None, frozenset(["worm", DEALT])))

    def test_text_mode_refuses_no_worm(self):
        for argv in (["--text", "--no-worm"], ["--no-dealt", "--no-worm", "--text"]):
            with self.assertRaises(SystemExit) as cm:
                dehulud.parse_args(argv)
            self.assertEqual(cm.exception.code, "dehulud-combat: text mode shows only the worm meter; drop --no-worm")
        self.assertEqual(dehulud.parse_args(["--text", "--no-taken", "--no-dealt"]),
                         (True, None, frozenset([TAKEN, DEALT])))
        err = io.StringIO()
        with mock.patch("sys.stderr", err):     # with --launch the game is never blocked
            self.assertEqual(dehulud.parse_args(["--text", "--no-worm", "--launch", "g"]),
                             (True, ["g"], frozenset(["worm"])))
        self.assertIn("drop --no-worm (the game starts without the meter)", err.getvalue())

    def test_flags_before_launch_count_after_it_belong_to_the_game(self):
        self.assertEqual(dehulud.parse_args(["--no-taken", "--launch", "game", "--no-worm"]),
                         (False, ["game", "--no-worm"], frozenset([TAKEN])))

    def test_help_names_the_flags(self):
        for flag in dehulud.FLAGS:
            self.assertIn(flag, dehulud.__doc__)
        with self.assertRaises(SystemExit):
            dehulud.parse_args(["--no-wurm"])


class Layout(unittest.TestCase):
    def test_height_of_all_eight_combinations(self):
        for combo, height in HEIGHTS.items():
            self.assertEqual(dehulud.layout(features(*combo))[1], height, combo)

    def test_sections_keep_their_order(self):
        self.assertEqual(dehulud.layout(ALL)[0], [("header", 0), ("worm", 18), ("status", 42)])
        self.assertEqual(dehulud.layout(frozenset([DEALT]))[0], [("header", 0), ("status", 18)])
        self.assertEqual(dehulud.layout(frozenset())[0], [("header", 0)])

    def test_header_zones(self):
        z = dehulud.header_zone
        self.assertEqual([z(x, 9) for x in (0, 56, 57, 116, 117, 179)],
                         ["worm", "worm", TAKEN, TAKEN, DEALT, DEALT])
        self.assertEqual([z(30, y) for y in (0, 17)], ["worm", "worm"])
        self.assertEqual([z(30, 18), z(30, -1), z(-1, 5), z(180, 5)], [None] * 4)

    def test_click_or_drag(self):
        self.assertTrue(all(dehulud.is_click(dx, dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2)))
        self.assertFalse(any(dehulud.is_click(dx, dy) for dx, dy in ((3, 0), (0, 3), (-3, 0), (0, -3), (5, 5))))

    def test_header_strings(self):
        self.assertEqual(dehulud.header_cells(ALL), [(6, "[x] Worm", "#d8cfb4"), (60, "[x] Taken", "#d8cfb4"),
                                                     (120, "[x] Dealt", "#d8cfb4")])
        self.assertEqual(dehulud.header_cells(frozenset([TAKEN])),
                         [(6, "[ ] Worm", "#6b7174"), (60, "[x] Taken", "#d8cfb4"), (120, "[ ] Dealt", "#6b7174")])


class Numbers(unittest.TestCase):
    def test_rounding_and_cap(self):
        n = dehulud.shown_number
        self.assertEqual([n(v) for v in (0, 0.49, 0.5, 1.5, 2.5, 36.6, 99999, 99999.4, 99999.5, 1e12)],
                         [None, None, 1, 2, 3, 37, 99999, 99999, 99999, 99999])
        self.assertEqual([n(v) for v in (-1, float("nan"), float("inf"), None, True)], [None] * 5)



class StubDamage(dehulud.NoDamage):
    """A damage source standing in for the readers: scripted values, every call logged (the hooks stay no-ops)."""

    def __init__(self, taken=(), dealt=((), ()), mode="on foot"):
        self.calls, self.values = [], {"taken": taken, "dealt": dealt, "mode": mode}

    def _call(self, name, game):
        self.calls.append(name)
        assert isinstance(game, dehulud.Attached)
        value = self.values[name]
        if isinstance(value, Exception):
            raise value
        return value

    def taken(self, game):
        return self._call("taken", game)

    def dealt(self, game):
        return self._call("dealt", game)

    def mode(self, game):
        return self._call("mode", game)


class OffMeansNoReads(GameTest):
    """A section that is off is not read: the poll never calls its route. Checked at the call boundary (the
    route and reader calls) and by the number of memory reads of a poll."""

    def setUp(self):
        super().setUp()
        self.damage = StubDamage(taken=(37,), dealt=((120,), (40,)))
        self.meter = dehulud.Meter(source=self.source, scan_interval=0, damage=self.damage)
        self.meter.poll()                       # attach and read the class slots once
        del self.damage.calls[:]

    def test_everything_on(self):
        r = self.meter.poll(ALL)
        self.assertEqual((r.status, r.percent, r.taken, r.dealt), ("on foot", 42, (37,), ((120,), (40,))))
        self.assertEqual(self.damage.calls, ["taken", "dealt"])
        self.assertEqual(self.meter.reads, 21)  # the PE header check + the worm route's 20

    def test_worm_off_never_walks_the_worm_route(self):
        with mock.patch.object(dehulud.Meter, "_route", side_effect=AssertionError("worm route read")):
            r = self.meter.poll(frozenset([TAKEN, DEALT]))
        self.assertEqual((r.status, r.percent, r.taken, r.dealt), ("on foot", None, (37,), ((120,), (40,))))
        self.assertEqual(self.damage.calls, ["mode", "taken", "dealt"])
        self.assertEqual(self.meter.reads, 1)   # the PE header check only

    def test_worm_on_is_unchanged_and_the_damage_readers_are_not_called(self):
        r = self.meter.poll(frozenset(["worm"]))
        self.assertEqual(r, dehulud.Reading("on foot", 42, 0.425))
        self.assertEqual(self.damage.calls, [])
        self.assertEqual(self.meter.reads, 21)

    def test_each_damage_section_alone(self):
        r = self.meter.poll(frozenset([TAKEN]))
        self.assertEqual((r.taken, r.dealt, self.damage.calls), ((37,), None, ["mode", "taken"]))
        del self.damage.calls[:]
        r = self.meter.poll(frozenset([DEALT]))
        self.assertEqual((r.taken, r.dealt, self.damage.calls), (None, ((120,), (40,)), ["mode", "dealt"]))

    def test_all_off_reads_nothing(self):
        r = self.meter.poll(frozenset())
        self.assertEqual((self.meter.reads, self.damage.calls, r.taken, r.dealt), (0, [], None, None))

    def test_worm_off_without_a_mode_says_no_data(self):
        self.damage.values["mode"] = None
        self.assertEqual(self.meter.poll(frozenset([TAKEN])).status, "no data")

    def test_a_reader_failure_is_dash_for_that_section_only(self):
        self.damage.values["taken"] = OSError(14, "Bad address")
        r = self.meter.poll(ALL)
        self.assertEqual((r.percent, r.taken, r.dealt), (42, None, ((120,), (40,))))

    def test_default_readers_show_dash(self):
        meter = dehulud.Meter(source=self.source, scan_interval=0)
        r = meter.poll()
        self.assertEqual((r.percent, r.taken, r.dealt), (42, None, None))


class Hooked(StubDamage):
    """Also logs the two hooks, with their arguments, in the same call log."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.times = []

    def begin(self, now, enabled, image):
        self.times.append(now)
        self.calls.append(("begin", tuple(f for f in dehulud.FEATURES if f in enabled), image))

    def reset(self, feature):
        self.calls.append(("reset", feature))


class Hooks(GameTest):
    """begin(now, enabled, image) once per poll before the readers, only while attached with a damage section on;
    reset(feature) forwarded from the meter."""
    extra = ("--fixed",)

    def test_begin_and_reset(self):
        d = Hooked()
        meter = dehulud.Meter(source=self.source, scan_interval=0, damage=d)
        meter.poll(ALL)
        self.assertEqual(d.calls, [("begin", ("worm", TAKEN, DEALT), 1), "taken", "dealt"])
        del d.calls[:]
        meter.poll(frozenset([TAKEN, DEALT]))
        self.assertEqual(d.calls, [("begin", (TAKEN, DEALT), 1), "mode", "taken", "dealt"])
        del d.calls[:]
        meter.poll(frozenset([DEALT]))
        self.assertEqual(d.calls, [("begin", (DEALT,), 1), "mode", "dealt"])
        del d.calls[:]
        meter.poll(frozenset(["worm"]))                 # no damage section on: no begin
        meter.poll(frozenset())
        self.assertEqual(d.calls, [])
        self.assertTrue(all(a <= b for a, b in zip(d.times, d.times[1:])), "monotonic")
        self.game.exec_image(1700000000)                # not attached (an unknown image): no begin
        self.assertEqual(meter.poll(ALL).status, "Unsupported game version")
        self.assertEqual(d.calls, [])
        self.game.exec_image(self.game.timestamp)       # attached again: a new serial
        meter.poll(ALL)
        self.assertEqual(d.calls[0], ("begin", ("worm", TAKEN, DEALT), 2))
        del d.calls[:]
        for f in dehulud.FEATURES:
            meter.reset(f)
        self.assertEqual(d.calls, [("reset", "worm"), ("reset", TAKEN), ("reset", DEALT)])

    def test_the_clock_is_the_meters(self):
        d = Hooked()
        meter = dehulud.Meter(source=self.source, scan_interval=0, damage=d, clock=lambda: 123.25)
        meter.poll(ALL)
        self.assertEqual(d.times, [123.25])

    def test_stand_ins_are_no_ops(self):
        nd = dehulud.NoDamage()
        self.assertIsNone(nd.begin(0.0, ALL, 1))
        self.assertIsNone(nd.reset(TAKEN))


class UnsupportedEverywhere(GameTest):
    extra = ("--timestamp", "1700000000")

    def test_unsupported_build_reads_no_section(self):
        damage = StubDamage(taken=(1,))
        meter = dehulud.Meter(source=self.source, scan_interval=0, damage=damage)
        r = meter.poll(ALL)
        self.assertEqual((r.status, r.taken, r.dealt, damage.calls), ("Unsupported game version", None, None, []))


# ---- the Tk window, through a recording stand-in for tkinter --------------------------------------------

class FakeCanvas:
    def __init__(self, root, width, height, **kw):
        self.root, self.width, self.height, self.items, self.binds, self.next = root, width, height, {}, {}, 1

    def pack(self):
        pass

    def config(self, height):
        self.height = height

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def delete(self, what):
        assert what == "all"
        self.items.clear()

    def _new(self, kind, coords, kw):
        i, self.next = self.next, self.next + 1
        self.items[i] = dict(kw, kind=kind, coords=coords)
        return i

    def create_text(self, *coords, **kw):
        return self._new("text", coords, kw)

    def create_rectangle(self, *coords, **kw):
        return self._new("rect", coords, kw)

    def itemcget(self, i, k):
        return self.items[i].get(k, "")

    def texts(self):
        return [(it["coords"], it["text"], it["fill"]) for it in self.items.values() if it["kind"] == "text"]


class FakeRoot:
    def __init__(self):
        self.geometries, self.afters, self.destroyed = [], [], False

    def title(self, t=None):
        return "DeHulud"

    def geometry(self, g=None):
        if g is None:
            return "180x198+%d+%d" % self.pos
        self.geometries.append(g)
        if "+" in g:
            self.pos = tuple(int(v) for v in g.split("+")[1:3])

    def after(self, ms, fn):
        self.afters.append(fn)
        return len(self.afters)

    def winfo_screen(self):
        return "unix/:9"

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_pointerxy(self):
        return (0, 0)

    def destroy(self):
        self.destroyed = True

    def __getattr__(self, name):                 # resizable, protocol, withdraw, attributes, ...
        return lambda *a, **k: None


class FakeToplevel:
    """The overlay's Toplevel: records what Tk would do with it, in order."""

    def __init__(self, root):
        self.root, self.calls = root, []

    def winfo_id(self):
        return 0x1e00006                         # Tk's own window; the server holds it in 0x1e00007 (see FakeXShape)

    def __getattr__(self, name):                 # withdraw, deiconify, lift, overrideredirect, title, ...
        return lambda *a, **k: self.calls.append((name,) + a)


class FakeXShape:
    """Records the shapes set, in order: (window, kind, rects)."""

    def __init__(self):
        self.calls, self.closed, self.tree = [], False, {0x1e00006: 0x1e00007}

    def top_level(self, window):
        return self.tree.get(window, 0)

    def combine(self, window, kind, rects):
        self.calls.append((window, kind, [tuple(r) for r in rects]))

    def close(self):
        self.closed = True


class FakeTk:
    class TclError(Exception):
        pass

    def Tk(self, screenName=None):
        self.root = FakeRoot()
        return self.root

    def Toplevel(self, root):
        self.top = FakeToplevel(root)
        return self.top

    def Canvas(self, root, **kw):
        c = FakeCanvas(root, **kw)
        if isinstance(root, FakeToplevel):
            self.ocanvas = c                     # the overlay's canvas
        else:
            self.canvas = c
        return c

    def BooleanVar(self, value):
        return mock.Mock(get=lambda: value)

    def Menu(self, root, tearoff):
        return mock.Mock()


class Ev:
    def __init__(self, x, y, pos):
        self.x, self.y, self.x_root, self.y_root = x, y, pos[0] + x, pos[1] + y


class Meter:
    def __init__(self, readings=()):
        self.readings, self.asked, self.resets = list(readings), [], []

    def reset(self, feature):
        self.resets.append(feature)

    def poll(self, enabled):
        self.asked.append(enabled)
        return self.readings.pop(0) if self.readings else dehulud.Reading("on foot", 42, 0.425, taken=(), dealt=((), ()))


class TkWindow(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "dehulud", "config.json")
        self.xs = FakeXShape()
        for name, value in (("monitors", [(0, 0, 1920, 1080, True)]), ("xshape", self.xs)):
            patcher = mock.patch.object(dehulud, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def window(self, cfg=None, off=(), meter=None, shape=None):
        if cfg is not None:
            dehulud.save_config(self.path, dict(DEFAULTS, **cfg))
        tk = FakeTk()
        w = dehulud.Window(tk, meter or Meter(), self.path, display=":9", off=frozenset(off), shape=shape)
        return w, tk

    def saved(self):
        return dehulud.load_config(self.path)

    def click(self, w, x, y, move=(0, 0)):
        w._press(Ev(x, y, w.pos))
        if move != (0, 0):
            w._drag(Ev(x + move[0], y + move[1], w.pos))
        w._release(Ev(x + move[0], y + move[1], w.pos))

    def test_opens_at_the_height_of_the_config_and_flags(self):
        for combo, height in HEIGHTS.items():
            w, tk = self.window(dict(zip(dehulud.FEATURES, combo)))
            self.assertEqual((tk.canvas.height, tk.root.geometries[0].split("+")[0]),
                             (height, "180x%d" % height), combo)
        w, tk = self.window({}, off=["worm", DEALT])
        self.assertEqual(tk.canvas.height, 38)

    def test_click_on_a_switch_flips_it_saves_it_and_resizes(self):
        w, tk = self.window({"x": 100, "y": 200})
        self.click(w, 80, 9)                     # Taken
        self.assertEqual(w.enabled, frozenset(["worm", DEALT]))
        self.assertEqual(self.saved(), dict(DEFAULTS, x=100, y=200, damage_taken=False))
        self.assertEqual((tk.canvas.height, tk.root.geometries[-1]), (62, "180x62"))  # size only: corner kept
        self.assertEqual(w.pos, (100, 200))
        self.click(w, 10, 9)                     # Worm: header + status line
        self.assertEqual((tk.canvas.height, tk.root.geometries[-1]), (38, "180x38"))
        self.assertEqual(w.pos, (100, 200))
        self.click(w, 80, 9)
        self.click(w, 10, 9)
        self.assertEqual((self.saved()[TAKEN], tk.canvas.height), (True, 62))

    def test_all_off_is_header_only_and_reads_nothing(self):
        meter = Meter()
        w, tk = self.window({}, meter=meter)
        for x in (10, 80, 150):
            self.click(w, x, 9)
        self.assertEqual((w.enabled, tk.canvas.height), (frozenset(), 18))
        self.assertEqual([t[1] for t in tk.canvas.texts()], ["[ ] Worm", "[ ] Taken", "[ ] Dealt"])
        w.tick()
        self.assertEqual(meter.asked, [])

    def test_the_poll_gets_the_enabled_set(self):
        meter = Meter()
        w, tk = self.window({"worm": False}, meter=meter)
        w.tick()
        self.click(w, 150, 9)
        w.tick()
        self.assertEqual(meter.asked, [frozenset([TAKEN, DEALT]), frozenset([TAKEN])])

    def test_a_flag_is_not_saved_and_the_file_keeps_its_value(self):
        w, tk = self.window({"x": 1, "y": 2}, off=["worm"])
        self.assertNotIn("worm", w.enabled)
        self.click(w, 150, 9)                    # another switch: saved, worm keeps its saved value
        self.assertEqual(self.saved(), dict(DEFAULTS, x=1, y=2, damage_dealt=False))
        w.quit()
        self.assertEqual(self.saved(), dict(DEFAULTS, x=1, y=2, damage_dealt=False))
        w, tk = self.window(None, off=["worm"])  # the next run with the flag: off again, file still says on
        self.click(w, 10, 9)                     # the click on the flagged label is what gets saved
        self.assertIn("worm", w.enabled)
        self.assertTrue(self.saved()["worm"])
        w, tk = self.window({"worm": False}, off=["worm"])
        self.click(w, 10, 9)                     # off by flag and by file: the click switches it on
        self.assertEqual((self.saved()["worm"], tk.canvas.height), (True, 62))

    def test_drag_in_the_header_moves_and_flips_nothing(self):
        w, tk = self.window({"x": 100, "y": 200})
        self.click(w, 10, 9, move=(3, 0))
        self.assertEqual((w.enabled, w.pos), (ALL, (103, 200)))
        self.assertEqual(self.saved(), dict(DEFAULTS, x=103, y=200))
        self.click(w, 10, 9, move=(2, -2))       # under 3 px: a click
        self.assertNotIn("worm", w.enabled)
        self.assertEqual(w.pos, (103, 200))

    def test_a_drag_without_motion_events_is_still_a_drag(self):
        w, tk = self.window({"x": 100, "y": 200})
        w._press(Ev(10, 9, w.pos))
        w._release(Ev(10, 19, w.pos))
        self.assertEqual((w.enabled, w.pos), (ALL, (100, 210)))

    def test_a_press_below_the_header_drags_at_once_and_flips_nothing(self):
        w, tk = self.window({"x": 100, "y": 200})
        self.click(w, 10, 30)
        self.assertEqual(w.enabled, ALL)
        self.click(w, 10, 30, move=(1, 1))
        self.assertEqual(w.pos, (101, 201))

    def test_what_is_drawn(self):
        meter = Meter([dehulud.Reading("on foot", 42, 0.425, taken=(37,), dealt=((120,), (40,))),
                       dehulud.Reading("on foot", 42, 0.425, taken=(12,), dealt=((), ()))])
        w, tk = self.window({}, meter=meter)
        w.tick()
        w.tick()
        texts = tk.canvas.texts()
        self.assertEqual(texts, [((6, 9), "[x] Worm", "#d8cfb4"), ((60, 9), "[x] Taken", "#d8cfb4"),
                                 ((120, 9), "[x] Dealt", "#d8cfb4"), ((6, 30), "WORM", "#d8cfb4"),
                                 ((87, 30), "", "#b8c0c4"), ((174, 30), "42%", "#f0f0f0"),
                                 ((6, 50), "on foot", "#aab4b8")])   # no damage numbers in the box
        bar = [it for it in tk.canvas.items.values() if it["kind"] == "rect"]
        self.assertEqual(bar[0]["coords"], (44, 24, 130, 36))
        self.assertEqual(tk.canvas.itemcget(w.pct, "text"), "42%")
        # the overlay: the drawing list of its numbers, outlines first, then fills
        view = dehulud.Overlay()
        view.step(dehulud.Reading("on foot", taken=(37,), dealt=((120,), (40,))), ALL)
        view.step(dehulud.Reading("on foot", taken=(12,), dealt=((), ())), ALL)
        _, _, _, _, s, o = dehulud.overlay_geometry((0, 0, 1920, 1080))
        outlines, fills = dehulud.overlay_rects(view, s, o)
        drawn = [it["coords"] + (it["fill"],) for it in tk.ocanvas.items.values()]
        self.assertEqual(drawn, dehulud.overlay_canvas_items(outlines, fills))
        self.assertTrue(all(it["width"] == 0 and it["kind"] == "rect" for it in tk.ocanvas.items.values()))
        self.assertEqual(w.overlay_state(), {"geometry": [859, 270, 202, 102, 2, 1], "mapped": True,
                                             "outlines": [list(r) for r in outlines],
                                             "fills": [list(f) for f in fills]})

    def test_a_flipped_switch_clears_its_column_at_once(self):
        def numbers():
            return dehulud.Reading("on foot", 42, 0.425, taken=(37,), dealt=((120,), (40,)))
        meter = Meter([numbers(), numbers()])
        w, tk = self.window({}, meter=meter)
        w.tick()
        self.assertEqual((len(w.view.taken), len(w.view.dealt)), (1, 2))
        self.click(w, 80, 9)                     # Taken off and straight on again, no poll between
        self.click(w, 80, 9)
        self.assertEqual((len(w.view.taken), len(w.view.dealt), w.overlay_state()["mapped"]), (0, 2, True))
        self.click(w, 150, 9)
        self.assertEqual((w.view.empty(), w.overlay_state()["mapped"]), (True, False))   # unmapped at once
        self.click(w, 150, 9)
        w.tick()
        for x in (10, 80, 150):                  # all off: no polls at all ...
            self.click(w, x, 9)
        self.assertFalse(w.overlay_state()["mapped"])
        w.tick()
        for x in (10, 80, 150):                  # ... then on again: the old numbers do not come back
            self.click(w, x, 9)
        self.assertTrue(w.view.empty())
        self.assertEqual(len(meter.asked), 2)

    def test_overlay_window_shape_and_map_state(self):
        meter = Meter([dehulud.Reading("on foot", taken=(37,), dealt=((), ())),
                       dehulud.Reading("on foot", taken=(), dealt=((), ()))] +
                      [dehulud.Reading("on foot", taken=(), dealt=((), ()))] * 4 +
                      [dehulud.Reading("no permission")])
        w, tk = self.window({}, meter=meter)
        top, xid = tk.top, 0x1e00007
        # created unmapped, override-redirect, on top, titled, placed once; empty input and bounding shapes
        # (mapped once off every screen so that Tk creates the X window it maps, that window, the one on the root
        # holding Tk's own window, shaped, unmapped, then placed)
        self.assertEqual(top.calls, [("withdraw",), ("overrideredirect", True), ("title", dehulud.OVERLAY_TITLE),
                                     ("geometry", "202x102+-10202+-10102"), ("deiconify",), ("update_idletasks",),
                                     ("withdraw",), ("geometry", "202x102+859+270"), ("attributes", "-topmost", True)])
        self.assertEqual(self.xs.calls, [(xid, dehulud.SHAPE_INPUT, []), (xid, dehulud.SHAPE_BOUNDING, [])])
        self.assertEqual((tk.ocanvas.width, tk.ocanvas.height, tk.ocanvas.root), (202, 102, top))
        del top.calls[:], self.xs.calls[:]
        w.tick()                                 # a number: shaped, then mapped and raised
        outlines = [tuple(r) for r in w.overlay_state()["outlines"]]
        self.assertTrue(outlines)
        self.assertEqual(self.xs.calls, [(xid, dehulud.SHAPE_BOUNDING, outlines)])
        self.assertEqual(top.calls, [("deiconify",), ("lift",), ("attributes", "-topmost", True)])
        del top.calls[:], self.xs.calls[:]
        for _ in range(4):                       # ages 1..4: the same shape, only the colour fades
            w.tick()
        self.assertEqual((top.calls, self.xs.calls), ([], []))
        w.tick()                                 # removed on its fifth poll: unmapped, the server's shape empty
        self.assertEqual((top.calls, w.overlay_state()["mapped"]), ([("withdraw",)], False))
        self.assertEqual(self.xs.calls, [(xid, dehulud.SHAPE_BOUNDING, [])])
        w.tick()                                 # unreadable: still nothing
        self.assertEqual(top.calls, [("withdraw",)])
        w.quit()
        self.assertTrue(self.xs.closed)

    def test_without_shape_no_overlay_and_no_damage_reads(self):
        for shape, xs in ((False, self.xs), (None, None)):   # forced off, or no SHAPE on the server
            meter = Meter()
            err = io.StringIO()
            with mock.patch.object(dehulud, "xshape", return_value=xs) as loader, mock.patch("sys.stderr", err):
                w, tk = self.window({}, meter=meter, shape=shape)
                w.tick()
                self.click(w, 80, 9)             # the switches still flip and save
                w.tick()
            self.assertEqual(loader.called, shape is None)
            self.assertEqual(err.getvalue(), dehulud.NO_SHAPE + "\n")
            self.assertIsNone(w.overlay_state())
            self.assertFalse(hasattr(tk, "top"))
            self.assertEqual(meter.asked, [frozenset(["worm"]), frozenset(["worm"])])
            self.assertFalse(self.saved()[TAKEN])
            self.assertTrue(w.help_text().endswith("\n" + dehulud.NO_SHAPE))
            dehulud.save_config(self.path, DEFAULTS)
        meter = Meter([dehulud.Reading("no permission", detail="FIX: sudo sysctl")])
        with mock.patch("sys.stderr", io.StringIO()):
            w, tk = self.window({}, meter=meter, shape=False)
        w.tick()
        shown = []
        box = mock.Mock(showinfo=lambda title, message, **kw: shown.append(message))
        with mock.patch.dict("sys.modules", {"tkinter": mock.Mock(messagebox=box), "tkinter.messagebox": box}):
            w.show_help()
        self.assertEqual(shown, ["FIX: sudo sysctl\n" + dehulud.NO_SHAPE])
        w, tk = self.window({})
        self.assertNotIn(dehulud.NO_SHAPE, w.help_text())
        # the server knows no window for the overlay: no overlay (never a shape request for window 0)
        err = io.StringIO()
        self.xs.tree.clear()
        with mock.patch("sys.stderr", err):
            w, tk = self.window({})
        self.assertEqual((w.overlay_state(), err.getvalue(), self.xs.calls[-2:]),
                         (None, dehulud.NO_SHAPE + "\n", [(0x1e00007, dehulud.SHAPE_INPUT, []),
                                                          (0x1e00007, dehulud.SHAPE_BOUNDING, [])]))
        self.assertTrue(self.xs.closed and ("destroy",) in tk.top.calls)
        meter = Meter()
        w, tk = self.window({"worm": False}, meter=meter, shape=False)
        w.tick()                                 # only damage switches on, no overlay: nothing to read
        self.assertEqual(meter.asked, [frozenset()])

    def test_every_click_resets_the_readers_but_not_the_flags_at_startup(self):
        meter = Meter()
        w, tk = self.window({"damage_dealt": False}, off=["worm", TAKEN], meter=meter)
        self.assertEqual(meter.resets, [])               # flag and file state at startup: no reset
        w.tick()
        self.click(w, 80, 9)                             # Taken on (it was off by flag)
        self.click(w, 80, 9)                             # off and on again with no poll between
        self.click(w, 80, 9)
        self.click(w, 150, 9)
        self.click(w, 10, 9)
        self.assertEqual(meter.resets, [TAKEN, TAKEN, TAKEN, DEALT, "worm"])
        self.click(w, 10, 9, move=(5, 0))                # a drag flips nothing and resets nothing
        self.assertEqual(len(meter.resets), 5)

    def test_a_meter_without_reset_still_works(self):
        class Plain:
            def poll(self, enabled):
                return dehulud.Reading("on foot")
        w, tk = self.window({}, meter=Plain())
        self.click(w, 80, 9)
        self.assertNotIn(TAKEN, w.enabled)

    def test_worm_off_still_names_the_state(self):
        meter = Meter([dehulud.Reading("waiting for game")])
        w, tk = self.window({"worm": False}, meter=meter)
        w.tick()
        texts = [t[1] for t in tk.canvas.texts()]
        self.assertIn("waiting for game", texts)
        self.assertNotIn("WORM", texts)
        self.assertNotIn("-", texts)              # no damage numbers in the box, and never a '-' in the overlay


class OwnIdentity(unittest.TestCase):
    def test_help_texts_name_dehulud_combat(self):
        here = os.path.realpath(dehulud.__file__)
        self.assertEqual(dehulud.Meter.program, here)
        import dehulud as plain
        for scope in (1, 2):
            text = plain.permission_help(scope, False, dehulud.Meter.program)
            self.assertIn(here, text)                    # the launch option to put in Steam is this file's
            self.assertNotIn(os.path.realpath(plain.__file__) + " ", text)
        self.assertIn(here, plain.outside_launch_help(7, 1, dehulud.Meter.program))
        self.assertIsNone(plain.Meter.program)           # DeHulud's own texts name dehulud.py, as before

    def test_own_config_folder_and_title(self):
        self.assertEqual(dehulud.config_path({"HOME": "/h"}), "/h/.config/dehulud-combat/config.json")
        self.assertEqual(dehulud.config_path({"XDG_CONFIG_HOME": "/x"}), "/x/dehulud-combat/config.json")
        self.assertEqual(dehulud.APP, "DeHulud Combat")
        self.assertTrue(dehulud.__doc__.startswith("DeHulud Combat - "))


class XShapeLoader(unittest.TestCase):
    """The X SHAPE layer without an X server: what makes it give up, and the call it makes."""

    def test_no_overlay_without_a_local_display_library_or_symbol(self):
        with mock.patch("ctypes.CDLL") as cdll:
            for name in ("", "host:0", "localhost:10.0", "/tmp/.X11-unix/X0"):
                self.assertIsNone(dehulud.xshape(name))
            cdll.assert_not_called()             # decided before any library is loaded
            cdll.side_effect = OSError("libXext.so.6: cannot open shared object file")
            self.assertIsNone(dehulud.xshape(":0"))
            cdll.side_effect = None
            cdll.return_value = mock.Mock(spec=["XOpenDisplay", "XCloseDisplay", "XFlush"])  # no XShape* symbols
            self.assertIsNone(dehulud.xshape(":0"))

    def fake_libs(self, has_shape=True, version=(1, 1)):
        x11 = mock.Mock()
        x11.XOpenDisplay.return_value = 0x1234
        xext = mock.Mock()
        xext.XShapeQueryExtension.return_value = has_shape

        def query_version(dpy, major, minor):
            major._obj.value, minor._obj.value = version
            return True
        xext.XShapeQueryVersion.side_effect = query_version
        return x11, xext

    def test_opens_the_unix_socket_form_and_needs_shape_1_1(self):
        for has, version, ok in ((True, (1, 1), True), (False, (1, 1), False), (True, (1, 0), False)):
            x11, xext = self.fake_libs(has, version)
            with mock.patch("ctypes.CDLL", side_effect=[x11, xext]):
                xs = dehulud.xshape(":7.0")
            x11.XOpenDisplay.assert_called_once_with(b"unix/:7.0")
            self.assertEqual(xs is not None, ok)
            self.assertEqual(x11.XCloseDisplay.called, not ok)
        x11, xext = self.fake_libs()
        x11.XOpenDisplay.return_value = None     # the display cannot be opened
        with mock.patch("ctypes.CDLL", side_effect=[x11, xext]):
            self.assertIsNone(dehulud.xshape(":7"))

    def test_combine_sets_and_flushes(self):
        x11, xext = self.fake_libs()
        with mock.patch("ctypes.CDLL", side_effect=[x11, xext]):
            xs = dehulud.xshape(":7")
        xs.combine(0x1e00007, dehulud.SHAPE_BOUNDING, [(0, 0, 18, 6), (2, 4, 10, 3)])
        args = xext.XShapeCombineRectangles.call_args[0]
        self.assertEqual((args[0], args[1], args[2], args[3], args[4], args[6], args[7], args[8]),
                         (0x1234, 0x1e00007, 0, 0, 0, 2, 0, 0))   # ShapeBounding at (0, 0), ShapeSet, Unsorted
        self.assertEqual([(r.x, r.y, r.width, r.height) for r in args[5]], [(0, 0, 18, 6), (2, 4, 10, 3)])
        x11.XFlush.assert_called_with(0x1234)
        xs.combine(0x1e00007, dehulud.SHAPE_INPUT, [])
        self.assertEqual(xext.XShapeCombineRectangles.call_args[0][2:7:4], (2, 0))
        xs.close()
        xs.close()
        x11.XCloseDisplay.assert_called_once_with(0x1234)

    def test_top_level_is_the_window_on_the_root(self):
        x11, xext = self.fake_libs()
        with mock.patch("ctypes.CDLL", side_effect=[x11, xext]):
            xs = dehulud.xshape(":7")
        tree = {0x506: 0x507, 0x507: 0x100, 0x100: 0}           # Tk's window -> its wrapper -> the root

        def query_tree(dpy, window, root, parent, children, n):
            if window not in tree:
                return 0                                         # BadWindow is not asked for: unknown = 0
            root._obj.value, parent._obj.value = 0x100, tree[window]
            return 1
        x11.XQueryTree.side_effect = query_tree
        self.assertEqual([xs.top_level(w) for w in (0x506, 0x507, 0x999, 0)], [0x507, 0x507, 0, 0])
        self.assertEqual(x11.XQueryTree.call_count, 3)          # never asked about window 0

    def test_help_names_the_missing_shape_whatever_it_shows(self):
        doc = dehulud.__doc__
        self.assertEqual(dehulud.help_shown("", True), doc)
        self.assertEqual(dehulud.help_shown("FIX: sudo sysctl", True), "FIX: sudo sysctl")
        self.assertEqual(dehulud.help_shown("", False), doc.rstrip("\n") + "\n" + dehulud.NO_SHAPE)
        self.assertEqual(dehulud.help_shown("FIX: sudo sysctl", False), "FIX: sudo sysctl\n" + dehulud.NO_SHAPE)

    def test_canvas_items_outlines_first(self):
        self.assertEqual(dehulud.overlay_canvas_items([(0, 0, 4, 3), (1, 1, 2, 2)], [(1, 1, 2, 1, "#ff4d3d")]),
                         [(0, 0, 4, 3, "#0b0c0d"), (1, 1, 3, 3, "#0b0c0d"), (1, 1, 3, 2, "#ff4d3d")])


class MainPassesFlags(unittest.TestCase):
    def test_flags_reach_the_window(self):
        made = []

        class W:
            def __init__(self, *args):
                made.append(args)

            def run(self):
                pass

        with mock.patch.object(dehulud, "Window", W), mock.patch.object(dehulud, "_import_tk", return_value=FakeTk()), \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(dehulud.main(["--no-taken", "--no-worm"], meter_factory=lambda launched: None,
                                          config_file="/nonexistent/c.json"), 0)
        self.assertEqual(made[0][-1], frozenset(["worm", TAKEN]))

    def run_main(self, argv, display=""):
        polled = []

        class M:
            def __init__(self, launched):
                pass

            def poll(self, enabled):
                polled.append(enabled)
                raise KeyboardInterrupt

        err = io.StringIO()
        with mock.patch("sys.stderr", err), mock.patch("sys.stdout", io.StringIO()), \
                mock.patch.dict(os.environ, {"DISPLAY": display}):
            try:
                rc = dehulud.main(argv, meter_factory=M, config_file="/nonexistent/c.json")
            except SystemExit as e:
                rc = e.code
        return rc, polled, err.getvalue()

    def test_no_worm_in_text_mode_reads_nothing(self):
        msg = "dehulud-combat: text mode shows only the worm meter; drop --no-worm"
        rc, polled, err = self.run_main(["--text", "--no-worm"])
        self.assertEqual((rc, polled), (msg, []))         # a usage error (exit status 1), before any poll
        rc, polled, err = self.run_main(["--no-worm"])    # no display: the text fallback has nothing to show
        self.assertEqual((rc, polled), (1, []))
        self.assertTrue(err.endswith(msg + "\n"), err)
        rc, polled, err = self.run_main(["--text", "--no-worm", "--launch", "/bin/sh", "-c", "exit 3"])
        self.assertEqual((rc, polled), (3, []))           # the game ran, no meter did
        rc, polled, err = self.run_main(["--text", "--no-taken", "--launch", "/bin/sh", "-c", "exit 3"])
        self.assertEqual((rc, polled), (3, [frozenset(["worm"])]))

    def test_text_mode_reads_only_the_worm(self):
        asked = []

        class M:
            def poll(self, enabled):
                asked.append(enabled)
                raise KeyboardInterrupt

        dehulud.run_text(M(), out=io.StringIO(), err=io.StringIO())
        self.assertEqual(asked, [frozenset(["worm"])])


if __name__ == "__main__":
    unittest.main()
