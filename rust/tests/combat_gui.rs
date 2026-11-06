//! GUI smoke test of DeHulud Combat: the real window of the test build, but ONLY on an owned, private display.
//!
//! Like tests/test_gui.py of the Python version, it never uses $DISPLAY / $WAYLAND_DISPLAY of the session
//! running the tests: it starts its own headless compositor (`kwin_wayland --virtual --xwayland`) under a private
//! D-Bus session with private HOME and XDG folders, and runs the probe below inside it (this same test program,
//! started again by the compositor). The probe refuses any X display that existed before the compositor started,
//! drives the window with synthetic X events (to DeHulud's own windows only), reads its state back from the X
//! server and its pixels, and writes a JSON result that this test checks. Skipped when kwin_wayland, Xwayland or
//! dbus-run-session is missing.
#![cfg(feature = "test-source")]

mod common;

use common::*;
use dehulud::display::{self, LocalDisplay};
use dehulud::json::{self, Value, quote};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use x11rb::connection::Connection;
use x11rb::protocol::shape::{self, ConnectionExt as _};
use x11rb::protocol::xproto::{
    self, AtomEnum, ButtonPressEvent, ConnectionExt as _, EventMask, ImageFormat, KeyButMask, MotionNotifyEvent,
};
use x11rb::rust_connection::{DefaultStream, RustConnection};

fn which(tool: &str) -> bool {
    std::env::var_os("PATH").is_some_and(|p| std::env::split_paths(&p).any(|d| d.join(tool).is_file()))
}

#[test]
fn window_on_owned_display() {
    let missing: Vec<&str> =
        ["kwin_wayland", "Xwayland", "dbus-run-session"].into_iter().filter(|t| !which(t)).collect();
    if !missing.is_empty() {
        eprintln!("skipped: no owned display server available (missing: {})", missing.join(", "));
        return;
    }
    let tmp = TempDir::new("gui");
    let dirs: Vec<(&str, PathBuf)> =
        ["home", "run", "cfg", "data", "cache", "state"].iter().map(|k| (*k, tmp.path().join(k))).collect();
    for (_, d) in &dirs {
        fs::create_dir(d).unwrap();
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(d, fs::Permissions::from_mode(0o700)).unwrap();
    }
    let dir = |k: &str| dirs.iter().find(|d| d.0 == k).unwrap().1.clone();
    let mut before: Vec<String> = fs::read_dir("/tmp/.X11-unix")
        .map(|r| r.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect())
        .unwrap_or_default();
    before.sort();
    let result = tmp.path().join("result.json");
    let app = tmp.path().join("app.sh");
    let me = std::env::current_exe().unwrap();
    script(
        &app,
        &format!(
            "#!/bin/sh\nexec {} --ignored --exact probe_inside_owned_compositor --nocapture --test-threads=1 >{} 2>&1\n",
            dehulud::help::shell_quote(&me.to_string_lossy()),
            dehulud::help::shell_quote(&tmp.path().join("probe.log").to_string_lossy())
        ),
    );
    let log = fs::File::create(tmp.path().join("kwin.log")).unwrap();
    let mut kwin: Child = Command::new("dbus-run-session")
        .args([
            "--",
            "kwin_wayland",
            "--virtual",
            "--xwayland",
            "--no-lockscreen",
            "--no-global-shortcuts",
            "--no-kactivities",
        ])
        .args(["--socket", "dehulud-combat-rs-test", "--width", "1280", "--height", "800", "--exit-with-session"])
        .arg(&app)
        .env_clear()
        .env("PATH", std::env::var("PATH").unwrap_or_else(|_| "/usr/bin:/bin".into()))
        .env("LANG", "C.UTF-8")
        .env("HOME", dir("home"))
        .env("XDG_RUNTIME_DIR", dir("run"))
        .env("XDG_CONFIG_HOME", dir("cfg"))
        .env("XDG_DATA_HOME", dir("data"))
        .env("XDG_CACHE_HOME", dir("cache"))
        .env("XDG_STATE_HOME", dir("state"))
        .env("TMPDIR", tmp.path())
        .env("DEHULUD_GUI_RESULT", &result)
        .env("DEHULUD_GUI_BEFORE", if before.is_empty() { "-".to_string() } else { before.join(",") })
        .env("DEHULUD_GUI_BIN", combat_bin())
        .env("DEHULUD_GUI_DIR", tmp.path())
        .stdin(Stdio::null())
        .stdout(log.try_clone().unwrap())
        .stderr(log)
        .spawn()
        .expect("dbus-run-session");
    let deadline = Instant::now() + Duration::from_secs(120);
    while kwin.try_wait().unwrap().is_none() {
        if Instant::now() > deadline {
            let _ = kwin.kill(); // our own child, stuck
            let _ = kwin.wait();
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    let tail = |name: &str| {
        let t = fs::read_to_string(tmp.path().join(name)).unwrap_or_default();
        t.chars().rev().take(3000).collect::<Vec<_>>().into_iter().rev().collect::<String>()
    };
    let Ok(text) = fs::read_to_string(&result) else {
        panic!("probe produced no result\n{}\n{}", tail("probe.log"), tail("kwin.log"));
    };
    if let Some(keep) = std::env::var_os("DEHULUD_GUI_KEEP") {
        // a developer's copy of the result and the window images
        let keep = PathBuf::from(keep);
        let _ = fs::create_dir_all(&keep);
        for e in fs::read_dir(tmp.path()).unwrap().flatten() {
            if e.path().is_file() {
                let _ = fs::copy(e.path(), keep.join(e.file_name()));
            }
        }
    }
    let r = json::parse(&text).unwrap();
    let get = |k: &str| r.get(k).unwrap_or_else(|| panic!("{k} missing in {text}\n{}", tail("probe.log"))).clone();
    let s = |v: &Value| match v {
        Value::Str(s) => s.clone(),
        o => panic!("{o:?}"),
    };
    let b = |v: Value| v == Value::Bool(true);
    let ints = |v: Value| match v {
        Value::Array(a) => a
            .iter()
            .map(|x| match x {
                Value::Int(Some(n)) => *n,
                o => panic!("{o:?}"),
            })
            .collect::<Vec<i64>>(),
        o => panic!("{o:?}"),
    };
    assert!(r.get("refused").is_none(), "{text}");
    let failures = match get("failures") {
        Value::Array(a) => a.iter().map(s).collect::<Vec<_>>(),
        o => panic!("{o:?}"),
    };
    assert_eq!(failures, Vec::<String>::new(), "{}", tail("probe.log"));
    assert!(s(&get("socket")).starts_with("/tmp/.X11-unix/X") || s(&get("socket")).starts_with("@/tmp/.X11-unix/X"));
    assert!(b(get("unix_sockets_only")));
    assert_eq!(s(&get("title")), "DeHulud Combat");
    assert!(b(get("above")), "_NET_WM_STATE_ABOVE");
    assert!(b(get("frameless")), "override-redirect");
    assert_eq!(ints(get("size")), [180, 62], "header, worm meter and status line by default");
    assert_eq!(ints(get("position")), [1280 - 180 - 24, 48], "top-right of the primary monitor");
    let shown = match get("shown") {
        Value::Array(a) => a
            .iter()
            .map(|v| match v {
                Value::Array(x) => x.iter().map(s).collect::<Vec<_>>(),
                o => panic!("{o:?}"),
            })
            .collect::<Vec<_>>(),
        o => panic!("{o:?}"),
    };
    assert_eq!(shown[0], ["42%", "on foot", "#c7df7a", ""]);
    assert_eq!(shown[1], ["-", "Unsupported game version", "#85969d", "PE 1700000000"]);
    assert_eq!(shown[2], ["100%", "vehicle", "#ee7868", ""]);
    assert_eq!(shown[3], ["-", "no permission", "#85969d", "right-click"]);
    assert!(b(get("lone_release_ignored")), "a release without a press chose a menu entry");
    assert_eq!(ints(get("size_without_taken")), [180, 62]);
    assert_eq!(ints(get("size_worm_only_off")), [180, 38]);
    assert_eq!(ints(get("size_all_off")), [180, 18]);
    assert_eq!(ints(get("size_all_on_again")), [180, 62]);
    assert!(s(&get("after_click")).contains("\"damage_taken\": false"), "the click is saved");
    assert!(b(get("corner_kept")), "the window keeps its top-left corner when it grows and shrinks");
    assert!(b(get("all_off_reads_nothing")), "a poll while every section was off");
    assert!(b(get("header_drag_flips_nothing")));
    assert_eq!(s(&get("help")), "FIX: sudo sysctl");
    assert!(b(get("help_window_mapped")));
    assert_eq!(
        s(&get("after_drag")),
        "{\"x\": 130, \"y\": 70, \"frame\": false, \"worm\": true, \"damage_taken\": true, \"damage_dealt\": true}"
    );
    assert_eq!(ints(get("dragged_to")), [130, 70]);
    assert!(s(&get("after_frame")).contains("\"frame\": true,"));
    assert!(b(get("framed_is_managed")), "a window manager frame around the framed window");
    assert_eq!(
        s(&get("after_reset")),
        "{\"x\": null, \"y\": null, \"frame\": true, \"worm\": true, \"damage_taken\": true, \"damage_dealt\": true}"
    );
    assert!(b(get("quit_exit_0")));
    // the damage overlay: a shaped, unmanaged window, placed once on the primary monitor (1280 x 800: s = 1)
    assert_eq!(s(&get("overlay_title")), "DeHulud Combat damage");
    assert!(b(get("overlay_override_redirect")));
    assert_eq!(ints(get("overlay_geometry")), [589, 200, 102, 52, 1, 1]);
    assert_eq!(ints(get("overlay_position")), [589, 200]);
    assert!(b(get("overlay_destroyed_on_quit")));
    // no SHAPE (test hook): one stderr line, no overlay, the damage features are not read
    assert!(b(get("no_shape_line_once")), "{}", s(&get("no_shape_stderr")));
    assert!(b(get("no_shape_no_overlay")));
    assert!(b(get("no_shape_reads_worm_only")));
    assert!(b(get("no_shape_help")));
    // the framed window's position is saved as its frame's top-left: reopening puts it at the same place
    assert_eq!(
        s(&get("after_quit")),
        "{\"x\": 1076, \"y\": 48, \"frame\": true, \"worm\": true, \"damage_taken\": true, \"damage_dealt\": true}"
    );
}

// ---- the probe: runs inside the private compositor ------------------------------------------------------

struct Probe {
    conn: RustConnection<DefaultStream>,
    root: u32,
    trace: PathBuf,
    ctl: PathBuf,
    control: Vec<String>,
    failures: Vec<String>,
    out: Vec<(String, String)>,
    dir: PathBuf,
}

impl Probe {
    fn check(&mut self, ok: bool, what: String) {
        if !ok {
            eprintln!("FAILED: {what}");
            self.failures.push(what);
        }
    }
    fn put(&mut self, k: &str, json_value: String) {
        self.out.push((k.into(), json_value));
    }
    fn set(&mut self, line: &str) {
        self.control.push(line.into());
        let tmp = self.ctl.with_extension("tmp");
        fs::write(&tmp, self.control.join("\n") + "\n").unwrap();
        fs::rename(tmp, &self.ctl).unwrap();
    }
    fn events(&self) -> Vec<Value> {
        fs::read_to_string(&self.trace).unwrap_or_default().lines().filter_map(|l| json::parse(l).ok()).collect()
    }
    /// The first traced window event after `skip` events that matches.
    fn wait(&self, what: &str, skip: usize, pred: impl Fn(&Value) -> bool) -> Value {
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Some(v) = self.events().into_iter().skip(skip).find(|v| v.get("window").is_some() && pred(v)) {
                return v;
            }
            assert!(Instant::now() < deadline, "no window event with {what}");
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    fn n(&self) -> usize {
        self.events().len()
    }
    fn send(&self, win: u32, kind: &str, button: u8, root: (i16, i16), at: (i16, i16)) {
        let (response_type, mask) = match kind {
            "press" => (xproto::BUTTON_PRESS_EVENT, EventMask::BUTTON_PRESS),
            "release" => (xproto::BUTTON_RELEASE_EVENT, EventMask::BUTTON_RELEASE),
            _ => unreachable!(),
        };
        let ev = ButtonPressEvent {
            response_type,
            detail: button,
            sequence: 0,
            time: 0,
            root: self.root,
            event: win,
            child: x11rb::NONE,
            root_x: root.0,
            root_y: root.1,
            event_x: at.0,
            event_y: at.1,
            state: KeyButMask::default(),
            same_screen: true,
        };
        self.conn.send_event(false, win, mask, ev).unwrap();
        self.conn.flush().unwrap();
    }
    fn motion(&self, win: u32, root: (i16, i16), at: (i16, i16)) {
        let ev = MotionNotifyEvent {
            response_type: xproto::MOTION_NOTIFY_EVENT,
            detail: xproto::Motion::NORMAL,
            sequence: 0,
            time: 0,
            root: self.root,
            event: win,
            child: x11rb::NONE,
            root_x: root.0,
            root_y: root.1,
            event_x: at.0,
            event_y: at.1,
            state: KeyButMask::BUTTON1,
            same_screen: true,
        };
        self.conn.send_event(false, win, EventMask::POINTER_MOTION, ev).unwrap();
        self.conn.flush().unwrap();
    }
    fn title(&self, win: u32) -> String {
        let r =
            self.conn.get_property(false, win, AtomEnum::WM_NAME, AtomEnum::STRING, 0, 64).unwrap().reply().unwrap();
        String::from_utf8_lossy(&r.value).into_owned()
    }
    fn atom(&self, name: &str) -> u32 {
        self.conn.intern_atom(false, name.as_bytes()).unwrap().reply().unwrap().atom
    }
    fn above(&self, win: u32) -> bool {
        let state = self.atom("_NET_WM_STATE");
        let above = self.atom("_NET_WM_STATE_ABOVE");
        let r = self.conn.get_property(false, win, state, AtomEnum::ATOM, 0, 32).unwrap().reply().unwrap();
        r.value32().is_some_and(|mut v| v.any(|a| a == above))
    }
    fn root_pos(&self, win: u32) -> (i64, i64) {
        let t = self.conn.translate_coordinates(win, self.root, 0, 0).unwrap().reply().unwrap();
        (i64::from(t.dst_x), i64::from(t.dst_y))
    }
    fn managed(&self, win: u32) -> bool {
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            let t = self.conn.query_tree(win).unwrap().reply().unwrap();
            if t.parent != t.root {
                return true;
            }
            if Instant::now() > deadline {
                return false;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
    }
    /// Opens the menu with a right-click on `win` and activates the entry `label`.
    fn menu(&self, win: u32, label: &str) {
        let (menu, at, root) = self.open_menu(win, label);
        self.send(menu, "press", 1, root, at);
        self.send(menu, "release", 1, root, at);
    }
    /// Opens the menu with a right-click on `win`: the menu window, and the point of entry `label` in it and on
    /// the root window.
    fn open_menu(&self, win: u32, label: &str) -> (u32, (i16, i16), (i16, i16)) {
        let (x, y) = self.root_pos(win);
        let n = self.n();
        let root = ((x + 60) as i16, (y + 30) as i16);
        self.send(win, "press", 3, root, (60, 30));
        self.send(win, "release", 3, root, (60, 30));
        let ev = self.wait("an open menu", n, |v| v.get("menu").is_some_and(|m| *m != Value::Null));
        let Some(Value::Int(Some(menu))) = ev.get("menu") else { unreachable!() };
        let menu = *menu as u32;
        let Some(Value::Array(items)) = ev.get("items") else { unreachable!() };
        let row = items
            .iter()
            .find_map(|it| match it {
                Value::Array(a) if a[0] == Value::Str(label.into()) => Some(a.clone()),
                _ => None,
            })
            .expect("menu entry");
        let (Value::Int(Some(y0)), Value::Int(Some(y1))) = (&row[1], &row[2]) else { unreachable!() };
        let at = (20i16, ((y0 + y1) / 2) as i16);
        let (mx, my) = self.root_pos(menu);
        std::thread::sleep(Duration::from_millis(100));
        self.keep(menu, &format!("menu-{}.ppm", label.split(' ').next().unwrap()));
        (menu, at, ((mx + 20) as i16, (my + i64::from(at.1)) as i16))
    }
    /// Our top-level window titled `title`, if there is one.
    fn find(&self, title: &str) -> Option<u32> {
        let t = self.conn.query_tree(self.root).unwrap().reply().unwrap();
        t.children.into_iter().find(|w| self.title(*w) == title)
    }
    fn viewable(&self, win: u32) -> bool {
        self.conn.get_window_attributes(win).unwrap().reply().unwrap().map_state == xproto::MapState::VIEWABLE
    }
    /// The pixels covered by a window's shape of kind `kind`, as a w x h bitmap.
    fn shape_bits(&self, win: u32, kind: shape::SK, w: usize, h: usize) -> (usize, Vec<bool>) {
        let r = self.conn.shape_get_rectangles(win, kind).unwrap().reply().unwrap();
        let rects: Vec<(i64, i64, i64, i64)> = r
            .rectangles
            .iter()
            .map(|r| (i64::from(r.x), i64::from(r.y), i64::from(r.width), i64::from(r.height)))
            .collect();
        (rects.len(), cover(&rects, w, h))
    }
    fn config(&self) -> String {
        fs::read_to_string(self.dir.join("cfg").join("dehulud-combat").join("config.json")).unwrap_or_default()
    }
    /// The window's pixels as 0xRRGGBB (32 bits per pixel, the usual 24-bit TrueColor layout).
    fn pixels(&self, win: u32) -> Vec<u32> {
        self.image(win).2
    }
    fn image(&self, win: u32) -> (u16, u16, Vec<u32>) {
        let g = self.conn.get_geometry(win).unwrap().reply().unwrap();
        let img =
            self.conn.get_image(ImageFormat::Z_PIXMAP, win, 0, 0, g.width, g.height, !0).unwrap().reply().unwrap();
        assert_eq!(img.data.len(), usize::from(g.width) * usize::from(g.height) * 4, "32 bits per pixel");
        (
            g.width,
            g.height,
            img.data.chunks(4).map(|p| u32::from_le_bytes([p[0], p[1], p[2], p[3]]) & 0xffffff).collect(),
        )
    }
    /// Keeps a picture of one of DeHulud's windows (for a developer; see DEHULUD_GUI_KEEP).
    fn keep(&self, win: u32, name: &str) {
        let (w, h, px) = self.image(win);
        save_ppm_sized(&self.dir.join(name), w, h, &px);
    }
}

fn save_ppm(path: &Path, px: &[u32]) {
    save_ppm_sized(path, 180, (px.len() / 180) as u16, px);
}

fn save_ppm_sized(path: &Path, w: u16, h: u16, px: &[u32]) {
    let mut data = format!("P6\n{w} {h}\n255\n").into_bytes();
    for p in px {
        data.extend_from_slice(&[(p >> 16) as u8, (p >> 8) as u8, *p as u8]);
    }
    fs::write(path, data).unwrap();
}

/// A union of rectangles as a w x h bitmap (what is outside the window is dropped).
fn cover(rects: &[(i64, i64, i64, i64)], w: usize, h: usize) -> Vec<bool> {
    let mut bits = vec![false; w * h];
    for (x, y, rw, rh) in rects {
        for yy in (*y).max(0)..(y + rh).min(h as i64) {
            for xx in (*x).max(0)..(x + rw).min(w as i64) {
                bits[yy as usize * w + xx as usize] = true;
            }
        }
    }
    bits
}

/// The traced overlay of an event: (mapped, outlines, fills as (x, y, w, h, colour)).
#[allow(clippy::type_complexity)]
fn traced_overlay(v: &Value) -> Option<(bool, Vec<(i64, i64, i64, i64)>, Vec<(i64, i64, i64, i64, String)>)> {
    let o = v.get("overlay")?;
    let int = |v: &Value| match v {
        Value::Int(Some(n)) => *n,
        o => panic!("{o:?}"),
    };
    let arr = |v: Option<&Value>| match v {
        Some(Value::Array(a)) => a.clone(),
        o => panic!("{o:?}"),
    };
    let outlines = arr(o.get("outlines"))
        .iter()
        .map(|r| {
            let r = arr(Some(r));
            (int(&r[0]), int(&r[1]), int(&r[2]), int(&r[3]))
        })
        .collect();
    let fills = arr(o.get("fills"))
        .iter()
        .map(|r| {
            let r = arr(Some(r));
            let Value::Str(c) = &r[4] else { panic!("{r:?}") };
            (int(&r[0]), int(&r[1]), int(&r[2]), int(&r[3]), c.clone())
        })
        .collect();
    Some((o.get("mapped") == Some(&Value::Bool(true)), outlines, fills))
}

const OV_TAKEN: [&str; 5] = ["#ff4d3d", "#ff4d3d", "#b63a2f", "#792923", "#3c1917"];
const OV_HEALTH: [&str; 5] = ["#3d9bff", "#3d9bff", "#2e70b6", "#224c7a", "#15293d"];
const OV_SHIELD: [&str; 5] = ["#9cd2ff", "#9cd2ff", "#7197b6", "#4c657a", "#28343d"];

/// Whether the traced overlay of an event has fills of any of `colours`.
fn has_fill(v: &Value, colours: &[&str]) -> bool {
    traced_overlay(v).is_some_and(|(_, _, f)| f.iter().any(|f| colours.contains(&f.4.as_str())))
}

/// (count, min x, max x, min y, max y) of the pixels of one colour.
fn ink(px: &[u32], rgb: u32) -> (usize, i64, i64, i64, i64) {
    ink_in(px, &[rgb], 0, i64::MAX)
}

/// The same for the pixels of any of `rgbs` in the rows y0..y1.
fn ink_in(px: &[u32], rgbs: &[u32], y0: i64, y1: i64) -> (usize, i64, i64, i64, i64) {
    let mut r = (0, i64::MAX, i64::MIN, i64::MAX, i64::MIN);
    for (i, p) in px.iter().enumerate() {
        if rgbs.contains(p) && (y0..y1).contains(&((i / 180) as i64)) {
            let (x, y) = ((i % 180) as i64, (i / 180) as i64);
            r = (r.0 + 1, r.1.min(x), r.2.max(x), r.3.min(y), r.4.max(y));
        }
    }
    r
}

/// The socket inodes of a process (our own child) and whether each is a Unix socket and none an IP socket.
fn unix_sockets_only(pid: u32) -> (bool, usize) {
    let mut inodes = Vec::new();
    for e in fs::read_dir(format!("/proc/{pid}/fd")).unwrap().flatten() {
        if let Ok(target) = fs::read_link(e.path()) {
            let t = target.to_string_lossy().into_owned();
            if let Some(ino) = t.strip_prefix("socket:[").and_then(|r| r.strip_suffix(']')) {
                inodes.push(ino.to_string());
            }
        }
    }
    let table = |name: &str| fs::read_to_string(format!("/proc/{pid}/net/{name}")).unwrap_or_default();
    let has = |text: &str, ino: &str| text.lines().skip(1).any(|l| l.split_whitespace().any(|w| w == ino));
    let unix = table("unix");
    let ip: String = ["tcp", "tcp6", "udp", "udp6", "raw", "raw6"].iter().map(|n| table(n)).collect();
    let ok = !inodes.is_empty() && inodes.iter().all(|i| has(&unix, i) && !has(&ip, i));
    (ok, inodes.len())
}

#[test]
#[ignore = "runs only inside the private compositor started by window_on_owned_display"]
fn probe_inside_owned_compositor() {
    let result = PathBuf::from(std::env::var_os("DEHULUD_GUI_RESULT").expect("started by window_on_owned_display"));
    let before = std::env::var("DEHULUD_GUI_BEFORE").unwrap_or_default();
    let display_name = std::env::var("DISPLAY").unwrap_or_default();
    let number =
        display_name.strip_prefix(':').map(|r| r.split('.').next().unwrap_or("").to_string()).unwrap_or_default();
    if number.is_empty() || before.split(',').any(|x| x == format!("X{number}")) {
        // never the session's own display
        fs::write(&result, format!("{{\"refused\": {}}}", quote(&display_name))).unwrap();
        return;
    }
    let dir = PathBuf::from(std::env::var_os("DEHULUD_GUI_DIR").unwrap());
    let bin = PathBuf::from(std::env::var_os("DEHULUD_GUI_BIN").unwrap());
    let d = LocalDisplay::parse(&display_name).expect("a local display");
    let c = display::connect(&d).expect("the private display");
    let root = c.conn.setup().roots[c.screen].root;
    let ctl = dir.join("control");
    let trace = dir.join("trace.jsonl");
    let mut p = Probe {
        conn: c.conn,
        root,
        trace: trace.clone(),
        ctl: ctl.clone(),
        control: vec![],
        failures: vec![],
        out: vec![],
        dir: dir.clone(),
    };
    for line in [
        "poll_ms=40".to_string(),
        format!("trace={}", trace.display()),
        "reading=on foot|42|0.425|||37|120/40".into(),
        "reading=Unsupported game version|-|-|PE 1700000000|PE timestamp 1700000000|-|-".into(),
        "reading=vehicle|100|1.0|||-|84/".into(),
        "reading=no permission|-|-|right-click|FIX: sudo sysctl|-|-".into(),
        "step=0".into(),
    ] {
        p.set(&line);
    }
    let mut child = Command::new(&bin)
        .env_clear()
        .env("PATH", std::env::var("PATH").unwrap_or_default())
        .env("HOME", dir.join("home"))
        .env("XDG_CONFIG_HOME", dir.join("cfg"))
        .env("DISPLAY", &display_name)
        .env("XAUTHORITY", std::env::var("XAUTHORITY").unwrap_or_default())
        .env("DEHULUD_TEST_SOURCE", &ctl)
        .stdout(fs::File::create(dir.join("dehulud.out")).unwrap())
        .stderr(fs::File::create(dir.join("dehulud.err")).unwrap())
        .spawn()
        .unwrap();
    let first = p.wait("the window", 0, |v| matches!(v.get("window"), Some(Value::Int(Some(w))) if *w != 0));
    let Some(Value::Int(Some(win))) = first.get("window") else { unreachable!() };
    let win = *win as u32;
    let socket = match first.get("socket") {
        Some(Value::Str(s)) => s.clone(),
        _ => String::new(),
    };
    p.put("socket", quote(&socket));
    let (only_unix, n) = unix_sockets_only(child.id());
    p.put("unix_sockets_only", only_unix.to_string());
    eprintln!("sockets of DeHulud: {n}, all Unix: {only_unix}");

    // the window as the X server sees it
    p.put("title", quote(&p.title(win)));
    p.put("above", p.above(win).to_string());
    let attrs = p.conn.get_window_attributes(win).unwrap().reply().unwrap();
    p.put("frameless", attrs.override_redirect.to_string());
    let g = p.conn.get_geometry(win).unwrap().reply().unwrap();
    p.put("size", format!("[{}, {}]", g.width, g.height));
    let pos = p.root_pos(win);
    p.put("position", format!("[{}, {}]", pos.0, pos.1));

    // the overlay window: there from the start, unmapped while there is nothing to show
    let overlay = p.find("DeHulud Combat damage");
    p.put("overlay_title", quote(&overlay.map_or(String::new(), |w| p.title(w))));
    let overlay = overlay.unwrap_or(0);
    let oattrs = p.conn.get_window_attributes(overlay).unwrap().reply().unwrap();
    p.put("overlay_override_redirect", oattrs.override_redirect.to_string());
    let geo = match first.get("overlay") {
        Some(Value::Object(_)) => {
            let Some(Value::Array(g)) = first.get("overlay").unwrap().get("geometry") else { unreachable!() };
            g.iter().map(|v| if let Value::Int(Some(n)) = v { *n } else { -1 }).collect::<Vec<i64>>()
        }
        o => panic!("overlay in the trace: {o:?}"),
    };
    p.put("overlay_geometry", format!("[{}]", geo.iter().map(i64::to_string).collect::<Vec<_>>().join(", ")));
    let opos = p.root_pos(overlay);
    p.put("overlay_position", format!("[{}, {}]", opos.0, opos.1));
    let og = p.conn.get_geometry(overlay).unwrap().reply().unwrap();
    p.check((i64::from(og.width), i64::from(og.height)) == (geo[2], geo[3]), format!("overlay size {og:?}"));
    let (ow, oh) = (geo[2] as usize, geo[3] as usize);
    let (n_input, input) = p.shape_bits(overlay, shape::SK::INPUT, ow, oh);
    p.check(n_input == 0 && !input.contains(&true), format!("overlay input shape is empty: {n_input} rectangles"));

    // four readings: what is shown, and where its pixels are. All on: header 0..18, worm 18..42, status 42..62.
    let mut shown = Vec::new();
    let statuses = ["on foot", "Unsupported game version", "vehicle", "no permission"];
    for (step, status) in statuses.iter().enumerate() {
        let n = p.n();
        p.set(&format!("step={step}"));
        let ev = p.wait(
            status,
            n,
            |v| matches!(v.get("shown"), Some(Value::Array(a)) if a[1] == Value::Str((*status).into())),
        );
        // the overlay: its bounding shape is the traced outline list, the server's map state the traced one,
        // and its numbers are drawn in their colours
        // (checked at the step's first tick: at 40 ms per poll its numbers are gone after about 200 ms)
        let (mapped, outlines, fills) = traced_overlay(&ev).expect("an overlay in the trace");
        let want_mapped = step == 0 || step == 2;
        p.check(mapped == want_mapped && p.viewable(overlay) == want_mapped, format!("step {step}: overlay mapped"));
        if mapped {
            let (_, bits) = p.shape_bits(overlay, shape::SK::BOUNDING, ow, oh);
            p.check(bits == cover(&outlines, ow, oh), format!("step {step}: bounding shape = the outline list"));
            // the numbers age while the probe looks: compare colour families (taken, health, shield), any age
            let family = |c: &str| {
                [("taken", OV_TAKEN), ("health", OV_HEALTH), ("shield", OV_SHIELD)]
                    .iter()
                    .find(|(_, f)| f.contains(&c))
                    .map_or("?", |f| f.0)
            };
            let mut got: Vec<&str> = fills.iter().map(|f| family(&f.4)).collect();
            got.dedup();
            let want: &[&str] = if step == 0 { &["taken", "health", "shield"] } else { &["health"] };
            p.check(got == want, format!("step {step}: overlay columns {got:?}"));
            let (iw, _, opx) = p.image(overlay);
            let at = |x: i64, y: i64| opx[y as usize * usize::from(iw) + x as usize];
            // fills in their colour family; the rest of the shape (the outlines around them) in the outline colour
            let filled = cover(&fills.iter().map(|f| (f.0, f.1, f.2, f.3)).collect::<Vec<_>>(), ow, oh);
            let shaped = cover(&outlines, ow, oh);
            let ok = fills.iter().all(|(x, y, _, _, c)| family(&format!("#{:06x}", at(*x, *y))) == family(c))
                && (0..ow * oh).all(|k| !shaped[k] || filled[k] || opx[k] == 0x0b0c0d);
            p.check(ok, format!("step {step}: overlay pixels"));
            p.keep(overlay, &format!("overlay-{step}.ppm"));
        } else {
            let (_, bits) = p.shape_bits(overlay, shape::SK::BOUNDING, ow, oh);
            p.check(!bits.contains(&true), format!("step {step}: unmapped, bounding shape empty"));
        }
        p.wait("one more tick", p.n(), |_| true);
        let Some(Value::Array(sh)) = ev.get("shown") else { unreachable!() };
        let sh: Vec<String> = sh
            .iter()
            .map(|v| match v {
                Value::Str(s) => quote(s),
                _ => "null".into(),
            })
            .collect();
        shown.push(format!("[{}]", sh.join(", ")));
        let px = p.pixels(win);
        save_ppm(&dir.join(format!("window-{step}.ppm")), &px);
        let (pct, hint, status_ink) = (ink(&px, 0xf0f0f0), ink(&px, 0xb8c0c4), ink(&px, 0xaab4b8));
        p.check(
            pct.0 > 0 && pct.1 >= 131 && pct.2 < 180 && pct.3 >= 18 + 7 && pct.4 < 18 + 18,
            format!("step {step}: the percent never covers the bar: {pct:?}"),
        );
        p.check(
            status_ink.0 > 0 && status_ink.3 >= 42 && status_ink.4 < 62,
            format!("step {step}: status line {status_ink:?}"),
        );
        let header = ink_in(&px, &[0xd8cfb4], 0, 18);
        p.check(
            header.0 > 0 && header.1 >= 6 && header.1 <= 7 && header.2 <= 173 && header.3 >= 6,
            format!("step {step}: header {header:?}"),
        );
        let worm = ink_in(&px, &[0xd8cfb4], 18, 42);
        p.check(worm.0 > 0 && worm.1 == 6 && worm.2 < 44, format!("step {step}: WORM {worm:?}"));
        p.check(px.len() == 180 * 62, format!("step {step}: the box is 62 px high ({} px)", px.len() / 180));
        let want_hint = step == 1 || step == 3;
        p.check((hint.0 > 0) == want_hint, format!("step {step}: hint shown {hint:?}"));
        if want_hint {
            p.check(hint.1 > 44 && hint.2 < 130 && hint.3 >= 18, format!("step {step}: hint inside the bar {hint:?}"));
        }
        let bar = [0xc7df7a, 0x2a2c2e, 0xee7868, 0x2a2c2e][step];
        let at = |x: usize, y: usize| px[y * 180 + x];
        p.check(at(45, 25) == bar, format!("step {step}: bar pixel {:06x}", at(45, 25)));
        if step == 0 {
            p.check(at(79, 25) == 0xc7df7a && at(81, 25) != 0xc7df7a, "42 % fills 36 of 86 bar pixels".into());
        }
        if step == 2 {
            p.check(at(129, 35) == 0xee7868, "100 % fills the whole bar".into());
        }
    }
    p.put("shown", format!("[{}]", shown.join(", ")));
    // the -37 of step 0 as traced poll by poll: full colour for two polls, three dim steps, gone on the fifth
    let n0 = p.n();
    p.set("step=0"); // a new step: its numbers are emitted once, on its first poll
    let ticks =
        |p: &Probe| p.events().iter().skip(n0).filter(|v| v.get("event") == Some(&Value::Str("tick".into()))).count();
    let deadline = Instant::now() + Duration::from_secs(10);
    while ticks(&p) < 10 && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    let mut ages: Vec<String> = Vec::new();
    for v in p.events().into_iter().skip(n0) {
        if v.get("event") != Some(&Value::Str("tick".into())) {
            continue;
        }
        let Some((_, _, fills)) = traced_overlay(&v) else { continue };
        let c = fills.iter().find(|f| OV_TAKEN.contains(&f.4.as_str())).map(|f| f.4.clone());
        let c = c.unwrap_or_else(|| "gone".into());
        if ages.last() != Some(&c) || c != "gone" {
            ages.push(c);
        }
        if ages.last().map(String::as_str) == Some("gone") && ages.len() > 1 {
            break;
        }
    }
    let ages: Vec<&str> = ages.iter().map(String::as_str).skip_while(|c| *c == "gone").collect();
    p.check(
        ages == ["#ff4d3d", "#ff4d3d", "#b63a2f", "#792923", "#3c1917", "gone"],
        format!("fade of -37 by poll: {ages:?}"),
    );
    let (_, bits) = p.shape_bits(overlay, shape::SK::BOUNDING, ow, oh);
    p.check(!p.viewable(overlay) && !bits.contains(&true), "expired: unmapped, bounding shape empty".into());
    let n = p.n();
    p.set("step=3"); // back to the reading with a detail for Help / details
    p.wait(
        "no permission",
        n,
        |v| matches!(v.get("shown"), Some(Value::Array(a)) if a[1] == Value::Str("no permission".into())),
    );

    // a button release alone (as of the right-click that opened the menu) never chooses an entry, even Quit
    let (menu, at, root_at) = p.open_menu(win, "Quit");
    p.send(menu, "release", 3, root_at, at);
    std::thread::sleep(Duration::from_millis(300));
    let alive = child.try_wait().unwrap().is_none();
    p.put("lone_release_ignored", alive.to_string());
    let n = p.n();
    let (x0, y0) = p.root_pos(win);
    p.send(win, "press", 1, ((x0 + 60) as i16, (y0 + 30) as i16), (60, 30)); // a click elsewhere closes the menu
    p.send(win, "release", 1, ((x0 + 60) as i16, (y0 + 30) as i16), (60, 30));
    p.wait("the menu closed", n, |v| v.get("event") == Some(&Value::Str("menu closed".into())));

    // Help / details (the current reading's detail)
    let n = p.n();
    p.menu(win, "Help / details");
    let ev = p.wait("a help window", n, |v| matches!(v.get("help"), Some(Value::Int(Some(_)))));
    let help_text = match ev.get("help_text") {
        Some(Value::Str(s)) => s.clone(),
        _ => String::new(),
    };
    p.put("help", quote(&help_text));
    let Some(Value::Int(Some(help_win))) = ev.get("help") else { unreachable!() };
    let help_win = *help_win as u32;
    let deadline = Instant::now() + Duration::from_secs(5);
    let mapped = loop {
        // a managed window is shown once the window manager has mapped it
        let viewable =
            p.conn.get_window_attributes(help_win).unwrap().reply().unwrap().map_state == xproto::MapState::VIEWABLE;
        if viewable || Instant::now() > deadline {
            break viewable;
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    p.check(p.title(help_win) == "DeHulud Combat help", "help window title".into());
    p.put("help_window_mapped", mapped.to_string());
    std::thread::sleep(Duration::from_millis(200));
    p.keep(help_win, "help.ppm");
    let n = p.n();
    p.send(help_win, "press", 1, (0, 0), (10, 10)); // a click closes it
    p.wait("the help window closed", n, |v| v.get("help") == Some(&Value::Null));

    // header switches: a click flips the section, saves it and resizes the window, keeping its top-left corner
    let corner = p.root_pos(win);
    let click = |p: &Probe, x: i16| {
        let n = p.n();
        let (x0, y0) = p.root_pos(win);
        p.send(win, "press", 1, ((x0 + i64::from(x)) as i16, (y0 + 9) as i16), (x, 9));
        p.send(win, "release", 1, ((x0 + i64::from(x) + 1) as i16, (y0 + 10) as i16), (x + 1, 10));
        p.wait("the switch", n, |v| v.get("event") == Some(&Value::Str("switched".into())))
    };
    let size = |p: &Probe| {
        let g = p.conn.get_geometry(win).unwrap().reply().unwrap();
        format!("[{}, {}]", g.width, g.height)
    };
    // a flipped switch clears its overlay column at once (Window::toggle), also with every switch off, when no
    // poll runs that could clear it
    let taken = |v: &Value| has_fill(v, &OV_TAKEN);
    let dealt = |v: &Value| has_fill(v, &OV_HEALTH) || has_fill(v, &OV_SHIELD);
    let mapped = |v: &Value| traced_overlay(v).is_some_and(|o| o.0);
    let fresh = |p: &mut Probe| {
        let n = p.n();
        p.set("step=1"); // unreadable: both columns cleared
        p.wait("the cleared step", n, |v| v.get("event") == Some(&Value::Str("tick".into())) && !mapped(v));
        let n = p.n();
        p.set("step=0"); // a new step: -37, 120, 40 emitted on its first poll
        p.wait("-37 on screen", n, taken);
    };
    fresh(&mut p);
    click(&p, 80); // Taken off and straight on again
    let ev = click(&p, 80);
    p.check(!taken(&ev) && dealt(&ev) && mapped(&ev), "taken off/on: its column cleared, dealt kept".into());
    fresh(&mut p);
    click(&p, 10); // worm off
    let ev = click(&p, 150); // dealt off: -37 still shown (the case below is not empty)
    p.check(taken(&ev) && !dealt(&ev), "-37 still shown before the last switch goes off".into());
    click(&p, 80); // taken off: every switch off, no polls from here
    std::thread::sleep(Duration::from_millis(300));
    p.check(!p.viewable(overlay), "every switch off: the overlay is unmapped".into());
    let (_, bits) = p.shape_bits(overlay, shape::SK::BOUNDING, ow, oh);
    p.check(!bits.contains(&true), "every switch off: bounding shape empty".into());
    let ev = click(&p, 80);
    p.check(!taken(&ev) && !mapped(&ev), "all off, then taken on: no old number".into());
    click(&p, 10);
    click(&p, 150);
    let n = p.n();
    p.set("step=3");
    p.wait(
        "no permission",
        n,
        |v| matches!(v.get("shown"), Some(Value::Array(a)) if a[1] == Value::Str("no permission".into())),
    );

    click(&p, 80);
    p.put("size_without_taken", size(&p));
    p.put("after_click", quote(&p.config()));
    p.keep(win, "window-no-taken.ppm");
    let mut corner_kept = p.root_pos(win) == corner;
    click(&p, 10);
    p.put("size_worm_only_off", size(&p)); // dealt still on: header + status
    corner_kept &= p.root_pos(win) == corner;
    click(&p, 150);
    p.put("size_all_off", size(&p));
    p.keep(win, "window-all-off.ppm");
    let px = p.pixels(win);
    p.check(
        ink_in(&px, &[0x6b7174], 0, 18).0 > 0 && ink_in(&px, &[0xd8cfb4], 0, 18).0 == 0,
        "all off: the three switches in the off colour".into(),
    );
    let polls = p.events().iter().filter(|v| v.get("event") == Some(&Value::Str("poll".into()))).count();
    std::thread::sleep(Duration::from_millis(300)); // several poll intervals
    let later = p.events().iter().filter(|v| v.get("event") == Some(&Value::Str("poll".into()))).count();
    p.put("all_off_reads_nothing", (later == polls).to_string());
    corner_kept &= p.root_pos(win) == corner;
    for x in [10, 80, 150] {
        click(&p, x);
    }
    p.put("size_all_on_again", size(&p));
    corner_kept &= p.root_pos(win) == corner;
    p.put("corner_kept", corner_kept.to_string());
    // every click reached the damage readers (Window::toggle -> Poll::reset), each just before its switch
    // event, with the clicked feature; nothing before the first click (no reset for the startup state)
    let kinds: Vec<(String, String)> = p
        .events()
        .iter()
        .filter_map(|v| match (v.get("event"), v.get("feature")) {
            (Some(Value::Str(e)), f) if e == "reset" || e == "switched" => {
                Some((e.clone(), if let Some(Value::Str(f)) = f { f.clone() } else { String::new() }))
            }
            _ => None,
        })
        .collect();
    let paired = kinds.len().is_multiple_of(2)
        && kinds.chunks(2).all(|c| c[0].0 == "reset" && c[1].0 == "switched")
        && kinds.iter().filter(|k| k.0 == "reset").count() >= 14;
    let firsts: Vec<&str> = kinds.iter().filter(|k| k.0 == "reset").take(2).map(|k| k.1.as_str()).collect();
    p.check(paired && firsts == ["damage_taken", "damage_taken"], format!("resets per click {kinds:?}"));
    // a press on a switch that moves 3 px is a drag: it moves the window and flips nothing
    let n = p.n();
    let (x0, y0) = p.root_pos(win);
    p.send(win, "press", 1, ((x0 + 10) as i16, (y0 + 9) as i16), (10, 9));
    p.motion(win, ((x0 + 13) as i16, (y0 + 9) as i16), (13, 9));
    p.send(win, "release", 1, ((x0 + 13) as i16, (y0 + 9) as i16), (13, 9));
    let ev = p.wait("the move", n, |v| v.get("event") == Some(&Value::Str("moved".into())));
    let flipped = p.events().iter().skip(n).any(|v| {
        v.get("event") == Some(&Value::Str("switched".into())) || v.get("event") == Some(&Value::Str("reset".into()))
    });
    p.put(
        "header_drag_flips_nothing",
        (!flipped && ev.get("enabled").is_some_and(|e| matches!(e, Value::Array(a) if a.len() == 3))).to_string(),
    );

    // drag with the left button
    let n = p.n();
    let (x0, y0) = p.root_pos(win);
    p.send(win, "press", 1, ((x0 + 4) as i16, (y0 + 2) as i16), (4, 2));
    p.motion(win, (100, 100), (4, 2));
    p.motion(win, (134, 72), (4, 2));
    p.send(win, "release", 1, (134, 72), (4, 2));
    p.wait("the move", n, |v| v.get("event") == Some(&Value::Str("moved".into())));
    p.put("after_drag", quote(&p.config()));
    let moved = p.root_pos(win);
    p.put("dragged_to", format!("[{}, {}]", moved.0, moved.1));

    // window frame on: a managed window with a title bar
    let n = p.n();
    p.menu(win, "Window frame");
    let ev = p.wait("the framed window", n, |v| v.get("frame") == Some(&Value::Bool(true)));
    let Some(Value::Int(Some(framed))) = ev.get("window") else { unreachable!() };
    let framed = *framed as u32;
    p.put("after_frame", quote(&p.config()));
    let attrs = p.conn.get_window_attributes(framed).unwrap().reply().unwrap();
    p.check(!attrs.override_redirect, "the framed window is not override-redirect".into());
    p.put("framed_is_managed", p.managed(framed).to_string());
    p.check(p.title(framed) == "DeHulud Combat", "framed window title".into());
    p.check(p.above(framed), "framed window keeps _NET_WM_STATE_ABOVE".into());

    // reset position
    let n = p.n();
    p.menu(framed, "Reset position");
    let deadline = Instant::now() + Duration::from_secs(10);
    while !p.config().contains("null") && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    let _ = n;
    p.put("after_reset", quote(&p.config()));

    // quit
    p.menu(framed, "Quit");
    let deadline = Instant::now() + Duration::from_secs(10);
    let code = loop {
        if let Some(st) = child.try_wait().unwrap() {
            break st.code();
        }
        if Instant::now() > deadline {
            let _ = child.kill(); // our own child, stuck
            let _ = child.wait();
            break None;
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    p.put("quit_exit_0", (code == Some(0)).to_string());
    p.put("after_quit", quote(&p.config()));
    p.put("overlay_destroyed_on_quit", p.find("DeHulud Combat damage").is_none().to_string());

    // a server without SHAPE (test hook): one line on stderr, no overlay window, the poll reads the worm only
    let ns = dir.join("no-shape");
    fs::create_dir_all(ns.join("cfg")).unwrap();
    let (saved_out, saved_failures) = (p.out, p.failures);
    let mut q = Probe {
        conn: p.conn,
        root,
        trace: ns.join("trace.jsonl"),
        ctl: ns.join("control"),
        control: vec![],
        failures: vec![],
        out: vec![],
        dir: ns.clone(),
    };
    for line in [
        "poll_ms=40".to_string(),
        format!("trace={}", ns.join("trace.jsonl").display()),
        "no_shape=1".into(),
        "reading=no permission|-|-|right-click||37|120/40".into(),
        "reading=no permission|-|-|right-click|FIX: sudo sysctl|37|120/40".into(),
        "step=0".into(),
    ] {
        q.set(&line);
    }
    let mut child = Command::new(&bin)
        .env_clear()
        .env("PATH", std::env::var("PATH").unwrap_or_default())
        .env("HOME", ns.join("home"))
        .env("XDG_CONFIG_HOME", ns.join("cfg"))
        .env("DISPLAY", &display_name)
        .env("XAUTHORITY", std::env::var("XAUTHORITY").unwrap_or_default())
        .env("DEHULUD_TEST_SOURCE", ns.join("control"))
        .stdout(fs::File::create(ns.join("dehulud.out")).unwrap())
        .stderr(fs::File::create(ns.join("dehulud.err")).unwrap())
        .spawn()
        .unwrap();
    let first = q.wait("the window", 0, |v| matches!(v.get("window"), Some(Value::Int(Some(w))) if *w != 0));
    let Some(Value::Int(Some(nwin))) = first.get("window") else { unreachable!() };
    let nwin = *nwin as u32;
    for _ in 0..3 {
        q.wait("a tick", q.n(), |v| v.get("event") == Some(&Value::Str("tick".into())));
    }
    let polls: Vec<Value> =
        q.events().into_iter().filter(|v| v.get("event") == Some(&Value::Str("poll".into()))).collect();
    let worm_only = !polls.is_empty()
        && polls.iter().all(|v| matches!(v.get("enabled"), Some(Value::Array(a)) if *a == [Value::Str("worm".into())]));
    let n = q.n();
    q.menu(nwin, "Help / details");
    let ev = q.wait("a help window", n, |v| matches!(v.get("help"), Some(Value::Int(Some(_)))));
    let help_ok = matches!(ev.get("help_text"), Some(Value::Str(t)) if t.ends_with("\ndamage numbers need the X SHAPE extension"));
    // a reading with a detail: the help shows the detail, still followed by the line
    let n = q.n();
    q.set("step=1");
    q.wait("the detail", n, |v| v.get("event") == Some(&Value::Str("tick".into())));
    let n = q.n();
    q.menu(nwin, "Help / details");
    let ev = q.wait(
        "a help window with the detail",
        n,
        |v| matches!(v.get("help_text"), Some(Value::Str(t)) if t.starts_with("FIX")),
    );
    let help_ok = help_ok
        && ev.get("help_text")
            == Some(&Value::Str("FIX: sudo sysctl\ndamage numbers need the X SHAPE extension".into()));
    let no_overlay = first.get("overlay") == Some(&Value::Null) && q.find("DeHulud Combat damage").is_none();
    q.set("stop=1");
    let deadline = Instant::now() + Duration::from_secs(10);
    while child.try_wait().unwrap().is_none() && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(20));
    }
    if child.try_wait().unwrap().is_none() {
        let _ = child.kill(); // our own child, stuck
        let _ = child.wait();
    }
    let err = fs::read_to_string(ns.join("dehulud.err")).unwrap_or_default();
    let once = err.lines().filter(|l| *l == "damage numbers need the X SHAPE extension").count() == 1;
    let out = vec![
        ("no_shape_line_once".to_string(), once.to_string()),
        ("no_shape_stderr".to_string(), quote(&err)),
        ("no_shape_no_overlay".to_string(), no_overlay.to_string()),
        ("no_shape_reads_worm_only".to_string(), worm_only.to_string()),
        ("no_shape_help".to_string(), help_ok.to_string()),
    ];
    let mut p = Probe { out: saved_out, failures: saved_failures, ..q };
    p.out.extend(out);

    let failures: Vec<String> = p.failures.iter().map(|f| quote(f)).collect();
    p.out.push(("failures".into(), format!("[{}]", failures.join(", "))));
    let body: Vec<String> = p.out.iter().map(|(k, v)| format!("{}: {v}", quote(k))).collect();
    fs::write(&result, format!("{{{}}}", body.join(", "))).unwrap();
}
