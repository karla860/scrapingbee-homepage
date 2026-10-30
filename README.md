# ScrapingBee homepage — hero prototype

An HTML prototype of the new ScrapingBee homepage hero, built from the Figma design
([ScrapingBee | Website Design](https://www.figma.com/design/o27qn0HSfcNB4AclrqFXyO/ScrapingBee-%7C-Website-Design?node-id=2592-2296))
with the navigation, copy and button behaviour of [scrapingbee.com](https://www.scrapingbee.com/).

The key visual is a Lottie animation: the ScrapingBee bee scans the cards of a web page,
and the scraped data streams into the terminal as clean JSON. Most scrapes succeed; one page
is confusing (resolved with AI extraction) and one is blocked by anti-bot (bypassed with a
stealth proxy). The loop ends with the whole page scraped in one call.

## View it

Open `index.html` in a browser (it loads the fonts and the Lottie player from public CDNs).

- `index.html?t=15` — freeze the animation at second 15 (handy for reviewing a moment)
- `index.html?still` — show the static resting frame

## What's where

| Path | What it is |
| --- | --- |
| `index.html` | The hero: header, copy, CTAs, and the key-visual stage (browser, terminal) |
| `kv-animation.json` | The Lottie animation (bee, scanner, beam, data stream) — usable in any Lottie player |
| `kv-animation.js` | The same animation plus the terminal timeline, loaded by `index.html` |
| `lottie/build_kv.py` | Builds both files with [python-lottie](https://pypi.org/project/lottie/) |
| `assets/` | Logo, icons, badges and key-visual pieces exported from Figma |
| `assets/bee/` | The "Mascot / Bee" component vectors (shared body + per-mood faces) |

## Rebuild the animation

```sh
pip install lottie==0.7.2
python lottie/build_kv.py
```

The script is the single source of timing: it writes the Lottie keyframes and the terminal
events (typed commands, JSON results) that `index.html` plays in sync with the animation.
Terminal copy, scene order and the bee's positions are all set in its "the story" section.

## Notes

- The bee uses the Figma "Mascot / Bee" moods: Focused (scraping), Happy (success),
  Curious (confusing page), Error (blocked) and Excited (finale).
- The prototype always plays; for production, respect `prefers-reduced-motion`
  (for example by starting on the `?still` frame).
