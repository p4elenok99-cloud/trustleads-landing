#!/usr/bin/env python3
"""Локальный статический сервер для лендинга с поддержкой Range-запросов
(нужно для перемотки видео) и без кэширования (чтобы превью не залипало).

Запуск:  python serve.py [порт]   (по умолчанию 5500)
Отдаёт файлы из той же папки, где лежит скрипт (web/).
Это ТОЛЬКО для локального просмотра — на проде используется nginx.
"""
import http.server
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # отключаем кэш, чтобы предпросмотр всегда показывал свежую версию
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        ctype = self.guess_type(path)
        rng = self.headers.get("Range")

        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                g_start, g_end = m.group(1), m.group(2)
                if g_start == "":  # суффиксный диапазон: bytes=-N
                    length = int(g_end or 0)
                    start = max(0, size - length)
                    end = size - 1
                else:
                    start = int(g_start)
                    end = int(g_end) if g_end else size - 1
                end = min(end, size - 1)

                if start >= size or start > end:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None

                length = end - start + 1
                self.send_response(206, "Partial Content")
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(length))
                self.end_headers()

                if self.command == "GET":
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break
                        remaining -= len(chunk)
                f.close()
                return None

        # обычный ответ (без Range)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        return f


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    with http.server.ThreadingHTTPServer(("", port), RangeHandler) as httpd:
        print(f"Serving {ROOT} at http://localhost:{port}/ (Range + no-cache)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
