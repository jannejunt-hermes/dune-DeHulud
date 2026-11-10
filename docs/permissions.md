# Permission to read the game

DeHulud reads the threat value and its threshold out of the running game's memory. Linux only allows
that if your system's *ptrace* setting permits it. Check yours:

```
cat /proc/sys/kernel/yama/ptrace_scope
```

| value | meaning | what to do |
|---|---|---|
| `0` | no extra restriction: a program may read your other programs under the normal rules (same user, the game not sandboxed or made unreadable, no security module refusing) | nothing, DeHulud should work as is |
| `1` | a program may read only its own descendants (the programs it started, and theirs) | **recommended:** start the game through DeHulud (Steam launch option, below), or switch to `0` |
| `2` | only programs with the `CAP_SYS_PTRACE` capability (normally only root) may read other programs | lower it to `1` (then use the launch option) or to `0` |
| `3` | no program may, and the value cannot be lowered until a reboot | change the file that sets it (below), then reboot |
| file missing | the Yama module is not active, or the setting is hidden (for example inside a container); a missing file does not prove that nothing restricts the read | nothing to change here; another sandbox or security module may still block it |

**Steam launch option (recommended for `1`)** - no system change needed. In Steam: right-click
Dune: Awakening > Properties > General > Launch Options, and enter

```
'/path/to/dehulud.py' --launch %command%
```

with the real path of the file, inside the single quotes: Steam runs this line as a shell command, so
a path with a space in it (a folder named `My Games`, for example) would otherwise be split into two
words and the game would not start. Make the file executable once (`chmod +x dehulud.py` in its
folder); then `./dehulud.py --launch` there prints this exact line with your path, already quoted (that
also works for a path that contains a `'`). Steam then starts the game as a child of DeHulud, which `1`
allows; DeHulud closes when the game exits. **This mode is not yet confirmed with the Steam
Linux Runtime container**: if Steam turns out to start the game outside DeHulud, the launch option cannot
work. The window then says `not started by --launch`, and right-click > *Help / details* says what does
for your setting: with `1` or `2`, switch to `0` (below) and start DeHulud by itself, without the launch
option; with `3`, the same after a reboot. With `0` a `--launch` DeHulud reads such a game anyway.

**Change the setting until the next reboot:**

```
sudo sysctl kernel.yama.ptrace_scope=0
```

**Change it permanently:** first look for a file that already sets it:
`grep -rs ptrace_scope /etc/sysctl.d /run/sysctl.d /usr/lib/sysctl.d /usr/local/lib/sysctl.d /etc/sysctl.conf`.

- If a file under `/etc/` sets it: **write down the old value**, change that line to `0`, then run
  `sudo sysctl --system` (or reboot, if the old value was `3`).
- Otherwise (nothing sets it, or only a packaged file under `/usr/lib/`, `/usr/local/lib/` or `/run/`):
  add a file of your own. Of several files that set the same value, the one whose name sorts last wins,
  so this file overrides the packaged one without touching it or its other settings:

  ```
  echo 'kernel.yama.ptrace_scope = 0' | sudo tee /etc/sysctl.d/99-dehulud-ptrace.conf
  sudo sysctl --system
  cat /proc/sys/kernel/yama/ptrace_scope
  ```

  The last line should print `0` (with `3` it cannot change before a reboot). Do not create a file with
  the *same name* as a packaged one: it replaces the packaged file completely, with all of its other
  settings.

**Trade-off:** with `0`, any program running as your user can read the memory of your other programs
(browser, password manager), which is exactly what `1` to `3` prevent, so prefer the launch option.

## Per-distribution notes

The sysctl commands above are the same everywhere (`/etc/sysctl.d/` is read at boot by
`systemd-sysctl` on all of the systems below). Defaults below are linked to their source and
can change with a release, so check yours with `cat /proc/sys/kernel/yama/ptrace_scope` and follow the table at the top of this page.

| distribution | install tkinter (for the window) | ptrace setting |
|---|---|---|
| Ubuntu, Linux Mint, Pop!_OS | `sudo apt install python3-tk` | default `1`, set by the file `/etc/sysctl.d/10-ptrace.conf` that ships with the system ([Ask Ubuntu](https://askubuntu.com/questions/146160/what-is-the-ptrace-scope-workaround-for-wine-programs-and-are-there-any-risks)): use the Steam launch option, or edit the value in that file to `0` and run `sudo sysctl --system` |
| Debian | `sudo apt install python3-tk` | Debian's kernel ships the patch "yama: Disable by default" (named in the Debian kernel changelog, `/usr/share/doc/linux-image-*/changelog.gz`), so the value is `0` unless something sets it |
| Fedora | `sudo dnf install python3-tkinter` | Fedora 45 and later: default `1` unless a debugger such as `gdb` is installed; `sudo dnf install yama-ptrace-enable` switches it to `0` the Fedora way. Fedora 44 and earlier: `0` ([Fedora change page](https://fedoraproject.org/wiki/Changes/Restrict_ptrace_by_default)). Check your value either way. Fedora also has the SELinux switch `deny_ptrace`: `getsebool deny_ptrace` must say `off` (`sudo setsebool deny_ptrace off`) |
| Arch, Manjaro, EndeavourOS | `sudo pacman -S tk` | Arch: default `1` ([ArchWiki, Security](https://wiki.archlinux.org/title/Security)); Manjaro and EndeavourOS use their own kernels, so check your value |
| openSUSE (Tumbleweed, Leap) | `sudo zypper install python3-tk` | check your value |
| SteamOS (Steam Deck) | the system is read-only: if `python3 -c "import tkinter"` fails, use `--text` in Desktop Mode (Konsole). Unlocking the system to install packages is undone by updates and not recommended | check your value. `sudo` needs a password: set one with `passwd` in Desktop Mode. `sudo sysctl ...` works until reboot; whether a file in `/etc/sysctl.d/` survives SteamOS updates is not verified |

**Steam Deck Game Mode:** untested. Game Mode shows one window at a time, so DeHulud's window is not
expected to be visible there and could confuse which window is shown; use Desktop Mode.

**Flatpak Steam:** the game then runs inside the Flatpak sandbox. What is known: DeHulud finds the game by
its process and file name, which the sandbox does not hide from your desktop session, and the kernel
permission rules above still apply. What is not known (not tested): whether reading a sandboxed game works
with `ptrace_scope` `0`, and whether `--launch` works at all inside the Flatpak (the launch option runs
inside the sandbox, which must be able to see `dehulud.py`, run Python 3 and open a window, and the
sandbox may block the read). The one live check so far used the native (non-Flatpak) Steam package (see
[Development](development.md)).

To undo a change, see [Uninstall](usage.md#uninstall), step 3.
