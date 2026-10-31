#!/usr/bin/env python3
"""Build a ready-to-run Motorhead folder for modern PCs from your own CD and the official patches.

Usage:
  python3 build.py DISC.cue|DISC.ccd --patch30 motorp30.exe --patch31 motorp31_euro.zip
                   --dgvoodoo DGVOODOO.zip --ogg-winmm OGG-WINMM.zip [--out DIR]
                   [--windows [--keep-cd-check]] [--sfx-db -14]

  DISC          your European Motorhead CD (1998, volume label MOTORHEAD) as .cue + .bin or .ccd + .img
  --patch30     patch 3.0 as downloaded (motorp30.exe, also known as mhp30.exe)
  --patch31     patch 3.1 for the European edition as downloaded (motorp31_euro.zip)
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --ogg-winmm   ogg-winmm release zip (or folder)
  --out         where to create Motorhead/ (default: this folder)
  --windows     a folder for Windows instead of the Steam Deck: no launch script, no frame cap
                (vsync holds the rate), Glide rendered at 2x. The game's CD check is patched to
                load the intro videos from the game folder (see README), unless --keep-cd-check:
                then motor.exe stays official and Motorhead-disc.iso is written to mount instead.
  --sfx-db      sound effect level in dB (default -14; 0 leaves them as on the disc)

Needs Python 3.8+ and an Ogg Vorbis encoder on the PATH: oggenc (vorbis-tools) or ffmpeg.
Nothing from the game is in this repository: every game file comes from your disc and the patches.
"""
import argparse, array, hashlib, os, shutil, struct, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, installshield5, mscab

DISC_EXE_MD5 = "78a85131f6247c8a9a93782d46e5b850"     # motor.exe in the European CD's installer
PATCH30_MD5 = "aea008665c551228c3dde05995643006"      # motorp30.exe / mhp30.exe, 26 Mar 1999
P31_EURO_MD5 = "b06a6345e19141643a299748b9069230"     # motor.exe in motorp31_euro.zip, 30 Oct 2000
P31_NOCD_MD5 = "8567d374ca91945d2c2f54852621fb59"     # the same after nocd()
DISC_GROUPS = ["Data", "Spawned", "Program Executable Files"]   # what the CD's installer copies
P30_GROUPS = ["Data", "DataNoDiamond", "Game Misc", "Spawned"]  # what patch 3.0 copies for the European
                                                                # edition (its motor.exe is replaced by 3.1)


def md5(data): return hashlib.md5(data).hexdigest()


def ci_join(root, rel):
    """root/rel, reusing existing names whatever their case, as Windows would (the installers use
    both Tracks\\track3 and Tracks\\Track3, and GAME2.SPR for game2.spr)."""
    path = root
    for part in [p for p in rel.replace("\\", "/").split("/") if p]:
        match = part
        if os.path.isdir(path):
            for e in os.listdir(path):
                if e.lower() == part.lower(): match = e; break
        path = os.path.join(path, match)
    return path


def install(cab, groups, game):
    for g in groups:
        for f in cab.group_files(g):
            dst = ci_join(game, f["dir"] + "\\" + f["name"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(cab.read(f))


def nocd(exe):
    """The CD check (3.1 Euro VA 0x436eb4) takes an output buffer in eax, scans the drives for a
    CD-ROM holding movies\\movies.pak of 116,849,720 bytes and writes that drive's root into it;
    0 = found. Its first 6 bytes become `mov byte [eax],0 ; xor eax,eax ; ret`: found, with an empty
    drive prefix, so the intro videos load from movies\\movies.pak in the game folder."""
    prologue = bytes.fromhex("56575581ec140c0000898424040c0000899424000c0000899c24080c0000898c")
    d = bytearray(exe); o = d.find(prologue)
    if o < 0 or d.find(prologue, o + 1) >= 0: sys.exit("CD check not found in motor.exe")
    d[o:o + 6] = bytes.fromhex("c6000031c0c3")
    return bytes(d)


def attenuate(path, gain):
    """Scales the samples of a 16-bit PCM WAV; every header byte and extra chunk stays as it was.
    The game's two volume sliders use the old mixer API, which does nothing on Windows 10/11 or
    under Wine, and the effects are mastered at full scale, far louder than the music."""
    d = bytearray(open(path, "rb").read())
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE": return
    o, bits = 12, None
    while o + 8 <= len(d):
        cid, sz = bytes(d[o:o + 4]), struct.unpack_from("<I", d, o + 4)[0]
        if cid == b"fmt ":
            tag, _, _, _, _, bits = struct.unpack_from("<HHIIHH", d, o + 8)
            if tag != 1 or bits != 16: return
        elif cid == b"data" and bits == 16:
            n = sz // 2
            s = array.array("h"); s.frombytes(bytes(d[o + 8:o + 8 + n * 2]))
            if sys.byteorder == "big": s.byteswap()
            for i in range(n): s[i] = max(-32768, min(32767, int(round(s[i] * gain))))
            if sys.byteorder == "big": s.byteswap()
            d[o + 8:o + 8 + n * 2] = s.tobytes()
        o += 8 + sz + (sz & 1)
    open(path, "wb").write(d)


def encoder():
    if shutil.which("oggenc"): return lambda wav, ogg: ["oggenc", "-Q", "-q", "7", wav, "-o", ogg]
    if shutil.which("ffmpeg"):
        return lambda wav, ogg: ["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "7", ogg]
    sys.exit("needs oggenc (vorbis-tools) or ffmpeg on the PATH to encode the soundtrack")


def rip(tracks, music):
    enc = encoder(); os.makedirs(music, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for t in tracks:
            if t.kind != "AUDIO": continue
            data = disc.audio(t)          # INDEX 01 to the next track's start: lengths match the disc's TOC
            wav = os.path.join(tmp, f"track{t.n:02d}.wav")
            with open(wav, "wb") as o:
                o.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                        struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16) + b"data" +
                        struct.pack("<I", len(data)) + data)
            subprocess.run(enc(wav, os.path.join(music, f"Track{t.n:02d}.ogg")), check=True); os.remove(wav)
            print(f"  Music/Track{t.n:02d}.ogg  {len(data) / 2352 / 75:6.1f} s")


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--patch30", required=True); ap.add_argument("--patch31", required=True)
    ap.add_argument("--dgvoodoo", required=True); ap.add_argument("--ogg-winmm", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    ap.add_argument("--keep-cd-check", action="store_true"); ap.add_argument("--sfx-db", type=float, default=-14)
    a = ap.parse_args()
    if a.keep_cd_check and not a.windows: sys.exit("--keep-cd-check goes with --windows (the Deck build never patches the check)")

    tracks = disc.tracks(a.disc)
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    if dt.label() != "MOTORHEAD": print(f"warning: volume label is {dt.label()!r}, this kit was made for MOTORHEAD")
    entries = list(dt.walk())

    p30 = open(a.patch30, "rb").read()
    if md5(p30) != PATCH30_MD5: sys.exit(f"{a.patch30} is not patch 3.0 (motorp30.exe, 14,025,656 bytes; MD5 {md5(p30)})")
    p31 = take(a.patch31, "motor.exe")
    if md5(p31) != P31_EURO_MD5: sys.exit(f"{a.patch31}: motor.exe is not the European patch 3.1 one (MD5 {md5(p31)})")

    pkg = os.path.join(os.path.abspath(a.out), "Motorhead"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    print("1/7 game files from the CD's installer")
    cab = next(((l, s) for p, d, l, s in entries if p.upper() == "MOTOR/DISK1/DATA1.CAB"), None)
    if not cab:
        sys.exit("no MOTOR\\DISK1\\DATA1.CAB on this CD: it isn't the European retail disc the kit was made for "
                 "(OEM bundle discs keep everything in an MHEAD folder and aren't supported yet)")
    install(installshield5.Cabinet(dt.read_file(*cab)), DISC_GROUPS, game)
    exe = os.path.join(game, "motor.exe")
    if md5(open(exe, "rb").read()) != DISC_EXE_MD5:
        sys.exit("this CD's motor.exe is not the European 1998 one the kit was made for "
                 f"(MD5 {md5(open(exe, 'rb').read())}); nothing else is supported yet")

    print("2/7 patch 3.0 (European edition files) and the 3.1 motor.exe")
    install(installshield5.Cabinet(mscab.Cabinet(p30).read("disk1/data1.cab")), P30_GROUPS, game)
    if a.windows and not a.keep_cd_check:
        p31 = nocd(p31)
        if md5(p31) != P31_NOCD_MD5: sys.exit("CD check patch gave an unexpected motor.exe")
    open(exe, "wb").write(p31)

    print("3/7 CD files")
    if not a.windows:            # the Deck build: a folder the launch script presents as a CD-ROM drive
        for p, is_dir, l, s in entries:
            if p.upper().split("/")[0] == "REDIST" or is_dir: continue   # DirectX 5 redistributable
            dt.copy_file(l, s, os.path.join(pkg, "cd", *p.split("/")))
        open(os.path.join(pkg, "cd", ".windows-label"), "w").write("MOTORHEAD\n")
    elif not a.keep_cd_check:    # the intro videos, beside the game for the patched check
        for p, is_dir, l, s in entries:
            if p.upper().startswith("MOVIES/") and not is_dir: dt.copy_file(l, s, os.path.join(game, *p.split("/")))
    else:
        dt.write_iso(os.path.join(pkg, "Motorhead-disc.iso"))

    print(f"4/7 sound effects at {a.sfx_db:+g} dB")
    if a.sfx_db:
        gain = 10 ** (a.sfx_db / 20)
        for d, _, fs in os.walk(ci_join(game, "Sounds")):
            for f in fs:
                if f.lower().endswith(".wav"): attenuate(os.path.join(d, f), gain)

    print("5/7 soundtrack")
    rip(tracks, os.path.join(game, "Music"))

    print("6/7 wrappers and settings")
    for member, name in [("MS/x86/DDraw.dll", "ddraw.dll"), ("MS/x86/D3DImm.dll", "d3dimm.dll"),
                         ("3Dfx/x86/Glide2x.dll", "glide2x.dll")]:
        open(os.path.join(game, name), "wb").write(take(a.dgvoodoo, member))
    for name in ("winmm.dll", "winmm.ini"):
        open(os.path.join(game, name), "wb").write(take(a.ogg_winmm, name))
    conf = "dgVoodoo-windows.conf" if a.windows else "dgVoodoo-deck.conf"
    shutil.copyfile(os.path.join(HERE, "config", conf), os.path.join(game, "dgVoodoo.conf"))

    print("7/7 Steam Deck launch script" if not a.windows else "7/7 done")
    if not a.windows:
        launch = os.path.join(pkg, "motorhead_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "motorhead_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
