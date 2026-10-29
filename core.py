import json, os, socket, time

BASE = os.environ.get("ANDROID_PRIVATE") or os.path.abspath(".")
QUEUE = os.path.join(BASE, "queue.json")
STATUS = os.path.join(BASE, "status.json")
FINAL = ("done", "error", "cancelled")


def read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".t.mp4")
        open(t, "w").close()
        os.remove(t)
        return True
    except Exception:
        return False


def out_dir():
    cands = ["/storage/emulated/0/Download/YTLoader"]
    try:
        from jnius import autoclass
        a = autoclass("org.kivy.android.PythonActivity").mActivity
        cands.append(str(a.getExternalFilesDir(None).getAbsolutePath()))
    except Exception:
        pass
    cands.append(os.path.join(BASE, "downloads"))
    for d in cands:
        if _writable(d):
            return d
    return cands[-1]


def online():
    try:
        socket.create_connection(("www.youtube.com", 443), 5).close()
        return True
    except OSError:
        return False


def source(job):
    q, k = job["query"].strip(), job["kind"]
    if k == "search":
        return f"ytsearch{job['count']}:{q}"
    if k == "channel":
        if not q.startswith("http"):
            q = "https://www.youtube.com/" + (q if q.startswith("@") else "@" + q)
        return q if "/videos" in q else q.rstrip("/") + "/videos"
    return q


def run_job(job, put, cancelled):
    import yt_dlp

    audio = job["fmt"] == "audio"

    def hook(d):
        if cancelled():
            raise yt_dlp.utils.DownloadCancelled()
        if d["status"] == "downloading":
            info = d.get("info_dict", {})
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            n = info.get("n_entries") or job["count"]
            put(title=(info.get("title") or "")[:70],
                pct=int(d["downloaded_bytes"] * 100 / tot) if tot else 0,
                idx=info.get("playlist_index") or 1,
                total=min(n, job["count"]))

    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best" if audio else "best[ext=mp4]/best",
        "outtmpl": os.path.join(job["out"], "%(uploader)s", "%(title).80s [%(id)s].%(ext)s"),
        "playlistend": job["count"],
        "noplaylist": job["kind"] == "url" and "list=" not in job["query"],
        "ignoreerrors": True, "retries": 20, "fragment_retries": 20,
        "continuedl": True, "socket_timeout": 30,
        "download_archive": os.path.join(job["out"], ".archive.txt"),
        "quiet": True, "no_warnings": True, "noprogress": True,
        "cachedir": False, "progress_hooks": [hook],
        "extractor_args": {"youtube": {"player_client": ["android_vr", "ios"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([source(job)])


def run_service():
    import yt_dlp
    os.environ.setdefault("HOME", BASE)
    status = {k: v for k, v in read(STATUS, {}).items() if v.get("state") in FINAL}
    idle = 0
    while idle < 20:
        q = read(QUEUE, {"jobs": [], "cancel": []})
        todo = [j for j in q["jobs"] if j["id"] not in status]
        if not todo:
            idle += 1
            time.sleep(1)
            continue
        idle = 0
        job, last = todo[0], [0.0]

        def put(force=False, **kw):
            status.setdefault(job["id"], {}).update(kw)
            if force or time.time() - last[0] > 0.7:
                write(STATUS, status)
                last[0] = time.time()

        chk = [0.0, False]

        def cancelled():
            if time.time() - chk[0] > 1:
                chk[0] = time.time()
                chk[1] = job["id"] in read(QUEUE, {}).get("cancel", [])
            return chk[1]

        if cancelled():
            put(True, state="cancelled")
            continue
        for attempt in range(6):
            put(True, state="waiting")
            while not online() and not cancelled():
                time.sleep(5)
            put(True, state="running", msg="")
            try:
                run_job(job, put, cancelled)
                put(True, state="done", pct=100)
                break
            except yt_dlp.utils.DownloadCancelled:
                put(True, state="cancelled")
                break
            except Exception as e:
                if attempt == 5:
                    put(True, state="error", msg=str(e)[:120])
                else:
                    time.sleep(10)
    try:
        from jnius import autoclass
        autoclass("org.kivy.android.PythonService").mService.stopSelf()
    except Exception:
        pass
