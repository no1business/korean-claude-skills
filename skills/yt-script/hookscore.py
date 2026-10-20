#!/usr/bin/env python3
"""hookscore.py - score a YouTube hook before you waste a take on it.

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one. The
weakest-link weighting is deliberate: a hook with four strong properties and one dead one is a hook
that leaks at the dead one, and averaging hides that.

    python3 hookscore.py hooks.txt            # one hook per line, ranked
    python3 hookscore.py --hook "one line"    # score a single hook
    python3 hookscore.py --json hooks.txt     # machine-readable

WHAT THIS CAN AND CANNOT TELL YOU. Measured against 74 real short-form hooks (first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels): it separates deliberately bad
hooks from real ones well, and it separates a creator's own hits from their own misses barely at
all. Treat a low score as a reason to look again, never a high score as a promise.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORMULAS = json.load(open(os.path.join(HERE, "hooks.json")))["hooks"]

FILLER = {"basically","actually","literally","just","really","very","so","kind","sort","like",
          "guys","hey","welcome","today","video","subscribe","channel"}
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","game","changer","secret",
         "powerful","ultimate","best","revolutionary","mind","blowing","unbelievable"}
CONCRETE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
YOU = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)

def words(t): return re.findall(r"[a-z0-9'%$.]+", t.lower())

def specificity(t):
    w = words(t)
    if not w: return 0
    nums = len(CONCRETE.findall(t))
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))

def address(t):
    n = len(YOU.findall(t))
    first = 30 if YOU.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes(t):
    n = len(STAKE.findall(t))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE.search(t) else 0)))

def curiosity(t):
    n = len(CURIOSITY.findall(t))
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if re.search(r"\b(because|so that|which means)\b", t, re.I) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity(t):
    n = len(words(t))
    if n == 0: return 0
    # 9-24 words is the band a spoken hook lands in at ~150wpm inside 10 seconds
    if 9 <= n <= 24: return 100
    if n < 9:  return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)


# ---- 한국어 (Korean edition) -------------------------------------------------------------------
# 한글이 들어간 후킹은 아래 한국어 기준으로 채점한다. 영어 기준은 영어 단어만 세기 때문에 한국어 후킹은
# 숫자 단위, 시청자 호칭, 손해 표현을 하나도 못 알아본다. 숫자는 원본과 같은 점수표를 쓰고, 길이는
# 단어 수 대신 음절 수로 잰다 (보통 말하기 속도로 10초 안쪽 = 약 15~50음절).
HANGUL = re.compile(r"[가-힣]")
def is_ko(t): return bool(HANGUL.search(t))
FILLER_KO = ["여러분 안녕하세요","안녕하세요","오늘은","오늘 영상","구독","좋아요","그냥","약간","일단","사실","진짜로","자 "]
VAGUE_KO = ["대박","미친","미쳤","엄청","역대급","레전드","충격","혁명","최고의","끝판왕","꿀팁","놀라운","대단한","완벽한","비밀"]
CONCRETE_KO = re.compile(r"\d[\d,.]*\s?(%|퍼센트|만|천|억|원|명|개|초|분|시간|일|주|달|개월|년|배|위|가지|번)?"
                         r"|(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|백|천|만)\s?(가지|개|명|번|배|시간|분|초|달|주)")
YOU_KO = re.compile(r"(여러분|당신|님|분들|하시는\s?분|이신\s?분|계신\s?분|되시는\s?분|사장님|본인|세요|나요|죠\b)")
STAKE_KO = re.compile(r"(손해|날리|날려|날립|망하|망해|망한|버리|버려|버립|잃|실패|포기|낭비|후회|늦|그만|모르면|안\s?하면|놓치|아깝|아까|큰일|고장|절대|돈\s?(나가|버리))")
CURIOSITY_KO = re.compile(r"(왜|어떻게|무엇|뭘|뭐가|어느|진짜\s?이유|아무도|대부분|99%|근데|그런데|사실은|딱\s?하나|단\s?하나|만\s?알면|이거|이것|비밀|몰랐)")
CLOSED_KO = re.compile(r"(때문이에요|때문입니다|그래서|그러니까|덕분에)")

def specificity_ko(t):
    nums = len(CONCRETE_KO.findall(t))
    vague = sum(t.count(w) for w in VAGUE_KO)
    filler = sum(t.count(w) for w in FILLER_KO)
    named = len(re.findall(r"\b[A-Za-z][A-Za-z0-9.+-]{1,}\b", t))   # Claude, GPT, YouTube 같은 고유명
    s = 34 + nums * 22 - vague * 16 - filler * 5 + min(18, 6 * named)
    return max(0, min(100, s))

def address_ko(t):
    n = len(YOU_KO.findall(t))
    first = 30 if YOU_KO.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes_ko(t):
    n = len(STAKE_KO.findall(t))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE_KO.search(t) else 0)))

def curiosity_ko(t):
    n = len(CURIOSITY_KO.findall(t))
    q = 18 if t.strip().endswith("?") else 0
    closed = -18 if CLOSED_KO.search(t) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity_ko(t):
    n = len(HANGUL.findall(t)) + len(re.findall(r"[A-Za-z0-9]+", t))
    if n == 0: return 0
    if 15 <= n <= 50: return 100
    if n < 15: return max(30, 100 - (15 - n) * 6)
    return max(10, 100 - (n - 50) * 4)

PROPS_KO = [("SPECIFICITY", specificity_ko), ("ADDRESS", address_ko), ("STAKES", stakes_ko),
            ("CURIOSITY", curiosity_ko), ("BREVITY", brevity_ko)]
LABEL_KO = {"SPECIFICITY": "구체성", "ADDRESS": "호명", "STAKES": "손해", "CURIOSITY": "궁금증", "BREVITY": "길이"}
FIX_KO = {
 "SPECIFICITY": "형용사 하나를 숫자, 이름, 날짜로 바꾸세요",
 "ADDRESS": "첫 여섯 어절 안에 시청자를 부르세요 ('~하시는 분', '사장님')",
 "STAKES": "지금처럼 하면 뭘 잃는지 말하세요 ('모르면 3개월 날려요')",
 "CURIOSITY": "스스로 답해버리는 뒷부분을 자르세요",
 "BREVITY": "15~50음절. 소리 내서 읽고 숨이 찰 때 끊으세요",
}
BAND_KO = {"STRONG": "강함", "WORKABLE": "쓸 만함", "WEAK": "약함"}

PROPS = [("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity)]

def classify(t):
    best, hits = None, 0
    for f in FORMULAS:
        n = sum(1 for p in f["match"] if re.search(p, t, re.I))
        if n > hits: best, hits = f, n
    if not best: return ("분류 안 됨" if is_ko(t) else "Unclassified"), 0
    return (f"{best.get('name_ko', best['name'])} ({best['name']})" if is_ko(t) else best["name"]), hits

def score(t):
    parts = {n: fn(t) for n, fn in (PROPS_KO if is_ko(t) else PROPS)}
    vals = list(parts.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    name, hits = classify(t)
    return parts, verdict, name, hits

def band(v): return "STRONG" if v >= 72 else "WORKABLE" if v >= 55 else "WEAK"

def report(t, parts, verdict, name, hits):
    ko = is_ko(t)
    print(f"\n  {t.strip()}")
    print(f"  {'-' * min(72, max(20, len(t.strip()) * (2 if ko else 1)))}")
    for k, v in parts.items():
        lab = f"{k} {LABEL_KO[k]}" if ko else k
        print(f"    {lab:<16} {v:3d}  {'#' * (v // 5)}")
    print(f"    {'VERDICT 판정' if ko else 'VERDICT':<16} {verdict:3d}  {band(verdict)}" + (f" ({BAND_KO[band(verdict)]})" if ko else ""))
    if ko:
        print(f"    공식             {name}" + (f"  (패턴 {hits}개 일치)" if hits else "  (맞는 공식 없음 - 보통 후킹이 아니라 요약이에요)"))
    else:
        print(f"    formula      {name}" + (f"  ({hits} pattern{'s' if hits != 1 else ''} matched)" if hits else "  (no formula matched - that is usually a summary, not a hook)"))
    low = min(parts, key=parts.get)
    print(f"    가장 약한 곳     {LABEL_KO[low]} - {FIX_KO[low]}" if ko else f"    weakest      {low} - {FIX[low]}")

FIX = {
 "SPECIFICITY": "swap one adjective for a number, a name or a date",
 "ADDRESS": "say 'you' in the first six words",
 "STAKES": "name what it costs them to keep doing it the current way",
 "CURIOSITY": "cut the half of the sentence that answers itself",
 "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}

def main():
    a = sys.argv[1:]
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if "--hook" in a:
        lines = [a[a.index("--hook") + 1]]
    elif a and os.path.exists(a[0]):
        lines = [l for l in open(a[0]).read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1 if not a else 0)
    out = []
    for t in lines:
        parts, verdict, name, hits = score(t)
        out.append({"hook": t.strip(), "properties": parts, "verdict": verdict,
                    "band": band(verdict), "formula": name, "matched": hits})
    out.sort(key=lambda r: -r["verdict"])
    if as_json:
        print(json.dumps([{k: v for k, v in r.items() if k != "matched"} for r in out], indent=1)); return
    for r in out:
        report(r["hook"], r["properties"], r["verdict"], r["formula"], r["matched"])
    if len(out) > 1:
        print(f"\n  winner: {out[0]['hook'].strip()}  ({out[0]['verdict']}, {out[0]['band']})\n")

if __name__ == "__main__":
    main()
