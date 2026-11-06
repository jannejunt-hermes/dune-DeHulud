//! Damage numbers, their lifetime and the bitmap rectangles of the transparent overlay.

use crate::config::Monitor;
use crate::font::BIG;
use crate::sections::{Feature, Features, LIFE, ROWS, shown_number};

pub const TITLE: &str = "DeHulud Combat damage";
pub const NO_SHAPE: &str = "damage numbers need the X SHAPE extension";
pub const OVERLAY_TAKEN: [u32; 5] = [0xff4d3d, 0xff4d3d, 0xb63a2f, 0x792923, 0x3c1917];
pub const OVERLAY_HEALTH: [u32; 5] = [0x3d9bff, 0x3d9bff, 0x2e70b6, 0x224c7a, 0x15293d];
pub const OVERLAY_SHIELD: [u32; 5] = [0x9cd2ff, 0x9cd2ff, 0x7197b6, 0x4c657a, 0x28343d];
pub const OUTLINE: u32 = 0x0b0c0d;

pub fn monitor(mons: &[Monitor], screen: (i32, i32, i32, i32)) -> (i32, i32, i32, i32) {
    mons.iter().find(|m| m.primary).or_else(|| mons.first()).map_or(screen, |m| (m.x, m.y, m.width, m.height))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Geometry {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub s: i32,
    pub o: i32,
}

pub fn geometry((x, y, width, height): (i32, i32, i32, i32)) -> Geometry {
    let s = ((height + 270).div_euclid(540)).max(1);
    let o = (s / 2).max(1);
    let (w, h) = (100 * s + 2 * o, 50 * s + 2 * o);
    Geometry { x: x + (width - w).div_euclid(2), y: y + height.div_euclid(4), w, h, s, o }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Channel {
    Health,
    Shield,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Overlay {
    pub taken: Vec<(u32, u32)>,
    pub dealt: Vec<(u32, u32, Channel)>,
}

impl Overlay {
    pub fn reset(&mut self, f: Feature) {
        match f {
            Feature::Worm => {}
            Feature::Taken => self.taken.clear(),
            Feature::Dealt => self.dealt.clear(),
        }
    }

    pub fn is_empty(&self) -> bool {
        self.taken.is_empty() && self.dealt.is_empty()
    }

    /// Advance one poll; an absent outer option means the feature is untrustworthy.
    pub fn step(&mut self, taken: Option<Option<f64>>, dealt: Option<(Option<f64>, Option<f64>)>, on: Features) {
        if let Some(value) = taken.filter(|_| on.taken) {
            self.taken.retain_mut(|(_, age)| {
                *age += 1;
                *age < LIFE
            });
            if let Some(n) = value.and_then(shown_number) {
                self.taken.insert(0, (n, 0));
            }
            self.taken.truncate(ROWS);
        } else {
            self.taken.clear();
        }
        if let Some((health, shield)) = dealt.filter(|_| on.dealt) {
            self.dealt.retain_mut(|(_, age, _)| {
                *age += 1;
                *age < LIFE
            });
            for (value, channel) in [(shield, Channel::Shield), (health, Channel::Health)] {
                if let Some(n) = value.and_then(shown_number) {
                    self.dealt.insert(0, (n, 0, channel));
                }
            }
            self.dealt.truncate(ROWS);
        } else {
            self.dealt.clear();
        }
    }
}

pub type Rect = (i32, i32, i32, i32);
pub type Fills = Vec<(Rect, u32)>;

/// Bounding outlines in run order, followed by the fills to paint over all outlines.
pub fn rects(view: &Overlay, s: i32, o: i32) -> (Vec<Rect>, Fills) {
    let mut outlines = Vec::new();
    let mut fills = Vec::new();
    let mut number = |text: String, row: usize, taken: bool, colour: u32| {
        let tx = if taken { 45 - BIG.width(&text, false) } else { 55 };
        for (rx, ry, rw) in BIG.runs(&text, tx, 13 * row as i32, false) {
            let (x, y, w, h) = (o + rx * s, o + ry * s, rw * s, s);
            outlines.push((x - o, y - o, w + 2 * o, h + 2 * o));
            fills.push(((x, y, w, h), colour));
        }
    };
    for (i, (n, age)) in view.taken.iter().take(ROWS).enumerate() {
        number(format!("-{n}"), i, true, OVERLAY_TAKEN[*age as usize]);
    }
    for (i, (n, age, channel)) in view.dealt.iter().take(ROWS).enumerate() {
        let colours = match channel {
            Channel::Health => OVERLAY_HEALTH,
            Channel::Shield => OVERLAY_SHIELD,
        };
        number(n.to_string(), i, false, colours[*age as usize]);
    }
    (outlines, fills)
}

pub fn read_features(on: Features, overlay_ok: bool) -> Features {
    if overlay_ok { on } else { Features { worm: on.worm, ..Features::NONE } }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn placement_and_monitor() {
        for (mon, want) in [
            ((0, 0, 1920, 1080), (859, 270, 202, 102, 2, 1)),
            ((0, 0, 2560, 1440), (1129, 360, 302, 152, 3, 1)),
            ((0, 0, 3840, 2160), (1718, 540, 404, 204, 4, 2)),
            ((-100, 37, 1919, 1079), (758, 306, 202, 102, 2, 1)),
            ((-30, -21, 99, 101), (-32, 4, 102, 52, 1, 1)),
        ] {
            let g = geometry(mon);
            assert_eq!((g.x, g.y, g.w, g.h, g.s, g.o), want);
        }
        let mons = [
            Monitor { x: 10, y: 20, width: 800, height: 600, primary: false },
            Monitor { x: -900, y: -50, width: 900, height: 1080, primary: true },
        ];
        assert_eq!(monitor(&mons, (0, 0, 1, 1)), (-900, -50, 900, 1080));
        assert_eq!(monitor(&mons[..1], (0, 0, 1, 1)), (10, 20, 800, 600));
        assert_eq!(monitor(&[], (1, 2, 3, 4)), (1, 2, 3, 4));
    }

    #[test]
    fn exact_rectangles_in_run_order() {
        let v = Overlay { taken: vec![(1, 2)], dealt: vec![(1, 4, Channel::Shield)] };
        let runs = [
            (32, 5, 5),
            (32, 6, 5),
            (41, 0, 2),
            (40, 1, 3),
            (39, 2, 4),
            (41, 3, 2),
            (41, 4, 2),
            (41, 5, 2),
            (41, 6, 2),
            (41, 7, 2),
            (41, 8, 2),
            (41, 9, 2),
            (39, 10, 6),
            (58, 0, 2),
            (57, 1, 3),
            (56, 2, 4),
            (58, 3, 2),
            (58, 4, 2),
            (58, 5, 2),
            (58, 6, 2),
            (58, 7, 2),
            (58, 8, 2),
            (58, 9, 2),
            (56, 10, 6),
        ];
        let outlines: Vec<Rect> = runs.iter().map(|(x, y, w)| (x * 2, y * 2, w * 2 + 2, 4)).collect();
        let fills: Fills = runs
            .iter()
            .enumerate()
            .map(|(i, (x, y, w))| ((1 + x * 2, 1 + y * 2, w * 2, 2), if i < 13 { 0xb63a2f } else { 0x28343d }))
            .collect();
        assert_eq!(rects(&v, 2, 1), (outlines, fills));
    }

    #[test]
    fn merge_cap_lifetime_and_colours() {
        let mut v = Overlay::default();
        v.step(Some(Some(1e9)), Some((Some(2.5), Some(4.5))), Features::ALL);
        assert_eq!(v.taken, [(99999, 0)]);
        assert_eq!(v.dealt, [(3, 0, Channel::Health), (5, 0, Channel::Shield)]);
        for age in 0..5 {
            let mut colours = Vec::new();
            for (_, c) in rects(&v, 1, 1).1 {
                if colours.last() != Some(&c) {
                    colours.push(c);
                }
            }
            assert_eq!(colours, [OVERLAY_TAKEN[age], OVERLAY_HEALTH[age], OVERLAY_SHIELD[age]]);
            v.step(Some(None), Some((None, None)), Features::ALL);
        }
        assert!(v.is_empty());
        assert_eq!(rects(&v, 1, 1), (vec![], vec![]));
        for n in 1..=5 {
            v.step(Some(Some(n as f64)), Some((Some(n as f64), Some((n + 10) as f64))), Features::ALL);
        }
        assert_eq!(v.taken, [(5, 0), (4, 1), (3, 2), (2, 3)]);
        assert_eq!(
            v.dealt,
            [(5, 0, Channel::Health), (15, 0, Channel::Shield), (4, 1, Channel::Health), (14, 1, Channel::Shield)]
        );
    }

    #[test]
    fn clear_reset_and_read_features() {
        let mut v = Overlay::default();
        assert!(v.is_empty());
        for on in [Features::ALL, Features::NONE] {
            v.step(Some(Some(1.0)), Some((Some(2.0), Some(3.0))), Features::ALL);
            v.step(None, None, on);
            assert!(v.is_empty());
            assert_eq!(rects(&v, 2, 1), (vec![], vec![]));
        }
        v.step(Some(Some(1.0)), Some((Some(2.0), None)), Features::ALL);
        v.step(Some(Some(9.0)), Some((Some(8.0), None)), Features::NONE);
        assert!(v.is_empty());
        v.step(Some(Some(0.1)), Some((Some(0.0), Some(0.49))), Features::ALL);
        assert!(v.is_empty());
        v.step(Some(Some(1.0)), Some((Some(2.0), None)), Features::ALL);
        v.reset(Feature::Worm);
        assert!(!v.is_empty());
        v.reset(Feature::Taken);
        assert!(v.taken.is_empty());
        v.reset(Feature::Dealt);
        assert!(v.is_empty());
        assert_eq!(read_features(Features::ALL, true), Features::ALL);
        assert_eq!(read_features(Features::ALL, false), Features::TEXT);
        assert_eq!(read_features(Features { taken: true, ..Features::NONE }, false), Features::NONE);
    }
}
