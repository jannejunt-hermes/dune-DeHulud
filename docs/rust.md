# Rust version

The folder `rust/` holds the same meter written in Rust: **one static binary, no Python and no Tk needed**,
nothing else to install. It finds the game the same way, checks the same game build (and re-checks it on every
poll), reads the same two values with the same type checks and owner rules, and shows the same window, menu,
statuses and terminal line. It uses the same config file (`$XDG_CONFIG_HOME/dehulud/config.json`), so a
position saved by one version is used by the other. (One small difference: the Rust version reads a config
file nested at most 500 levels deep and uses the defaults for a deeper one. DeHulud itself only ever writes a
flat file, so this matters only for a hand-edited file.)

**Run the prebuilt binary** (when you have one): put the file `dehulud` in a folder of your own, open a
terminal in that folder and run

```
chmod +x dehulud              # once
./dehulud                     # window
./dehulud --text              # one line in the terminal
./dehulud --launch CMD...     # Steam launch option, as for the Python version
```

For the Steam launch option enter `'/path/to/dehulud' --launch %command%`; `./dehulud --launch` prints that
exact line with your path, already quoted.

**Build it from source:** install Rust with [rustup](https://rustup.rs), then

```
rustup target add x86_64-unknown-linux-musl
cd rust
RUSTFLAGS="--remap-path-prefix=$HOME=~" cargo build --release --target x86_64-unknown-linux-musl
```

The binary is `rust/target/x86_64-unknown-linux-musl/release/dehulud`: one static executable of about 0.7 MB
for x86-64 Linux. The `RUSTFLAGS` part is optional; it keeps your home folder's path out of the
binary (Rust stores source file paths for its error messages), which matters if you pass the file on. It uses
two libraries (crates): `libc` (system calls such as `process_vm_readv`) and `x11rb` (the X11 protocol, written in
Rust, with the RandR extension for the monitor list); no system library is needed.

**Permission:** [permission to read the game](permissions.md) applies unchanged: the same `ptrace_scope` rules, the same
launch option, the same messages (*Help / details*, or the terminal).

**Reads:** the same as the Python version (see [How much it reads](how-it-works.md)): 4 polls per second, 16 fixed reads
on foot / 15 in a vehicle plus one per class-hierarchy step, so 84 / 80 reads per second in the test layout,
and only a look at `/proc` every 2 seconds while the game is not found.

**Differences from the Python version:**

- The window, the right-click menu and the *Help / details* box are drawn by DeHulud itself, with a bitmap font
  built into the binary (no toolkit, no fonts from your system). The text therefore looks pixel-style instead
  of your desktop's font; positions, sizes and colours are the same. *Help / details* opens a small window
  titled `DeHulud help`; a click or a key closes it.
- The window opens the X display itself, through the display's Unix socket: first the socket file
  `/tmp/.X11-unix/XN` (what sandboxes and containers pass on to the programs inside them), then the abstract
  socket `@/tmp/.X11-unix/XN` (for a program with its own private `/tmp`). It never tries TCP. `DISPLAY` must
  be a display on this computer (`:N`, `:N.S`, `unix:N`), as for the Python version; anything else gives the
  text meter and a one-line reason.
- Without a local display the message says that the window needs an X11 or XWayland display (there is no
  tkinter to install), and it does not read `/etc/os-release`.
- Ctrl-C in the terminal that started it also closes the window cleanly and keeps its position (the Python
  version prints an error there). With the window frame on, the saved position is the top-left corner of the frame,
  taken from the window manager's frame size (`_NET_FRAME_EXTENTS`).
- Messages from the operating system are worded the Rust way (for example `No such file or directory` without
  Python's `[Errno 2]`).

**Its tests** (in `rust/`):

```
cargo test                                      # unit tests, source lint, comparison with dehulud.py,
                                                # and the binary as built against the fake game in a
                                                # private PID namespace (unshare, no root needed;
                                                # skipped where that is not available)
cargo test --release --features test-source     # also: the fake-game scenarios of the Python tests,
                                                # and the window on a private headless compositor
```

`test-source` is a test-only build option: it lets the tests point the meter at their own fake game and record
each poll. The normal build commands above never enable it (the code is not compiled in); only a build that
names `--features test-source` - such as the test command above, even with `--release` - contains it, and a
binary built with it refuses to run without the test's control file. Share only binaries from the normal build. The Python tests (`python3 -m unittest discover -s tests`) are unchanged
and cover the Python version.
