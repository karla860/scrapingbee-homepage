"""
Builds the hero key-visual animation as a Lottie file with python-lottie.

The whole key visual is one self-contained Lottie: the background circles, the browser with its cards, the
terminal (typed commands, JSON results, blinking cursor), the scanner, the dashed beam, the data stream and the
bee (Figma "Mascot / Bee" vectors imported from SVG, with its moods, eyelid blinks and wing flutter).
Text is converted to vector outlines from the bundled fonts (lottie/fonts, SIL OFL), so no fonts are needed to play it.
Static layout comes from kv-layout.json, measured from the original HTML build of the scene.

Run:  python build_kv.py         ->  ../kv-animation.json  +  ../kv-animation.js
"""
import json, math, random, re
from pathlib import Path
from lottie.parsers.svg import parse_svg_file
from glyphs import Font

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BEE = ROOT / "assets" / "bee"
FPS = 60
W, H = 722, 650

# Layout of the HTML scene (measured from the page, KV coordinates)
CARDS = [[215.06, 339.75, 132.27, 110.36], [353.27, 339.75, 132.27, 110.36], [491.47, 339.75, 132.27, 110.36],
         [215.06, 454.52, 132.27, 110.36], [353.27, 454.52, 132.27, 110.36], [491.47, 454.52, 132.27, 110.36],
         [215.06, 569.28, 132.27, 110.36], [353.27, 569.28, 132.27, 110.36], [491.47, 569.28, 132.27, 110.36]]
GRID = [215.06, 339.75, 412.17, 339.89]
BODY = [65, 287.52, 586, 334.48]
TERM_IN = (200, 120)                      # where streamed data lands in the terminal

BEE_ORIGIN = (330, -20)                   # bee box top-left (330 × 286)
PIVOT = (148.5, 171.6)                    # 45% / 60% of the bee box
APEX = (147, 240)                         # beam origin under the bee
ART_SCALE = 110

# ---------------------------------------------------------------- keyframe tracks
LIN, HOLD = (0, 0, 1, 1), "hold"
EASE = (.25, .1, .25, 1)
EASE_IO = (.42, 0, .58, 1)
FLY = (.45, 0, .25, 1)
SCAN = (.5, 0, .25, 1)
POP = (.3, 1.6, .5, 1)


def bezier_y(e, p):
    if e == HOLD:
        return 0.0
    x1, y1, x2, y2 = e
    lo, hi = 0.0, 1.0
    for _ in range(40):
        s = (lo + hi) / 2
        x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
        lo, hi = (s, hi) if x < p else (lo, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3


class Track:
    """Piecewise-eased values; the same data drives the Lottie keys and the beam maths."""

    def __init__(self, v):
        self.k = [[0.0, list(v) if isinstance(v, (list, tuple)) else [v], HOLD]]

    def val(self, t):
        k = self.k
        if t <= k[0][0]:
            return k[0][1]
        for a, b in zip(k, k[1:]):
            if a[0] <= t < b[0]:
                y = bezier_y(a[2], (t - a[0]) / (b[0] - a[0]))
                return [u + (w - u) * y for u, w in zip(a[1], b[1])]
        return k[-1][1]

    def seq(self, t0, steps):
        """steps: [(dt, value, ease_of_segment_into_it)] relative to t0. Later calls override earlier ones."""
        cur = self.val(t0)
        self.k = [x for x in self.k if x[0] < t0 - 1e-6]
        if self.k:
            self.k[-1][2] = HOLD if self.k[-1][1] == cur else self.k[-1][2]
        self.k.append([t0, cur, HOLD])
        for dt, v, e in steps:
            self.k[-1][2] = e
            self.k.append([t0 + dt, list(v) if isinstance(v, (list, tuple)) else [v], HOLD])

    def to(self, t0, dur, v, e):
        self.seq(t0, [(dur, v, e)])

    def lottie(self, dims=None, z=False):
        def fmt(v):
            v = [round(x, 3) for x in v]
            return v + [0] if z else (v if len(v) > 1 or dims else v)
        if len(self.k) == 1:
            v = fmt(self.k[0][1])
            return {"a": 0, "k": v if len(v) > 1 else v[0]}
        keys = []
        for i, (t, v, e) in enumerate(self.k):
            key = {"t": round(t * FPS, 3), "s": fmt(v)}
            if i < len(self.k) - 1:
                if e == HOLD:
                    key["h"] = 1
                else:
                    key["o"] = {"x": [e[0]], "y": [e[1]]}
                    key["i"] = {"x": [e[2]], "y": [e[3]]}
            keys.append(key)
        return {"a": 1, "k": keys}


def static(v):
    return {"a": 0, "k": v}


def ks(p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100):
    return {"p": p if isinstance(p, dict) else static([*p, 0]), "a": a if isinstance(a, dict) else static([*a, 0]),
            "s": s if isinstance(s, dict) else static([*s, 100]), "r": r if isinstance(r, dict) else static(r),
            "o": o if isinstance(o, dict) else static(o)}


def rgb(hexs, a=1):
    h = hexs.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [a]


def tr(p=None):
    return {"ty": "tr", "p": p or static([0, 0]), "a": static([0, 0]), "s": static([100, 100]), "r": static(0),
            "o": static(100), "sk": static(0), "sa": static(0)}


def rect(size, pos=(0, 0), r=0):
    return {"ty": "rc", "d": 1, "p": pos if isinstance(pos, dict) else static(list(pos)),
            "s": size if isinstance(size, dict) else static(list(size)), "r": static(r)}


def fill(c, o=100):
    return {"ty": "fl", "c": static(rgb(c)), "o": static(o), "r": 1}


def stroke(c, w, dash=None, cap=2):
    s = {"ty": "st", "c": static(rgb(c)), "o": static(100), "w": static(w), "lc": cap, "lj": 2, "ml": 4}
    if dash:
        d, g, off = dash
        s["d"] = [{"n": "d", "nm": "dash", "v": static(d)}, {"n": "g", "nm": "gap", "v": static(g)},
                  {"n": "o", "nm": "offset", "v": off}]
    return s


def group(items, nm="g", p=None):
    return {"ty": "gr", "nm": nm, "it": items + [tr(p)]}


def path(pts, closed=False, i=None, o=None):
    z = [[0, 0]] * len(pts)
    return {"i": i or z, "o": o or z, "v": [[round(x, 2), round(y, 2)] for x, y in pts], "c": closed}


def circle(cx, cy, r):
    k = 0.5523 * r
    return path([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], True,
                i=[[-k, 0], [0, -k], [k, 0], [0, k]], o=[[k, 0], [0, k], [-k, 0], [0, -k]])


# ---------------------------------------------------------------- layers
LAYERS = []          # top-most first, like Lottie
_ind = [0]


def layer(nm, ty, k, parent=None, shapes=None, **extra):
    _ind[0] += 1
    d = {"ddd": 0, "ind": _ind[0], "ty": ty, "nm": nm, "sr": 1, "ks": k, "ao": 0, "ip": 0, "op": 0, "st": 0, "bm": 0}
    if parent:
        d["parent"] = parent
    if ty == 4:
        d["shapes"] = shapes or []
    d.update(extra)
    return d


def svg_shapes(name):
    """python-lottie SVG import → shapes in the SVG's own units (the importer's fit-to-integer scale is dropped)."""
    anim = parse_svg_file(str(BEE / name)).to_dict()
    return [s for l in anim["layers"] for s in l.get("shapes", [])]


def svg_size(name):
    m = re.search(r'width="([\d.]+)" height="([\d.]+)"', (BEE / name).read_text())
    return float(m.group(1)), float(m.group(2))


# ---------------------------------------------------------------- timeline state
T_END = [0.0]
move = Track([0, 0]); tilt = Track(0); bob = Track(0)
r_off = Track([0, 0]); r_rot = Track(0); r_scale = Track([100, 100])
scan = Track(CARDS[4][:2] + [CARDS[4][2] + .24, CARDS[4][3]])
sweep_on = Track(0)
scan_windows = []        # (t0, t1, rect)
flying = []              # (t0, t1)
moods = [(0.0, "happy")]
streams = []             # (t, n)
events = []
markers = []
beepos = [0, 0]


def ev(t, a, **kw):
    events.append({"t": round(t, 3), "a": a, **kw})
    markers.append({"tm": round(t * FPS, 2), "cm": a, "dr": 0})


def type_dur(lines, speed):
    return ((sum(sum(len(s[0]) for s in ln) + 1 for ln in lines) + 1) * speed / 1000) * 1.12


def term_type(t, lines, append=False, speed=16):
    ev(t, "type", lines=lines, append=append, speed=speed)
    return type_dur(lines, speed) + (0 if append else .25)


def term_reveal(t, lines, append=False):
    ev(t, "reveal", lines=lines, append=append)
    return (0 if append else .25) + .5 + len(lines) * .08


def set_mood(t, m):
    if moods[-1][1] == m:
        return
    moods.append((t, m))
    r_scale.seq(t, [(.18, [102, 97.5], EASE_IO), (.42, [100, 100], EASE_IO)])


def move_bee(t, x, y):
    d = (x > beepos[0]) - (x < beepos[0])
    beepos[:] = [x, y]
    move.to(t, 1.25, [x, y], FLY)
    tilt.seq(t, [(.5, d * 6, EASE_IO), (.8, d * 6, HOLD), (1.4, 0, EASE_IO)])
    flying.append((t, t + .9))


def react(t, kind):
    E = EASE_IO
    if kind == "hop":
        d = .9; r_off.seq(t, [(d * .25, [0, -10], E), (d * .5, [0, 0], E), (d * .75, [0, -4], E), (d, [0, 0], E)])
        r_rot.seq(t, [(d * .25, -3, E), (d * .5, 0, E), (d * .75, 2, E), (d, 0, E)])
    elif kind == "spin":
        d = 1.1; r_off.seq(t, [(d * .25, [0, -18], E), (d * .5, [0, -10], E), (d * .75, [0, -16], E), (d, [0, 0], E)])
        r_rot.seq(t, [(d * .25, -8, E), (d * .5, 8, E), (d * .75, -4, E), (d, 0, E)])
    elif kind == "wobble":
        d = 1.3; r_rot.seq(t, [(d * .2, -8, E), (d * .4, 6, E), (d * .6, -4, E), (d * .8, 2, E), (d, 0, E)])
    elif kind == "shake":
        d = .52; xs = [-8, 8, -6, 5, -2, 0]; rs = [-3, 3, 0, 0, 0, 0]
        r_off.seq(t, [(d * (i + 1) / 6, [x, 0], E) for i, x in enumerate(xs)])
        r_rot.seq(t, [(d * (i + 1) / 6, r, E) for i, r in enumerate(rs)])


def scanner_to(t, rect_):
    scan.to(t, 1.1, rect_, SCAN)


def card_rect(i):
    x, y, w, h = CARDS[i]
    return [x, y, w + .24, h]


def page_rect():
    pad = 6
    gx, gy, gw, gh = GRID
    bottom = min(gy + gh, BODY[1] + BODY[3])
    return [gx - pad, gy - pad, gw + 2 * pad, bottom - gy + pad - 4]


_scan_start = [None]


def scan_on(t):
    sweep_on.to(t, .2, 1, LIN)
    _scan_start[0] = t


def scan_off(t):
    sweep_on.to(t, .2, 0, LIN)
    scan_windows.append((_scan_start[0], t + .2, scan.val(_scan_start[0])))


def stream(t, n):
    streams.append((t, n))
    return .7 + n * .085


# The browser shows a feed (filters on the left, cards with a thumbnail, headline and summary), so the bee scrapes
# articles into LLM-ready records — the RAG / AI use case from the hero copy. Keep each line ≤ 27 characters (and clear of the bee).
J = lambda title, author, date: [
    [["{"]],
    [["  "], ['"title"', "k"], [f': "{title}"', "v"], [","]],
    [["  "], ['"author"', "k"], [f': "{author}"', "v"], [","]],
    [["  "], ['"date"', "k"], [f': "{date}"', "v"]],
    [["}"]],
]
REST = ["LLM-ready Web", "K. Silva", "2026-10-24"]     # the design's resting state (card 5)
REQ = lambda p: [[["$ ", "dim"], ["scrapingbee scrape \\"]], [["    "], [p, "v"]]]
OK = lambda ms: [[["✓ 200 OK", "ok"], [f" · {ms}", "dim"]]]
done = []


def scrape(t, i, x, y, p):
    set_mood(t, "focused")
    move_bee(t, x, y)
    scanner_to(t, page_rect() if i is None else card_rect(i))
    t += term_type(t, REQ(p)) + .35
    scan_on(t)
    return t


def deliver(t, i, data, ms, mood="happy"):
    scan_off(t)
    t += term_type(t, OK(ms), append=True, speed=10)
    set_mood(t, mood); react(t, "hop")
    t += stream(t, 6)
    done.append(i)
    t += term_reveal(t, J(*data))
    return t + 1.0


# ---------------------------------------------------------------- the story
ev(0, "reset", lines=J(*REST))
t = 1.0
t = scrape(t, 0, -10, 0, "news.dev/rag-at-scale") + .9
t = deliver(t, 0, ["RAG at Scale", "M. Okafor", "2026-10-21"], "0.8s")

t = scrape(t, 1, 20, -6, "news.dev/vector-search") + .8
t = deliver(t, 1, ["Vector Search", "L. Chen", "2026-10-18"], "0.6s")

# Confusing page: the article shows two different dates — AI extraction sorts it out
t = scrape(t, 2, 80, -10, "news.dev/llm-evals") + .9
scan_off(t); set_mood(t, "curious"); react(t, "wobble")
t += term_reveal(t, [[["? ", "warn"], ["2 dates found:", "warn"]], [['  "Oct 3" ', "v"], ["or", "dim"], [' "2026-10-09"', "v"]]]) + 1.0
set_mood(t, "focused")
t += term_type(t, [[["→ ai_extract: ", "dim"], ["date", "k"]]], append=True)
scan_on(t); t += .9
t = deliver(t, 2, ["LLM Evals 101", "S. Patel", "2026-10-09"], "1.1s")

t = scrape(t, 5, 90, 18, "news.dev/agent-memory") + .8
t = deliver(t, 5, ["Agent Memory", "J. Romero", "2026-10-15"], "0.7s")

# Blocked by the site's anti-bot — ScrapingBee retries through a stealth proxy and gets in
t = scrape(t, 3, 0, 28, "news.dev/prompt-cache") + .9
scan_off(t); set_mood(t, "error"); react(t, "shake")
t += term_reveal(t, [[["✕ 403 ", "err"], ["· blocked by anti-bot", "dim"]], [["↻ retrying · ", "dim"], ["stealth_proxy", "k"]]]) + 1.2
set_mood(t, "focused"); scan_on(t); t += .9
t = deliver(t, 3, ["Prompt Cache", "A. Novak", "2026-10-12"], "1.4s")

t = scrape(t, 4, 0, 0, "news.dev/llm-ready-web") + .8
t = deliver(t, 4, REST, "0.7s")

# Finale: the whole feed in one call — everything comes back clean
t = scrape(t, None, 10, 6, "news.dev/latest") + 1.3
scan_off(t)
t += term_type(t, OK("1.9s"), append=True, speed=10)
set_mood(t, "excited"); react(t, "spin")
dur = stream(t, 12)
for k, i in enumerate([6, 7, 8]):
    done.append(i)
t += dur
t += term_reveal(t, [
    [["✓ ", "ok"], ["9/9 articles", "ok"], [" scraped", "dim"]],
    [["[ "], ["{…}", "v"], [", "], ["{…}", "v"], [", "], ["{…}", "v"], [","]],
    [["  "], ["{…}", "v"], [", "], ["{…}", "v"], [", "], ["{…}", "v"], [","]],
    [["  "], ["{…}", "v"], [", "], ["{…}", "v"], [", "], ["{…}", "v"], [" ]"]],
]) + 2.6
set_mood(t, "happy"); t += 1.6

# Settle back into the design's resting pose so the loop is seamless
move_bee(t, 0, 0); scanner_to(t, card_rect(4))
term_reveal(t, J(*REST))
t += 2.2
END = t

# ---------------------------------------------------------------- continuous motion
for k in range(int(END / .9) + 2):
    bob.k.append([k * .9 + .9, [-7 if k % 2 == 0 else 0], HOLD])
for k in bob.k[:-1]:
    k[2] = EASE_IO
bob.k = [k for k in bob.k if k[0] <= END + .9]

rng = random.Random(7)
blinks, bt = [], 1.6
while bt < END - .5:
    blinks.append(bt)
    if rng.random() < .25:
        blinks.append(bt + .35)
    bt += 2.2 + rng.random() * 2.6


def is_flying(t):
    return any(a <= t <= b for a, b in flying)


def flap(lo, hi, start_hi=False):
    tr_r, tr_s, t, up = Track(hi if start_hi else lo), Track([100, 100]), 0.0, not start_hi
    tr_r.k[0][2] = EASE_IO; tr_s.k[0][2] = EASE_IO
    while t < END:
        t += .05 if is_flying(t) else .08
        tr_r.k.append([t, [hi if up else lo], EASE_IO])
        tr_s.k.append([t, [94, 94] if up else [100, 100], EASE_IO])
        up = not up
    return tr_r, tr_s


# ---------------------------------------------------------------- bee rig
def piece(name, svg, box, img, inner=None, pivot=None, parent=None, opacity=None, pop=None, rot_track=None, scale_track=None):
    L, T_, BW, BH = box
    cw, ch, rot = inner if inner else (BW, BH, 0)
    C = (L + BW / 2, T_ + BH / 2)
    lp, tp, wp, hp = [v / 100 for v in img]
    sw, sh = svg_size(svg)
    sx, sy = wp * cw / sw, hp * ch / sh
    if pivot:   # pivot given in % of the image (wings)
        a = (pivot[0] / 100 * sw, pivot[1] / 100 * sh)
        p = (L + lp * cw + a[0] * sx, T_ + tp * ch + a[1] * sy)
    else:
        a = ((cw / 2 - lp * cw) / sx, (ch / 2 - tp * ch) / sy)
        p = C
    k = ks(p=p, a=a, s=(sx * 100, sy * 100), r=rot)
    if rot_track:
        k["r"] = rot_track.lottie()
    if scale_track:
        k["s"] = {"a": 1, "k": [{**x, "s": [v * sx for v in x["s"][:1]] + [x["s"][1] * sy, 100]}
                                for x in scale_track.lottie()["k"]]}
    if pop:
        k["s"] = pop(sx * 100, sy * 100)
    if opacity:
        k["o"] = opacity
    return layer(name, 4, k, parent=parent, shapes=svg_shapes(svg))


def mood_opacity(m):
    tk = Track(100 if moods[0][1] == m else 0)
    for t0, mm in moods[1:]:
        tk.to(t0, .28, 100 if mm == m else 0, EASE_IO)
    return tk.lottie()


def mood_pop(m):
    def f(bx, by):
        tk = Track([bx, by])
        for t0, mm in moods[1:]:
            if mm == m:
                tk.seq(t0, [(.001, [0, 0], HOLD), (.45, [bx, by], POP)])
        return tk.lottie(z=False) if len(tk.k) > 1 else static([bx, by, 100])
    return f


EYE = (-4.02, -4.02, 108.04, 108.04)
FILL = (0, 0, 100, 100)
FACES = {
    "focused": [("mouth", "focused-mouth.svg", (98.61, 171.18, 15.39, 4.42), (-10, -160, 120, 420), (16.01, 1, 16), None),
                ("eye-l", "focused-eye-l.svg", (48.81, 86.24, 79.92, 79.92), EYE, (58.39, 58.39, 30.43), 28.545),
                ("eye-r", "focused-eye-r.svg", (109.53, 111.59, 64.59, 64.56), EYE, (58.42, 58.39, 6.43), 28.545)],
    "happy": [("blush", "happy-blush.svg", (72.24, 154.41, 93.54, 29.17), FILL, None, None),
              ("mouth", "happy-mouth.svg", (96, 167.75, 21.69, 11.08), (-7.62, -29.09, 115.24, 158.18), (20.99, 5.5, 16), None),
              ("eye-l", "happy-eye.svg", (51.84, 89.26, 73.86, 73.87), EYE, (58.39, 58.39, 18.43), 18.545),
              ("eye-r", "happy-eye.svg", (104.91, 106.94, 73.86, 73.86), EYE, (58.39, 58.39, 18.43), 18.545)],
    "excited": [("blush", "happy-blush.svg", (72.24, 154.41, 93.54, 29.17), FILL, None, None),
                ("mouth", "excited-mouth.svg", (92.55, 166.24, 27.36, 18.43), (-6, -12.5, 112, 112.5), (25.02, 12, 16), None),
                ("eye-l", "excited-eye.svg", (51.84, 89.26, 73.86, 73.87), EYE, (58.39, 58.39, 18.43), None),
                ("eye-r", "excited-eye.svg", (104.91, 106.94, 73.86, 73.86), EYE, (58.39, 58.39, 18.43), None)],
    "curious": [("mouth", "curious-mouth.svg", (98.34, 169.26, 17.16, 7.59), (-9.41, -53.33, 118.82, 206.68), (17, 3.01, 16), None),
                ("eye-l", "curious-eye.svg", (51.84, 89.26, 73.86, 73.87), EYE, (58.39, 58.39, 18.43), 12.545),
                ("eye-r", "curious-eye.svg", (104.91, 106.94, 73.86, 73.86), EYE, (58.39, 58.39, 18.43), 12.545)],
    "error": [("mouth", "error-mouth.svg", (94.35, 171.34, 21.3, 9.62), (-7.14, -37.5, 114.28, 175), (21.01, 4, 16), None),
              ("eye-l", "error-eye-l.svg", (58.35, 95.78, 60.84, 60.84), EYE, (58.41, 58.41, 2.43), 15.545),
              ("eye-r", "error-eye-r.svg", (101.25, 103.27, 81.18, 81.2), EYE, (58.4, 58.4, 34.43), 15.545)],
}
EXTRAS = {
    "focused": [("dots", "focused-dots.svg", (203.01, 56.99, 45.99, 22), FILL, None)],
    "excited": [("sparkles", "excited-sparkles.svg", (30.99, 50, 233.01, 67.99), (-.56, -1.91, 101.12, 103.82), None)],
    "curious": [("question", "curious-question.svg", (33.66, 35.28, 27.24, 44.64), (-15.79, -7.21, 131.58, 107.21), (19, 41.6, -12))],
    "error": [("sweat", "error-sweat.svg", (187.95, 74.49, 16.11, 25.3), (-8.7, -5.53, 117.4, 111.06), None),
              ("alert", "error-alert-lines.svg", (152.01, 2, 19.98, 32.01), (-8.5, -5.31, 117, 110.62), None)],
}


# The eye outline is a 4.69 stroke centred on r = 29.2. The lid is clipped to the outline's inner edge so it never
# covers part of the outline, and its edge uses the same 4.69 weight.
EYE_STROKE = 4.69
EYE_INNER = 29.2 - EYE_STROKE / 2


def lid_layer(nm, parent, y, opacity):
    tk = Track([0, 0])
    for b in blinks:
        tk.seq(b, [(.09, [0, 61 - y], (.45, 0, .55, 1)), (.11, [0, 61 - y], HOLD), (.2, [0, 0], (.45, 0, .55, 1))])
    edge = group([{"ty": "sh", "ks": static(path([(0, y), (63.09, y)]))}, stroke("#141414", EYE_STROKE, cap=2)], "lid edge")
    lid_fill = group([rect((63.09, 64), (31.545, y - 32)), fill("#EFAE26")], "lid fill")
    g = group([edge, lid_fill], "lid", p=tk.lottie())
    lid = layer(nm, 4, ks(o=opacity), parent=parent, shapes=[g], hasMask=True,
                masksProperties=[{"inv": False, "mode": "a", "pt": static(circle(31.545, 31.545, EYE_INNER)), "o": static(100),
                                  "x": static(0), "nm": "eye"}])
    return lid


def build_bee():
    n_move = layer("bee · move", 3, ks(p={"a": 1, "k": [{**k, "s": [k["s"][0] + BEE_ORIGIN[0], k["s"][1] + BEE_ORIGIN[1], 0]}
                                                          for k in move.lottie(z=True)["k"]]}))
    n_tilt = layer("bee · tilt", 3, ks(p=PIVOT, a=PIVOT, r=tilt.lottie()), parent=n_move["ind"])
    n_bob = layer("bee · bob", 3, ks(p={"a": 1, "k": [{**k, "s": [0, k["s"][0], 0]} for k in bob.lottie()["k"]]}), parent=n_tilt["ind"])
    n_react = layer("bee · react", 3, ks(p={"a": 1, "k": [{**k, "s": [k["s"][0] + PIVOT[0], k["s"][1] + PIVOT[1], 0]}
                                                           for k in r_off.lottie(z=True)["k"]]},
                                          a=PIVOT, r=r_rot.lottie(), s={"a": 1, "k": [{**k, "s": k["s"] + [100]} for k in r_scale.lottie()["k"]]}),
                    parent=n_bob["ind"])
    n_art = layer("bee · art", 3, ks(s=(ART_SCALE, ART_SCALE)), parent=n_react["ind"])
    A = n_art["ind"]
    rb, sb = flap(6, -18)
    rf, sf = flap(-6, 16, start_hi=True)
    top = []
    for m, items in EXTRAS.items():
        for nm, svg, box, img, inner in items:
            top.append(piece(f"{m} · {nm}", svg, box, img, inner, parent=A, opacity=mood_opacity(m), pop=mood_pop(m)))
    top.append(piece("stripes", "stripes.svg", (83.13, 137.02, 119.73, 87.18), FILL, parent=A))
    for m, items in FACES.items():
        op = mood_opacity(m)
        for nm, svg, box, img, inner, lid in items:
            p = piece(f"{m} · {nm}", svg, box, img, inner, parent=A, opacity=op)
            if lid is not None:
                top.append(lid_layer(f"{m} · {nm} · lid", p["ind"], lid, op))
            top.append(p)
    top.append(piece("body", "body.svg", (68.52, 89.62, 134.49, 135.46), (-1.95, -1.93, 103.9, 103.86), parent=A))
    top.append(piece("wing front", "wing-front.svg", (193, 150, 50.16, 53.53), (-5.86, -5.45, 111.67, 110.9), pivot=(4, 52),
                     parent=A, rot_track=rf, scale_track=sf))
    top.append(piece("wing back", "wing-back.svg", (174.78, 119.24, 55.59, 56.65), (-5.24, -5.15, 110.49, 110.87), pivot=(22, 82),
                     parent=A, rot_track=rb, scale_track=sb))
    return top + [n_art, n_react, n_bob, n_tilt, n_move]


# ---------------------------------------------------------------- scanner, sweep, beam, data stream
def scanner_layer():
    pos = Track(scan.k[0][1][:2]); size = Track(scan.k[0][1][2:])
    pos.k, size.k = [], []
    for t0, v, e in scan.k:
        pos.k.append([t0, [v[0] + v[2] / 2, v[1] + v[3] / 2], e]); size.k.append([t0, v[2:], e])
    half = lambda sgn: {"a": 1, "k": [{**k, "s": [sgn * k["s"][0] / 2 - 4, -k["s"][1] / 2 - 50]} for k in size.lottie()["k"]]} \
        if len(size.k) > 1 else static([0, 0])
    grad = {"ty": "gf", "o": static(35), "r": 1, "t": 1, "s": half(-1), "e": half(1),
            "g": {"p": 3, "k": static([0, *rgb("#F7CA4C")[:3], .5, 1, 1, 1, 1, *rgb("#F7CA4C")[:3]])}}
    shapes = [group([rect(size.lottie(), r=16.56), grad, stroke("#000000", 2.76, (12.42, 12.42, static(-6)), cap=2)], "scanner")]
    return layer("scanner", 4, ks(p={"a": 1, "k": [{**k, "s": k["s"] + [0]} for k in pos.lottie()["k"]]}), shapes=shapes)


def sweep_layer():
    y = Track(0); x = Track(0); w = Track(120)
    for t0, t1, (sx, sy, sw, sh) in scan_windows:
        x.to(t0 - .01, .001, sx + sw / 2, HOLD); w.to(t0 - .01, .001, sw - 6, HOLD)
        top, bot = sy + 4.5, sy + sh - 4.5
        y.to(t0 - .01, .001, top, HOLD)
        tt, down = t0, True
        while tt < t1:
            y.to(tt, .9, bot if down else top, EASE_IO); tt += .9; down = not down
    p = {"a": 1, "k": []}
    times = sorted({round(k[0], 4) for k in x.k + y.k})
    for t0 in times:
        p["k"].append({"t": round(t0 * FPS, 3), "s": [round(x.val(t0)[0], 2), round(y.val(t0)[0], 2), 0],
                       "o": {"x": [.42], "y": [0]}, "i": {"x": [.58], "y": [1]}})
    bar_w = {"a": 1, "k": [{**k, "s": [k["s"][0], 3]} for k in w.lottie()["k"]]}
    glow_w = {"a": 1, "k": [{**k, "s": [k["s"][0], 16]} for k in w.lottie()["k"]]}
    shapes = [group([rect(bar_w, r=1.5), fill("#FFC91F")], "bar"), group([rect(glow_w, r=8), fill("#FFC91F", 35)], "glow")]
    return layer("scanner · sweep", 4, ks(p=p, o={"a": 1, "k": [{**k, "s": [k["s"][0] * 100]} for k in sweep_on.lottie()["k"]]}), shapes=shapes)


def world_apex(t):
    dx, dy = move.val(t); ti = math.radians(tilt.val(t)[0]); b = bob.val(t)[0]
    ox, oy = r_off.val(t); rr = math.radians(r_rot.val(t)[0]); sx, sy = [v / 100 for v in r_scale.val(t)]
    vx, vy = (APEX[0] - PIVOT[0]) * sx, (APEX[1] - PIVOT[1]) * sy
    px = PIVOT[0] + ox + vx * math.cos(rr) - vy * math.sin(rr)
    py = PIVOT[1] + oy + vx * math.sin(rr) + vy * math.cos(rr) + b
    qx, qy = px - PIVOT[0], py - PIVOT[1]
    return (BEE_ORIGIN[0] + dx + PIVOT[0] + qx * math.cos(ti) - qy * math.sin(ti),
            BEE_ORIGIN[1] + dy + PIVOT[1] + qx * math.sin(ti) + qy * math.cos(ti))


def beam_layer():
    k1, k2, step = [], [], 1 / 30
    n = int(END / step) + 1
    for s in range(n + 1):
        t0 = min(s * step, END)
        ax, ay = world_apex(t0)
        x, y, w, h = scan.val(t0)
        f = round(t0 * FPS, 3)
        k1.append({"t": f, "s": [path([(x, y), (ax, ay), (x + w, y)])]})
        k2.append({"t": f, "s": [path([(x, y + h), (ax, ay), (x + w, y + h)])]})
    for k in k1[:-1] + k2[:-1]:
        k["o"] = {"x": [0], "y": [0]}; k["i"] = {"x": [1], "y": [1]}
    off = {"a": 1, "k": [{"t": 0, "s": [0], "o": {"x": [0], "y": [0]}, "i": {"x": [1], "y": [1]}},
                         {"t": round(END * FPS, 3), "s": [round(-22 * END / .6, 2)]}]}
    shapes = [{"ty": "sh", "nm": "top", "ks": {"a": 1, "k": k1}}, {"ty": "sh", "nm": "bottom", "ks": {"a": 1, "k": k2}},
              stroke("#000000", 2.5, (11, 11, off), cap=1)]
    return layer("beam", 4, ks(), shapes=shapes)


def bit_layers():
    out = []
    for i in range(12):
        pos, op, sc = [], Track(0), Track([60, 60])
        for t0, n in streams:
            if i >= n:
                continue
            x, y, w, h = scan.val(t0)
            s = (x + w / 2, y + h * .35); e = TERM_IN
            c1 = (s[0] - 30, s[1] - 150); c2 = (e[0] + 120, e[1] + 40)
            ts, d = t0 + i * .085, 1.05
            pos.append({"t": round(ts * FPS, 2), "s": [s[0], s[1], 0], "to": [c1[0] - s[0], c1[1] - s[1], 0],
                        "ti": [c2[0] - e[0], c2[1] - e[1], 0], "o": {"x": [.65], "y": [0]}, "i": {"x": [.35], "y": [1]}})
            pos.append({"t": round((ts + d) * FPS, 2), "s": [e[0], e[1], 0], "h": 1})
            op.seq(ts, [(d * .18, 100, LIN), (d * .8, 100, HOLD), (d, 0, LIN)])
            sc.seq(ts, [(d * .18, [100, 100], LIN), (d * .8, [90, 90], LIN), (d, [40, 40], LIN)])
        if pos:
            pos[-1].pop("h", None)
        bw = 12 + ((i * 7) % 3) * 7
        shapes = [group([rect((bw + 10, 16), r=8), fill("#FFC91F", 30)], "glow"),
                  group([rect((bw, 6), r=3), stroke("#0F0F0E", 1.5), fill("#FFC91F")], "bit")]
        out.append(layer(f"data · {i + 1}", 4, ks(p={"a": 1, "k": pos} if len(pos) > 1 else static([0, 0, 0]), o=op.lottie(),
                                                 s={"a": 1, "k": [{**k, "s": k["s"] + [100]} for k in sc.lottie()["k"]]}), shapes=shapes))
    return out


# ---------------------------------------------------------------- static scene (circles, browser, cards)
LAYOUT = json.loads((HERE / "kv-layout.json").read_text())
MONO = Font(HERE / "fonts" / "GeistMono-Regular.ttf")
FLOW = Font(HERE / "fonts" / "FlowCircular-Regular.ttf")


def css_hex(c):
    r, g, b = [int(v) for v in re.findall(r"\d+", c)[:3]]
    return f"#{r:02X}{g:02X}{b:02X}"


def rrect_path(x, y, w, h, r):
    k = 0.5523 * r
    pts = [(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)]
    i = [[-k, 0], [0, 0], [0, -k], [0, 0], [k, 0], [0, 0], [0, k], [0, 0]]
    o = [[0, 0], [k, 0], [0, 0], [0, k], [0, 0], [-k, 0], [0, 0], [0, -k]]
    return path(pts, True, i=i, o=o)


def mask(pt):
    return {"inv": False, "mode": "a", "pt": pt if "a" in pt else static(pt), "o": static(100), "x": static(0), "nm": "clip"}


def outline_group(beziers, color, nm="text"):
    return group([{"ty": "sh", "ks": static(b)} for b in beziers] + [fill(color)], nm)


def ellipse(cx, cy, w, h):
    return {"ty": "el", "d": 1, "p": static([cx, cy]), "s": static([w, h])}


def scene_layers():
    """Returns (above_scanner, below_scanner) layer lists, top-most first."""
    bx, by, bw, bh = LAYOUT["browser"]
    border = layer("browser · border", 4, ks(), shapes=[group([rect((bw - 5.521, bh - 5.521), (bx + bw / 2, by + bh / 2), r=14.689 - 2.76),
                                                                stroke("#000000", 5.521)], "border")])
    # page content, clipped to the browser body
    shapes = []
    for t in LAYOUT["texts"]:
        sz, bez = t["size"], []
        for line in t["lines"]:
            for ch, x, top in line:
                bez += FLOW.contours(ch, sz, x, top + FLOW.asc / FLOW.upm * sz)
        shapes.append(outline_group(bez, css_hex(t["color"]), t["cls"] or "sidebar"))
    for x, y, w, h, col in LAYOUT["cardSq"]:
        shapes.append(group([rect((w, h), (x + w / 2, y + h / 2), r=3.664), fill(css_hex(col))], "thumb"))
    for x, y, w, h in LAYOUT["cards"]:
        shapes.append(group([rect((w - 3.664, h - 3.664), (x + w / 2, y + h / 2), r=10.991 - 1.832), stroke("#F2F2F2", 3.664)], "card"))
    px, py, pw, ph = LAYOUT["body"]
    page = layer("browser · page", 4, ks(), shapes=shapes, hasMask=True, masksProperties=[mask(path(
        [(px, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)], True))])
    # body, toolbar and frame
    tx, ty, tw, th = LAYOUT["toolbar"]
    chrome = [group([{"ty": "sh", "ks": static(path([(px, ty + th - .918), (px + pw, ty + th - .918)]))}, stroke("#E6E6E6", 1.836, cap=1)], "toolbar line")]
    x, y, w, h = LAYOUT["pill"]
    chrome.append(group([rect((w, h), (x + w / 2, y + h / 2), r=h / 2), fill("#F1F1F1")], "pill"))
    for n, (x, y, w, h) in enumerate(LAYOUT["squares"]):
        chrome.append(group([rect((w, h), (x + w / 2, y + h / 2), r=3.664), fill("#F1F1F1" if n < 2 else "#F8F8F8")], "square"))
    chrome.append(group([rect((pw, ph + 20), (px + pw / 2, py + (ph + 20) / 2)), fill("#FFFFFF")], "body"))
    body = layer("browser · body", 4, ks(), shapes=chrome, hasMask=True, masksProperties=[mask(rrect_path(bx, by, bw, bh, 14.689))])
    frame = [group([ellipse(x + w / 2, y + h / 2, w, h) for x, y, w, h in LAYOUT["dots"]] + [fill("#FFFFFF")], "dots"),
             group([rect((bw, bh), (bx + bw / 2, by + bh / 2), r=14.689), fill("#0F0F0E")], "frame"),
             group([rect((bw, bh), (bx + bw / 2 + 16, by + bh / 2 + 16), r=14.689), fill("#000000", 50)], "shadow")]
    browser = layer("browser · frame", 4, ks(), shapes=frame)
    cx, cy, cw, _ = LAYOUT["circles"]
    circles = layer("circles", 4, ks(), shapes=[
        group([ellipse(cx + cw / 2, cy + cw / 2, 395, 395), fill("#FF9D28", 30)], "inner"),
        group([ellipse(cx + cw / 2, cy + cw / 2, 529, 529), fill("#FF9D28", 18)], "outer")])
    return [border], [page, body, browser, circles]


# ---------------------------------------------------------------- terminal (typed commands, results, cursor)
TX, TY, LH, ADV, TSIZE = 151, 39, 24.75, 9, 15
BASE = (LH - (MONO.asc + MONO.desc) * TSIZE / MONO.upm) / 2 + MONO.asc * TSIZE / MONO.upm   # baseline within a line box
LINE_W = 260
TCOL = {None: "#FFFFFF", "k": "#FF9D28", "v": "#FFC91F", "dim": "#7B7B7A", "ok": "#1CD2B4", "warn": "#FF9D28", "err": "#FF5A6E"}
ASSETS = []
_line_ids = {}


def special_glyph(ch, x, b, col):
    """✓ ✕ ↻ are not in Geist Mono (the browser used a fallback font) — drawn as strokes in the same 9px cell."""
    if ch == "✓":
        segs = [[(x + 1.2, b - 5.2), (x + 3.6, b - 2.6), (x + 8, b - 9.4)]]
    elif ch == "✕":
        segs = [[(x + 1.8, b - 9.2), (x + 7.2, b - 3.8)], [(x + 7.2, b - 9.2), (x + 1.8, b - 3.8)]]
    else:  # ↻
        cx, cy, r = x + 4.5, b - 5.8, 3.4
        arc = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(-80, 221, 25)]
        ex, ey = arc[0]
        segs = [arc, [(ex - 2.4, ey - 1.6), (ex, ey), (ex - 1.2, ey + 2.4)]]
    items = [{"ty": "sh", "ks": static(path(s))} for s in segs]
    return group(items + [stroke(col, 1.6, cap=2)], ch)


def line_asset(segs):
    key = json.dumps(segs, ensure_ascii=False)
    if key in _line_ids:
        return _line_ids[key]
    x, groups = 0.0, []
    for seg in segs:
        text, col = seg[0], TCOL[seg[1] if len(seg) > 1 else None]
        bez = []
        for ch in text:
            if ch in "✓✕↻":
                groups.append(special_glyph(ch, x, BASE, col))
            elif ch != " ":
                bez += MONO.contours(ch, TSIZE, x, BASE)
            x += ADV
        if bez:
            groups.append(outline_group(bez, col))
    aid = f"line_{len(_line_ids)}"
    _line_ids[key] = aid
    ASSETS.append({"id": aid, "nm": "".join(s[0] for s in segs), "w": LINE_W, "h": 26,
                   "layers": [{"ddd": 0, "ind": 1, "ty": 4, "nm": "glyphs", "sr": 1, "ks": ks(), "ao": 0, "ip": 0, "op": 10 ** 6,
                               "st": 0, "bm": 0, "shapes": groups}]})
    return aid


def terminal_layers(op_frames):
    out, screen = [], []
    cur_keys, cur_fade = [(0.0, 0, 0)], Track(100)

    def instance(segs, idx, opacity, pos=None, mask_keys=None):
        k = ks(p=(TX, TY + idx * LH), o=opacity)
        if pos:
            k["p"] = {"a": 1, "k": [{**kk, "s": [kk["s"][0] + TX, kk["s"][1] + TY + idx * LH, 0]} for kk in pos.lottie(z=True)["k"]]}
        d = {"ddd": 0, "ind": 0, "ty": 0, "nm": "".join(s[0] for s in segs) or "(blank)", "refId": line_asset(segs), "sr": 1, "ks": k,
             "ao": 0, "w": LINE_W, "h": 26, "ip": 0, "op": op_frames, "st": 0, "bm": 0}
        if mask_keys:
            d["hasMask"] = True
            d["masksProperties"] = [mask({"a": 1, "k": mask_keys})]
        return d

    def cursor_at(t, idx, nchars):
        cur_keys.append((t, TX + nchars * ADV + 1, TY + idx * LH + BASE - 14))

    def fade(t):
        for ln in screen:
            ln["op"].to(t, .25, 0, EASE_IO)
        cur_fade.seq(t, [(.25, 0, EASE_IO), (.26, 100, HOLD)])
        screen.clear()

    pending = []
    for e in events:
        t, a = e["t"], e["a"]
        if a == "reset":
            for i, segs in enumerate(e["lines"]):
                tk = Track(100)
                pending.append((segs, i, tk, None, None)); screen.append({"op": tk})
            cursor_at(0.0, len(e["lines"]) - 1, sum(len(s[0]) for s in e["lines"][-1]))
            cur_keys.pop(0)
        elif a == "type":
            t0 = t if e["append"] else t + .25
            if not e["append"]:
                fade(t)
            sp, g, idx0 = e["speed"] / 1000, 0, len(screen)
            for n_line, segs in enumerate(e["lines"]):
                idx, n = idx0 + n_line, sum(len(s[0]) for s in segs)
                tk = Track(0); tk.to(t0, .001, 100, HOLD)
                mk = [{"t": round(t0 * FPS, 2), "s": [path([(-1, -2), (.01, -2), (.01, 28), (-1, 28)], True)], "h": 1}]
                if n_line > 0 or not e["append"]:
                    cursor_at(t0 + g * sp, idx, 0)
                for c in range(n):
                    tc = t0 + (g + c + 1) * sp
                    w = (c + 1) * ADV
                    mk.append({"t": round(tc * FPS, 2), "s": [path([(-1, -2), (w, -2), (w, 28), (-1, 28)], True)], "h": 1})
                    cursor_at(tc, idx, c + 1)
                mk.append({"t": round((t0 + (g + n + 1) * sp) * FPS, 2) + 1,
                           "s": [path([(-1, -2), (LINE_W, -2), (LINE_W, 28), (-1, 28)], True)]})
                pending.append((segs, idx, tk, None, mk)); screen.append({"op": tk})
                g += n + 1
        elif a == "reveal":
            t0 = t if e["append"] else t + .25
            if not e["append"]:
                fade(t)
            idx0 = len(screen)
            for n_line, segs in enumerate(e["lines"]):
                td = t0 + n_line * .08
                tk = Track(0); tk.to(td, .5, 100, (.2, .7, .2, 1))
                pos = Track([0, 7]); pos.to(td, .5, [0, 0], (.2, .7, .2, 1))
                pending.append((segs, idx0 + n_line, tk, pos, None)); screen.append({"op": tk})
            last = e["lines"][-1]
            cursor_at(t0, idx0 + len(e["lines"]) - 1, sum(len(s[0]) for s in last))
    for segs, idx, tk, pos, mk in pending:
        out.append(instance(segs, idx, tk.lottie(), pos, mk))
    # cursor: position steps, layer fade with the screen, group opacity blinks (visible the first half of every second)
    cur_keys.sort()
    p = {"a": 1, "k": [{"t": round(tt * FPS, 2), "s": [x, y, 0], "h": 1} for tt, x, y in cur_keys]}
    blink = {"a": 1, "k": [{"t": round(s * .5 * FPS, 2), "s": [0 if s % 2 else 100], "h": 1} for s in range(int(END * 2) + 2)]}
    cursor = layer("terminal · cursor", 4, ks(p=p, o=cur_fade.lottie()), shapes=[
        {"ty": "gr", "nm": "block", "it": [rect((8, 17), (4, 8.5)), fill("#FFC91F"),
                                           {**tr(), "o": blink}]}])
    out.reverse()                       # later lines on top
    x, y, w, h = LAYOUT["terminal"]
    box = layer("terminal · box", 4, ks(), shapes=[
        group([rect((w - 4, h - 4), (x + w / 2, y + h / 2), r=10), stroke("#000000", 4)], "border"),
        group([rect((w, h), (x + w / 2, y + h / 2), r=12), fill("#0F0F0E")], "fill"),
        group([rect((w, h), (x + w / 2 + 10, y + h / 2 + 10), r=12), fill("#000000", 30)], "shadow")])
    return [cursor] + out + [box]


# ---------------------------------------------------------------- assemble
events.sort(key=lambda e: e["t"])
OP = round(END * FPS)
bee_layers = build_bee()
above, below = scene_layers()
LAYERS = (bit_layers() + bee_layers + terminal_layers(OP) + [beam_layer()] + above
          + [sweep_layer(), scanner_layer()] + below)
for n, l in enumerate(LAYERS):
    l["op"] = OP
    if l["ty"] == 0:                    # precomp instances have no parent links, so their index can be reassigned freely
        l["ind"] = 10000 + n
anim = {"v": "5.12.2", "fr": FPS, "ip": 0, "op": OP, "w": W, "h": H, "nm": "ScrapingBee hero · key visual", "ddd": 0,
        "assets": ASSETS, "layers": LAYERS, "markers": markers,
        "meta": {"g": "python-lottie build_kv.py"}}
data = json.dumps(anim, separators=(",", ":"), ensure_ascii=False)
(ROOT / "kv-animation.json").write_text(data)
(ROOT / "kv-animation.js").write_text("// Generated by lottie/build_kv.py — do not edit by hand.\n"
                                      f"window.KV_ANIMATION = {data};\n")
print(f"duration {END:.2f}s · {OP} frames · {len(LAYERS)} layers · {len(ASSETS)} line assets · {len(data) / 1024:.0f} KB · {len(blinks)} blinks")
