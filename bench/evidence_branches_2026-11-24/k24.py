import sys, json, types
from pathlib import Path
root = Path.cwd(); sys.path.insert(0, str(root))
from ocr import formula
import ocr.coherence as C
tt = formula.TexTeller()
p = root/"bench/formula_flywheel/own/ketten/png/ketten_K24_s1.png"
glm_log = {}
def glm(img):
    r = formula.glm_live(img); glm_log['g']=r[0]; return r
orig = formula.recognize
t_raw = tt(str(p))[0]
print("TT raw:", t_raw)
o = orig(p, tt=tt, glm=glm)
print("GLM:", glm_log.get('g')); print("result:", o)
