# DeHulud - sandworm threat meter for Dune: Awakening on Linux

DeHulud shows how close you are to the sandworm attack threshold, in a tiny always-on-top window or as one
line in a terminal. It finds a running Dune: Awakening (Steam + Proton) by itself and only reads from it.
No sound, no account, no network.

```
WORM [########......]  42%
on foot
```

- **DeHulud** is the worm meter: one Python file (`dehulud.py`) or one static binary (`dehulud`).
- **DeHulud Combat** is the same meter plus damage taken and damage dealt numbers on the screen
  (`dehulud_combat.py` or `dehulud-combat`).

Unofficial fan tool. Read [Terms of service and anti-cheat](#terms-of-service-and-anti-cheat) before you use it.

## Download and run

Get `DeHulud-vX.Y.Z.zip` or `DeHulud-Combat-vX.Y.Z.zip` from the
[Releases page](https://github.com/jannejunt-hermes/dune-DeHulud/releases), unzip it into a folder of your
own and open a terminal there.

```
chmod +x dehulud      # once
./dehulud             # window
./dehulud --text      # one line in the terminal instead
```

- The binary needs nothing installed. The Python file does the same (`python3 dehulud.py`); it needs
  Python 3.9 or newer, and tkinter for the window.
- Combat: `./dehulud-combat`, or `python3 dehulud_combat.py` with `dehulud.py` in the same folder.
- Start it before or after the game. Drag the window with the left mouse button; right-click opens the menu.
- If it says `no permission`, see the next section.

Step by step, the window, placement and the config file: [docs/usage.md](docs/usage.md).

## Before you start: permission to read the game

DeHulud reads the threat value and its threshold out of the running game's memory. Linux only allows that
if your system's *ptrace* setting permits it. Check yours:

```
cat /proc/sys/kernel/yama/ptrace_scope
```

| value | what to do |
|---|---|
| `0` | nothing, DeHulud should work as is |
| `1` | **recommended:** start the game through DeHulud (Steam launch option, below), or switch to `0` |
| `2` | lower it to `1` (then use the launch option) or to `0` |
| `3` | change the file that sets it, then reboot |
| file missing | nothing to change here; another sandbox or security module may still block the read |

**Steam launch option (recommended for `1`)** - no system change needed. In Steam: right-click
Dune: Awakening > Properties > General > Launch Options, and enter

```
'/path/to/dehulud' --launch %command%
```

`./dehulud --launch` (or `./dehulud.py --launch`) prints this exact line with your path, already quoted.
**This mode is not yet confirmed with the Steam Linux Runtime container.** If the window says
`not started by --launch`, right-click > *Help / details* says what works for your setting.

**Change the setting until the next reboot:** `sudo sysctl kernel.yama.ptrace_scope=0`

**Change it permanently:** if a file under `/etc/` already sets the value, write down the old value and
change that line to `0`. Otherwise add a file of your own. Then apply it:

```
echo 'kernel.yama.ptrace_scope = 0' | sudo tee /etc/sysctl.d/99-dehulud-ptrace.conf
sudo sysctl --system
```

**Trade-off:** with `0`, any program running as your user can read the memory of your other programs
(browser, password manager), which is exactly what `1` to `3` prevent, so prefer the launch option.

What each value means, how to find the file that sets it, per-distribution notes (tkinter package, known
defaults, Steam Deck, Flatpak Steam): [docs/permissions.md](docs/permissions.md).

## What the meter shows

- **Percent** = your current threat value divided by the sandworm attack threshold. 100 % means the worm
  *may* target you (the game also checks other conditions), not "attacked now".
- **Colour:** green below 50 %, amber from 50 %, red from 75 %; grey when there is no value.
- **`-` instead of a number** (never a fake `0%`) whenever there is nothing trustworthy to show: no game,
  menus and loading screens, a failed check, or no threshold (for example outside a worm area).
- **Status line:** what it is reading (`on foot`, `vehicle`) or why there is no value.

Not yet confirmed in a live game: whether the percent matches the game's own threat indicator. Every status
and the details: [docs/usage.md](docs/usage.md#what-the-meter-shows).

## Supported game versions

DeHulud supports the current game version only; after a game update you need a new DeHulud release.

| game build | PE timestamp | SizeOfImage |
|---|---|---|
| 26592269 | 1794396660 (2026-11-11 11:31 UTC) | 217272320 |

**After a game update** DeHulud shows `-` and `Unsupported game version`, never a guess, until a new
DeHulud release replaces the supported build.

## DeHulud Combat

The same worm meter, plus damage numbers in the middle of the primary monitor with no background: damage
taken in red on the left, damage dealt on the right (enemy health purple, shield light blue). The meter box
has three one-click switches, and a switched-off part does no reads:

```
[x] Worm  [x] Taken  [x] Dealt
```

The numbers come from health and shield drops read about four times a second, so they have limits: hits
within one poll merge into one number, healing hides damage, and other players' hits on the same enemy count
too. Details: [docs/combat.md](docs/combat.md).

## Read-only and no network

- It reads game memory only with `process_vm_readv`. It never writes to the game, never attaches a debugger,
  never sends signals, injects nothing and simulates no input.
- It opens no network connection of any kind (no update check, no telemetry). The window only uses an X
  display on this computer.
- The worm meter does roughly 60 to 144 small reads per second.

Exact files and reads, how it finds the value, and what the source lint does and does not prove:
[docs/how-it-works.md](docs/how-it-works.md).

## Terms of service and anti-cheat

DeHulud does not change the game, but reading another program's memory may still be against the game's
terms of service, and anti-cheat software may treat it as suspicious. Nobody can promise that it is safe
for your account. This applies to DeHulud Combat in the same way. **Use at your own risk.**

DeHulud is an unofficial fan tool. It is not affiliated with or endorsed by Funcom or the rights holders
of Dune.

## More

- [Using DeHulud](docs/usage.md): first run step by step, window and placement, every status, uninstall.
- [Permission to read the game](docs/permissions.md): the full ptrace guide and per-distribution notes.
- [DeHulud Combat](docs/combat.md): switches, config file, what the damage numbers can and cannot show.
- [Rust version](docs/rust.md): build from source, differences from the Python version, its tests.
- [How it works](docs/how-it-works.md): what it reads and how much.
- [Development](docs/development.md): the test suite and what was checked live.

**Uninstall:** delete the files and the config folders `~/.config/dehulud` and `~/.config/dehulud-combat`,
remove the Steam launch option, and undo any ptrace change ([how](docs/usage.md#uninstall)).

The ZIP files do not include the `docs/` pages; they are at
https://github.com/jannejunt-hermes/dune-DeHulud/tree/main/docs.

## License

MIT. See [LICENSE](LICENSE).
