//! The window's sections: the three switches, the layout (section order and heights), the header's click zones
//! and click-or-drag rule, and how an emitted drop becomes a shown number (rounding, the five-digit cap, life in
//! polls, rows per column) for the damage overlay ([`crate::overlay`]). Pure functions, the same as in
//! `dehulud_combat.py`; the drawing is in [`crate::combat_window`].

/// The window's width; the height follows the sections that are on.
pub const W: i32 = 180;
/// Section heights in pixels, top to bottom.
pub const HEADER_H: i32 = 18;
pub const WORM_H: i32 = 24;
pub const STATUS_H: i32 = 20;
/// The tallest window (every section on).
pub const MAX_H: i32 = HEADER_H + WORM_H + STATUS_H;
/// A press that moves this far (in x or y) by its release is a drag, not a click.
pub const CLICK_PX: i32 = 3;
/// A number is removed on its fifth poll (shown at ages 0 to 4).
pub const LIFE: u32 = 5;
/// Numbers per column.
pub const ROWS: usize = 4;
/// At most five digits.
pub const CAP: u32 = 99999;

pub const LABEL: u32 = 0xd8cfb4;
pub const OFF: u32 = 0x6b7174;
/// One of the window's three switchable sections.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Feature {
    Worm,
    Taken,
    Dealt,
}

impl Feature {
    pub const ALL: [Feature; 3] = [Feature::Worm, Feature::Taken, Feature::Dealt];

    /// The config file key (also the name the Python version uses).
    pub fn key(self) -> &'static str {
        match self {
            Feature::Worm => "worm",
            Feature::Taken => "damage_taken",
            Feature::Dealt => "damage_dealt",
        }
    }

    /// The command-line flag that switches it off for one run.
    pub fn flag(self) -> &'static str {
        match self {
            Feature::Worm => "--no-worm",
            Feature::Taken => "--no-taken",
            Feature::Dealt => "--no-dealt",
        }
    }

    /// Its header switch: click zone x0..=x1, x of the text, label.
    pub fn zone(self) -> (i32, i32, i32, &'static str) {
        match self {
            Feature::Worm => (0, 56, 6, "Worm"),
            Feature::Taken => (57, 116, 60, "Taken"),
            Feature::Dealt => (117, 179, 120, "Dealt"),
        }
    }
}

/// A set of features: the sections that are on (or, for flags, the ones switched off).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Features {
    pub worm: bool,
    pub taken: bool,
    pub dealt: bool,
}

impl Features {
    pub const ALL: Features = Features { worm: true, taken: true, dealt: true };
    pub const NONE: Features = Features { worm: false, taken: false, dealt: false };
    /// What the terminal line shows (the section flags are for the window).
    pub const TEXT: Features = Features { worm: true, taken: false, dealt: false };

    pub fn has(self, f: Feature) -> bool {
        match f {
            Feature::Worm => self.worm,
            Feature::Taken => self.taken,
            Feature::Dealt => self.dealt,
        }
    }

    pub fn set(&mut self, f: Feature, on: bool) {
        match f {
            Feature::Worm => self.worm = on,
            Feature::Taken => self.taken = on,
            Feature::Dealt => self.dealt = on,
        }
    }

    pub fn any(self) -> bool {
        self.worm || self.taken || self.dealt
    }

    /// The config keys of the features in the set, in header order.
    pub fn keys(self) -> Vec<&'static str> {
        Feature::ALL.iter().filter(|f| self.has(**f)).map(|f| f.key()).collect()
    }
}

/// The window's sections, top to bottom.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Section {
    Header,
    Worm,
    Status,
}

impl Section {
    /// The name the Python version uses for it.
    pub fn name(self) -> &'static str {
        match self {
            Section::Header => "header",
            Section::Worm => "worm",
            Section::Status => "status",
        }
    }
}

/// The sections shown with their top y, and the window height. The header is always shown, the status line
/// whenever at least one section is on; the order never changes.
pub fn layout(on: Features) -> (Vec<(Section, i32)>, i32) {
    let all =
        [(Section::Header, HEADER_H, true), (Section::Worm, WORM_H, on.worm), (Section::Status, STATUS_H, on.any())];
    let mut y = 0;
    let mut out = Vec::new();
    for (s, h, shown) in all {
        if shown {
            out.push((s, y));
            y += h;
        }
    }
    (out, y)
}

/// The feature whose header switch is at window pixel (x, y), or None outside the header row.
pub fn header_zone(x: i32, y: i32) -> Option<Feature> {
    if !(0..HEADER_H).contains(&y) {
        return None;
    }
    Feature::ALL.into_iter().find(|f| {
        let (x0, x1, _, _) = f.zone();
        x0 <= x && x <= x1
    })
}

/// Whether a press that moved (dx, dy) by its release is a click (else it is a drag).
pub fn is_click(dx: i32, dy: i32) -> bool {
    dx.abs() < CLICK_PX && dy.abs() < CLICK_PX
}

/// The header row: x, text and colour of the three switches.
pub fn header_cells(on: Features) -> Vec<(i32, String, u32)> {
    Feature::ALL
        .iter()
        .map(|f| {
            let (_, _, x, label) = f.zone();
            if on.has(*f) { (x, format!("[x] {label}"), LABEL) } else { (x, format!("[ ] {label}"), OFF) }
        })
        .collect()
}

/// The whole points shown for an emitted drop (capped at five digits), or None for nothing (a drop that rounds
/// to 0, or a value that is not a non-negative number).
pub fn shown_number(v: f64) -> Option<u32> {
    if !v.is_finite() || v < 0.0 {
        return None;
    }
    let n = (v + 0.5).floor();
    if n <= 0.0 { None } else { Some(n.min(f64::from(CAP)) as u32) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn feats(worm: bool, taken: bool, dealt: bool) -> Features {
        Features { worm, taken, dealt }
    }

    #[test]
    fn heights_of_all_eight_combinations() {
        // the damage numbers are in the overlay: the box is header + worm meter + status line
        let want = [
            ((false, false, false), 18),
            ((true, false, false), 62),
            ((false, true, false), 38),
            ((false, false, true), 38),
            ((true, true, false), 62),
            ((true, false, true), 62),
            ((false, true, true), 38),
            ((true, true, true), 62),
        ];
        for ((w, t, d), h) in want {
            assert_eq!(layout(feats(w, t, d)).1, h, "{w} {t} {d}");
        }
        assert_eq!(MAX_H, 62);
        assert_eq!(layout(Features::ALL).0, [(Section::Header, 0), (Section::Worm, 18), (Section::Status, 42)]);
        assert_eq!(layout(feats(false, true, true)).0, [(Section::Header, 0), (Section::Status, 18)]);
        assert_eq!(layout(Features::NONE).0, [(Section::Header, 0)]);
    }

    #[test]
    fn header_zones_and_clicks() {
        let z: Vec<_> = [0, 56, 57, 116, 117, 179].iter().map(|x| header_zone(*x, 9)).collect();
        use Feature::*;
        assert_eq!(z, [Some(Worm), Some(Worm), Some(Taken), Some(Taken), Some(Dealt), Some(Dealt)]);
        assert_eq!([header_zone(30, 0), header_zone(30, 17)], [Some(Worm), Some(Worm)]);
        assert_eq!([header_zone(30, 18), header_zone(30, -1), header_zone(-1, 5), header_zone(180, 5)], [None; 4]);
        assert!(is_click(2, -2) && is_click(0, 0) && !is_click(3, 0) && !is_click(0, -3));
    }

    #[test]
    fn header_strings_fit_their_zones() {
        for f in Feature::ALL {
            let (x0, x1, x, label) = f.zone();
            let w = crate::font::SMALL.width(&format!("[x] {label}"), false);
            assert!(x0 <= x && x + w <= x1 + 1, "{label}");
        }
        assert_eq!(header_cells(feats(false, true, false))[0], (6, "[ ] Worm".to_string(), OFF));
    }

    #[test]
    fn rounding_and_cap() {
        let got: Vec<_> = [0.0, 0.49, 0.5, 1.5, 2.5, 36.6, 99999.4, 99999.5, 1e12, -1.0, f64::NAN, f64::INFINITY]
            .iter()
            .map(|v| shown_number(*v))
            .collect();
        let want = [None, None, Some(1), Some(2), Some(3), Some(37), Some(99999), Some(99999), Some(99999)];
        assert_eq!(got[..9], want);
        assert_eq!(got[9..], [None; 3]);
    }
}
