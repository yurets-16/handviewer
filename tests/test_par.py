"""calcPar in handviewer.html against par_vectors.json: double-dummy tables with the par endplay
(DDS) gives them, picked for sacrifices, tied contracts and slams, plus the deals where the level
or the seat that names the contract is the hard part."""
import json, os, re, shutil, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = r"""
const fs=require('fs'), [html,vectors]=process.argv.slice(1);
const code=fs.readFileSync(html,'utf8').match(/const DD_RE[\s\S]*?\n(?=\/\/ ---- double-dummy play line)/)[0];
const calcPar=new Function(code+';return calcPar;')();
console.log(JSON.stringify(JSON.parse(fs.readFileSync(vectors,'utf8')).map(r=>calcPar(r.dd,r.d,r.v))));
"""


SCORES = r"""
const fs=require('fs'), [html]=process.argv.slice(1);
const code=fs.readFileSync(html,'utf8').match(/const DD_RE[\s\S]*?\n(?=\/\/ ---- double-dummy play line)/)[0];
const score=new Function(code+';return bridgeScore;')(), out=[];
for(let level=1;level<=7;level++) for(const strain of 'shdcn') for(let dbl=0;dbl<3;dbl++)
  for(let tricks=0;tricks<=13;tricks++) for(const vul of [false,true])
    out.push([level,strain,dbl,tricks,vul,score(level,strain,dbl,tricks,vul)]);
console.log(JSON.stringify(out));
"""


def as_endplay(par):
    """'3ntn= NS +400' -> ('3NTN=', 400); 'Passed out' -> ('', 0)."""
    if par == "Passed out":
        return "", 0
    c, score = par.split(" NS ")
    m = re.match(r"(\d)(nt|[shdc])(.*)$", c)
    strain = "NT" if m[2] == "nt" else {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}[m[2]]
    return m[1] + strain + m[3][0].upper() + m[3][1:], int(score)


@unittest.skipUnless(shutil.which("node"), "needs node")
class Par(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors_path = os.path.join(ROOT, "tests", "par_vectors.json")
        with open(cls.vectors_path, encoding="utf-8") as f:
            cls.vectors = json.load(f)
        out = subprocess.run(["node", "-e", RUN, os.path.join(ROOT, "handviewer.html"), cls.vectors_path],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        cls.pars = json.loads(out)

    def test_score_and_contract_match_dds(self):
        for r, par in zip(self.vectors, self.pars):
            contract, score = as_endplay(par)
            self.assertEqual(score, r["score"], (r, par))
            if contract:
                self.assertIn(contract, r["c"], (r, par))

    def test_covers_the_hard_cases(self):
        self.assertTrue(any("x" in p for p in self.pars), "a sacrifice")
        self.assertIn("Passed out", self.pars)       # the one hand-made row: six tricks all round


@unittest.skipUnless(shutil.which("node"), "needs node")
class Score(unittest.TestCase):
    def test_every_contract_against_endplay(self):
        try:
            from endplay.types import Contract, Denom, Penalty, Player, Vul
        except ImportError:
            self.skipTest("endplay is not installed")
        denom = {"s": Denom.spades, "h": Denom.hearts, "d": Denom.diamonds, "c": Denom.clubs, "n": Denom.nt}
        penalty = [Penalty.passed, Penalty.doubled, Penalty.redoubled]
        out = subprocess.run(["node", "-e", SCORES, os.path.join(ROOT, "handviewer.html")],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        rows = json.loads(out)
        self.assertEqual(len(rows), 7 * 5 * 3 * 14 * 2)
        for level, strain, dbl, tricks, vul, score in rows:
            c = Contract(level=level, denom=denom[strain], declarer=Player.north, penalty=penalty[dbl],
                         result=tricks - level - 6)
            self.assertEqual(score, c.score(Vul.ns if vul else Vul.none), (level, strain, dbl, tricks, vul))


MOMENTS = r"""
const fs=require('fs'), [html,cases]=process.argv.slice(1);
const code=fs.readFileSync(html,'utf8').match(/const DD_RE[\s\S]*?\n(?=\/\/ ---- double-dummy play line)/)[0];
const {onlyMove,keyMoments,parseTC,tcCell}=new Function(code+';return {onlyMove,keyMoments,parseTC,tcCell};')();
const {only,evs,keys,table}=JSON.parse(cases);
console.log(JSON.stringify({only:only.map(c=>onlyMove({best:c.best,cards:c.cards},new Set(c.gone))),
  moments:keyMoments(evs,keys,false,2),table:keyMoments(evs,table,true,4),top:keyMoments(evs,table,true,2),
  tc:["3nt.s","5DX.E","3n.w","4h","8s.n","4h.q",""].map(parseTC),cell:[[10,"h","n"],[6,"NT","e"],[13,"s","w"]].map(a=>tcCell(...a))}));
"""


@unittest.skipUnless(shutil.which("node"), "needs node")
class Moments(unittest.TestCase):
    def test_only_moves(self):
        ev = lambda best, **cards: {"best": best, "cards": cards}
        case = lambda e, *gone: {**e, "gone": list(gone)}
        moved = {"only": [
            case(ev(3, hq=3, h5=2, c2=1)),                    # one card, the rest is worse: 1 by the best other
            case(ev(3, hq=3, hj=3, c2=2)),                    # touching cards are one card
            case(ev(3, hq=3, h9=3, c2=2), "hj", "ht"),        # the cards between are gone
            case(ev(3, hq=3, h9=3, c2=2), "hj"),              # the ten is alive between them
            case(ev(3, hq=3, c2=3, d4=2)),                    # two suits work
            case(ev(3, hq=3, h5=3)),                          # nothing is worse
        ], "evs": [
            ev(5, sa=5, s2=4), ev(5, h2=5, h3=4), None, ev(5, c2=5, c3=2), ev(5, d2=5, d3=5),
            ev(5, sk=5, s3=4, s4=4), ev(5, c5=5, d5=5, h5=4),
        ], "keys": ["sa", "h2", "d9", "c2", "d2", "sk", "c5"],
           "table": ["sa", "h3", "d9", "c3", "d2", "s3", "h5"]}     # four cards that gave a trick away
        out = subprocess.run(["node", "-e", MOMENTS, os.path.join(ROOT, "handviewer.html"), json.dumps(moved)],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        r = json.loads(out)
        self.assertEqual([bool(x) for x in r["only"]], [True, True, True, False, False, False])
        self.assertEqual(r["only"][0]["gap"], 1)
        self.assertEqual([m["i"] for m in r["moments"]], [3, 5])   # dearest first, shown in play order
        self.assertEqual([m["i"] for m in r["table"]], [1, 3, 5, 6])
        self.assertTrue(all(m["err"] for m in r["table"]))         # 6 counts though it is no only move
        self.assertEqual(r["table"][3]["best"], ["c5", "d5"])
        self.assertEqual(r["table"][1]["gap"], 3)
        self.assertEqual([m["i"] for m in r["top"]], [3, 5])       # the table's dearest cards first
        self.assertEqual(r["tc"], [{"c": "3nt", "dl": "s"}, {"c": "5dx", "dl": "e"}, {"c": "3nt", "dl": "w"},
                                   None, None, None, None])
        self.assertEqual(r["cell"], ["4h.n", "1nt.e", "7s.w"])     # what makes exactly, at least the one level


PBN = r"""
const fs=require('fs'), [html,cases]=process.argv.slice(1);
const code=fs.readFileSync(html,'utf8').match(/const DD_RE[\s\S]*?\n(?=\/\/ ---- double-dummy play line)/)[0];
const {pbnText}=new Function(code+';return {pbnText};')();
console.log(JSON.stringify(JSON.parse(cases).map(pbnText)));
"""


@unittest.skipUnless(shutil.which("node"), "needs node")
class Pbn(unittest.TestCase):
    HANDS = {"n": {"s": "3", "h": "4JA3", "d": "AJ42", "c": "KJ42"}, "e": {"s": "AK6", "h": "T5", "d": "8753", "c": "AQ95"},
             "s": {"s": "Q942", "h": "Q8762", "d": "K9", "c": "83"}, "w": {"s": "JT875", "h": "K9", "d": "QT6", "c": "T76"}}

    def texts(self, *cases):
        out = subprocess.run(["node", "-e", PBN, os.path.join(ROOT, "handviewer.html"), json.dumps(cases)],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        return json.loads(out)

    def test_a_board_reads_back_in_endplay(self):
        try:
            from endplay.parsers import pbn
            from endplay.types import Denom, Penalty, Player, Vul
        except ImportError:
            self.skipTest("needs endplay")
        cards = ["sk", "s2", "s5", "s3", "c5", "c3", "c6", "ck", "ha", "h5", "h2", "h9", "h3"]
        play = [{"card": c, "who": w} for c, w in zip(cards, "eswn" "eswn" "nesw" "n")]    # North wins the second
        full = dict(event="BridgeTournament", site="results.neobridge.eu", date="2026.11.02",
                    hands=self.HANDS, dealer="e", vul="b", board="12", contract="4hx", decl="n", result="+1",
                    auction=["1d", "p", "1h", "x", "2h", "p", "4h", "x", "p", "p", "p"], play=play,
                    players={"n": {"n": 'An"n'}, "w": {"n": "Ю\nВ"}})
        text = self.texts(full)[0]
        self.assertIn('[Deal "E:AK6.T5.8753.AQ95 Q942.Q8762.K9.83 JT875.K9.QT6.T76 3.AJ43.AJ42.KJ42"]', text)
        self.assertIn('[Result "11"]', text)
        self.assertIn('[Event "BridgeTournament"]\n[Site "results.neobridge.eu"]\n[Date "2026.11.02"]\n', text)
        self.assertIn('[West "Ю В"]', text)                            # no new tag out of a name
        self.assertIn('[Play "E"]\nSK S2 S5 S3\nC5 C3 C6 CK\nH5 H2 H9 HA\n- - - H3\n*\n', text)   # a column to a seat
        b = pbn.loads(text)[0]
        self.assertEqual(b.board_num, 12)
        self.assertEqual(b.dealer, Player.east)
        self.assertEqual(b.vul, Vul.both)
        self.assertEqual(str(b.deal.north), "3.AJ43.AJ42.KJ42")
        self.assertEqual(str(b.deal.west), "JT875.K9.QT6.T76")
        self.assertEqual((b.contract.level, b.contract.denom, b.contract.declarer, b.contract.penalty, b.contract.result),
                         (4, Denom.hearts, Player.north, Penalty.doubled, 1))
        self.assertEqual(len(b.auction), 11)
        suit = str.maketrans("♠♥♦♣", "shdc")
        self.assertEqual([str(c).translate(suit).lower() for c in b.play], cards)    # played in the order it went

    def test_what_the_link_does_not_say(self):
        bare, out, junk = self.texts(
            dict(hands=self.HANDS, dealer="n", vul="-"),
            dict(hands=self.HANDS, dealer="s", vul="n", auction=["p", "p", "p", "p"]),
            dict(hands={**self.HANDS, "w": {"s": "", "h": "", "d": "", "c": ""}}, dealer="n", vul="e", board="<b>",
                 contract="9zz", decl="q", result="x", auction=["1h", "<i>", "p"]))
        self.assertIn('[Vulnerable "None"]', bare)
        self.assertIn('[Site "?"]\n[Date "????.??.??"]\n', bare)
        self.assertIn('[Contract "?"]', bare)
        self.assertNotIn("[Auction", bare)
        self.assertIn('[Contract "Pass"]', out)                        # passed out is an answer, not unknown
        self.assertIn('[Declarer ""]', out)
        self.assertTrue(junk.split('[Deal "')[1].startswith("N:3.AJ43.AJ42.KJ42 AK6.T5.8753.AQ95 Q942.Q8762.K9.83 -"))
        self.assertIn('[Board "?"]', junk)
        self.assertIn('[Declarer "?"]', junk)
        self.assertIn("1H Pass *", junk)                               # the junk call is gone, the auction is unfinished


LANGS = r"""
const fs=require('fs'), path=require('path'), [root]=process.argv.slice(1);
const html=fs.readFileSync(path.join(root,'handviewer.html'),'utf8'), window={};
new Function('window',fs.readFileSync(path.join(root,'lang','ru.js'),'utf8'))(window);
new Function('window',fs.readFileSync(path.join(root,'lang','en.js'),'utf8'))(window.en={});
const keys=[...html.matchAll(/(?<![\w.$])T\("((?:[^"\\]|\\.)*)"/g)].map(m=>JSON.parse(`"${m[1]}"`));
const titles=[...html.matchAll(/ title="([^"$]*)"/g)].map(m=>m[1]);
const pack=window.HV_LANG;
console.log(JSON.stringify({keys,titles,text:pack.text,en:window.en.HV_LANG,tricks:[1,2,5,11,12,21,22,25].map(pack.tricks)}));
"""


@unittest.skipUnless(shutil.which("node"), "needs node")
class Languages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", "-e", LANGS, ROOT], capture_output=True, text=True, encoding="utf-8", check=True).stdout
        cls.r = json.loads(out)

    def test_russian_has_every_phrase_and_no_stray_one(self):
        used, text = set(self.r["keys"]) | set(self.r["titles"]), self.r["text"]
        self.assertEqual(sorted(used - set(text)), [])
        self.assertEqual(sorted(set(text) - used), [])

    def test_values_go_through(self):
        for k, v in self.r["text"].items():
            self.assertEqual(sorted(re.findall(r"\{\d\}", k)), sorted(re.findall(r"\{\d\}", v)), k)

    def test_word_for_tricks(self):
        self.assertEqual(self.r["tricks"], ["1 взятку", "2 взятки", "5 взяток", "11 взяток", "12 взяток",
                                            "21 взятку", "22 взятки", "25 взяток"])

    def test_the_page_itself_is_english(self):
        self.assertEqual(self.r["en"], {"lang": "en"})
        with open(os.path.join(ROOT, "handviewer.html"), encoding="utf-8") as f:
            self.assertIsNone(re.search("[А-Яа-яЁё]", f.read()))


if __name__ == "__main__":
    unittest.main()
