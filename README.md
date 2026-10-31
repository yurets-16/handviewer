# Hand viewer

A bridge deal viewer in one static HTML file: the four hands around the table, the auction, the
double-dummy makeable-tricks grid and par, and a play panel. The panel steps through a recorded or
double-dummy line card by card, or lets you play the hand yourself, alone or against the
double-dummy.

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
| `c`    | contract, with `x`/`xx` for doubled/redoubled | `4s`, `3nt`, `5dx` |
| `dl`   | declarer; with `c`, it turns on the play panel | `n` |
| `r`    | result, shown as text next to the contract | `+1`, `=`, `-2` |
| `a`    | auction from the dealer, calls separated by `-` or `,`: `p`, `x`, `xx`, `1c` … `7nt` | `1nt-p-3nt-p-p-p` |
| `dd`   | makeable tricks: 20 base-36 digits, five per seat in the order N, E, S, W, and within a seat NT, ♠, ♥, ♦, ♣ | `bbba922233bbba922233` |
| `par`  | par: level, strain, optional declarer, then free text; left out, it is worked out from `dd`, `d` and `v` | `3ntn +460` |
| `p`    | a card play sequence from the opening lead, separated by commas or spaces | `h2,hq,h9,h6` |
| `pa`   | `1` = the `p` line is the play at the table; otherwise it is labelled a double-dummy line | `1` |
| `pl`   | who sat where: `name\|team` per seat in the order N, E, S, W, joined by `~` | `Ann\|Lions~Bob\|Tigers~…` |
| `l`    | opening lead the API should start its DD line from | `c9` |
| `api`  | URL of the double-dummy API (see below); left out, the page tries `/api/ddline` on its own site; empty, the API stays off | `https://example.org/dd` |
| `back` | URL for a "← back" link (http/https only) | `https://example.org/round/3` |

Every value from the URL is escaped before it reaches the page, so links from untrusted sources
are safe to open.

Keyboard: in the line view ←/→ step, ↓ next trick, ↑ restart, space autoplay; when you play the
hand yourself ⌫ undo, R restart, B best line, C claim.

## The double-dummy API

`server/ddserver.py` is a standard-library HTTP server over `server/ddline.py`, which drives the
[DDS](https://github.com/dds-bridge/dds) solver through endplay. Hands use the viewer's format.

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
