# Read-only and no network: what DeHulud does and does not do

DeHulud Combat follows the same rules (read-only and no network) and reads health and shield for its damage
sections the same way; the read counts below are for the worm meter.

- It reads `/proc/<pid>/cmdline`, `/proc/<pid>/maps` and `/proc/<pid>/status` of processes that belong to
  you, `/proc/sys/kernel/yama/ptrace_scope`, `/etc/os-release` (only to name the tkinter package) and its
  own config file.
- It reads game memory only with `process_vm_readv`. It never writes to the game, never attaches a
  debugger (no ptrace attach), never sends signals, injects nothing, simulates no input, and opens no
  network connection of any kind (no update check, no telemetry). `--launch` only starts Steam's command
  as a normal child process and waits for it.
- The window only uses an X display on this computer: `DISPLAY` must be `:N` or `unix:N` (optionally with a
  screen, `:N.S`). A display on another machine (`host:N`, or `localhost:N` as set by `ssh -X`) is refused
  before anything graphical is loaded, and DeHulud runs as the text meter with a one-line explanation. It
  hands Tk the display as `unix/:N`, the form with which Xlib uses only the display's Unix socket: with a
  plain `:N` Xlib falls back to a TCP connection on `localhost` when that socket cannot be reached.
- A source lint in the test suite checks the code of `dehulud.py`: it fails if the file contains a
  memory-write, debugger, signal, process-kill or network call, or imports a network module. That is a
  check of this file's text, not complete enforcement: it cannot see what libraries such as Tk and Xlib do
  at run time (the display check above covers the window's connection), and it is not a sandbox.

**How much it reads.** 4 polls per second. While the game is not found it only looks at `/proc` every
2 seconds. Once found: one 1024-byte read of the PE header and 8 reads of class pointers, then per poll
a fixed **16 reads on foot / 15 in a vehicle** plus one read for every class-hierarchy step the type checks
walk (0-4 steps per check, five checks), i.e.:

| | reads per poll | reads per second |
|---|---|---|
| on foot | 17 - 36 | 68 - 144 |
| in a vehicle | 15 - 35 | 60 - 140 |
| test layout (the fake game's class chains: 1-2 steps per check) | 21 on foot / 20 vehicle | **84 / 80** |

One of the fixed reads re-reads the start of the game's PE header (up to SizeOfImage: the header offset
`e_lfanew` + 88 bytes, 216 bytes in the test layout), so that a different program image under the same
process id is noticed and identified again instead of being read with the old build's offsets. The other
reads are 8 bytes (a pointer), 12 bytes (the local-players array) or 24 bytes (threat value and threshold
together); about 400 bytes per poll in the test layout.

**How it finds the value.** From the game's GWorld slot: World > GameInstance > LocalPlayers[0] (the
array size is checked before element 0 is read) > PlayerController > the possessed pawn (`Pawn`). If that
pawn is a vehicle (ADuneVehicle) it reads the vehicle's `m_SandwormThreatSourceComponent`; if it is the
player character (ADuneCharacter and ADunePlayerCharacter) and also the controller's `AcknowledgedPawn`, the
character's. Any other pawn, or none, shows `-`: DeHulud never falls back to another object's value. Then it
reads the component's `m_CurrentThreatBlobValue` and `m_CurrentSandwormAttackThreshold`. Every object on the
way is type-checked against the game's own class pointers, so a moved or freed object normally fails a
check and shows `-` instead of garbage. A type check cannot catch everything: memory that was freed and
then reused by another object of the same type passes it. Every offset in `dehulud.py` is commented with
the game member it reads.
