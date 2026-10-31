# Motorhead (PC, 1998) on modern PCs and the Steam Deck

## Why this exists

When Motorhead came out in 1998 it was mind-blowing: smooth graphics and an amazing soundtrack.
The PlayStation version plays just as well, but the PC version is technically miles ahead, with
improved graphics, effects and car models. Getting it running today means fighting a 16-bit
installer, a CD check, CD-audio music, a DirectX 5 / 3dfx Glide renderer and volume sliders that
no longer do anything. This kit sorts all of that out, so the PC version can be played again.

## What this does

Turns **your own** European Motorhead CD, plus the official patches 3.0 and 3.1, into a folder that
runs on the Steam Deck (Proton) or on Windows 10/11, with no installer and no registry entries:

- **Installed straight from the CD's archives** and patched to 3.0 + the 3.1 `motor.exe` (fixes
  the invisible HUD on modern graphics cards and a crash at the end of races), without running any
  1998 installer.
- **CD soundtrack** from OGG files ripped from your disc.
- **3dfx Glide and Direct3D** through dgVoodoo2 (on the Deck: Vulkan via DXVK), rendered sharper
  than the original resolution, with the frame rate held where the physics expect it.
- **Sound effects brought down to sit with the music** (-14 dB): the game's volume sliders use an
  old Windows mixer API that no longer does anything.
- **The CD check**: on the Steam Deck the launch script presents a folder of your CD's files as a
  CD-ROM drive, and the game's own check passes unchanged. On Windows it's your choice (below).

**No game files are in this repository.** Everything from the game comes from your disc and the
official patches when you run `build.py`.

## What you need

| | |
|---|---|
| The game | The **European Motorhead CD** (1998, volume label `MOTORHEAD`, installer in `MOTOR\DISK1`) as `.cue` + `.bin` or CloneCD `.ccd` + `.img`. `build.py` checks the game files and stops on another edition (OEM bundle discs, with everything in an `MHEAD` folder, aren't supported yet). |
| Patch 3.0 | `motorp30.exe` (26 March 1999), from [motorhead.cc's patch page](https://motorhead.cc/download_patches.php). Also known as `mhp30.exe`. Keep it as downloaded; it isn't run. |
| Patch 3.1 (European) | `motorp31_euro.zip` (30 October 2000), from the same page. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| An OGG encoder | `oggenc` (vorbis-tools; Windows builds at rarewares.org) or `ffmpeg`, on the PATH. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |
| ogg-winmm | by AyuanX: [GitHub releases](https://github.com/ayuanx/ogg-winmm/releases) (tested with v2025.01.16). Keep the zip as downloaded. |

## Build

For the Steam Deck:

```
python3 build.py MOTORHEAD.cue --patch30 motorp30.exe --patch31 motorp31_euro.zip \
    --dgvoodoo dgVoodoo2_79_3.zip --ogg-winmm ogg-winmm_binary.zip
```

creates `Motorhead/` with `game/`, `cd/` (the CD's files, for the fake CD-ROM drive) and
`motorhead_launch.sh`. It takes under a minute.

For Windows, add `--windows` (frame rate held by vsync instead of a cap, Glide rendered at 2x).
Then the CD check:

- **default**: `motor.exe` gets a 6-byte change so it finds the intro videos (`movies\movies.pak`,
  copied from your CD) in the game folder instead of looking for a CD-ROM drive. Nothing else in
  the game is changed.
- **`--keep-cd-check`**: `motor.exe` stays exactly as Gremlin released it, and `build.py` writes
  `Motorhead-disc.iso` (your CD's data track). Double-click it to mount it before playing.

`--sfx-db` sets the sound effect level (default -14; 0 leaves them as on the disc). `--out DIR`
puts the result somewhere else.

## Play on the Steam Deck

1. Copy `Motorhead/` to the Deck, for example to `/home/deck/Games/Motorhead/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../Motorhead/game/motor.exe`.
   Rename the shortcut "Motorhead".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/Motorhead/motorhead_launch.sh %command%
   ```
5. Launch. The first run creates the Proton prefix, adds the fake CD-ROM drive, restarts Wine
   once, then starts the game: Smacker intro, then the menu. If the first launch asks for the CD,
   launch once more. `launch.log` beside the script shows what it did.
6. Steam Input: the "Gamepad with Mouse Trackpad" template works for the menus; or map the D-pad /
   left stick to the arrow keys, A = Enter, B = Esc, X / Y = S / A for gears.

If you move or rename the folder, fix the shortcut and the launch option; the script repairs its
fake drive on the next run.

## Play on Windows

Run `game/motor.exe` (with `--keep-cd-check`, mount `Motorhead-disc.iso` first). Windows may ask
to install the legacy **DirectPlay** component; let it.

## In the game

- Options > Graphics: choose **3Dfx Glide** (dgVoodoo's Direct3D path draws the shadows wrongly)
  and a resolution. Leave "Z Read" off.
- Options > Controls: Keyboard or Joystick (the Deck shows up as a DirectInput joystick).
- Settings, hiscores and leagues are saved inside `game/` (`Game\MotorHead.CFG`, `HiScores\`,
  `League\`), so the folder is portable.

## Tuning

- `game/dgVoodoo.conf`: `[Glide] Resolution` (`unforced`, `2x`, ...), `[General] ScalingMode`.
  **The physics depend on the frame rate**: at very high rates nobody can steer. The Deck build
  caps at 60 (`FPSLimit`); the Windows build relies on vsync, fine up to about 250 Hz. Without
  dgVoodoo, cap the frame rate in the graphics driver.
- Music level: `CDDAVolume` in `game/winmm.ini` (0-100).
- Sound effects: rebuild with another `--sfx-db`.
- Course music: `CDTrack_*` and `MenuCDTrack` in `game/Game/MotorHead.CFG`.
- Deck renderer: put `RENDERER=wined3d` (plain Wine DirectDraw/Direct3D) or `RENDERER=d7vk`
  (GE-Proton 11+) before the script path in the launch options. Default: dgVoodoo for everything.

## Troubleshooting

- *"Please insert Motorhead CD"* (Deck): look at the `drive letters:` and `registry Drives:` lines
  in `launch.log`; a letter must point at `.../Motorhead/cd` and be marked `cdrom`. The first
  launch after a change can fail; launch again.
- *No music*: `launch.log` must show `WINEDLLOVERRIDES=winmm=n,b;...`, and `game/Music/Track02.ogg`
  must exist.
- *Black screen or crash entering a race*: try the other in-game renderer, or `RENDERER=wined3d`.
- *"Couldn't find a valid screenmode for menu 640x400,8"*: the menu needs an 8-bit DirectDraw
  mode; dgVoodoo provides one, plain Wine/Windows DirectDraw may not.
- *Cars drive straight into the first corner*: frame rate too high (see Tuning).
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: installs from the CD's InstallShield archive, applies patch 3.0's European files and the 3.1 exe, rips the soundtrack, quietens the effects, adds the wrappers and settings. Python standard library only. |
| `installshield5.py`, `mscab.py`, `disc.py` | Readers for the 1998 InstallShield 5 cabinets, the Microsoft cabinet inside `motorp30.exe`, and the CD image. Each runs on its own too. |
| `config/dgVoodoo-deck.conf`, `config/dgVoodoo-windows.conf` | dgVoodoo2 settings for each build. |
| `steamdeck/motorhead_launch.sh` | Proton launch wrapper: DLL overrides and the fake CD-ROM drive. |
| `docs/TECHNICAL.md` | How each part works. |

## Credits

- **Digital Illusions** (now DICE) made Motorhead; **Gremlin Interactive** published it. Please own
  the game: this kit needs your disc.
- **motorhead.cc**, for keeping the official patches and the game's history online.
- **Dege**: dgVoodoo2. **AyuanX**: ogg-winmm.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, its patches, dgVoodoo2 or ogg-winmm.

Not affiliated with or endorsed by the game's rights holders.
