#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Double-dummy optimal PLAY LINE for one deal+contract, with a persistent on-disk cache.

The board popup already shows the makeable-tricks grid and par (a static, build-time DDS table).
This adds the actual card-by-card line: fix the opening lead, then let double-dummy play best for
everyone. It is far too expensive to precompute for every board+contract at build time (~52 DDS
solves each), so it is computed lazily — once per (deal, contract, lead) — and cached to disk, so
the second request for the same board (any viewer, any rebuild) is a cheap file read.

Card strings are the hand-viewer's `p=` format: suit letter + rank, ten as 'T', e.g. 'c7','hA','sT'.
Needs endplay (DDS); without it every call returns [] and the caller simply omits the play line.
"""
import os, sys, json, hashlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from endplay.types import Deal, Player, Denom
    from endplay.dds import solve_board
    HAVE_DDS = True
except Exception:
    HAVE_DDS = False

# reuse butler's seat/strain maps + lead-substitution so this line is consistent with the popup's
# "DD·lead" number (same leader, same nearest-card handling for a recorded lead not in the hand).
import butler
_STRAIN = butler._STRAIN                    # {"NT":"nt","S":"spades",...}
_PLR = butler._PLR                          # {"N":"north",...}
_LHO = butler._LHO                          # opening leader = declarer's LHO
_pbn = butler._pbn
_pick_lead_rank = butler._pick_lead_rank
_CARD_SUIT = {"♣": "c", "♦": "d", "♥": "h", "♠": "s"}   # ♣♦♥♠ -> letters


def _card_str(card):
    """An endplay Card ('♣3','♠A','♥T') -> the viewer's 'c3'/'sA'/'hT'."""
    s = str(card)
    return _CARD_SUIT.get(s[:1], s[:1].lower()) + s[1:]


def dd_play_line(hands, strain, declarer, lead=None):
    """The double-dummy optimal line as a list of 52 cards ('c7','hA',...). Starts with `lead`
    (resolved to the nearest card of that suit actually in the leader's hand, matching the popup);
    if `lead` is missing/void, double-dummy also chooses the opening lead. [] if DDS is unavailable
    or the inputs are unusable (no hands, odd strain/declarer, engine error)."""
    if not HAVE_DDS or not hands or strain not in _STRAIN or declarer not in _LHO:
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
    via its PBN so the same board at both tables (and across rebuilds) shares one entry."""
    raw = f"{_pbn(hands)}|{strain}|{declarer}|{(lead or '').upper()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _default_cache_dir():
    return os.environ.get("BUTLER_DDCACHE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "_ddcache")


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
