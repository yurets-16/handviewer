import os, sys, tempfile, threading, unittest
from urllib.parse import parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))
os.environ.setdefault("DDLINE_CACHE", tempfile.mkdtemp(prefix="ddcache-"))
import ddline, ddserver

DEAL = ("n=sA643hKJT8d92cAK3&e=s2h653dQJT7cT9842&s=sKQ97hQ9dAK54cJ75&w=sJT85hA742d863cQ6"
        "&c=4s&dl=n")

def ask(q):
    return ddserver.compute(parse_qs(q, keep_blank_values=True))


class Helpers(unittest.TestCase):
    def test_valid_deal(self):
        hands = {s.upper(): ddserver._parse_hand(parse_qs(DEAL)[s][0]) for s in "nesw"}
        self.assertTrue(ddline._valid_deal(hands))
        short = dict(hands, W=dict(hands["W"], S="JT8"))
        self.assertFalse(ddline._valid_deal(short))
        dup = dict(hands, W=dict(hands["W"], S="AT85"))     # the spade ace twice
        self.assertFalse(ddline._valid_deal(dup))
        self.assertFalse(ddline._valid_deal({"N": hands["N"]}))

    def test_pick_lead_rank(self):
        self.assertEqual(ddline._pick_lead_rank("KQ72", "Q"), ("Q", False))
        self.assertEqual(ddline._pick_lead_rank("KQ72", "9"), ("7", True))
        self.assertEqual(ddline._pick_lead_rank("KQ", "2"), ("Q", True))
        self.assertEqual(ddline._pick_lead_rank("", "2"), (None, False))


@unittest.skipUnless(ddline.HAVE_DDS, "endplay is not installed")
class Api(unittest.TestCase):
    def test_line(self):
        r = ask(DEAL + "&l=d8")
        self.assertEqual(len(r["p"]), 52)
        self.assertEqual(r["p"][0], "d7")                  # East has no d8: nearest lower is d7
        self.assertEqual(len(set(r["p"])), 52)

    def test_eval_and_continuation(self):
        r = ask(DEAL + "&played=")
        self.assertEqual(r["turn"], "E")
        self.assertEqual(13 - r["best"], 11)               # N-S make eleven tricks in spades
        cont = ask(DEAL + "&played=dq&line=1")["p"]
        self.assertEqual(len(cont), 51)

    def test_broken_deals_never_reach_dds(self):
        for bad in (DEAL.replace("w=sJT85", "w=sAT85"),     # duplicated card
                    DEAL.replace("w=sJT85", "w=sJT8"),      # twelve cards
                    DEAL.replace("&e=s2h653dQJT7cT9842", "")):
            self.assertEqual(ask(bad)["p"], [])
            self.assertFalse(ask(bad + "&played=").get("cards"))
            self.assertEqual(ask(bad + "&played=&line=1")["p"], [])

    def test_cache(self):
        cache = os.environ["DDLINE_CACHE"]
        hands = {s.upper(): ddserver._parse_hand(parse_qs(DEAL)[s][0]) for s in "nesw"}
        line = ddline.line_for(hands, "S", "N")
        self.assertTrue(os.path.exists(os.path.join(cache, ddline.cache_key(hands, "S", "N") + ".json")))
        # a cache hit must not wait for the solver lock (held here as if another request were solving)
        with ddline._DDS_LOCK:
            out = []
            t = threading.Thread(target=lambda: out.append(ddline.line_for(hands, "S", "N")))
            t.start(); t.join(5)
            self.assertEqual(out, [line])
        # an unusable continuation (the prefix is not a card East holds) is answered but not stored
        before = set(os.listdir(cache))
        self.assertEqual(ddline.line_from_for(hands, "S", "N", ["sa"]), [])
        self.assertEqual(set(os.listdir(cache)), before)

    def test_bad_contract(self):
        self.assertEqual(ask(DEAL.replace("c=4s", "c=zz"))["p"], [])


if __name__ == "__main__":
    unittest.main()
