# How it works

Notes on the European retail release of Motorhead (Digital Illusions / Gremlin, April 1998, disc
label `MOTORHEAD`) with the official patches 3.0 (26 March 1999) and 3.1 (30 October 2000).
Addresses are virtual addresses in the European 3.1 `motor.exe` unless stated.

## Installing without the installer

The disc's installer is a 16-bit InstallShield launcher (`MOTOR\DISK1\SETUP.EXE`), which 64-bit
Windows can't run and Wine runs badly. The files it copies are in `MOTOR\DISK1\DATA1.CAB`, an
InstallShield 5 cabinet with its header inside. `installshield5.py` reads it (layout as documented
by the unshield project); this early version stores no usable MD5s, so each file is checked for
its size and for every compressed chunk ending cleanly, and `build.py` then checks `motor.exe`
against the European disc's.

The installer copies three file groups, `Data`, `Spawned` and `Program Executable Files`, all into
the game folder; the cabinet's directory names (`Cars\car01`, `Tracks\track3\Packed`, ...) give
the layout.

Patch 3.0 (`motorp30.exe`) is a self-extracting Microsoft cabinet (MSZIP) holding another
InstallShield 5 setup. Its `data1.cab` has 18 file groups, one set per edition (US, Sony, Creative
Labs, Matrox, Diamond, Logitech bundles...); for the European retail edition the installer copies
`Data`, `DataNoDiamond`, `Game Misc` and `Spawned`. That set reproduces a real Windows install of
the European CD + patch 3.0 file for file. Patch 3.0's own `motor.exe` is then replaced by the 3.1
one: 3.1 is a single `motor.exe` per edition that fixes the HUD disappearing on GeForce-class and
later cards. It also cures a crash at the finish line of every race under Proton
("referenced memory at 0000008c" at 0x471a3f; the faulting routine is unchanged, so the fix is
elsewhere in 3.1). The European 3.1 exe still says "3.0" in the menus (cosmetic, per DICE).

The game writes `Game\MotorHead.CFG` (settings, from a template inside the exe), `HiScores\` and
`League\` itself on first run.

## CD audio

The music is ten CD audio tracks (2-11). The game plays them through MCI (`mciSendCommand`,
`cdaudio`). ogg-winmm is a replacement `winmm.dll` that answers those calls by playing
`Music\TrackNN.ogg` and forwards every other winmm function to the real DLL. Wine treats `winmm`
as a builtin, so the launch script sets `WINEDLLOVERRIDES=winmm=n,b`. `MotorHead.CFG` maps courses
to track numbers (`CDTrack_*`, menu track 3); the OGG numbering follows the disc. Each track is
ripped from its start to the next track's start, so lengths match the disc's table of contents.

## The CD check

The check (3.0 at 0x4370d4, 3.1 Euro at 0x436eb4, same code) is called with `movies\movies.pak`
and 116,849,720:

1. `GetLogicalDriveStringsA` lists the drives;
2. `GetDriveTypeA` must say `DRIVE_CDROM`;
3. `<drive>movies\movies.pak` must exist with exactly that size;
4. the drive is remembered and the intro videos are read from it.

No volume label or table-of-contents check. So:

- **Steam Deck**: the launch script links a high drive letter (M: upward; Wine gives D: and up to
  removable media, and the Deck's SD card is D:) in the Proton prefix to the `cd` folder, marks it
  `cdrom` under `HKLM\Software\Wine\Drives` (what winecfg does) and restarts the wineserver, since
  Wine reads both only when the prefix boots. The unmodified exe then passes its check.
- **Windows, default**: the routine's first 6 bytes become `mov byte [eax],0 ; xor eax,eax ; ret`:
  "found", with an empty drive prefix, so the videos load from `movies\movies.pak` in the game
  folder (`build.py` copies them there from your CD).
- **Windows, `--keep-cd-check`**: the exe stays official; mount `Motorhead-disc.iso`.

## Graphics

The exe has four renderers: Direct3D 5, 3dfx Glide (`glide2x.dll`), PowerVR SGL and software.
Under Proton, DirectDraw / Direct3D up to 7 go through Wine's own `ddraw` on WineD3D, not DXVK, and
old DirectDraw games hit palette and mode-switch problems there; on Windows 11 the menu can fail
with "Couldn't find a valid screenmode for menu 640x400,8". dgVoodoo2 replaces `glide2x.dll`,
`ddraw.dll` and `d3dimm.dll` and renders through Direct3D 11 (Vulkan via DXVK under Proton).
Version 2.79.3 is needed under Wine: 2.80 and later fail to initialise DirectDraw there (Wine bug
58731). `glide2x.dll` has no Wine builtin and loads from the game folder; `ddraw` and `d3dimm` need
the `n,b` override, which the launch script sets. In-game, 3dfx Glide looks right; dgVoodoo's
Direct3D path draws the shadows wrongly.

dgVoodoo settings: `ScalingMode = stretched_ar` (4:3 with bars), vsync forced for Glide and
DirectX, watermark off. The physics are frame-rate dependent: at very high rates the per-frame
steering step vanishes and nobody, AI included, can steer. The Deck build caps at 60
(`FPSLimit = 60`); the Windows build has no cap (vsync holds it at the monitor's rate, fine up to
about 250 Hz) and renders Glide at 2x.

## Volume

Both in-game sliders use the Windows 3.x-era mixer API (`mixerOpen`, `mixerSetControlDetails`).
Wine exports no mixer device, and on Windows 10/11 the API no longer reaches the game's audio, so
the sliders do nothing, and the effects are mastered at full scale, far above the music.
`build.py` scales the samples of every 16-bit WAV in `Sounds\` (default -14 dB) and leaves every
header byte and extra chunk as it was. Music has its own level: `CDDAVolume` in `winmm.ini`.

## Not needed

- `a3dapi.dll`, `sgl.dll`, `glide2x.dll` are loaded only when that driver is selected.
- DirectPlay (`dplayx`) is imported, but Wine has a builtin; Windows offers its legacy component.
- `motorm.exe`, `mplaynow*`, `Mplaynow\`, `AddressBook\`: the MPlayer online client from 1999,
  long dead. Left as the installer puts them.
