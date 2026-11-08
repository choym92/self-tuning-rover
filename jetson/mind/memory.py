"""Kalman's memory of earlier conversations: sessions, session summaries and day summaries.

The journal (one JSONL file per day) is the only record, and nothing is ever deleted from it. A session
is everything said from Kalman being called until a stretch of quiet (30 minutes by default; Paul's
choice, 2026-11-07). After a session closes, a background worker asks the language model for a short
summary made only from what was said and writes it back to the journal as a `session_summary` event.
After a day ends, that day's session summaries become one `day_summary`. Summaries are an index for
recall, not truth: the raw turns stay, and the prompt labels summaries as possibly misheard.

Nothing here knows about the robot. It needs a journal folder, a write(kind, **fields) function, an
ask(system, user) -> text function for the language model, and a prompts() -> {"summary", "day"} function.
"""
import json
import os
import threading
from datetime import datetime


def read_events(folder, days=8):
    """Events from the last `days` day files, oldest first."""
    out = []
    for name in sorted(f for f in os.listdir(folder) if f.endswith(".jsonl"))[-days:]:
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def day_of(sid):
    """'s20261107-185501' -> '2026-11-07' (the day the session started)."""
    return f"{sid[1:5]}-{sid[5:7]}-{sid[7:9]}"


def clock_of(sid):
    return f"{sid[10:12]}:{sid[12:14]}"


def transcript(events, sid):
    lines = []
    for e in events:
        if e.get("session") == sid and e.get("kind") == "reply" and e.get("heard"):
            lines += ["Paul: " + e["heard"], "Kalman: " + e.get("text", "")]
    return "\n".join(lines)


class Memory:
    def __init__(self, folder, write, ask, prompts):
        self.folder, self.write, self.ask, self.prompts = folder, write, ask, prompts
        self.lock = threading.Lock()
        self.nudged = threading.Event()
        self.last_error = None

    def close_dangling(self):
        """Close sessions left open by a restart, so they are summarised too."""
        events = read_events(self.folder)
        started = [e["session"] for e in events if e.get("kind") == "session_start" and e.get("session")]
        ended = {e.get("session") for e in events if e.get("kind") == "session_end"}
        for sid in started:
            if sid not in ended:
                self.write("session_end", session=sid, reason="restart")

    def pending(self, today=None):
        """Closed sessions with turns and no summary yet; finished days with session summaries but no day
        summary. A day waits until all its sessions are summarised."""
        today = today or datetime.now().strftime("%Y-%m-%d")
        events = read_events(self.folder)
        closed = {e.get("session") for e in events if e.get("kind") == "session_end"}
        talked = {e.get("session") for e in events if e.get("kind") == "reply" and e.get("heard")}
        done = {e.get("session") for e in events if e.get("kind") == "session_summary"}
        sessions = sorted(s for s in (closed & talked) - done if s)
        waiting = {day_of(s) for s in sessions}
        days_done = {e.get("day") for e in events if e.get("kind") == "day_summary"}
        days = sorted({day_of(s) for s in done if s} - days_done - waiting - {today})
        return sessions, days, events

    def catch_up(self, today=None):
        with self.lock:
            sessions, _, events = self.pending(today)
            for sid in sessions:
                text = self.ask(self.prompts()["summary"], transcript(events, sid)).strip()
                self.write("session_summary", session=sid, day=day_of(sid), text=text)
            _, days, events = self.pending(today)
            for d in days:
                lines = [f"{clock_of(e['session'])} {e['text']}" for e in events
                         if e.get("kind") == "session_summary" and e.get("day") == d]
                text = self.ask(self.prompts()["day"], "\n\n".join(lines)).strip()
                self.write("day_summary", session=None, day=d, text=text)

    def earlier_today(self, current, n=3, today=None):
        """[(start time, summary)] of today's finished sessions, newest last, for the prompt."""
        today = today or datetime.now().strftime("%Y-%m-%d")
        found = [(clock_of(e["session"]), e.get("text", "")) for e in read_events(self.folder, days=2)
                 if e.get("kind") == "session_summary" and e.get("day") == today and e.get("session") != current]
        return found[-n:]

    def start(self, every_s=60):
        """Summarise in the background: when nudged (a session just closed) or every minute, so a summary
        missed while the model was offline is made later. Never slows a reply."""
        def loop():
            while True:
                try:
                    self.catch_up()
                    self.last_error = None
                except Exception as e:
                    if str(e) != self.last_error:          # log a lasting outage once, not every minute
                        self.last_error = str(e)
                        self.write("error", session=None, where="memory", error=str(e))
                self.nudged.wait(every_s)
                self.nudged.clear()
        threading.Thread(target=loop, daemon=True).start()
