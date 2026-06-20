#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 키오스크 (학생 배포판) — 터미널 없이 버튼으로 내 GitHub 저장소 관리.

이 한 파일이 (1) 대시보드 화면을 직접 서빙하고 (2) 버튼 클릭을 받아 실제 git/gh 를
대신 실행한다. Caddy·도메인·인증 설정이 필요 없다 — 127.0.0.1(내 컴퓨터)에서만 열린다.

실행: `python3 server.py` (또는 동봉된 start.command / start.bat 더블클릭).
설정: 처음 실행 시 자동으로 빈 포트를 잡고 브라우저를 연다. 프로젝트 폴더는 홈 디렉터리를
      스캔하며, 화면에서 언제든 바꿀 수 있다(config.json 에 저장).

안전: 127.0.0.1 바인딩(외부 접근 불가) · 경로 주입 차단 · subprocess 인자 리스트(shell=False)
      · 삭제/force-push/history rewrite 없음(v1 안전 범위).
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
GIT = shutil.which("git") or "git"
GH = shutil.which("gh") or "gh"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# 홈 스캔에서 건너뛸 디렉터리(용량 큰 시스템/캐시 폴더) — 속도·정확도
PRUNE = {"Library", "Applications", ".Trash", "node_modules", ".git", "Music", "Movies",
         "Pictures", "Photos Library.photoslibrary", ".cache", ".npm", ".cargo", ".rustup",
         "Downloads", "go", ".gradle", ".m2", "venv", ".venv", "__pycache__", "site-packages",
         ".vscode", ".idea", "Dropbox.nosync"}

_cache = {"gh": None, "gh_ts": 0.0}
_now = datetime.now  # (학생 배포판은 일반 환경 — datetime 사용 OK)


def load_config() -> dict:
    try:
        return json.load(open(CONFIG_PATH, encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict):
    try:
        json.dump(cfg, open(CONFIG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass


def repo_root() -> str:
    cfg = load_config()
    r = cfg.get("repo_root") or os.environ.get("GH_REPO_ROOT") or os.path.expanduser("~")
    return os.path.expanduser(r)


def owner() -> str:
    """gh 로 로그인한 사용자명 자동 감지 (설정 불요)."""
    cfg = load_config()
    if cfg.get("owner"):
        return cfg["owner"]
    rc, out, _ = run([GH, "api", "user", "-q", ".login"], timeout=15)
    if rc == 0 and out.strip():
        cfg["owner"] = out.strip()
        save_config(cfg)
        return out.strip()
    return ""


def run(args, cwd=None, timeout=120):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"명령을 찾을 수 없음: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # noqa
        return 1, "", f"{type(e).__name__}: {e}"


def discover_repos() -> list[dict]:
    root = repo_root()
    out = []
    if not os.path.isdir(root):
        return out
    base = root.rstrip("/").count(os.sep)
    for cur, dirs, _ in os.walk(root):
        depth = cur.count(os.sep) - base
        if depth >= 4:
            dirs[:] = []
            continue
        # 프루닝: 시스템/캐시/숨김(.으로 시작) 폴더 제외 (단 .git 자체는 탐지용)
        dirs[:] = [d for d in dirs if d not in PRUNE and not (d.startswith(".") and d != ".git")]
        if os.path.isdir(os.path.join(cur, ".git")):
            out.append({"name": os.path.basename(cur), "path": cur,
                        "rel": os.path.relpath(cur, root)})
            dirs[:] = []  # 저장소 내부는 더 안 들어감
    out.sort(key=lambda r: r["rel"].lower())
    return out


def gh_meta() -> dict:
    import time
    if _cache["gh"] is not None and time.time() - _cache["gh_ts"] < 60:
        return _cache["gh"]
    meta = {}
    own = owner()
    if own:
        rc, o, _ = run([GH, "repo", "list", own, "--limit", "400",
                        "--json", "name,description,isArchived,visibility"], timeout=40)
        if rc == 0:
            try:
                for it in json.loads(o):
                    meta[it["name"]] = {"description": it.get("description") or "",
                                        "archived": bool(it.get("isArchived")),
                                        "visibility": (it.get("visibility") or "").lower()}
            except Exception:
                pass
    _cache["gh"] = meta
    _cache["gh_ts"] = time.time()
    return meta


def repo_status(repo: dict) -> dict:
    p = repo["path"]
    _, branch, _ = run([GIT, "-C", p, "symbolic-ref", "--short", "HEAD"], timeout=15)
    _, st, _ = run([GIT, "-C", p, "status", "--porcelain"], timeout=20)
    dirty = len([l for l in st.splitlines() if l.strip()])
    _, url, _ = run([GIT, "-C", p, "remote", "get-url", "origin"], timeout=10)
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url.strip())
    remote = m.group(1) if m else "(none)"
    ahead = behind = None
    rc2, ab, _ = run([GIT, "-C", p, "rev-list", "--left-right", "--count", "@{u}...HEAD"], timeout=15)
    if rc2 == 0 and len(ab.split()) == 2:
        behind, ahead = int(ab.split()[0]), int(ab.split()[1])
    return {**repo, "branch": branch.strip() or "DETACHED", "dirty": dirty,
            "ahead": ahead, "behind": behind, "remote": remote}


def full_status() -> dict:
    repos = discover_repos()
    meta = gh_meta()
    rows = list(ThreadPoolExecutor(max_workers=8).map(repo_status, repos)) if repos else []
    for r in rows:
        nm = r["remote"].split("/")[-1] if r["remote"] != "(none)" else r["name"]
        m = meta.get(nm) or meta.get(r["name"]) or {}
        r["description"] = m.get("description", "")
        r["archived"] = m.get("archived", False)
        r["gh_name"] = nm
        r["has_remote"] = r["remote"] != "(none)"
    dirty = [r for r in rows if r["dirty"] > 0 or (r["ahead"] or 0) > 0]
    return {"root": repo_root(), "owner": owner(),
            "repos": rows,
            "summary": {"total": len(rows), "act": len(dirty),
                        "clean": len(rows) - len(dirty),
                        "scanned_at": _now().strftime("%Y-%m-%d %H:%M:%S")}}


def find_repo(name: str):
    if not NAME_RE.match(name or ""):
        return None
    for r in discover_repos():
        if r["name"] == name:
            return r
    return None


def commit_push_one(repo: dict, message: str) -> dict:
    p, name = repo["path"], repo["name"]
    run([GIT, "-C", p, "add", "-A"], timeout=60)
    rc, _, _ = run([GIT, "-C", p, "diff", "--cached", "--quiet"], timeout=20)
    committed = False
    if rc == 1:
        rc_c, _, err_c = run([GIT, "-C", p, "commit", "-m", message], timeout=60)
        if rc_c != 0:
            return {"name": name, "ok": False, "message": (err_c or "커밋 실패").strip()[:300]}
        committed = True
    _, ab, _ = run([GIT, "-C", p, "rev-list", "--count", "@{u}..HEAD"], timeout=15)
    if not (committed or (ab.strip().isdigit() and int(ab.strip()) > 0)):
        return {"name": name, "ok": True, "skipped": True, "message": "변경 없음 (이미 최신)"}
    rc_p, _, err_p = run([GIT, "-C", p, "push"], timeout=300)
    if rc_p == 0:
        return {"name": name, "ok": True, "message": "커밋·푸시 완료" if committed else "푸시 완료"}
    err = (err_p or "").strip()
    hint = ""
    if "exceeds GitHub's file size limit" in err or "GH001" in err:
        hint = " — 100MB 초과 파일 때문입니다. .gitignore 에 그 파일을 추가하세요."
    elif "pre-receive hook declined" in err:
        hint = " — 서버가 거부했습니다(대용량 파일 또는 비밀키 감지 가능)."
    elif "no upstream" in err or "set-upstream" in err:
        hint = " — 원격(GitHub) 연결이 없습니다. 먼저 GitHub에 저장소를 만들고 연결하세요."
    return {"name": name, "ok": False, "message": ((err[:380] + hint) if err else "푸시 실패" + hint)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype: str, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/")
        if p in ("", "/index.html") or p == "/index":
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(f.read(), "text/html; charset=utf-8")
            except Exception as e:  # noqa
                self._send(f"index.html 없음: {e}".encode(), "text/plain; charset=utf-8", 500)
        elif p.endswith("/api/github/health"):
            self._json({"ok": True, "owner": owner(), "root": repo_root(),
                        "git": bool(shutil.which("git")), "gh": bool(shutil.which("gh"))})
        elif p.endswith("/api/github/config"):
            self._json({"root": repo_root(), "owner": owner(), "home": os.path.expanduser("~")})
        elif p.endswith("/api/github/status"):
            try:
                self._json(full_status())
            except Exception as e:  # noqa
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = self.path.split("?")[0].rstrip("/")
        b = self._body()
        if p.endswith("/api/github/commit-push"):
            self._commit_push(b)
        elif p.endswith("/api/github/describe"):
            self._describe(b)
        elif p.endswith("/api/github/archive"):
            self._archive(b)
        elif p.endswith("/api/github/set-root"):
            self._set_root(b)
        else:
            self._json({"error": "not found"}, 404)

    def _set_root(self, b):
        root = os.path.expanduser((b.get("root") or "").strip())
        if not root or not os.path.isdir(root):
            self._json({"ok": False, "error": "폴더가 존재하지 않습니다."}, 400); return
        cfg = load_config(); cfg["repo_root"] = root; save_config(cfg)
        _cache["gh"] = None
        self._json({"ok": True, "root": root})

    def _commit_push(self, b):
        names = b.get("names") or []
        msg = (b.get("message") or "").strip() or f"작업 저장 (키오스크) {_now().strftime('%Y-%m-%d %H:%M')}"
        repos = [r for r in (find_repo(n) for n in names) if r]
        if not repos:
            self._json({"error": "유효한 저장소가 없습니다."}, 400); return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(o):
            try:
                self.wfile.write((json.dumps(o, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

        ok = fail = skip = 0
        emit({"type": "start", "total": len(repos), "message": msg})
        for i, repo in enumerate(repos, 1):
            emit({"type": "progress", "i": i, "name": repo["name"]})
            res = commit_push_one(repo, msg); res["type"] = "result"; res["i"] = i
            ok += res.get("ok") and not res.get("skipped"); skip += bool(res.get("skipped")); fail += not res.get("ok")
            emit(res)
        emit({"type": "done", "ok": int(ok), "fail": int(fail), "skip": int(skip)})

    def _describe(self, b):
        name = (b.get("name") or "").removesuffix(".git")
        if not NAME_RE.match(name):
            self._json({"error": "invalid name"}, 400); return
        own = owner()
        if not own:
            self._json({"ok": False, "error": "GitHub 로그인이 필요합니다 (gh auth login)."}, 400); return
        rc, _, err = run([GH, "repo", "edit", f"{own}/{name}", "--description", (b.get("description") or "").strip()], timeout=30)
        _cache["gh"] = None
        self._json({"ok": rc == 0, "name": name} if rc == 0 else {"ok": False, "error": (err or "실패").strip()[:300]}, 200 if rc == 0 else 502)

    def _archive(self, b):
        name = (b.get("name") or "").removesuffix(".git")
        if not NAME_RE.match(name):
            self._json({"error": "invalid name"}, 400); return
        own = owner()
        cmd = "archive" if b.get("archived", True) else "unarchive"
        rc, _, err = run([GH, "repo", cmd, f"{own}/{name}", "--yes"], timeout=30)
        _cache["gh"] = None
        self._json({"ok": rc == 0, "name": name} if rc == 0 else {"ok": False, "error": (err or "실패").strip()[:300]}, 200 if rc == 0 else 502)


def pick_port(start=5210, end=5260) -> int:
    import socket
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    port = int(os.environ.get("GH_KIOSK_PORT", "0")) or pick_port()
    url = f"http://127.0.0.1:{port}/"
    print("=" * 56)
    print("  GitHub 키오스크 — 터미널 없이 버튼으로 저장소 관리")
    print(f"  주소: {url}")
    print(f"  프로젝트 폴더: {repo_root()}")
    own = owner()
    print(f"  GitHub 계정: {own or '(로그인 필요 — gh auth login)'}")
    print("  이 창은 닫지 마세요. 종료하려면 Ctrl+C.")
    print("=" * 56, flush=True)
    if not os.environ.get("GH_KIOSK_NO_OPEN"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n종료했습니다.")
        sys.exit(0)
