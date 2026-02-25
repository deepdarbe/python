#!/usr/bin/env python3
"""Yerel bilgisayar kullanım istatistikleri toplayan aktivite izleme servisi.

Özellikler:
- Aktif uygulama kullanım süresi ölçümü
- Mouse tıklama ve klavye tuş basım sayımı
- Basit yanıt hızı metriği (girdi olayları arasındaki ortalama süre)
- SQLite üzerinde kalıcı kayıt
- Markdown/JSON rapor üretimi

Not: Bu bir MVP örneğidir. Kurumsal kullanım için KVKK/GDPR, açık rıza,
veri saklama politikası ve güvenlik kontrolleri eklenmelidir.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Bu script için 'psutil' gerekiyor. Kurulum: pip install psutil pynput") from exc

try:
    from pynput import keyboard, mouse
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Bu script için 'pynput' gerekiyor. Kurulum: pip install psutil pynput") from exc


@dataclass
class ActivityEvent:
    ts: float
    event_type: str


class ActivityMonitor:
    def __init__(self, db_path: Path, sample_interval: int = 2, flush_interval: int = 60) -> None:
        self.db_path = db_path
        self.sample_interval = sample_interval
        self.flush_interval = flush_interval

        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self.current_app: Optional[str] = None
        self.current_start_ts: float = time.time()

        self.mouse_clicks = 0
        self.key_presses = 0
        self.input_events: list[ActivityEvent] = []

        self._last_flush = time.time()
        self._setup_db()

    def _setup_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT NOT NULL,
                    start_ts REAL NOT NULL,
                    end_ts REAL NOT NULL,
                    duration_sec REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS input_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_start_ts REAL NOT NULL,
                    period_end_ts REAL NOT NULL,
                    mouse_clicks INTEGER NOT NULL,
                    key_presses INTEGER NOT NULL,
                    avg_response_sec REAL
                )
                """
            )

    def _detect_active_app(self) -> str:
        if os.name == "nt":
            return self._detect_windows_app()

        # Linux: xdotool varsa kullan.
        if os.name == "posix":
            linux_app = self._detect_linux_app()
            if linux_app:
                return linux_app
            mac_app = self._detect_macos_app()
            if mac_app:
                return mac_app

        return "unknown_app"

    @staticmethod
    def _detect_windows_app() -> str:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown_app"

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return "unknown_app"

        try:
            proc = psutil.Process(pid.value)
            return proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "unknown_app"

    @staticmethod
    def _detect_linux_app() -> Optional[str]:
        try:
            wid = subprocess.check_output(["xdotool", "getactivewindow"], stderr=subprocess.DEVNULL).decode().strip()
            pid = subprocess.check_output(["xdotool", "getwindowpid", wid], stderr=subprocess.DEVNULL).decode().strip()
            proc = psutil.Process(int(pid))
            return proc.name()
        except Exception:
            return None

    @staticmethod
    def _detect_macos_app() -> Optional[str]:
        script = (
            'tell application "System Events"\n'
            'set frontApp to name of first application process whose frontmost is true\n'
            'return frontApp\n'
            "end tell"
        )
        try:
            out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL).decode().strip()
            return out or None
        except Exception:
            return None

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:  # noqa: ARG002
        if pressed:
            with self._lock:
                self.mouse_clicks += 1
                self.input_events.append(ActivityEvent(ts=time.time(), event_type="mouse"))

    def _on_key_press(self, key: keyboard.KeyCode | keyboard.Key) -> None:  # noqa: ARG002
        with self._lock:
            self.key_presses += 1
            self.input_events.append(ActivityEvent(ts=time.time(), event_type="keyboard"))

    def _flush_input_stats(self, now_ts: float) -> None:
        with self._lock:
            events = self.input_events[:]
            self.input_events.clear()
            mouse_clicks = self.mouse_clicks
            key_presses = self.key_presses
            self.mouse_clicks = 0
            self.key_presses = 0

        avg_response = self._calculate_avg_response(events)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO input_stats (period_start_ts, period_end_ts, mouse_clicks, key_presses, avg_response_sec)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self._last_flush, now_ts, mouse_clicks, key_presses, avg_response),
            )

        self._last_flush = now_ts

    @staticmethod
    def _calculate_avg_response(events: list[ActivityEvent]) -> Optional[float]:
        if len(events) < 2:
            return None

        deltas = []
        for first, second in zip(events, events[1:]):
            delta = second.ts - first.ts
            if 0 < delta <= 5:
                deltas.append(delta)

        if not deltas:
            return None
        return sum(deltas) / len(deltas)

    def _close_app_session(self, end_ts: float) -> None:
        app_name = self.current_app or "unknown_app"
        duration = max(0.0, end_ts - self.current_start_ts)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO app_sessions (app_name, start_ts, end_ts, duration_sec)
                VALUES (?, ?, ?, ?)
                """,
                (app_name, self.current_start_ts, end_ts, duration),
            )

    def run(self) -> None:
        print("[monitor] İzleme başlatıldı. Durdurmak için Ctrl+C")

        self.current_app = self._detect_active_app()
        self.current_start_ts = time.time()
        self._last_flush = self.current_start_ts

        mouse_listener = mouse.Listener(on_click=self._on_click)
        keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        mouse_listener.start()
        keyboard_listener.start()

        try:
            while not self._stop_event.is_set():
                now_ts = time.time()
                active_app = self._detect_active_app()

                if active_app != self.current_app:
                    self._close_app_session(now_ts)
                    self.current_app = active_app
                    self.current_start_ts = now_ts

                if now_ts - self._last_flush >= self.flush_interval:
                    self._flush_input_stats(now_ts)

                time.sleep(self.sample_interval)

        except KeyboardInterrupt:
            print("\n[monitor] Durduruluyor...")
        finally:
            stop_ts = time.time()
            self._close_app_session(stop_ts)
            self._flush_input_stats(stop_ts)
            mouse_listener.stop()
            keyboard_listener.stop()
            print(f"[monitor] Kayıt tamamlandı -> {self.db_path}")


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def generate_report(db_path: Path, start: Optional[str], end: Optional[str], out: Optional[Path]) -> dict:
    if not db_path.exists():
        raise SystemExit(f"Veritabanı bulunamadı: {db_path}")

    start_ts = datetime.fromisoformat(start).timestamp() if start else 0
    end_ts = datetime.fromisoformat(end).timestamp() if end else time.time()

    with sqlite3.connect(db_path) as conn:
        app_rows = conn.execute(
            """
            SELECT app_name, SUM(duration_sec) as total_sec
            FROM app_sessions
            WHERE start_ts >= ? AND end_ts <= ?
            GROUP BY app_name
            ORDER BY total_sec DESC
            """,
            (start_ts, end_ts),
        ).fetchall()

        input_rows = conn.execute(
            """
            SELECT SUM(mouse_clicks), SUM(key_presses), AVG(avg_response_sec)
            FROM input_stats
            WHERE period_start_ts >= ? AND period_end_ts <= ?
            """,
            (start_ts, end_ts),
        ).fetchone()

    total_mouse = input_rows[0] or 0
    total_keys = input_rows[1] or 0
    avg_response = input_rows[2]

    report = {
        "range": {"start": _fmt_ts(start_ts), "end": _fmt_ts(end_ts)},
        "applications": [
            {"app": app_name, "total_seconds": round(total_sec, 2), "total_minutes": round(total_sec / 60, 2)}
            for app_name, total_sec in app_rows
        ],
        "input": {
            "mouse_clicks": int(total_mouse),
            "key_presses": int(total_keys),
            "avg_response_seconds": round(avg_response, 3) if avg_response is not None else None,
        },
    }

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".json":
            out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            lines = [
                "# Aktivite Raporu",
                "",
                f"- Aralık: {report['range']['start']} - {report['range']['end']}",
                f"- Mouse tıklama: {report['input']['mouse_clicks']}",
                f"- Klavye tuş basımı: {report['input']['key_presses']}",
                f"- Ortalama yanıt süresi (s): {report['input']['avg_response_seconds']}",
                "",
                "## Uygulama Kullanımı",
            ]
            for app in report["applications"]:
                lines.append(f"- {app['app']}: {app['total_minutes']} dk")
            out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yerel kullanım istatistiği izleme servisi")
    parser.add_argument("--db", default="data/activity_stats.db", help="SQLite veritabanı yolu")

    subparsers = parser.add_subparsers(dest="command", required=True)

    start_cmd = subparsers.add_parser("start", help="İzlemeyi başlat")
    start_cmd.add_argument("--sample-interval", type=int, default=2, help="Aktif pencere örnekleme aralığı (sn)")
    start_cmd.add_argument("--flush-interval", type=int, default=60, help="Girdi istatistiği yazma aralığı (sn)")

    report_cmd = subparsers.add_parser("report", help="Rapor üret")
    report_cmd.add_argument("--start", help="Başlangıç tarihi (ISO, örn: 2026-02-25T08:00:00)")
    report_cmd.add_argument("--end", help="Bitiş tarihi (ISO, örn: 2026-02-25T18:00:00)")
    report_cmd.add_argument("--out", help="Rapor dosya yolu (.md veya .json)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    db_path = Path(args.db)

    if args.command == "start":
        monitor = ActivityMonitor(db_path, sample_interval=args.sample_interval, flush_interval=args.flush_interval)
        monitor.run()
    elif args.command == "report":
        out = Path(args.out) if args.out else None
        report = generate_report(db_path=db_path, start=args.start, end=args.end, out=out)
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
