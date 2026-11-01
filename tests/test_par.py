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


if __name__ == "__main__":
    unittest.main()
