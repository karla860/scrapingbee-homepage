"""Font → Lottie glyph data (shared by the test and the real build)."""
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen


class _Pen(BasePen):
    def __init__(s, gs, k, ox=0.0, oy=0.0):
        super().__init__(gs); s.k, s.ox, s.oy = k, ox, oy; s.out = []; s.cur = None

    def P(s, p):
        return [round(s.ox + p[0] * s.k, 2), round(s.oy - p[1] * s.k, 2)]

    def _moveTo(s, p):
        s.cur = {"v": [s.P(p)], "i": [[0, 0]], "o": [[0, 0]]}

    def _lineTo(s, p):
        s.cur["v"].append(s.P(p)); s.cur["i"].append([0, 0]); s.cur["o"].append([0, 0])

    def _curveToOne(s, p1, p2, p3):
        a = s.cur["v"][-1]; b1, b2, b3 = s.P(p1), s.P(p2), s.P(p3)
        s.cur["o"][-1] = [round(b1[0] - a[0], 2), round(b1[1] - a[1], 2)]
        s.cur["v"].append(b3); s.cur["i"].append([round(b2[0] - b3[0], 2), round(b2[1] - b3[1], 2)]); s.cur["o"].append([0, 0])

    def _qCurveToOne(s, p1, p2):
        p0 = s._getCurrentPoint()
        c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
        c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
        s._curveToOne(c1, c2, p2)

    def _closePath(s):
        c = s.cur
        if c is None:
            return
        if len(c["v"]) > 1 and c["v"][-1] == c["v"][0]:
            c["i"][0] = c["i"][-1]; c["v"].pop(); c["i"].pop(); c["o"].pop()
        c["c"] = True; s.out.append(c); s.cur = None

    _endPath = _closePath


class Font:
    def __init__(s, path):
        t = TTFont(str(path))
        s.gs, s.cmap, s.upm, s.hmtx, s.asc = t.getGlyphSet(), t.getBestCmap(), t["head"].unitsPerEm, t["hmtx"], t["hhea"].ascent
        s.desc = -t["hhea"].descent

    def has(s, ch):
        return ord(ch) in s.cmap

    def adv(s, ch, size):
        return s.hmtx[s.cmap[ord(ch)]][0] * size / s.upm

    def contours(s, ch, size, x=0.0, base=0.0):
        pen = _Pen(s.gs, size / s.upm, x, base); s.gs[s.cmap[ord(ch)]].draw(pen); return pen.out
