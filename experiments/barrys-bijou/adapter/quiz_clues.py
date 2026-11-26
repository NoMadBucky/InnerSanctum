"""Quiz-only, noncanonical synopsis cache for Personal Sync."""

import re
import sqlite3
import threading
import time
import unicodedata


def words(text):
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                                                   if not unicodedata.combining(c))))


def usable(title, text):
    text = " ".join(text.split()) if isinstance(text, str) else ""
    if not 40 <= len(text) <= 2000 or any(mark in text for mark in ("http", "](", "[[", "```", "<", ">")):
        return None
    title = words(title)
    return text if title and f" {title} " not in f" {words(text)} " else None


def local_clue(film):
    # Take only the first prose paragraph in a labeled section, never trailing personal commentary.
    lines = film["body"].splitlines()
    for index, line in enumerate(lines):
        if re.fullmatch(r"#{1,6}\s+(Synopsis|Overview)\s*", line, re.I):
            paragraph = []
            for next_line in lines[index + 1:]:
                if next_line.startswith(("#", "*", "-", ">")) or not next_line.strip() and paragraph:
                    break
                if next_line.strip():
                    paragraph.append(next_line.strip())
            if clue := usable(film["title"], " ".join(paragraph)):
                return clue
    return None


class QuizCache:
    def __init__(self, state, fetch, token):
        self.db = state / "quiz-overviews.sqlite"
        self.fetch, self.token = fetch, token
        self.busy = threading.Lock()
        self.retry_after = 0

    def attach(self, films):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE IF NOT EXISTS overviews (id TEXT PRIMARY KEY, text TEXT NOT NULL)")
            saved = dict(db.execute("SELECT id,text FROM overviews"))
        missing = set()
        for film in films:
            if not film["viewed"]:
                continue
            mid = (film.get("tmdb") or "").rsplit("/", 1)[-1]
            clue = local_clue(film)
            if not clue and mid.isascii() and mid.isdigit():
                if mid in saved:
                    clue = usable(film["title"], saved[mid])
                else:
                    missing.add(mid)
            if clue:
                film["quizClue"] = clue
        if missing and time.monotonic() >= self.retry_after and self.busy.acquire(blocking=False):
            threading.Thread(target=self.fill, args=(sorted(missing),), daemon=True).start()

    def fill(self, ids):
        try:
            credential = self.token()
            with sqlite3.connect(self.db) as db:
                for mid in ids:
                    movie = self.fetch(f"movie/{mid}", credential)
                    if movie.get("id") == int(mid):
                        db.execute("INSERT OR REPLACE INTO overviews VALUES (?,?)", (mid, movie.get("overview") or ""))
                        db.commit()  # A subsequent sync can use a partially filled cache.
                    time.sleep(0.12)
        except Exception:
            self.retry_after = time.monotonic() + 300
        finally:
            self.busy.release()
