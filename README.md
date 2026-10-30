# ScrapingBee homepage — hero prototype

An HTML prototype of the new ScrapingBee homepage hero, built from the Figma design
([ScrapingBee | Website Design](https://www.figma.com/design/o27qn0HSfcNB4AclrqFXyO/ScrapingBee-%7C-Website-Design?node-id=2592-2296))
with the navigation, copy and button behaviour of [scrapingbee.com](https://www.scrapingbee.com/).

The whole key visual is a single, self-contained Lottie animation: the ScrapingBee bee scans the
cards of a web page, and the scraped articles stream into the terminal as clean JSON. Most scrapes succeed; one page
is confusing (resolved with AI extraction) and one is blocked by anti-bot (bypassed with a
stealth proxy). The loop ends with the whole page scraped in one call.

## View it

Open `index.html` in a browser (it loads the page fonts and the Lottie player from public CDNs).

- `index.html?t=15` — freeze the animation at second 15 (handy for reviewing a moment)
- `index.html?still` — show the static resting frame

## What's where

| Path | What it is |
| --- | --- |
| `index.html` | The hero: header, copy, CTAs, and the Lottie player for the key visual |
| `kv-animation.json` | The key-visual Lottie — browser, cards, terminal, scanner, beam, data stream and bee — usable in any Lottie player |
| `kv-animation.js` | The same animation wrapped for `index.html` (so it also works when opened from disk) |
| `lottie/build_kv.py` | Builds both files with [python-lottie](https://pypi.org/project/lottie/) |
| `lottie/glyphs.py` | Converts font glyphs to Lottie outlines |
| `lottie/kv-layout.json` | Positions of the browser, cards and card text, measured from the original HTML build of the scene |
| `lottie/fonts/` | Geist Mono (terminal) and Flow Circular (card text), both SIL Open Font License |
| `assets/` | Logo, icons and badges exported from Figma |
| `assets/bee/` | The "Mascot / Bee" component vectors (shared body + per-mood faces) |
| `figma-ref.png` | Screenshot of the Figma hero frame, for reference |

## Rebuild the animation

```sh
pip install lottie==0.7.2 fonttools==4.59.0
cd lottie && python build_kv.py
```

Everything the animation shows — terminal copy, scene order, the bee's moods and positions — is set in
the script's "the story" section. Text is converted to vector outlines from the bundled fonts, so the
Lottie needs no fonts to play. Each unique terminal line is stored once and reused (precomps).

## Notes

- The bee uses the Figma "Mascot / Bee" moods: Focused (scraping), Happy (success),
  Curious (confusing page), Error (blocked) and Excited (finale).
- The prototype always plays; for production, respect `prefers-reduced-motion`
  (for example by starting on the `?still` frame).
