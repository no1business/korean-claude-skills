#!/usr/bin/env python3
"""ai-sales-ko 메일러 — 네이버/지메일 무료 계정(SMTP+IMAP, 앱 비밀번호)으로
제안 메일을 하루 상한·시간대·간격을 지키며 보내고, 답장을 읽어 파일로 남긴다.
표준 라이브러리만 쓴다. 방구석프로 제작 · MIT.

사용법:  python mailer.py <명령> [옵션]
  init            sales/config.json 만들기
  check           로그인만 확인 (메일 안 보냄)
  status          오늘 상한·보낸 수·대기 초안·새 답장 수
  approve <파일|all>  초안을 승인 (status=approved)
  send [--dry-run] [--max N] [--no-wait]   승인된 메일 보내기
  inbox           새 답장 가져오기 → sales/replies/
  reply [--dry-run]   승인된 답장 보내기 (원래 스레드로)
  run             시간대 안에서 발송·답장 확인을 반복 (Ctrl+C 종료)
  stop / resume   전체 발송 중단 / 재개
"""
import email, email.utils, imaplib, json, os, random, re, smtplib, ssl, sys, time
from datetime import datetime, date, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except Exception:  # 윈도우에 tzdata가 없을 때
    from datetime import timezone
    KST = timezone(timedelta(hours=9))

ROOT = Path(os.environ.get("SALES_DIR", "sales"))
CFG, STATE, SUP, STOP = ROOT / "config.json", ROOT / "state.json", ROOT / "suppress.txt", ROOT / "STOP"
OUT, REP, LOG = ROOT / "outbox", ROOT / "replies", ROOT / "sent.log"

PROVIDERS = {
    "gmail": {"smtp": ("smtp.gmail.com", 465), "imap": ("imap.gmail.com", 993)},
    "naver": {"smtp": ("smtp.naver.com", 465), "imap": ("imap.naver.com", 993)},
}
DEFAULT = {
    "product": "기업용 AI 업무 자동화 세팅",
    "sender": {"name": "", "company": "", "email": "", "signature": "", "contact": ""},
    "account": {"provider": "naver", "user": ""},
    "require_approval": True,
    "ad_label": False,
    "warmup": [5, 8, 12, 15, 20],
    "max_daily": 20,
    "window": {"days": [0, 1, 2, 3, 4], "start": 9, "end": 18},
    "gap_minutes": [3, 9],
    "one_per_domain": True,
    "unsubscribe_line": "더 이상 연락을 원하지 않으시면 '수신거부'라고 답장 주세요. 바로 반영하겠습니다.",
    "meeting": {"length": "20분 화상", "slots": []},
    "pricing_note": "",
}
FREE_DOMAINS = {"gmail.com", "naver.com", "daum.net", "hanmail.net", "kakao.com", "nate.com", "hotmail.com", "outlook.com"}


# ---------- 공통 ----------
def now():
    return datetime.now(KST)


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return d


def jsave(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def cfg():
    c = jload(CFG)
    if not c:
        sys.exit("sales/config.json이 없습니다. 먼저 `python mailer.py init`")
    return c


def password():
    pw = os.environ.get("SALES_APP_PASSWORD")
    if not pw:
        sys.exit("환경변수 SALES_APP_PASSWORD가 없습니다. 앱 비밀번호를 사용자가 직접 설정하세요.")
    return pw


def suppressed():
    if not SUP.exists():
        return set()
    return {l.strip().lower() for l in SUP.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def suppress(addr, why=""):
    addr = addr.strip().lower()
    if addr and addr not in suppressed():
        with SUP.open("a", encoding="utf-8") as f:
            f.write(f"{addr}\n")
        print(f"  수신거부 목록 추가: {addr} {why}")


def sent_rows():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def domain(a):
    return a.split("@")[-1].lower().strip()


def state():
    return jload(STATE, {"first_send": None, "seen_uids": [], "last_inbox": None})


def business_days(a, b):
    n, d = 0, a
    while d < b:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def today_cap(c, st):
    if not st.get("first_send"):
        i = 0
    else:
        i = business_days(date.fromisoformat(st["first_send"]), now().date())
    w = c["warmup"]
    return min(w[min(i, len(w) - 1)], c["max_daily"])


def sent_today():
    t = now().date().isoformat()
    return sum(1 for r in sent_rows() if r["at"][:10] == t and r.get("kind") == "first")


def in_window(c):
    n, w = now(), c["window"]
    return n.weekday() in w["days"] and w["start"] <= n.hour < w["end"]


def smtp_login(c):
    host, port = PROVIDERS[c["account"]["provider"]]["smtp"]
    s = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30)
    s.login(c["account"]["user"], password())
    return s


def imap_login(c):
    host, port = PROVIDERS[c["account"]["provider"]]["imap"]
    m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
    m.login(c["account"]["user"], password())
    return m


def build(c, to, subject, body, reply_to_id=None, refs=None):
    msg = EmailMessage()
    s = c["sender"]
    msg["From"] = email.utils.formataddr((s.get("name") or "", c["account"]["user"]))
    msg["To"] = to
    if c.get("ad_label") and not reply_to_id and not subject.startswith("(광고)"):
        subject = "(광고)" + subject
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    mid = email.utils.make_msgid(domain=domain(c["account"]["user"]))
    msg["Message-ID"] = mid
    if reply_to_id:
        msg["In-Reply-To"] = reply_to_id
        msg["References"] = " ".join([x for x in [refs, reply_to_id] if x])
    text = body.rstrip()
    if not reply_to_id:
        tail = [c.get("unsubscribe_line", "")]
        if c.get("ad_label"):
            tail.append(f"보낸 곳: {s.get('company','')} {s.get('name','')} {s.get('contact','')}".strip())
        text += "\n\n" + "\n".join(t for t in tail if t)
    msg.set_content(text)
    return msg, mid


def stopped():
    if STOP.exists():
        print("STOP 파일이 있어 발송하지 않습니다. 재개: python mailer.py resume")
        return True
    return False


# ---------- 명령 ----------
def cmd_init(_):
    for d in (ROOT, OUT, REP):
        d.mkdir(parents=True, exist_ok=True)
    if CFG.exists():
        print("이미 있습니다:", CFG)
    else:
        jsave(CFG, DEFAULT)
        print("만들었습니다:", CFG, "→ 상품·보내는 사람·계정을 채우세요.")
    if not SUP.exists():
        SUP.write_text("# 다시 보내면 안 되는 주소 (한 줄에 하나)\n", encoding="utf-8")
    lead = ROOT / "leads.csv"
    if not lead.exists():
        lead.write_text("company,region,job_title,duties,quote,posting_url,contact_email,email_source\n", encoding="utf-8")


def cmd_check(_):
    c = cfg()
    print("계정:", c["account"]["provider"], c["account"]["user"])
    s = smtp_login(c); s.quit(); print("  보내기(SMTP) 로그인 OK")
    m = imap_login(c); m.select("INBOX", readonly=True); m.logout(); print("  받기(IMAP) 로그인 OK")
    print("메일은 보내지 않았습니다.")


def outbox_files():
    return sorted(OUT.glob("*.json"))


def cmd_status(_):
    c, st = cfg(), state()
    q = [jload(f) for f in outbox_files()]
    cnt = lambda s: sum(1 for x in q if x.get("status") == s)
    newr = sum(1 for f in REP.glob("*.json") if jload(f).get("status") == "new")
    print(f"오늘 상한 {today_cap(c, st)} · 보냄 {sent_today()} · 초안 {cnt('draft')} · 승인 {cnt('approved')} · "
          f"발송완료 {cnt('sent')} · 건너뜀 {cnt('skipped')} · 새 답장 {newr} · 수신거부 {len(suppressed())}"
          + (" · ⛔STOP" if STOP.exists() else "") + (" · 시간대 밖" if not in_window(c) else ""))


def cmd_approve(args):
    if not args:
        sys.exit("approve <파일명|all>")
    fs = outbox_files() if args[0] == "all" else [OUT / a if not a.startswith(str(OUT)) else Path(a) for a in args]
    for f in fs:
        d = jload(f)
        if d and d.get("status") == "draft":
            d["status"] = "approved"; d["approved_at"] = now().isoformat(); jsave(f, d); print("승인:", f.name)


def next_sendable(c, sent_to, sent_domains, sup, exclude=(), persist=True):
    want = {"approved"} | ({"draft"} if not c.get("require_approval", True) else set())
    for f in outbox_files():
        d = jload(f)
        if d.get("status") not in want or f.name in exclude:
            continue
        to = (d.get("to") or "").strip().lower()
        why = None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to):
            why = "주소 없음/형식 오류"
        elif to in sup or domain(to) in sup:
            why = "수신거부 목록"
        elif to in sent_to:
            why = "이미 보냄"
        elif c.get("one_per_domain", True) and domain(to) not in FREE_DOMAINS and domain(to) in sent_domains:
            why = "같은 회사 도메인에 이미 보냄"
        if why:
            print(f"  건너뜀 {f.name}: {why}")
            if persist:
                d["status"] = "skipped"; d["skip_reason"] = why; jsave(f, d)
            else:
                exclude.add(f.name)
            continue
        return f, d
    return None, None


def send_one(c, f, d, dry):
    msg, mid = build(c, d["to"], d["subject"], d["body"])
    if dry:
        print(f"[미리보기] → {d['to']} | {msg['Subject']}\n{msg.get_content()}\n" + "-" * 40)
        return
    s = smtp_login(c); s.send_message(msg); s.quit()
    st = state()
    if not st.get("first_send"):
        st["first_send"] = now().date().isoformat(); jsave(STATE, st)
    d.update(status="sent", sent_at=now().isoformat(), message_id=mid); jsave(f, d)
    with LOG.open("a", encoding="utf-8") as lf:
        lf.write(json.dumps({"at": now().isoformat(), "to": d["to"], "company": d.get("company"), "message_id": mid,
                             "subject": msg["Subject"], "file": f.name, "kind": "first"}, ensure_ascii=False) + "\n")
    print(f"  보냄 → {d.get('company','')} {d['to']}")


def cmd_send(args):
    c = cfg(); dry = "--dry-run" in args; nowait = "--no-wait" in args or dry
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 10 ** 6
    if not dry and stopped():
        return
    if not dry and not in_window(c):
        print("지금은 발송 시간대가 아닙니다.", c["window"]); return
    left = min(today_cap(c, state()) - sent_today(), mx) if not dry else mx
    if left <= 0:
        print("오늘 상한에 도달했습니다. 남은 메일은 다음 영업일에 보냅니다."); return
    rows = sent_rows(); sent_to = {r["to"].lower() for r in rows}; sent_dom = {domain(r["to"]) for r in rows}
    sup = suppressed(); n = 0; seen = set()
    while n < left:
        if not dry and (stopped() or not in_window(c)):
            break
        f, d = next_sendable(c, sent_to, sent_dom, sup, seen, persist=not dry)
        if not f:
            break
        send_one(c, f, d, dry); n += 1; seen.add(f.name)
        sent_to.add(d["to"].lower()); sent_dom.add(domain(d["to"]))
        if n < left and not nowait:
            g = random.uniform(*c["gap_minutes"]) * 60
            print(f"  다음 메일까지 {g/60:.1f}분 대기"); time.sleep(g)
    print(f"이번에 {'미리본' if dry else '보낸'} 메일 {n}통")


def dec(s):
    try:
        return str(make_header(decode_header(s or "")))
    except Exception:
        return s or ""


def text_of(m):
    if m.is_multipart():
        for p in m.walk():
            if p.get_content_type() == "text/plain" and not p.get_filename():
                return p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
        for p in m.walk():
            if p.get_content_type() == "text/html":
                h = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", h)
        return ""
    return m.get_payload(decode=True).decode(m.get_content_charset() or "utf-8", "replace")


def strip_quote(t):
    out = []
    for l in t.splitlines():
        if l.startswith(">") or re.match(r"^(-+\s*Original Message|-+원본 메시지|On .+wrote:|.+님이 작성:|20\d\d.+작성:)", l.strip()):
            break
        out.append(l)
    return "\n".join(out).strip()[:4000]


def cmd_inbox(_):
    c, st = cfg(), state()
    rows = sent_rows(); by_mid = {r["message_id"]: r for r in rows}; by_to = {r["to"].lower(): r for r in rows}
    if not rows:
        print("아직 보낸 메일이 없습니다."); return
    since = (now() - timedelta(days=21)).strftime("%d-%b-%Y")
    m = imap_login(c); m.select("INBOX", readonly=True)
    typ, data = m.uid("search", None, f"(SINCE {since})")
    seen = set(st.get("seen_uids", [])); new = 0
    for uid in (data[0].split() if data and data[0] else []):
        u = uid.decode()
        if u in seen:
            continue
        typ, md = m.uid("fetch", uid, "(BODY.PEEK[])")
        seen.add(u)
        if not md or not md[0]:
            continue
        msg = email.message_from_bytes(md[0][1])
        frm = email.utils.parseaddr(msg.get("From", ""))[1].lower()
        irt = (msg.get("In-Reply-To") or "").strip(); refs = msg.get("References", "")
        orig = by_mid.get(irt) or next((by_mid[x] for x in refs.split() if x in by_mid), None) or by_to.get(frm)
        body = text_of(msg)
        if re.search(r"mailer-daemon|postmaster", frm) or re.search(r"Undeliver|Delivery Status|반송|전송 실패", dec(msg.get("Subject"))):
            hit = next((r for r in rows if r["to"].lower() in body.lower()), None)
            if hit:
                suppress(hit["to"], "(반송)"); new += 1
            continue
        if not orig:
            continue
        rid = f"{now():%Y%m%d}_{u}"
        jsave(REP / f"{rid}.json", {
            "id": rid, "from": frm, "company": orig.get("company"), "subject": dec(msg.get("Subject")),
            "date": msg.get("Date"), "message_id": msg.get("Message-ID"), "references": refs,
            "orig_file": orig.get("file"), "orig_subject": orig.get("subject"),
            "body": strip_quote(body), "status": "new", "intent": "", "handoff": False, "reply": ""})
        new += 1; print(f"  새 답장: {orig.get('company')} <{frm}>")
    m.logout()
    st["seen_uids"] = sorted(seen)[-5000:]; st["last_inbox"] = now().isoformat(); jsave(STATE, st)
    print(f"새 답장/반송 {new}건 → {REP}/  (분류와 답장 초안은 클로드가 references/handler.md로 채웁니다)")


def cmd_reply(args):
    c = cfg(); dry = "--dry-run" in args
    for f in sorted(REP.glob("*.json")):
        d = jload(f)
        if d.get("intent") in ("거절", "수신거부") and d.get("status") != "done":
            suppress(d["from"], f"({d['intent']})")
            if d["intent"] == "수신거부":
                dm = domain(d["from"])
                if dm not in FREE_DOMAINS:
                    suppress(dm, "(수신거부 회사 도메인)")
            d["status"] = "done"; jsave(f, d); continue
        if d.get("handoff") and d.get("status") != "done":
            print(f"  ⚠ 사람 확인 필요: {d.get('company')} <{d['from']}> — {f.name}")
            continue
        ok = d.get("status") == "approved" or (d.get("status") == "drafted" and not c.get("require_approval", True))
        if not ok or not d.get("reply"):
            continue
        if not dry and stopped():
            return
        subj = d["subject"] if d["subject"].lower().startswith("re:") else "Re: " + d["subject"]
        msg, mid = build(c, d["from"], subj, d["reply"], reply_to_id=d.get("message_id"), refs=d.get("references"))
        if dry:
            print(f"[미리보기] → {d['from']} | {subj}\n{d['reply']}\n" + "-" * 40); continue
        s = smtp_login(c); s.send_message(msg); s.quit()
        d.update(status="sent", replied_at=now().isoformat(), reply_message_id=mid); jsave(f, d)
        with LOG.open("a", encoding="utf-8") as lf:
            lf.write(json.dumps({"at": now().isoformat(), "to": d["from"], "company": d.get("company"), "message_id": mid,
                                 "subject": subj, "file": f.name, "kind": "reply"}, ensure_ascii=False) + "\n")
        print(f"  답장 보냄 → {d.get('company')} {d['from']}")


def cmd_run(_):
    c = cfg(); print("반복 실행 시작 (Ctrl+C 종료). 시간대 밖에는 답장 확인만 합니다.")
    last_inbox = 0
    while True:
        if STOP.exists():
            print("STOP 파일 감지 → 종료"); return
        if time.time() - last_inbox > 15 * 60:
            try:
                cmd_inbox([])
            except Exception as e:
                print("  답장 확인 실패:", e)
            last_inbox = time.time()
        c = cfg()
        if in_window(c) and sent_today() < today_cap(c, state()):
            try:
                cmd_send(["--max", "1", "--no-wait"])
            except Exception as e:
                print("  발송 실패:", e)
        time.sleep(random.uniform(*c["gap_minutes"]) * 60)


def cmd_stop(_):
    STOP.write_text(now().isoformat(), encoding="utf-8"); print("⛔ 전체 발송을 멈췄습니다.")


def cmd_resume(_):
    if STOP.exists():
        STOP.unlink()
    print("발송을 다시 허용합니다.")


CMDS = {"init": cmd_init, "check": cmd_check, "status": cmd_status, "approve": cmd_approve, "send": cmd_send,
        "inbox": cmd_inbox, "reply": cmd_reply, "run": cmd_run, "stop": cmd_stop, "resume": cmd_resume}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__); sys.exit(1)
    CMDS[sys.argv[1]](sys.argv[2:])
