# Hand viewer

A bridge deal viewer in one static HTML file: the four hands around the table, the auction, the
double-dummy makeable-tricks grid and par, and a play panel. The panel steps through a recorded or
double-dummy line card by card, or lets you play the hand yourself, alone, against the double-dummy
or blind. It also checks the table's play card by card, lists what every opening lead is worth and
sets the deal as a "guess the lead" problem. The page speaks English and Russian.

Everything the viewer shows comes from the URL, so any results site can link to it without a
build step, a framework or a database. The double-dummy features of the play panel (the DD line,
per-card DDS, best line, claim, playing against the double-dummy) need a small optional API,
included here in `server/`.

## Quick start

Serve the page with any static server:

```bash
python -m http.server 8000
```

Then open

```
http://127.0.0.1:8000/handviewer.html?n=sA643hKJT8d92cAK3&e=s2h653dQJT7cT9842&s=sKQ97hQ9dAK54cJ75&w=sJT85hA742d863cQ6&d=n&v=-&c=4s&dl=n&r=%2B1&a=1nt-p-2c-p-2h-p-3nt-p-4s-p-p-p&dd=bbba922233bbba922233&par=3ntn%20%2B460
```

To light up the double-dummy features, run the API (it needs [endplay](https://github.com/dominicprice/endplay)):

```bash
pip install -r requirements.txt
```

```bash
python server/ddserver.py --host 127.0.0.1 --port 8098
```

The page looks for the API at `/api/ddline` on its own site, so behind a proxy at that path (see
below) links need nothing more. Anywhere else, add `&api=http://127.0.0.1:8098/ddline` to the link.
The API answers with `Access-Control-Allow-Origin: *`, so it may live on another host or port.

## Link parameters

Seats are `n`, `e`, `s`, `w`; suits `s`, `h`, `d`, `c`; ranks `AKQJT98765432` (ten is `T`).
Letters are case-insensitive. Only the hands are required.

| Param  | Meaning | Example |
|--------|---------|---------|
| `n` `e` `s` `w` | a hand: each suit letter followed by its ranks | `sA643hKJT8d92cAK3` |
| `d`    | dealer (default `n`) | `e` |
| `v`    | vulnerability: `-` none, `n` N-S, `e` E-W, `b` both | `b` |
| `c`    | contract, with `x`/`xx` for doubled/redoubled | `4s`, `3nt` (or `3n`), `5dx` |
| `dl`   | declarer; with `c`, it turns on the play panel | `n` |
| `r`    | result, shown as text next to the contract | `+1`, `=`, `-2` |
| `b`    | board number | `12` |
| `a`    | auction from the dealer, calls separated by `-` or `,`: `p`, `x`, `xx`, `1c` … `7nt`; run together as in BBO, with `D` and `R` for the doubles, it works too. Without `c`, the contract and declarer are read from it | `1nt-p-3nt-p-p-p`, `ppp3NDppp` |
| `dd`   | makeable tricks: 20 base-36 digits, five per seat in the order N, E, S, W, and within a seat NT, ♠, ♥, ♦, ♣; left out, the page asks the API for them | `bbba922233bbba922233` |
| `par`  | par: level, strain, optional declarer, then free text; left out, it is worked out from `dd`, `d` and `v` | `3ntn +460` |
| `p`    | a card play sequence from the opening lead, separated by commas or spaces | `h2,hq,h9,h6` |
| `pa`   | `1` = the `p` line is the play at the table; otherwise it is labelled a double-dummy line | `1` |
| `pl`   | who sat where: `name\|team` per seat in the order N, E, S, W, joined by `~` | `Ann\|Lions~Bob\|Tigers~…` |
| `l`    | opening lead the DD line starts from; ▶, best line and claim open with it too, and the play panel says what it cost | `c9`, `ct` (or `c10`) |
| `at`   | open "Play it yourself" with these cards played; the ⧉ button makes such a link | `c5,cq,c2` |
| `pos`  | open the line at this step; the ⧉ button makes such a link | `17` |
| `quiz` | `1` = open as "Guess the lead": only the hand on lead and the auction show until a card is picked | `1` |
| `blind` | `1` = open as declarer playing blind: your two hands only, no hints, a review after the last card | `1` |
| `lang` | `ru` or `en`; left out, the browser's language decides | `ru` |
| `api`  | URL of the double-dummy API (see below); left out, the page tries `/api/ddline` on its own site; empty, the API stays off | `https://example.org/dd` |
| `back` | URL for a "← back" link (http/https only) | `https://example.org/round/3` |

Every value from the URL is escaped before it reaches the page, so links from untrusted sources
are safe to open.

Keyboard: in both views ←/→ step, ↓ next trick, ↑ or Home first card, End last card. In the line
view space is autoplay; when you play the hand yourself ⌫ also steps back, R restarts, B plays the
best line, C claims.

With the API, the opening leads are listed by what declarer then makes. When `pa=1` marks the play
as the table's, every card is checked in turn: that is up to 48 requests per deal, three at a time.
Playing blind, the defenders are the double-dummy: they see all four hands and never slip, so a line
that needs a mistake from them will not work.

## Links in BBO's format

A link written for BBO's handviewer works here as it stands: `b`, `d`, `v`, `n`, `e`, `s`, `w` and
`a` mean the same, `--` is a void, and only the address changes:

```
https://www.bridgebase.com/tools/handviewer.html?b=1&d=n&v=-&n=s--hKQT96dAT94cAT86&…&a=ppp3NDppp
https://example.org/handviewer.html?b=1&d=n&v=-&n=s--hKQT96dAT94cAT86&…&a=ppp3NDppp
```

`handviewer.svg` is a small square button for such a link, a spade with a play sign cut out of it:

```html
<a href="/handviewer.html?…" target="_blank"><img src="/handviewer.svg" width="16" height="16" alt="Play the hand"></a>
```

## The double-dummy API

`server/ddserver.py` is a standard-library HTTP server over `server/ddline.py`, which drives the
[DDS](https://github.com/dds-bridge/dds) solver through endplay. Hands use the viewer's format.

- `GET /ddline?n=&e=&s=&w=&grid=1` returns the makeable-tricks grid, no contract needed:
  `{"p": [], "dd": "bbba922233bbba922233"}`
- `GET /ddline?n=&e=&s=&w=&c=&dl=&l=` returns the full DD line from the opening lead:
  `{"p": ["c7","cA",…], "strain": "H", "declarer": "E", "lead": "C9"}`
- `GET /ddline?…&played=k1,k2,…` evaluates the position after those cards for the player on turn:
  `{"turn": "W", "side": "ew", "best": 5, "cards": {"c7": 5, "ca": 4, …}}`
- `GET /ddline?…&played=k1,k2,…&line=1` returns the DD-optimal continuation: `{"p": […]}`

An incomplete or illegal deal, or a contract it cannot read, gets an empty answer (`p: []` /
`cards: {}`), never an error page. Such deals are rejected before they reach DDS, because a
malformed deal can crash the solver.

Results are cached as one JSON file per position in `.ddcache/` next to `server/`, or in the
directory named by `DDLINE_CACHE`. The cache is never pruned. On a public server, anyone can grow
it by requesting new deals, so give it a disk quota, clean it from cron, or rate-limit the
endpoint in your proxy.

The DDS engine is not thread-safe, so the server runs one solve at a time. Each solve takes
milliseconds.

Behind nginx:

```nginx
location = /api/ddline { proxy_pass http://127.0.0.1:8098/ddline; }
```

## Tests

```bash
python -m unittest discover tests
```

The tests that need endplay are skipped without it.

## Licence

MIT, see [LICENSE](LICENSE). endplay is MIT-licensed and DDS is Apache-2.0.
