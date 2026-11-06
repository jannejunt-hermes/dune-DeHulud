# DeHulud Combat: how it looks

This page is about **DeHulud Combat**, the second program in this repo, in both of its versions (Tk in
`dehulud_combat.py`, the drawn window with the built-in bitmap font in the `dehulud-combat` binary). Combat has two
windows:

- **the meter box**: the small window titled `DeHulud Combat` with the header switches `[x] Worm  [x] Taken  [x] Dealt`,
  the worm meter and the status line. This is the window you drag, right-click and that remembers its place in
  Combat's config file (`dehulud-combat` folder, keys `x`, `y`, `frame` and the three switches).
- **the damage overlay**: a second window with no background, no frame and no border, near the top middle of the
  screen, that shows only the damage numbers: **damage taken in red, damage dealt in blue**. It is on screen only
  while it has a number to show; it is not meant to be clicked (clicks go through it on a display server that
  honours input shapes), and it has no menu and no position of its own.

**Plain DeHulud is not changed by this page**: its window stays 180 x 44, with no header row and the status line under
the bar, exactly as shipped. Combat's worm meter is the same meter drawn the same way, under the header.

Behaviour (what is read, when a number is emitted) is not repeated here; this page only says what is drawn where, in
which colour and size. Everything in the box is in window pixels; everything in the overlay is in *font pixels* that
are scaled up to the screen (see [Placement and scale](#placement-and-scale)). Both versions place every item at the
same pixel: the small font is 5 x 9 per character, 6 px per character advance (7 when bold), ascent 7; the big bold
font is 11 px tall, 7 px per digit, 5 px for `-`, 1 px between glyphs.

## The meter box

The box stays **180 px wide**; only its height changes.

| section | height | shown when |
|---|---|---|
| header (the three switches) | 18 | always |
| worm meter (label, bar, percent) | 24 | `worm` on |
| status line (`on foot`, `waiting for game`, ...) | 20 | at least one of the three switches on |

There is no damage section in the box any more: the damage numbers are in the overlay. Window height = the sum of
the shown sections; the order never changes and a section that is off takes no space.

| worm | taken | dealt | height | the window |
|---|---|---|---|---|
| off | off | off | 18 | header only, no status line |
| on | any | any | 62 | header, meter, status |
| off | on | off | 38 | header, status |
| off | off | on | 38 | header, status |
| off | on | on | 38 | header, status |

So the box is one of three heights: **18, 38 or 62**. It keeps its top-left corner when it grows or shrinks (the
saved position is that corner). The height changes at once on a click in the header, and the window opens at the
right height for the config file and flags. Menu, the frame option, drag and the help box are as before.

### Colours in the box

| use | hex | note |
|---|---|---|
| background | `#1d1f21` | as in plain DeHulud |
| `WORM` label; a switch that is on | `#d8cfb4` | plain DeHulud's label colour |
| a switch that is off | `#6b7174` | the status colour at 55 % over the background |
| `-` in the worm meter (nothing trustworthy) | `#85969d` | the bar's grey |
| status line, hint | `#aab4b8`, `#b8c0c4` | as in plain DeHulud |

### Header: `[x] Worm  [x] Taken  [x] Dealt`

Small font, regular. Text vertically centred at y = 9 (bitmap: top row at y = 6). Three fixed strings at fixed x:

| switch | text (on / off) | x of the first character | click zone (x) |
|---|---|---|---|
| worm | `[x] Worm` / `[ ] Worm` | 6 | 0 to 56 |
| taken | `[x] Taken` / `[ ] Taken` | 60 | 57 to 116 |
| dealt | `[x] Dealt` / `[ ] Dealt` | 120 | 117 to 179 |

The last string ends at x = 172, leaving the same 6 to 7 px margin as on the left. "Off" reads two ways at once: the
box is empty and the whole string is in the off colour; "on" is a filled box in the label colour. Nothing else
changes with the state (no strike-through, no size change).

A click is a left-button press and release inside the header row (y from 0 to 17) with less than 3 px of movement:
on the release, the switch of the zone under the pointer flips. A press that moves 3 px or more is a drag and moves
the window as before; it flips nothing. Right-click in the header opens the menu as everywhere else. The three zones
cover the full row width, so the target is the whole row, not just the characters.

`Taken` and `Dealt` switch the two overlay columns. Turning one off clears its column in the overlay at once; with
both off the overlay is not on screen at all. The switches work, flip and save even when the overlay is not
available (see [When there is no overlay](#when-there-is-no-overlay)).

### Worm meter

Plain DeHulud's meter row, moved down by the header: inside its 24 px, `WORM` bold at (6, centre 12), the bar from
(44, 6) to (130, 18), the hint centred in the bar, the percent in the big font right-aligned to x = 174 at centre 12.
Nothing trustworthy shows a grey `-` in place of the percent, as in plain DeHulud.

### Status line

The status line is one for the whole program and keeps plain DeHulud's texts and colour. In Combat it is its own
section at the bottom of the box, so that `waiting for game` and `Unsupported game version` are still shown when
the worm meter is off. It is the only place that says *why* a damage column is empty: the overlay never does.

## The damage overlay

A second window that the program opens at start-up, next to the box, when the display can show it (any X server
with the SHAPE extension; the usual desktops do).

- Window title `DeHulud Combat damage`, so it can be found with `xwininfo`.
- Not managed by the desktop: no frame, no title bar, never takes focus, and it is raised above everything each
  time it appears. No menu, no drag, no entry in the config file: its place follows from the monitor.
- **Only the glyphs are the window.** The window's shape is exactly the union of the outlined digit strokes
  described below; between and around the glyphs there is no window at all, so whatever is underneath (the game)
  shows through. Its input shape is set to empty (zero rectangles), so where the display server honours input
  shapes a click lands on what is underneath, even on a digit; the window itself never reacts to one.
- **On screen only while it has at least one number to show.** As soon as both columns are empty it disappears,
  and it comes back with the next number.

### Placement and scale

Chosen once at start-up from the primary monitor (the same monitor list the program already uses for the box; no
primary = the first monitor; no monitor list = the whole X screen). With the monitor's origin `mon_x`, `mon_y` and
size `mon_w` x `mon_h` in screen pixels:

| | formula | 1280 x 720 | 1920 x 1080 | 2560 x 1440 | 3840 x 2160 |
|---|---|---|---|---|---|
| scale `s` (screen px per font px) | `max(1, (mon_h + 270) // 540)` | 1 | 2 | 3 | 4 |
| outline width `o` | `max(1, s // 2)` | 1 | 1 | 1 | 2 |
| window width `W` | `100*s + 2*o` | 102 | 202 | 302 | 404 |
| window height `H` | `50*s + 2*o` | 52 | 102 | 152 | 204 |
| window x | `mon_x + (mon_w - W) // 2` | 589 | 859 | 1129 | 1718 |
| window y | `mon_y + mon_h // 4` | 180 | 270 | 360 | 540 |

`//` is floor division in both versions, also for a monitor at a negative or offset origin. The window is
horizontally centred on the monitor and its top edge is a quarter of the way down, so the numbers sit in the middle
of the screen, about 25 % from the top. One font pixel is drawn as an `s` x `s` square of screen pixels.

### Layout, in font pixels

The window holds a 100 x 50 font-pixel area, inset by the outline width `o` on every side. Two columns, four rows
each, no labels, no column headers, no background:

```
x=0        x=45  x=55        x=100
 +-----------+   +-----------+
 |       -37 |   | 120       |  row 0, y=0,  newest
 |       -12 |   | 84        |  row 1, y=13
 |        -9 |   | 40        |  row 2, y=26   (dim)
 |           |   | 240       |  row 3, y=39   (dimmer)
 +-----------+   +-----------+  y=50
   damage taken      damage dealt
   right-aligned     left-aligned
```

| column | side | text | alignment | widest text |
|---|---|---|---|---|
| damage taken | left of centre | `-N` | right-aligned: the text ends at x = 45 (last ink column 44) | `-99999`, 45 px, from x = 0 |
| damage dealt | right of centre | `N` (no sign) | left-aligned: the text starts at x = 55 | `99999`, 39 px, to x = 94 |

- Row `i` (0 = newest, at the top) has its glyph top at y = `13*i`: rows at y = 0, 13, 26, 39 (13 px pitch: 11 px
  glyph + 2 px gap); the last row ends at y = 50. A new number goes to row 0 and pushes the others down one row;
  more than four and the oldest drops out. The two columns move independently.
- The 10 font px between x = 45 and x = 55 stay empty, so the glyph fills of the two columns are `10*s` screen
  pixels apart, either side of the monitor's centre line. The outline grows each run by `o`, so the nearest
  outlined edges are `10*s - 2*o` apart: 18 px at 1080p, 36 px at 4K.
- Glyphs: the big bitmap font of the binary, 7 x 11 digits, 5 x 11 `-`, 1 px between glyphs, never bold. The Tk
  version draws the overlay from the same digit and `-` rows as a table, so both versions put the same font pixels
  in the same places; no Tk font is used for the overlay.
- Numbers are whole points, rounded as before; a value that rounds to 0 is not drawn. Never more than five digits:
  a larger value is drawn as `-99999` / `99999`.
- Damage dealt keeps its two channels, **health** and **shield**, as two shades of blue in the one column. When a
  poll emits both, the shield numbers go in first and the health numbers after them, so the health number ends on
  top (row 0) with the shield number under it.
- **No standalone `-` is ever drawn in the overlay.** The grey `-` that the worm meter shows for "nothing
  trustworthy" has no counterpart here; the minus sign of a taken number (`-N`) is part of the number and stays. A
  poll with nothing trustworthy for a feature clears that column; the box's status line says why. A switch turned off clears its column at once. With both columns empty the window is
  off screen.

### Colours and fade

Age counts polls (4 polls per second), not wall time, so the two versions and the tests agree poll by poll. A number
is drawn at full colour for its first two polls, then in three dimmer steps, and is removed on its fifth poll: about
1.25 s on screen.

| use | full (ages 0, 1) | age 2 | age 3 | age 4 | age 5 |
|---|---|---|---|---|---|
| damage taken (red) | `#ff4d3d` | `#b63a2f` | `#792923` | `#3c1917` | removed |
| damage dealt, health (blue) | `#3d9bff` | `#2e70b6` | `#224c7a` | `#15293d` | removed |
| damage dealt, shield (light blue) | `#9cd2ff` | `#7197b6` | `#4c657a` | `#28343d` | removed |
| outline (every age) | `#0b0c0d` | | | | |

The dim steps are the colour blended towards the outline colour at 70 %, 45 % and 20 %
(`round(base + (c - base) * f)`, halves up); both versions use the literal table above, not the formula at run time.

### Strokes and outline

Every glyph is a list of horizontal pixel runs `(rx, ry, rw)` in font pixels (the same runs the binary already uses
for its text). For each run:

- the **fill** rectangle is `(o + rx*s, o + ry*s, rw*s, s)` in the row's colour;
- the **outline** rectangle is the fill rectangle grown by `o` on every side, in the outline colour.

All outline rectangles are drawn first, then all fill rectangles, so each digit has a thin dark rim (1 screen px up
to 1440p, 2 px at 4K) that keeps it readable over bright ground. The window's shape is the list of outline
rectangles, columns taken then dealt, rows 0 to 3 within each: the dark rim is the edge of the window.

### When there is no overlay

Without the SHAPE extension the program has no way to draw the numbers without a background, so it draws none:

- one line once on stderr, `damage numbers need the X SHAPE extension`, and the same line in the help text;
- no overlay window, and no damage reads at all (the poll runs with the two damage features off);
- the box is unchanged: the `Taken` and `Dealt` switches still flip, save and change the box height as above, they
  just have nothing to show.

## `-`, empty columns and `Unsupported game version`

The worm meter shows a grey `-` in place of the percent whenever the poll had nothing trustworthy for it. The two
overlay columns are simply cleared in the same case, with the status line naming the state:

| state | worm meter (box) | taken (overlay) | dealt (overlay) | status line |
|---|---|---|---|---|
| no game, not in world, no data, no permission, not started by `--launch` | `-` | empty | empty | as in plain DeHulud |
| `Unsupported game version` | `-`, hint `PE ...` in the bar | empty | empty | `Unsupported game version` |
| in the world, worm threshold unset or value invalid | `-` | numbers | numbers | `on foot, no threshold` etc. |
| in a vehicle, no own-character route in the constants, or an invalid health pair | numbers or `-` | empty | numbers | `vehicle` |
| in the world, nothing hit and nothing hitting | numbers | empty | empty | `on foot` |

A per-target failure in damage dealt (a stale handle, a vehicle target, a failed class check) is silent: that target
simply shows nothing. An empty column by itself says nothing about why: the switch may be off, the overlay may not
be available, there may be no valid target, or a drop may have rounded to 0, as well as the states in the table.
The status line is the place that names the state; do not read a failure into an empty column. With the worm meter off, the `PE ...` hint of an unsupported build is not shown
anywhere; the status line still names the state and right-click > *Help / details* has the number.

## Mocks

The box with all three on, in the world (62 px tall):

```
+------------------------------------+
| [x] Worm  [x] Taken  [x] Dealt     |  18
| WORM  [########......]        42%  |  24
| on foot                            |  20
+------------------------------------+
```

Worm off, both damage switches on, game not running (38 px):

```
+------------------------------------+
| [ ] Worm  [x] Taken  [x] Dealt     |  18
| waiting for game                   |  20
+------------------------------------+
```

All off (18 px): `| [ ] Worm  [ ] Taken  [ ] Dealt     |`, nothing else, no status line.

The overlay on a 1920 x 1080 monitor, a moment after a hit on you and one of yours that took shield and health off the
target: a 202 x 102 window at (859, 270), scale 2, and on the screen nothing but these glyphs, each with a 1 px dark
rim:

```
                          -37     120        <- row 0: red; health blue (newest)
                                  40         <- row 1: shield light blue
                                             <- rows 2, 3: empty
```

A second later the three numbers have gone through the dim steps and the window is off screen again.

## Fonts in the Tk version

The Tk version draws the box's strings at the same anchors with its default font; glyph shapes and exact text widths
differ from the bitmap font, which is why the percent is right-aligned to a fixed x. The overlay is the exception:
both versions draw it from the same bitmap digit table, pixel for pixel.

| item | Tk font | bitmap font |
|---|---|---|
| header switches, status line | `TkDefaultFont` 8 | small, regular |
| `WORM` | `TkDefaultFont` 8 bold | small, bold |
| percent, `-` in the meter | `TkDefaultFont` 11 bold | big |
| hint in the bar | `TkDefaultFont` 7 | small, regular |
| overlay numbers | the big bitmap digit table, scaled by `s` | big, scaled by `s` |

## Identical in both versions / may differ

Identical: the box's section order and heights, every x and y above, the box width, the overlay's scale, size,
position, glyph pixels, rectangle list and order, the colours and fade steps by poll age, the strings, the click
zones and the click-or-drag rule, when a column is cleared, the shield-then-health order, the five-digit cap, the
overlay's title and that it is never on screen while empty, the no-SHAPE line, the config keys (`worm`,
`damage_taken`, `damage_dealt`) and flags (`--no-worm`, `--no-taken`, `--no-dealt`), and that a click in the header
saves the clicked switch to Combat's config file (a switch set by a `--no-*` flag keeps the file's value until it is
clicked).

May differ: glyph shapes, anti-aliasing and the exact pixel width of a text in the box (hence the right-aligned
percent), the menu (Tk's own menu against the drawn one) and the help box, as in plain DeHulud.

Not covered here: Combat's terminal line (`--text`), and anything about plain DeHulud, which this page leaves as it is.
