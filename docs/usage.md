# Using DeHulud

## Running it

Requirements: Linux, Python 3.9 or newer (tested with 3.11, 3.12 and 3.13; `python3 --version` shows
yours), and tkinter for the window (without tkinter it falls back to text mode and tells you which package
to install).

**The first time, step by step:**

1. Download `dehulud.py` from the project page, or one of the ZIP files there, then unzip it: right-click the
   ZIP > *Extract*, or `unzip` in a terminal. `DeHulud.zip` holds `dehulud.py`, the `dehulud` binary and the
   README; `DeHulud-Combat.zip` holds `dehulud.py`, `dehulud_combat.py`, the `dehulud-combat` binary and the
   README (see [DeHulud Combat](combat.md)).
2. Put `dehulud.py` in a folder of your own and leave it there, for example a new folder `dehulud` in your
   home folder. The Steam launch option, if you use it, points to this place.
3. Open a terminal in that folder: in the file manager, right-click inside the folder > *Open Terminal
   Here* (Dolphin: *Open Terminal*, or F4; GNOME Files: *Open in Terminal*). Or open any terminal and type
   `cd ~/dehulud`.
4. Make the file executable, once: `chmod +x dehulud.py`
5. Check [permission to read the game](permissions.md), then start it: `./dehulud.py`

```
./dehulud.py                  # window
./dehulud.py --text           # one line in the terminal instead
./dehulud.py --launch CMD...  # start CMD (Steam's %command%) and read the game it starts
python3 dehulud.py            # the same without chmod
```

Start it before or after the game; it waits for the game and notices when the game exits.

**The window** is about 180 x 44 pixels, always on top and frameless. Drag it with the left mouse
button. Right-click opens the menu: *Window frame* (show/hide the title bar), *Reset position*,
*Help / details* (the full message behind `no permission` and similar states) and *Quit*. Its position is
remembered in `$XDG_CONFIG_HOME/dehulud/config.json` (normally `~/.config/dehulud/config.json`); a damaged
config file is ignored. Without `HOME` (and without an absolute `XDG_CONFIG_HOME`) no position is kept: DeHulud
does not look the home folder up in the user database, because that can involve a local name service. (With
`HOME` unset, the Python interpreter's own start-up may still do that lookup; the Rust version does not.)

**Placement:** the first time, it opens at the top-right of your main screen (with several screens it
picks a real screen when the display reports its monitors through XRandR); *Reset position* puts it back
there. It is meant to stay above games in *windowed* or *borderless windowed* mode and works on a second
screen. In *exclusive fullscreen* the game may cover it. On Wayland desktops the window runs through XWayland and staying on top is up to your
compositor: checked on KDE Plasma (Wayland) over the running game in fullscreen, with three screens.

## What the meter shows

- **Percent** = your current threat value divided by the sandworm attack threshold, rounded down to a
  whole percent and capped at 0-100 %. The bar is the same ratio.
  100 % means you are at or above the threshold from which the worm *may* target you (the game also
  checks other conditions, so it does not mean "attacked now").
- **Colour:** green below 50 %, amber from 50 % to below 75 %, red from 75 %; grey when there is no value.
- **`-` instead of a number** (never a fake `0%`) whenever there is nothing trustworthy to show: no game,
  not in the world (menus, loading), a type check of the route failed, a value is not a number or negative,
  or the threshold is missing or `<= 0` (for example outside a worm area). `0%` is a real reading: because
  the percent is rounded down, it means a valid threat below 1 % of the threshold (a small non-zero threat
  shows `0%` too), never a missing value.
- **Status line:**

| status | meaning |
|---|---|
| `on foot` / `vehicle` | reading the character's / the driven vehicle's threat (the vehicle's, like the game's own meter, while you drive) |
| `on foot, no threshold` / `on foot, no value` | in the world, but the threshold is unset (`<= 0`) or the value is invalid: shows `-` |
| `waiting for game` | the game is not running (or not loaded yet) |
| `not in world` | game found, but no player in a world yet (menus, loading screens), or the player controls no pawn |
| `no data` | a type check failed or memory moved during the read; usually only during loading, or for a moment when the controlled pawn changes (getting on or off a vehicle) |
| `Unsupported game version` | a game build DeHulud does not know; the bar area shows its PE timestamp |
| `no permission` | see [permission to read the game](permissions.md); right-click > *Help / details* shows the exact fix for your setting |
| `not started by --launch` | launch-option mode, but Steam started the game outside DeHulud and your ptrace setting (`1` to `3`) does not allow reading it; *Help / details* says what works |

Not yet confirmed in a live game: whether the two values are kept up to date on your PC (the server
replicates them) and whether the percent matches the game's own threat indicator. The game's own widget
is drawn by game scripts DeHulud cannot see. If DeHulud stays at `-` (`no threshold`) or at `0%` while the
game shows threat, that is the reason, not a fault of your setup.

## Supported game versions

| game build | PE timestamp | SizeOfImage |
|---|---|---|
| 26548928 | 1794246991 (2026-11-09 17:56 UTC) | 217268224 |
| 26333948 | 1793384724 (2026-10-30 18:25 UTC) | 220024832 |
| 26224975 | 1793030166 (2026-10-26 15:56 UTC) | 219996160 |
| 26083551 | 1792504044 (2026-10-20 13:47 UTC) | 220008448 |

DeHulud identifies the build from the game's own PE header in memory (TimeDateStamp + SizeOfImage) and
re-checks those two numbers on every poll. That is a quick check of two header fields, not a checksum of
the game file.
**After a game update** the offsets move: DeHulud then shows `-` and `Unsupported game version` with the new
build's PE timestamp, never a guess. It needs a new DeHulud release with that build in its builds table
(`BUILDS` in `dehulud.py`).

## Uninstall

1. Delete `dehulud.py` and/or the Rust binary `dehulud`, and the config folder `~/.config/dehulud` (or
   `$XDG_CONFIG_HOME/dehulud`). For DeHulud Combat also delete `dehulud_combat.py` and/or the `dehulud-combat`
   binary, and the config folder `~/.config/dehulud-combat` (or `$XDG_CONFIG_HOME/dehulud-combat`).
2. Remove the Steam launch option if you added one (Steam > Dune: Awakening > Properties > General >
   Launch Options: delete the line).
3. If you changed the ptrace setting, put back what was there before:
   - Changed only with `sudo sysctl kernel.yama.ptrace_scope=0`: a reboot restores it, or set your old
     value now, for example `sudo sysctl kernel.yama.ptrace_scope=1`.
   - Created `/etc/sysctl.d/99-dehulud-ptrace.conf`: `sudo rm /etc/sysctl.d/99-dehulud-ptrace.conf`, then
     `sudo sysctl --system`. That applies a packaged file's value again; if no file sets the value, the
     kernel's default only returns with a reboot (or set the old value with `sudo sysctl` as above).
   - Edited a line in an existing file: set that line back to the old value you wrote down, then run
     `sudo sysctl --system`.
   - Fedora, if you used them: `sudo dnf remove yama-ptrace-enable`, and `sudo setsebool deny_ptrace on`
     if you switched SELinux's `deny_ptrace` off (add `-P` if you used `-P`).
