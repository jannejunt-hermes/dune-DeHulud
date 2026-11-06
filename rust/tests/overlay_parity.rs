//! Ordered overlay rectangles and colours agree across languages for identical scripted readings.
mod common;

use dehulud::json::{self, Value, quote};
use dehulud::overlay::{self, Overlay};
use dehulud::sections::Features;
use std::io::Write;
use std::process::{Command, Stdio};

const SCRIPT: &str = r#"
import json, sys
sys.path.insert(0, sys.argv[1])
import dehulud_combat as m
inp = json.load(sys.stdin)
out = []
for mon in inp['monitors']:
    g, view, frames = m.overlay_geometry(mon), m.Overlay(), []
    for line in inp['readings']:
        f = line.split('=', 1)[1].split('|')
        values = lambda s: () if not s else (float(s),)
        t = None if f[5] == '-' else values(f[5])
        d = None if f[6] == '-' else tuple(values(s) for s in f[6].split('/'))
        view.step(m.Reading(f[0], taken=t, dealt=d), m.ALL)
        outlines, fills = m.overlay_rects(view, g[4], g[5])
        frames.append([list(g), outlines, fills])
    out.append(frames)
print(json.dumps(out))
"#;

#[test]
fn identical_scripted_readings_and_placements() {
    let monitors =
        [(0, 0, 1920, 1080), (0, 0, 2560, 1440), (0, 0, 3840, 2160), (-100, 37, 1919, 1079), (-30, -21, 99, 101)];
    let readings = [
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425|||37|120/40",
        "reading=on foot|42|0.425|||12.5|84/10",
        "reading=on foot|42|0.425|||0.49|0.5/2.5",
        "reading=on foot|42|0.425|||999999|999999/999999",
        "reading=on foot|42|0.425|||9|6/7",
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425||||/",
        "reading=on foot|42|0.425|||8|7/6",
        "reading=unsupported|||||-|-",
    ];
    let input = format!(
        "{{\"monitors\":[{}],\"readings\":[{}]}}",
        monitors.iter().map(|(x, y, w, h)| format!("[{x},{y},{w},{h}]")).collect::<Vec<_>>().join(","),
        readings.iter().map(|s| quote(s)).collect::<Vec<_>>().join(",")
    );
    let mut child = Command::new(common::python())
        .args(["-B", "-I", "-c", SCRIPT, &common::repo().to_string_lossy()])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(input.as_bytes()).unwrap();
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    let Value::Array(expected) = json::parse(&String::from_utf8(output.stdout).unwrap()).unwrap() else {
        panic!("array")
    };
    for (mi, mon) in monitors.into_iter().enumerate() {
        let g = overlay::geometry(mon);
        let mut view = Overlay::default();
        let Value::Array(frames) = &expected[mi] else { panic!("frames") };
        for (i, reading) in readings.iter().enumerate() {
            let fields: Vec<_> = reading.split_once('=').unwrap().1.split('|').collect();
            let taken = if fields[5] == "-" { None } else { Some(fields[5].parse().ok()) };
            let dealt = if fields[6] == "-" {
                None
            } else {
                let (h, s) = fields[6].split_once('/').unwrap();
                Some((h.parse().ok(), s.parse().ok()))
            };
            view.step(taken, dealt, Features::ALL);
            let (outlines, fills) = overlay::rects(&view, g.s, g.o);
            if fields[5] == "-" && fields[6] == "-" {
                assert!(outlines.is_empty() && fills.is_empty(), "no standalone missing-value dash may be drawn");
            }
            let outlines =
                outlines.iter().map(|(x, y, w, h)| format!("[{x},{y},{w},{h}]")).collect::<Vec<_>>().join(",");
            let fills = fills
                .iter()
                .map(|((x, y, w, h), c)| format!("[{x},{y},{w},{h},\"#{c:06x}\"]"))
                .collect::<Vec<_>>()
                .join(",");
            let got =
                json::parse(&format!("[[{},{},{},{},{},{}],[{}],[{}]]", g.x, g.y, g.w, g.h, g.s, g.o, outlines, fills))
                    .unwrap();
            assert_eq!(got, frames[i], "monitor {mon:?}, poll {i}: {reading}");
        }
    }
}

#[test]
fn meter_has_no_damage_sections() {
    for bits in 0..8 {
        let on = Features { worm: bits & 1 != 0, taken: bits & 2 != 0, dealt: bits & 4 != 0 };
        let (sections, height) = dehulud::sections::layout(on);
        assert!(sections.iter().all(|(section, _)| ["header", "worm", "status"].contains(&section.name())));
        assert_eq!(
            height,
            if on.worm {
                62
            } else if on.taken || on.dealt {
                38
            } else {
                18
            }
        );
    }
}
