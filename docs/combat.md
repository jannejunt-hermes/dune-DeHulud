# DeHulud Combat

**DeHulud Combat** is a second, separate program: the same worm meter as plain DeHulud, plus **Damage taken**
and **Damage dealt** numbers on the screen. Plain DeHulud stays exactly as described in [Using DeHulud](usage.md); run Combat
instead if you want the damage numbers. Its window is titled `DeHulud Combat`, so you can tell the two apart, and
[permission to read the game](permissions.md) applies unchanged.

```
python3 dehulud_combat.py    # needs dehulud.py in the same folder
./dehulud-combat             # the Rust binary (chmod +x dehulud-combat once, as for dehulud)
```

Its meter box keeps a header row with three switches, and below it the worm meter and the status line:

```
[x] Worm  [x] Taken  [x] Dealt
```

One click on a label switches that part on or off. A switched-off worm meter disappears and the box shrinks to
fit; a switched-off damage column clears at once, and Combat does no reads for it. With all three off only the
header row is left, so you can switch one back on. The damage numbers themselves no longer show in the box:
they appear in the middle of the primary monitor, about a quarter of the way down from the top, as numbers
with no background - damage taken in red on the left, damage dealt on the right (enemy health purple, shield
light blue). The numbers need an X server with the SHAPE extension, which the usual desktops have; without it
Combat prints one line (`damage numbers need the X SHAPE extension`) and shows no damage numbers.

Combat has its own config file, `$XDG_CONFIG_HOME/dehulud-combat/config.json` (normally
`~/.config/dehulud-combat/config.json`), separate from plain DeHulud's. The switches are in it as `worm`,
`damage_taken` and `damage_dealt`: booleans, all `true` (on) by default. The flags `--no-worm`, `--no-taken` and
`--no-dealt` switch one of the three off for that run only: they override the config file and are not saved. A
click on a label, on the other hand, is saved to the config file, so it stays as you left it; one switched off
only by a flag keeps its saved value until you click its label. Text mode (`--text`) shows only the worm
meter, so it refuses `--no-worm` (`--no-taken` and `--no-dealt` are accepted there and change nothing); started
with `--launch`, the game still starts, just without the meter. All of this is the same for `dehulud_combat.py`
and the `dehulud-combat` binary.

As with the worm meter, a failed check shows `-`, never `0`, and never another character's value; for the
damage numbers a failed check clears that column instead, and the box's status line says why. A game build
Combat does not know shows `Unsupported game version`. Both programs support the current game version only;
after a game update you need a new DeHulud release.

**Damage taken** shows your own character's health drops. Combat reads your current health about four times a
second (once per poll) and shows each drop since the last poll as a red `-N`, rounded to whole points; a drop
that rounds to `0` shows nothing. The newest number is on top, at most 4 are visible, and each fades after about
a second. **Limits:** two hits within one poll merge into one number. Healing in the same poll hides part or all
of a hit. The number is a net health drop, not the weapon's damage.

**Damage dealt** shows health and shield lost by the enemies you fight, in the one column on the right: health
in purple and shield in light blue, without a minus sign. It shows up to 4 numbers, the newest at the top, each
fading after about a second. Hits within the same poll merge into one number. Tracked are the enemy you are
aiming at, your melee soft-lock target, and the last 4 distinct enemies you aimed at, each kept for 18 seconds
after you last aimed at it. Only characters count. **Limits:** other players' hits on the same enemy count too.
Healing or regeneration hides damage. A killing blow shows at most the health that was left. Only aimed,
soft-locked and recently aimed enemies are tracked. Vehicles show nothing.
