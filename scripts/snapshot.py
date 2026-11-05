#!/usr/bin/env python3
"""Зберігає знімок карти Google Мої карти в папку history/ (запускається автоматично на GitHub).

Що робить:
  1. Завантажує поточну карту (KML) за її mid.
  2. Порівнює зміст з останнім збереженим знімком.
  3. Якщо карта змінилась — записує history/РРРР-ММ-ДД.kml.gz (за київською датою; якщо за день
     змін було кілька, лишається останній стан дня) і оновлює history/index.json.
  4. Завжди оновлює history/latest.kml.gz — свіжа копія для сайту.
"""
import gzip, hashlib, io, json, os, re, sys, urllib.request, zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "history")
INDEX = os.path.join(HIST, "index.json")


def canon_hash(kml: bytes) -> str:
    """Хеш лише змісту карти (назви, стилі, координати) — щоб дрібниці формату не давали «нових версій»."""
    text = kml.decode("utf-8", "replace")
    blocks = re.findall(r"<Placemark.*?</Placemark>", text, flags=re.S)
    norm = []
    for b in blocks:
        b = re.sub(r'\sid="[^"]*"', "", b)
        b = re.sub(r",0(?=\s|<)", "", b)
        b = re.sub(r"\s+", " ", b).strip()
        norm.append(b)
    return hashlib.sha256("\n".join(norm).encode("utf-8")).hexdigest()


def fetch_kml() -> bytes:
    local = os.environ.get("KML_FILE")          # для перевірки без інтернету
    if local:
        data = open(local, "rb").read()
    else:
        mid = os.environ["MAP_ID"]
        url = f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (map-snapshot)"})
        data = urllib.request.urlopen(req, timeout=90).read()
    if data[:2] == b"PK":                       # KMZ → дістаємо doc.kml
        z = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
        data = z.read(name)
    if b"<kml" not in data[:3000] and b"<kml" not in data:
        raise SystemExit("Відповідь не схожа на KML — знімок не збережено (карта закрита для перегляду?).")
    return data


def main():
    os.makedirs(HIST, exist_ok=True)
    data = fetch_kml()
    h = canon_hash(data)
    idx = {"snapshots": []}
    if os.path.exists(INDEX):
        idx = json.load(open(INDEX, encoding="utf-8"))
    mid = os.environ.get("MAP_ID", "")
    if idx.get("mid") != mid:                   # карту замінили — стару історію скидаємо
        for f in os.listdir(HIST):
            if f.endswith(".kml.gz"): os.remove(os.path.join(HIST, f))
        idx = {"snapshots": []}
    idx["mid"] = mid
    snaps = idx.get("snapshots", [])
    gz = gzip.compress(data, 9, mtime=0)
    open(os.path.join(HIST, "latest.kml.gz"), "wb").write(gz)
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # зберегти mid

    if snaps and snaps[-1].get("h") == h:
        print("Змін немає — новий знімок не потрібен.")
        return
    today = datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
    fname = f"{today}.kml.gz"
    open(os.path.join(HIST, fname), "wb").write(gz)
    entry = {"d": today, "f": fname, "h": h}
    if snaps and snaps[-1]["d"] == today:
        snaps[-1] = entry                       # той самий день — оновлюємо стан дня
    else:
        snaps.append(entry)
    idx["snapshots"] = snaps
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Збережено знімок", fname)


if __name__ == "__main__":
    main()
