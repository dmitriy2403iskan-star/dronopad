import threading, uuid
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

import core

KV = """
<Card>:
    orientation: "vertical"
    size_hint_y: None
    height: dp(100)
    padding: dp(8)
    canvas.before:
        Color:
            rgba: .17, .17, .21, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
    Label:
        id: title
        text: root.title
        text_size: self.size
        halign: "left"
        valign: "middle"
        shorten: True
    ProgressBar:
        id: bar
        max: 100
        size_hint_y: None
        height: dp(8)
    BoxLayout:
        Label:
            id: info
            text_size: self.size
            halign: "left"
            valign: "middle"
            font_size: sp(13)
            color: .7, .7, .75, 1
        Button:
            text: "Отмена"
            size_hint_x: .3
            on_release: app.cancel(root.job_id)

BoxLayout:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(8)
    Label:
        text: "YT Loader"
        bold: True
        font_size: sp(22)
        size_hint_y: None
        height: dp(40)
    Spinner:
        id: mode
        text: "Канал"
        values: ["Канал", "Ссылка", "Поиск"]
        size_hint_y: None
        height: dp(46)
        on_text: query.hint_text = {"Канал": "@имя или ссылка на канал", "Ссылка": "https://youtu.be/...", "Поиск": "что искать"}[self.text]
    TextInput:
        id: query
        hint_text: "@имя или ссылка на канал"
        multiline: False
        size_hint_y: None
        height: dp(46)
    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        Spinner:
            id: fmt
            text: "Видео"
            values: ["Видео", "Аудио"]
        TextInput:
            id: count
            text: "5"
            hint_text: "Сколько видео"
            input_filter: "int"
            multiline: False
    Button:
        text: "Добавить в очередь"
        size_hint_y: None
        height: dp(50)
        on_release: app.add()
    ScrollView:
        GridLayout:
            id: jobs
            cols: 1
            spacing: dp(8)
            size_hint_y: None
            height: self.minimum_height
    Button:
        text: "Убрать завершённые"
        size_hint_y: None
        height: dp(42)
        on_release: app.clear_done()
    Label:
        id: folder
        text: ""
        font_size: sp(12)
        size_hint_y: None
        height: dp(24)
"""

STATE = {"waiting": "Жду интернет…", "running": "Качаю", "done": "Готово",
         "error": "Ошибка", "cancelled": "Отменено", None: "В очереди"}
KIND = {"Канал": "channel", "Ссылка": "url", "Поиск": "search"}


class Card(BoxLayout):
    job_id = StringProperty("")
    title = StringProperty("")


def start_service():
    if platform == "android":
        from jnius import autoclass
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        svc = autoclass(act.getPackageName() + ".ServiceDownloader")
        try:
            svc.start(act, "")
        except Exception:
            svc.start(act, "icon", "YT Loader", "Скачиваю…", "")
    elif not any(t.name == "svc" for t in threading.enumerate()):
        threading.Thread(target=core.run_service, name="svc", daemon=True).start()


class YTApp(App):
    def build(self):
        Window.clearcolor = (.09, .09, .11, 1)
        self.cards = {}
        self.root_w = Builder.load_string(KV)
        return self.root_w

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions
            request_permissions(["android.permission.WRITE_EXTERNAL_STORAGE",
                                 "android.permission.READ_EXTERNAL_STORAGE",
                                 "android.permission.POST_NOTIFICATIONS"])
        Clock.schedule_interval(self.refresh, 1)

    def queue(self):
        return core.read(core.QUEUE, {"jobs": [], "cancel": []})

    def add(self):
        ids = self.root_w.ids
        text = ids.query.text.strip()
        if not text:
            return
        out = core.out_dir()
        job = {"id": uuid.uuid4().hex[:8], "kind": KIND[ids.mode.text], "query": text,
               "count": max(1, min(int(ids.count.text or 5), 200)),
               "fmt": "audio" if ids.fmt.text == "Аудио" else "video", "out": out}
        q = self.queue()
        q["jobs"].append(job)
        core.write(core.QUEUE, q)
        ids.query.text = ""
        ids.folder.text = "Папка: " + out
        start_service()

    def cancel(self, job_id):
        q = self.queue()
        q.setdefault("cancel", []).append(job_id)
        core.write(core.QUEUE, q)

    def clear_done(self):
        st = core.read(core.STATUS, {})
        q = self.queue()
        q["jobs"] = [j for j in q["jobs"] if st.get(j["id"], {}).get("state") not in core.FINAL]
        core.write(core.QUEUE, q)

    def refresh(self, dt):
        st = core.read(core.STATUS, {})
        jobs = self.queue()["jobs"]
        box = self.root_w.ids.jobs
        alive = {j["id"] for j in jobs}
        for jid in list(self.cards):
            if jid not in alive:
                box.remove_widget(self.cards.pop(jid))
        for j in jobs:
            c = self.cards.get(j["id"])
            if not c:
                c = Card(job_id=j["id"], title=f"{j['query']}  ×{j['count']}")
                self.cards[j["id"]] = c
                box.add_widget(c, index=0)
            s = st.get(j["id"], {})
            state = s.get("state")
            c.ids.bar.value = s.get("pct", 0)
            extra = ""
            if state == "running":
                extra = f" {s.get('idx', 1)}/{s.get('total', j['count'])}: {s.get('title', '')}"
            elif state == "error":
                extra = " " + s.get("msg", "")
            c.ids.info.text = STATE.get(state, state) + extra


YTApp().run()
