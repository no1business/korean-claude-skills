"""바이브코딩 앱 출시 전 점검 (한국판)
사용: python scan.py <프로젝트 폴더 또는 .zip> [결과.md]
1) 비밀 키 노출  2) 개인정보처리방침 빠진 항목  3) 다크패턴 의심 화면
결과는 '후보'다. 표시된 곳을 직접 열어 확인한 뒤 고친다.
"""
import os, re, sys, zipfile, tempfile, base64, json

SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "build", "out", ".vercel", "coverage", "__pycache__", ".turbo", "venv", ".venv"}
TEXT_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".htm", ".py", ".rb", ".php", ".java", ".kt",
            ".swift", ".dart", ".go", ".json", ".yml", ".yaml", ".toml", ".env", ".md", ".mdx", ".txt", ".sql", ".astro"}
CLIENT_HINT = re.compile(r"(^|/)(app|pages|src|components|public|web|frontend|client|lib)/|\.(jsx|tsx|vue|svelte|html|astro)$")

# ---------- 1. 비밀 키 ----------
SECRETS = [
    ("토스페이먼츠 시크릿 키", re.compile(r"\b(live|test)_sk_[A-Za-z0-9]{10,}")),
    ("스트라이프 시크릿 키", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{10,}")),
    ("OpenAI API 키", re.compile(r"\bsk-(proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Anthropic API 키", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("AWS 액세스 키", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("구글 API 키", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("개인 키(PEM)", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("슬랙 토큰", re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}")),
    ("깃허브 토큰", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
]
JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")
PW = re.compile(r"""(?i)\b(admin_?pass(word)?|password|passwd|db_?pass(word)?|secret)\s*[:=]\s*['"][^'"\s]{6,}['"]""")
PUBLIC_SECRET_ENV = re.compile(r"\b(NEXT_PUBLIC|VITE|REACT_APP|EXPO_PUBLIC|NUXT_PUBLIC)_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|SK|PASSWORD)[A-Z0-9_]*")

# ---------- 2. 개인정보 ----------
FIELDS = [
    ("이메일", re.compile(r"(?i)type=['\"]email|\bemail\b|이메일")),
    ("휴대폰 번호", re.compile(r"(?i)type=['\"]tel|\bphone\b|mobile|휴대폰|전화번호|연락처")),
    ("이름", re.compile(r"(?i)name=['\"](full_?name|user_?name|name)['\"]|\bfullName\b|이름|성명")),
    ("생년월일", re.compile(r"(?i)birth|생년월일|생일")),
    ("주소", re.compile(r"(?i)\baddress\b|postcode|zipcode|주소|우편번호")),
    ("결제 정보", re.compile(r"(?i)card_?number|billing|requestPayment|payment|결제|카드번호")),
    ("위치 정보", re.compile(r"(?i)geolocation|getCurrentPosition|latitude|위치 정보")),
    ("성별", re.compile(r"(?i)\bgender\b|\bsex\b|성별")),
]
VENDORS = [
    ("토스페이먼츠", re.compile(r"(?i)tosspayments|@tosspayments|loadTossPayments")),
    ("포트원(아임포트)", re.compile(r"(?i)portone|iamport")),
    ("스트라이프", re.compile(r"(?i)\bstripe\b")),
    ("구글 애널리틱스", re.compile(r"(?i)gtag\(|googletagmanager|google-analytics")),
    ("메타 픽셀", re.compile(r"(?i)fbq\(|connect\.facebook\.net")),
    ("카카오", re.compile(r"(?i)kakao")),
    ("수파베이스", re.compile(r"(?i)supabase")),
    ("파이어베이스", re.compile(r"(?i)firebase")),
    ("채널톡", re.compile(r"(?i)channel\.io|ChannelIO")),
    ("센트리", re.compile(r"(?i)@sentry|sentry\.io")),
    ("믹스패널", re.compile(r"(?i)mixpanel")),
    ("앰플리튜드", re.compile(r"(?i)amplitude")),
    ("OpenAI", re.compile(r"(?i)openai")),
    ("Anthropic", re.compile(r"(?i)anthropic")),
]
POLICY_FILE = re.compile(r"(?i)privacy|개인정보")
POLICY_TEXT = re.compile(r"개인정보\s*처리\s*방침|개인정보처리방침|Privacy Policy", re.I)
SECTIONS = [
    ("수집하는 개인정보 항목", re.compile(r"수집.{0,10}항목|수집하는 (개인)?정보")),
    ("이용 목적", re.compile(r"이용\s*목적|처리\s*목적")),
    ("보유·이용 기간", re.compile(r"보유.{0,6}기간|이용\s*기간")),
    ("파기 절차·방법", re.compile(r"파기")),
    ("처리 위탁 / 제3자 제공", re.compile(r"위탁|제3자")),
    ("정보주체의 권리와 행사 방법", re.compile(r"권리|열람|정정|삭제\s*요구")),
    ("개인정보 보호책임자", re.compile(r"보호\s*책임자")),
]

# ---------- 3. 다크패턴 ----------
SUB = re.compile(r"(?i)구독|정기\s*결제|subscription|billingKey|월\s*[\d,]+\s*원|/\s*월")
TRIAL = re.compile(r"(?i)무료\s*체험|free\s*trial|체험\s*기간")
TRIAL_NOTICE = re.compile(r"(?i)유료\s*전환.{0,15}(전|안내|알림)|결제\s*예정.{0,10}(안내|알림)|전환\s*전.{0,10}(알려|안내)|reminder")
CANCEL_UI = re.compile(r"(?i)(구독|멤버십)?\s*해지(하기)?\s*<|>\s*[^<]{0,10}해지[^<]{0,10}<|cancelSubscription|onCancel|/cancel|해지\s*신청")
CANCEL_HARD = re.compile(r"(?i)해지[^\n]{0,40}(고객센터|전화|이메일로|메일로|문의)|(고객센터|전화)[^\n]{0,30}해지")
PRECHECK = re.compile(r"(?i)(defaultChecked(\s*=\s*\{?\s*true\s*\}?)?|checked\s*=\s*\{?\s*true\s*\}?|\bchecked\b(?!=))")
PRECHECK_CTX = re.compile(r"(?i)마케팅|광고|수신|선택|옵션|추가|보험|후원|자동\s*갱신|marketing|newsletter|addon")
REPEAT = re.compile(r"(?i)setInterval\([^)]*(modal|popup|팝업|setOpen|setShow)")
HIDDEN_FEE = re.compile(r"(?i)(배송비|수수료|부가세|서비스\s*요금).{0,20}(별도|추가|결제\s*단계)")


def mask(s):
    s = s.strip("'\"")
    return s[:6] + "****" + (s[-2:] if len(s) > 12 else "")


def jwt_role(tok):
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get("role")
    except Exception:
        return None


def load(root):
    files = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            p = os.path.join(d, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT and not f.startswith(".env"):
                continue
            if os.path.getsize(p) > 800_000 or f in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                continue
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            files.append((os.path.relpath(p, root).replace("\\", "/"), txt))
    return files


def lines_of(txt, rx):
    for i, line in enumerate(txt.splitlines(), 1):
        m = rx.search(line)
        if m:
            yield i, line.strip(), m


def scan(root):
    files = load(root)
    F = {"키": [], "개인정보": [], "다크패턴": []}
    gitignore = next((t for p, t in files if p == ".gitignore"), "")

    # 1. 키
    for p, t in files:
        is_env = os.path.basename(p).startswith(".env")
        if is_env and not p.endswith(".example") and ".env" not in gitignore:
            F["키"].append(("고칠 것", p, 0, ".env 파일이 프로젝트에 들어 있고 .gitignore에 빠져 있어요", "깃허브에 올라가면 키가 그대로 공개돼요. .gitignore에 .env 추가, 이미 올렸다면 키를 새로 발급"))
        for i, line, m in lines_of(t, PUBLIC_SECRET_ENV):
            F["키"].append(("고칠 것", p, i, f"비밀 키를 브라우저용 이름({m.group(0)})으로 쓰고 있어요", "NEXT_PUBLIC_·VITE_ 로 시작하는 값은 누구나 볼 수 있어요. 서버에서만 쓰도록 옮기고 키를 새로 발급"))
        for name, rx in SECRETS:
            for i, line, m in lines_of(t, rx):
                if is_env:
                    continue
                where = "브라우저에 보이는 코드" if CLIENT_HINT.search(p) else "코드"
                F["키"].append(("고칠 것", p, i, f"{name}가 {where}에 그대로 있어요 ({mask(m.group(0))})", "환경변수(.env)로 옮기고, 이미 배포·공유했다면 키를 새로 발급"))
        for i, line, m in lines_of(t, JWT):
            if is_env:
                continue
            if jwt_role(m.group(0)) == "service_role":
                F["키"].append(("고칠 것", p, i, f"수파베이스 service_role 키가 코드에 있어요 ({mask(m.group(0))})", "모든 데이터에 접근하는 관리자 키예요. 서버 전용 환경변수로 옮기고 새로 발급"))
        for i, line, m in lines_of(t, PW):
            if is_env:
                continue
            F["키"].append(("확인 권장", p, i, "비밀번호가 코드에 직접 적혀 있어요", "환경변수로 옮기기"))

    # 2. 개인정보
    code = [(p, t) for p, t in files if not POLICY_FILE.search(p) and not p.endswith((".md", ".txt")) and not os.path.basename(p).startswith(".env")]
    got, ven = {}, {}
    for p, t in code:
        if p.endswith((".json", ".yml", ".yaml", ".toml")):
            for label, rx in VENDORS:
                if rx.search(t):
                    ven.setdefault(label, p)
            continue
        for label, rx in FIELDS:
            for i, line, m in lines_of(t, rx):
                got.setdefault(label, (p, i))
                break
        for label, rx in VENDORS:
            if rx.search(t):
                ven[label] = p
    pol = [(p, t) for p, t in files if POLICY_FILE.search(p) and POLICY_TEXT.search(t)] or [(p, t) for p, t in files if POLICY_TEXT.search(t) and len(t) > 600]
    if not pol:
        F["개인정보"].append(("고칠 것", "-", 0, "개인정보처리방침 페이지를 찾지 못했어요", "개인정보를 받는다면 처리방침을 누구나 볼 수 있게 공개해야 해요 (개인정보 보호법 제30조)"))
    else:
        pp, pt = pol[0]
        for label, (fp, li) in got.items():
            if not re.search(label.replace("·", ".?").replace(" ", r"\s*"), pt) and not (label == "휴대폰 번호" and re.search("전화|연락처|휴대", pt)) and not (label == "결제 정보" and re.search("결제|카드", pt)):
                F["개인정보"].append(("고칠 것", pp, 0, f"앱이 '{label}' 항목을 받는데 처리방침 수집 항목에 없어요 (받는 곳: {fp}:{li})", f"수집 항목에 '{label}' 추가"))
        for label, fp in ven.items():
            if label not in pt and not re.search(re.escape(label.split("(")[0]), pt):
                F["개인정보"].append(("확인 권장", pp, 0, f"'{label}'를 쓰는데 처리방침에 위탁·제공 업체로 안 나와요 (사용: {fp})", "개인정보가 넘어간다면 처리 위탁(또는 제3자 제공) 항목에 업체명과 업무 내용 추가"))
        for label, rx in SECTIONS:
            if not rx.search(pt):
                F["개인정보"].append(("고칠 것", pp, 0, f"처리방침에 '{label}' 항목이 없어요", f"'{label}' 항목 추가"))

    # 3. 다크패턴
    alltxt = "\n".join(t for p, t in code)
    has_sub = bool(SUB.search(alltxt))
    if has_sub:
        if not CANCEL_UI.search(alltxt) or CANCEL_HARD.search(alltxt):
            hit = next(((p, i, l) for p, t in code for i, l, m in lines_of(t, CANCEL_HARD)), None)
            loc = (hit[0], hit[1]) if hit else ("-", 0)
            F["다크패턴"].append(("고칠 것", loc[0], loc[1], "구독은 앱에서 바로 되는데 해지는 전화·고객센터로만 받는 것 같아요 (취소·탈퇴 방해)", "가입한 것과 같은 방법·같은 단계로 앱 안에서 바로 해지할 수 있게 버튼 추가"))
        if TRIAL.search(alltxt) and not TRIAL_NOTICE.search(alltxt):
            hit = next(((p, i) for p, t in code for i, l, m in lines_of(t, TRIAL)), ("-", 0))
            F["다크패턴"].append(("고칠 것", hit[0], hit[1], "무료 체험이 끝나면 자동으로 유료 결제되는데 전환 전 안내가 안 보여요 (숨은 갱신)", "유료로 넘어가기 전에 금액·날짜를 알리고 동의받기 (안내 메일·알림)"))
    for p, t in code:
        ls = t.splitlines()
        for i, line, m in lines_of(t, PRECHECK):
            ctx = " ".join(ls[max(0, i - 2):i + 1])
            if "checkbox" in ctx.lower() and PRECHECK_CTX.search(line + " " + (ls[i] if i < len(ls) else "")) and "필수" not in line:
                F["다크패턴"].append(("고칠 것", p, i, "선택 항목(마케팅 수신·추가 옵션 등)이 미리 체크돼 있어요 (특정옵션 사전선택)", "기본값을 체크 해제로 바꾸기"))
        for i, line, m in lines_of(t, REPEAT):
            F["다크패턴"].append(("확인 권장", p, i, "팝업을 반복해서 띄우는 코드가 있어요 (반복간섭)", "한 번 닫으면 일정 기간 다시 안 띄우기"))
        for i, line, m in lines_of(t, HIDDEN_FEE):
            F["다크패턴"].append(("확인 권장", p, i, "추가 요금이 뒤 단계에서 붙는 것 같아요 (순차공개 가격)", "첫 화면 가격에 필수 요금 포함해서 보여주기"))
    return files, F, got, ven, has_sub


def report(root, out):
    files, F, got, ven, has_sub = scan(root)
    n = {k: len(v) for k, v in F.items()}
    L = [f"# 출시 전 점검 결과", "",
         f"- 점검한 파일 {len(files)}개 · 비밀 키 {n['키']}건 · 개인정보처리방침 {n['개인정보']}건 · 다크패턴 의심 {n['다크패턴']}건",
         f"- 앱이 받는 정보: {', '.join(got) or '찾지 못함'}",
         f"- 연결된 외부 서비스: {', '.join(ven) or '찾지 못함'}",
         "- 표시된 건 '후보'예요. 해당 줄을 열어 확인하고 고치세요. 법 위반 여부의 최종 판단은 전문가에게 확인하세요.", ""]
    names = {"키": "1. 비밀 키 노출", "개인정보": "2. 개인정보처리방침", "다크패턴": "3. 다크패턴 의심 화면"}
    for k in ("키", "개인정보", "다크패턴"):
        L += [f"## {names[k]} ({n[k]}건)", ""]
        if not F[k]:
            L += ["- 찾은 것 없음", ""]
            continue
        L += ["| 구분 | 위치 | 무엇 | 고치는 법 |", "|---|---|---|---|"]
        for lv, p, i, what, fix in F[k]:
            loc = f"{p}:{i}" if i else p
            L.append(f"| {lv} | `{loc}` | {what} | {fix} |")
        L.append("")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(f"비밀 키 {n['키']}건 · 개인정보처리방침 {n['개인정보']}건 · 다크패턴 의심 {n['다크패턴']}건 -> {out}")
    for k in ("키", "개인정보", "다크패턴"):
        for lv, p, i, what, fix in F[k][:4]:
            print(f"  [{names[k][3:]}] {what}")


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "출시전_점검결과.md"
    if src.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp()
        zipfile.ZipFile(src).extractall(tmp)
        ent = [e for e in os.listdir(tmp) if not e.startswith("__MACOSX")]
        src = os.path.join(tmp, ent[0]) if len(ent) == 1 and os.path.isdir(os.path.join(tmp, ent[0])) else tmp
    report(src, out)
