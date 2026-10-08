"""Where things live (unpacked disc, outputs) and the roster."""
import glob
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
XB = os.path.join(ROOT, 'out/files/oob/PS3_GAME/USRDIR/xbdata')
PC = os.path.join(XB, 'ueno/pc')
OUT_MODELS = os.path.join(ROOT, 'out/models/oob')
OUT_ANIMS = os.path.join(ROOT, 'out/anims/oob')
OUT_TEX = os.path.join(ROOT, 'out/textures/oob')

# kikkawa/menu/profile_txt.xb0 .../profile2/pcNN.dat (name, title, country)
ROSTER = ['Jasmine', 'Nick', 'Sophie', 'Bjorn', 'Sasha', 'Fernando', 'Sonia', 'Felipe', 'Bloom', 'L.J.', 'Kate',
          'Dino', 'Anya', 'Suzuki', 'S. Maruyama', 'Alex', 'Gloria']


def slug(pc):
    return f'pc{pc:02d}_' + ROSTER[pc].lower().replace('. ', '_').replace('.', '').replace(' ', '_')


def rem_path(pc, costume):
    g = glob.glob(os.path.join(PC, f'pc{pc:02d}/pc{pc:02d}_c{costume:02d}_0_core.xb/data/ueno/cgpc/pc/pc{pc:02d}/*.rem'))
    return g[0] if g else None


def tex_dir(pc, costume):
    return os.path.join(PC, f'pc{pc:02d}/pc{pc:02d}_c{costume:02d}_0_tex.xb/data/ueno/cgpc/pc/pc{pc:02d}')


def find_tex(pc, costume, name):
    """Case-insensitive lookup (REM names differ in case from the archive, e.g. p00_Honaka vs p00_honaka)."""
    d = tex_dir(pc, costume)
    want = name.lower()
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.lower() == want:
            return os.path.join(d, f)
    return None


def motion_files(pc, ext='mot'):
    """(clip name, path) of every .mot (or .mor / .uva) for this character: its own motion archive, the menu archive and the
    result-screen (prize) archive."""
    out = {}
    pats = [f'pc{pc:02d}/pc{pc:02d}_motion.xb/**/*.{ext}', f'pc{pc:02d}/pc{pc:02d}_motion_menu.xb/**/*.{ext}']
    for p in pats:
        for f in glob.glob(os.path.join(PC, p), recursive=True):
            out.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    for f in glob.glob(os.path.join(XB, f'azuma/prize/pc/pc{pc:02d}*.xb/**/*.{ext}'), recursive=True):
        out.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    return sorted(out.items())


def avatar_motion_files():
    return sorted((os.path.splitext(os.path.basename(f))[0], f)
                  for f in glob.glob(os.path.join(XB, 'nakazawa/avatar_common.xb/data/nakazawa/avatar/motion/*.mot')))


def avatar_body_rem():
    return glob.glob(os.path.join(XB, 'nakazawa/avatar_body000.xb/**/body000.rem'), recursive=True)[0]
