#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Double-dummy optimal PLAY LINE for one deal+contract, with a persistent on-disk cache.

The makeable-tricks grid and par can be baked into a viewer link (dd=, par=) at build time; this
adds the actual card-by-card line: fix the opening lead, then let double-dummy play best for
everyone. It is far too expensive to precompute for every board+contract (~52 DDS solves each),
so it is computed lazily — once per (deal, contract, lead) — and cached to disk, so the second
request for the same board (any viewer) is a cheap file read.

Hands are dicts {"N"|"E"|"S"|"W": {"S"|"H"|"D"|"C": "AKT2"}} — ranks high to low, ten as 'T'.
Card strings are the hand-viewer's `p=` format: suit letter + rank, ten as 'T', e.g. 'c7','hA','sT'.
Needs endplay (DDS); without it every call returns [] and the caller simply omits the play line.
"""
import os, json, hashlib, tempfile

try:
    from endplay.types import Deal, Player, Denom
    from endplay.dds import solve_board
    HAVE_DDS = True
except Exception:
    HAVE_DDS = False

_STRAIN = {"NT": "nt", "S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
_PLR = {"N": "north", "E": "east", "S": "south", "W": "west"}
_LHO = {"N": "E", "E": "S", "S": "W", "W": "N"}   # opening leader = declarer's left-hand opponent
_RANKS = "AKQJT98765432"   # high -> low

def _pbn(hands):
    seat = lambda s: ".".join(hands[s][x] for x in "SHDC")
    return "N:" + " ".join(seat(s) for s in ("N", "E", "S", "W"))

def _valid_deal(hands):
    """True iff `hands` is a complete, legal deal — four hands of thirteen cards, all 52 distinct.
    The hands arrive straight from a public URL, and a partial or duplicated deal can HARD-CRASH the
    DDS C solver with an uncatchable SIGSEGV (taking the whole service down), so every entry point
    below rejects one first rather than feeding it in."""
    seats = ("N", "E", "S", "W")
    try:
        cards = [(su, c) for s in seats for su in "SHDC" for c in hands[s][su]]
        if any(sum(len(hands[s][su]) for su in "SHDC") != 13 for s in seats):
            return False
    except (KeyError, TypeError):
        return False
    return len(cards) == 52 and len(set(cards)) == 52

def _pick_lead_rank(cards, spec):
    """cards: the rank chars the opening leader holds in the led suit (e.g. 'KQ72'). spec: the
    recorded lead's rank ('9','T','A'). -> (rank_to_use, substituted).
    Exact card in hand -> it, not substituted. Otherwise the closest card of that suit: the
    HIGHEST card ranked BELOW the recorded one, or (if none) the LOWEST card ranked ABOVE it.
    (None, False) only when the leader is void in the suit."""
    if not cards:
        return None, False
    spec = "T" if spec == "10" else spec
    if spec in cards:
        return spec, False
    if spec not in _RANKS:
        return None, False
    si = _RANKS.index(spec)
    below = [c for c in cards if _RANKS.index(c) > si]   # ranked lower than the recorded card
    if below:
        return min(below, key=_RANKS.index), True         # highest of those below
    above = [c for c in cards if _RANKS.index(c) < si]
    return max(above, key=_RANKS.index), True             # lowest of those above

_CARD_SUIT = {"♣": "c", "♦": "d", "♥": "h", "♠": "s"}   # ♣♦♥♠ -> letters


def _card_str(card):
    """An endplay Card ('♣3','♠A','♥T') -> the viewer's 'c3'/'sA'/'hT'."""
    s = str(card)
    return _CARD_SUIT.get(s[:1], s[:1].lower()) + s[1:]

def _card_key(card):
    """Lower-case play key matching the viewer's interactive cards: '♣A' -> 'ca', '♥T' -> 'ht'."""
    s = str(card)
    return _CARD_SUIT.get(s[:1], s[:1].lower()) + s[1:].lower()

_SEATS_PL = (("N", "north"), ("E", "east"), ("S", "south"), ("W", "west"))

def _replay_prefix(d, played):
    """Play the cards in `played` (lower-case keys, in order) onto deal d. False if a key isn't a
    card available to whoever is on turn there (prefix inconsistent with the deal)."""
    for k in (played or []):
        card = None
        for _lbl, nm in _SEATS_PL:                        # the card is unique — find whichever hand
            card = next((c for c in d[getattr(Player, nm)] if _card_key(c) == k), None)
            if card:
                break
        if card is None:
            return False
        d.play(card)
    return True

def _pos_deal(hands, strain, declarer, played):
    """A Deal set to trump + opening leader with `played` already applied. None if unusable/illegal."""
    if (not HAVE_DDS or not hands or strain not in _STRAIN or declarer not in _LHO
            or not _valid_deal(hands)):
        return None
    try:
        d = Deal(_pbn(hands))
        d.trump = getattr(Denom, _STRAIN[strain])
        d.first = getattr(Player, _PLR[_LHO[declarer]])   # opening leader = declarer's LHO
        return d if _replay_prefix(d, played) else None
    except Exception:
        return None

def dd_eval(hands, strain, declarer, played):
    """Double-dummy evaluation at the position reached after `played` (lower-case keys like
    'c2','ht', in play order). For the player now on turn, the DD tricks their side can still take
    with each of their legal cards — the caller turns that into 'declarer makes N from here' and the
    cost of an off-best card. -> {"turn","side","best","cards":{key:tricks}} or None."""
    if played and len(played) >= 52:                      # nothing left — never solve an empty deal
        return None                                       # (an empty board aborts the DDS engine)
    d = _pos_deal(hands, strain, declarer, played)
    if d is None:
        return None
    try:
        turn = ["N", "E", "S", "W"][int(d.curplayer)]     # curplayer accounts for the partial trick
        cards = {_card_key(c): t for c, t in solve_board(d)}
        if not cards:
            return None
        return {"turn": turn, "side": "ns" if turn in ("N", "S") else "ew",
                "best": max(cards.values()), "cards": cards}
    except Exception:
        return None

def dd_line_from(hands, strain, declarer, played):
    """The double-dummy optimal continuation (lower-case keys) from the position after `played` to
    the end of the hand — every seat playing its own side's best. [] if unusable (the prefix must be
    a legal play sequence)."""
    d = _pos_deal(hands, strain, declarer, played)
    if d is None:
        return []
    try:
        seq = []
        while len(seq) < 52 - len(played or []):
            pairs = list(solve_board(d))
            if not pairs:
                break
            pick = max(pairs, key=lambda ct: ct[1])[0]
            d.play(pick)
            seq.append(_card_key(pick))
        return seq
    except Exception:
        return []


def dd_play_line(hands, strain, declarer, lead=None):
    """The double-dummy optimal line as a list of 52 cards ('c7','hA',...). Starts with `lead`
    (resolved to the nearest card of that suit actually in the leader's hand);
    if `lead` is missing/void, double-dummy also chooses the opening lead. [] if DDS is unavailable
    or the inputs are unusable (no hands, odd strain/declarer, engine error)."""
    if (not HAVE_DDS or not hands or strain not in _STRAIN or declarer not in _LHO
            or not _valid_deal(hands)):
        return []
    try:
        d = Deal(_pbn(hands))
        d.trump = getattr(Denom, _STRAIN[strain])
        leader = _LHO[declarer]                       # opening leader = declarer's LHO
        d.first = getattr(Player, _PLR[leader])
        forced = None                                 # the fixed opening lead as (suit_letter, rank)
        if lead and len(lead) >= 2 and lead[0] in "SHDC":
            rank, _sub = _pick_lead_rank(hands.get(leader, {}).get(lead[0], ""), lead[1:])
            if rank is not None:
                forced = (lead[0].lower(), rank)
        seq = []
        while len(seq) < 52:
            pairs = list(solve_board(d))              # [(Card, tricks_for_side_to_play), ...]
            if not pairs:
                break
            if not seq and forced:
                pick = next((c for c, _t in pairs
                             if _CARD_SUIT.get(str(c)[:1]) == forced[0] and str(c)[1:] == forced[1]),
                            None)
                if pick is None:                      # resolved lead not legal (shouldn't happen) —
                    pick = max(pairs, key=lambda ct: ct[1])[0]     # fall back to DD-best
            else:
                pick = max(pairs, key=lambda ct: ct[1])[0]
            d.play(pick)
            seq.append(_card_str(pick))
        return seq
    except Exception:
        return []


# ----------------------------------------------------------------- persistent cache (dir of files)
def cache_key(hands, strain, declarer, lead=None):
    """A stable short key for (deal, contract-strain, declarer, opening lead). The deal is hashed
    via its PBN so the same board at every table shares one entry."""
    raw = f"{_pbn(hands)}|{strain}|{declarer}|{(lead or '').upper()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _default_cache_dir():
    return os.environ.get("DDLINE_CACHE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".ddcache")


def _cached_json(kind, keyraw, compute, cache_dir=None):
    """Generic one-file-per-key cache (same discipline as line_for): return the cached object if
    present, else compute, store atomically and return. Falsy results are returned but never
    stored — the engine may be off or the position transiently unsolvable."""
    cache_dir = cache_dir or _default_cache_dir()
    key = f"{kind}-{hashlib.sha1(keyraw.encode('utf-8')).hexdigest()[:16]}"
    path = os.path.join(cache_dir, key + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        pass
    obj = compute()
    if obj:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f)
            os.replace(tmp, path)                      # atomic publish
        except OSError:
            pass
    return obj

def eval_for(hands, strain, declarer, played, cache_dir=None):
    """Cache-aware dd_eval: the per-position evaluations are the viewer's most frequent request
    (one per card stepped), identical across visitors — a pure function of the position, so cached
    forever like the play lines."""
    raw = f"{_pbn(hands)}|{strain}|{declarer}|{','.join(played)}|eval"
    return _cached_json("pos", raw, lambda: dd_eval(hands, strain, declarer, played), cache_dir)

def line_from_for(hands, strain, declarer, played, cache_dir=None):
    """Cache-aware dd_line_from (DD-optimal continuation from a mid-play position)."""
    raw = f"{_pbn(hands)}|{strain}|{declarer}|{','.join(played)}|line"
    obj = _cached_json("posline", raw,
                       lambda: {"p": dd_line_from(hands, strain, declarer, played)}, cache_dir)
    return (obj or {}).get("p", [])

def line_for(hands, strain, declarer, lead=None, cache_dir=None):
    """Cache-aware dd_play_line: return the cached line if present, else compute, store and return.
    One JSON file per key (concurrency-friendly — independent boards never touch the same file)."""
    cache_dir = cache_dir or _default_cache_dir()
    key = cache_key(hands, strain, declarer, lead)
    path = os.path.join(cache_dir, key + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("p", [])
    except (FileNotFoundError, ValueError):
        pass
    line = dd_play_line(hands, strain, declarer, lead)
    if line:                                          # never cache an empty (engine-off) result
        try:
            os.makedirs(cache_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"p": line, "strain": strain, "declarer": declarer,
                           "lead": (lead or "").upper()}, f)
            os.replace(tmp, path)                      # atomic publish
        except OSError:
            pass                                       # a cache write failure must never break a view
    return line
