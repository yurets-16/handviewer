# Hand viewer

A bridge deal viewer in one static HTML file: the four hands around the table, the auction, the
double-dummy makeable-tricks grid and par, and a play panel. The panel steps through a recorded or
double-dummy line card by card, or lets you play the hand yourself, alone, against the double-dummy
or blind. It also checks the table's play card by card, lists what every opening lead is worth and
sets the deal as a "guess the lead" or "find the card" problem. A link can hold a whole set of deals
with a score. Deals print on one sheet and save as SVG or PNG. The page speaks English and Russian.

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
| `c`    | contract, with `x`/`xx` for doubled/redoubled; a bare number is BBO's tricks claimed (see below) | `4s`, `3nt` (or `3n`), `5dx` |
| `dl`   | declarer; with `c`, it turns on the play panel | `n` |
| `r`    | result, shown as text next to the contract | `+1`, `=`, `-2` |
| `b`    | board number | `12` |
| `a`    | auction from the dealer, calls separated by `-` or `,`: `p`, `x`, `xx`, `1c` … `7nt`; run together as in BBO, with `D` and `R` for the doubles, it works too. Without `c`, the contract and declarer are read from it | `1nt-p-3nt-p-p-p`, `ppp3NDppp` |
| `dd`   | makeable tricks: 20 base-36 digits, five per seat in the order N, E, S, W, and within a seat NT, ♠, ♥, ♦, ♣; left out, the page asks the API for them | `bbba922233bbba922233` |
| `par`  | par: level, strain, optional declarer, then free text; left out, it is worked out from `dd`, `d` and `v` | `3ntn +460` |
| `p`    | a card play sequence from the opening lead, separated by commas or spaces, or run together as in BBO | `h2,hq,h9,h6`, `H2HQH9H6` |
| `pa`   | `1` = the `p` line is the play at the table; otherwise it is labelled a double-dummy line | `1` |
| `pl`   | who sat where: `name\|team` per seat in the order N, E, S, W, joined by `~` | `Ann\|Lions~Bob\|Tigers~…` |
| `nn` `en` `sn` `wn` | a player per seat as BBO links give them, without a team; `pl` wins | `nn=Ann&sn=Bob` |
| `l`    | opening lead the DD line starts from; ▶, best line and claim open with it too, and the play panel says what it cost | `c9`, `ct` (or `c10`) |
| `at`   | open "Play it yourself" with these cards played; the ⧉ button makes such a link | `c5,cq,c2` |
| `pos`  | open the line at this step; the ⧉ button makes such a link | `17` |
| `quiz` | `1` = open as "Guess the lead": only the hand on lead and the auction show until a card is picked | `1` |
| `task` | `1` = open as "Find the card": the line stops at its key moments, where one card keeps the result | `1` |
| `set`  | a JSON file on the same site with a set of deals (see below); alone in the link, it opens at `i` | `/sets/leads.json` |
| `i`    | the place in the set, from 0 | `3` |
| `tc`   | a contract to practise, `contract.declarer`: it replaces `c` and `dl` on the page and drops the table's lead, play and result; `c` and `dl` stay in the link, and the page goes back to them. Needs all four hands, and a set ignores it | `3nt.s`, `5dx.e` |
| `view` | `1` = the deal alone, with no double-dummy of any kind (grid, par, hints, leads) and neither the table's lead nor its result, even if the link carries them, and nothing highlighted; "Play it yourself" stays a tab away, there is no other contract. For a deal set as a problem | `1` |
| `ol`   | the field's opening leads, card and count, most led first; "Guess the lead" shows them after the answer | `sk12,d34` |
| `blind` | `1` = open as declarer playing blind: your two hands only, no hints, a review after the last card | `1` |
| `api`  | URL of the double-dummy API (see below); left out, the page tries `/api/ddline` on its own site; empty, the API stays off | `https://example.org/dd` |
| `back` | URL for a "← back" link (http/https only) | `https://example.org/round/3` |

Every value from the URL is escaped before it reaches the page, so links from untrusted sources
are safe to open.

Keyboard: in both views ←/→ step, ↓ next trick, ↑ or Home first card, End last card. In the line
view space is autoplay; when you play the hand yourself ⌫ or U also steps back, R restarts, B plays
the best line, C claims, and Tab reaches the cards, Enter or space plays one. In a set PgUp and PgDn
change the deal, and Enter goes on from an answer.

The table opens with North on top, or with the hand on lead at the bottom in "Guess the lead". A
button in declarer's label puts declarer at the bottom and then North back on top; ↻ turns the table
a seat at a time. A print keeps North on top. Played cards stay in the hands in grey; "hide played" at the top takes them out,
and the page remembers the choice in this browser. A print always shows the whole deal. DDS at the top
marks the cards of the hand on turn with what the contract makes after each, card by card along a
line or while you play the hand yourself.
SVG, PNG and PBN at the foot of the page save the deal.

On a phone or a touch screen the play stays right under the table and the hand on turn comes again
there in cards big enough for a finger. A light system gets light colours.

With the API, the opening leads are listed by what declarer then makes. When `pa=1` marks the play
as the table's, every card is checked in turn: that is up to 48 requests per deal, three at a time.
Playing blind, the defenders are the double-dummy: they see all four hands and never slip, so a line
that needs a mistake from them will not work.

"Another contract" replays the deal with any contract and declarer. A cell of the double-dummy grid
fills in the form with the contract that makes exactly, or a one-level one when even that fails, and
"Play it" starts the hand; the choice goes into the link as `tc=`, so it can be sent on. A set of deals
does not offer it: the task stays as set.

"Find the card" walks the line, the table's or the double-dummy one, and asks the API about every
position. On a line played at a table (`pa=1`), every card that gave a trick away is a key moment,
and these come first. After them come the moments where the best cards are a single card or touching
ones and the hand holds something worse. Up to five are kept, the dearest first, and shown in play
order. You see what the player on turn sees, that hand and dummy, until the card is found.

## Languages

The page is written in English and works alone in that language. To change it, put a language pack
next to the page as `handviewer.lang.js`: `lang/ru.js` for Russian, `lang/en.js` for English. The
site decides, a link or a browser does not.

A pack is the page's English and what shows instead of it, `{0}` and on for the values put in, and
`tricks` for the word "trick" with its number. What stands after `|` in a key is left out of the
English: it tells apart phrases that English writes alike and another language does not. A phrase the
pack lacks stays English, so a new language can start small.

## Sets of deals

`set=` names a JSON file on the same site. `deals` holds link parameters, one string per deal;
`mode` is `quiz`, `task` or `blind` and is optional, and a bare list of strings works too:

```json
{"title": "Leads of the week", "mode": "quiz", "deals": ["n=sA643hKJT8d92cAK3&e=…&c=4s&dl=n&l=d8", "n=…"]}
```

A bar at the top moves through the set and counts the deals you got right the first time: the best
lead, every key moment at the first try, or a blind hand with no card given away. The score stays
in this browser, under the set's address. A deal's own mode in its string wins over `mode`.

## Links in BBO's format

A link written for BBO's handviewer works here as it stands: `b`, `d`, `v`, `n`, `e`, `s`, `w`,
`a`, `p` and the names `nn`, `en`, `sn`, `wn` mean the same, `--` is a void, and only the address
changes:

```
https://www.bridgebase.com/tools/handviewer.html?b=1&d=n&v=-&n=s--hKQT96dAT94cAT86&…&a=ppp3NDppp
https://example.org/handviewer.html?b=1&d=n&v=-&n=s--hKQT96dAT94cAT86&…&a=ppp3NDppp
```

The rest of BBO's parameters:

- `c` is a number there, the tricks declarer claimed: the play stops where `p` stops, and the result
  comes from the claim and the contract the auction gives.
- `lin` holds a whole LIN record, BBO's own file. Its deal, board, vulnerability, players, auction,
  play and claim stand in for the parameters above; of a file with several boards, the first.
- `linurl` is the address of such a file, plain or in an XML wrapper. The page fetches it and opens
  again with what it holds; when the other site does not allow that, it offers the deal on BBO.
- `myhand` names a deal in BBO's own store, which only BBO can read, so the page links to it there.
- `tbt=y` makes ▶ and → step the line a trick at a time, as BBO's NEXT button does.
- `k` (kibitz) changes nothing: all four hands always show.

A play from a BBO link, run together or from a LIN record, or with a claim, is taken as the play at
the table, as `pa=1` marks it.

The PBN button saves the deal as a file: the hands, dealer, vulnerability, contract, result, auction
and players the link gives, `?` for what it does not, and the play only when `pa=1` marks it as the
table's. The event is `BridgeTournament`, the site is the page's host name, the date is today's. With `tc=` it holds the practice contract, without the table's auction.

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
