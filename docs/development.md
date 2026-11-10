# Development

```
python3 -m unittest discover -s tests
```

The tests start a fake game: a child Python process that lays out the whole route (fake PE header, class
objects, pointers and the two floats) in its own memory, and DeHulud reads it with `process_vm_readv`
through an injected `/proc` source that only lists that child. They cover build matching, on foot, vehicle,
owner selection (a pawn that fails its check is `-`), the same process exec'ing into another image,
`LocalPlayers` empty, every type check, invalid values, permission errors for each `ptrace_scope` value
(simulated), `--launch` for each value with and without the game descending from DeHulud, the game exiting
during a poll, the local-display check, quoting of printed commands, config handling and text mode. The
GUI test builds the real window only on a private headless compositor (`kwin_wayland --virtual --xwayland` under its own
D-Bus session and runtime directory) and is skipped when that or tkinter is missing; it never uses your
desktop's display. Checked live once, on one PC: KDE Plasma (Wayland), native Steam, the game in
fullscreen. Not tested: `--launch` under the real Steam Linux Runtime, Flatpak Steam, other desktops and
other distributions.

The Rust version has its own tests: see [Rust version](rust.md).
