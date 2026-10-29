#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toggl Desktop 时间记录镜像接收服务（单文件、零第三方依赖）。

用途
    Toggl Desktop 客户端在把一条时间记录同步到 Toggl 官方之后，会额外把
    同一份 JSON POST 到 <镜像地址>/v1/time_entries。本脚本就是接收端：
    解压、解析、按 guid 幂等写入 SQLite。

运行环境
    Ubuntu 20.04+ / 任意带 Python 3.8+ 的 Linux，只用标准库。

快速启动
    python3 toggl_mirror.py --port 8080 --db /var/lib/toggl-mirror/mirror.db

接口
    POST /v1/time_entries    接收一条记录（客户端调用）
    GET  /v1/time_entries    导出记录，支持 ?since=<unix>&limit=<n>
    GET  /v1/stats           统计信息
    GET  /health             健康检查

客户端实际发来的请求有两个坑，脚本里都处理了：
    1. Body 是 gzip 压缩的（Content-Encoding: gzip）
    2. 用 chunked 传输，没有 Content-Length
"""

import argparse
import base64
import gzip
import json
import os
import sqlite3
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS time_entries (
    guid            TEXT PRIMARY KEY,
    id              INTEGER,
    workspace_id    INTEGER,
    description     TEXT,
    start_at        TEXT,
    stop_at         TEXT,
    duration        INTEGER,
    billable        INTEGER DEFAULT 0,
    tags            TEXT,
    project_id      TEXT,
    task_id         TEXT,
    created_with    TEXT,
    ui_modified_at  INTEGER,
    deleted_at      INTEGER DEFAULT 0,
    raw             TEXT NOT NULL,
    received_at     INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_time_entries_start ON time_entries(start_at);
CREATE INDEX IF NOT EXISTS idx_time_entries_received ON time_entries(received_at);
"""


def ensure_schema(conn):
    """建表 + 增量迁移，老库直接升级不用重建。"""
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(time_entries)")}
    if "deleted_at" not in cols:
        conn.execute(
            "ALTER TABLE time_entries ADD COLUMN deleted_at INTEGER DEFAULT 0"
        )
        conn.commit()
        log("数据库迁移：time_entries 增加 deleted_at 列")


def log(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    sys.stderr.write("[%s] %s\n" % (stamp, msg))
    sys.stderr.flush()


def read_chunked(rfile):
    """读取 chunked 请求体。标准库不会帮忙做这件事。"""
    chunks = []
    while True:
        line = rfile.readline(65536)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            size = int(line.split(b";")[0], 16)
        except ValueError:
            break
        if size == 0:
            # 吃掉 trailer
            while True:
                trailer = rfile.readline(65536)
                if trailer in (b"\r\n", b"\n", b""):
                    break
            break
        chunks.append(rfile.read(size))
        rfile.read(2)  # 每个 chunk 结尾的 CRLF
    return b"".join(chunks)


def read_body(handler):
    """按 chunked 或 Content-Length 读原始 body，必要时解 gzip。"""
    encoding = (handler.headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in encoding:
        raw = read_chunked(handler.rfile)
    else:
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length) if length > 0 else b""

    content_encoding = (handler.headers.get("Content-Encoding") or "").lower()
    if "gzip" in content_encoding or (raw[:2] == b"\x1f\x8b"):
        try:
            raw = gzip.decompress(raw)
        except (OSError, zlib.error) as exc:
            raise ValueError("gzip 解压失败: %s" % exc)
    elif "deflate" in content_encoding:
        try:
            raw = zlib.decompress(raw)
        except zlib.error as exc:
            raise ValueError("deflate 解压失败: %s" % exc)

    return raw


def normalize_entry(item):
    """把客户端的 JSON 映射成表字段。客户端字段名见 toggl_desktop 的 TimeEntry::SaveToJSON。"""
    guid = (item.get("guid") or "").strip()
    if not guid:
        # 理论上一定有 guid；没有就退化成按内容哈希，避免重复写入
        import hashlib
        guid = "sha1:" + hashlib.sha1(
            json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    tags = item.get("tags")
    if isinstance(tags, list):
        tags = json.dumps(tags, ensure_ascii=False)

    return {
        "guid": guid,
        "id": item.get("id"),
        "workspace_id": item.get("workspace_id"),
        "description": item.get("description"),
        "start_at": item.get("start"),
        "stop_at": item.get("stop"),
        "duration": item.get("duration"),
        "billable": 1 if item.get("billable") else 0,
        "tags": tags,
        "project_id": item.get("project_id"),
        "task_id": item.get("task_id"),
        "created_with": item.get("created_with"),
        "ui_modified_at": item.get("ui_modified_at"),
        "deleted_at": item.get("deleted_at") or 0,
        "raw": json.dumps(item, ensure_ascii=False),
    }


def store(db_path, entries):
    """按 guid upsert，天然幂等：同一条记录重推不会产生重复。"""
    now = int(time.time())
    with DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=10)
        try:
            ensure_schema(conn)
            cur = conn.cursor()
            created = updated = 0
            for e in entries:
                exists = cur.execute(
                    "SELECT 1 FROM time_entries WHERE guid = ?", (e["guid"],)
                ).fetchone()
                if exists and e["deleted_at"]:
                    # 删除事件只打标记，不能把已经存下来的内容覆盖成空
                    cur.execute(
                        """UPDATE time_entries SET deleted_at=?, raw=?, updated_at=?
                           WHERE guid=?""",
                        (e["deleted_at"], e["raw"], now, e["guid"]),
                    )
                    updated += 1
                elif exists:
                    cur.execute(
                        """UPDATE time_entries SET
                               id=?, workspace_id=?, description=?, start_at=?, stop_at=?,
                               duration=?, billable=?, tags=?, project_id=?, task_id=?,
                               created_with=?, ui_modified_at=?, deleted_at=?, raw=?,
                               updated_at=?
                           WHERE guid=?""",
                        (
                            e["id"], e["workspace_id"], e["description"], e["start_at"],
                            e["stop_at"], e["duration"], e["billable"], e["tags"],
                            e["project_id"], e["task_id"], e["created_with"],
                            e["ui_modified_at"], e["deleted_at"], e["raw"], now,
                            e["guid"],
                        ),
                    )
                    updated += 1
                elif e["deleted_at"]:
                    # 远端本来就没有这条，删除事件无需落库
                    continue
                else:
                    cur.execute(
                        """INSERT INTO time_entries
                               (guid, id, workspace_id, description, start_at, stop_at,
                                duration, billable, tags, project_id, task_id,
                                created_with, ui_modified_at, deleted_at, raw,
                                received_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            e["guid"], e["id"], e["workspace_id"], e["description"],
                            e["start_at"], e["stop_at"], e["duration"], e["billable"],
                            e["tags"], e["project_id"], e["task_id"], e["created_with"],
                            e["ui_modified_at"], e["deleted_at"], e["raw"], now, now,
                        ),
                    )
                    created += 1
            conn.commit()
            return created, updated
        finally:
            conn.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "TogglMirror/1.0"
    protocol_version = "HTTP/1.1"

    # ---- 由 run() 注入 ----
    db_path = "mirror.db"
    tokens = []
    verbose = True

    def log_message(self, fmt, *args):
        if self.verbose:
            log("%s - %s" % (self.address_string(), fmt % args))

    # ---- 基础响应 ----

    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        if not self.tokens:
            return True
        header = self.headers.get("Authorization") or ""
        if not header.lower().startswith("basic "):
            return False
        try:
            decoded = base64.b64decode(header.split(None, 1)[1]).decode("utf-8", "replace")
        except Exception:
            return False
        username = decoded.split(":", 1)[0]
        return username in self.tokens or decoded in self.tokens

    # ---- 路由 ----

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/health":
            self.send_json(200, {"ok": True, "service": "toggl-mirror"})
            return

        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return

        if path == "/v1/stats":
            self.send_json(200, self.stats())
            return

        if path == "/v1/time_entries":
            self.send_json(200, {"ok": True, "items": self.export_entries()})
            return

        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/v1/time_entries":
            self.send_json(404, {"ok": False, "error": "not found"})
            return

        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            body = read_body(self)
            if not body:
                self.send_json(400, {"ok": False, "error": "empty body"})
                return

            payload = json.loads(body.decode("utf-8"))
        except ValueError as exc:
            log("解析失败: %s" % exc)
            self.send_json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # 客户端中途断开等
            log("读取请求失败: %s" % exc)
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        items = payload if isinstance(payload, list) else [payload]
        entries = [normalize_entry(i) for i in items if isinstance(i, dict)]
        if not entries:
            self.send_json(400, {"ok": False, "error": "no usable entry"})
            return

        try:
            created, updated = store(self.db_path, entries)
        except Exception as exc:
            log("写库失败: %s" % exc)
            self.send_json(500, {"ok": False, "error": "storage error"})
            return

        log("接收 %d 条（新增 %d，更新 %d）: %s" % (
            len(entries), created, updated,
            "; ".join((e["description"] or "(无描述)")[:40] for e in entries[:3]),
        ))
        self.send_json(200, {"ok": True, "created": created, "updated": updated})

    # ---- 查询 ----

    def stats(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            ensure_schema(conn)
            cur = conn.cursor()
            total = cur.execute(
                "SELECT COUNT(*) FROM time_entries WHERE deleted_at = 0"
            ).fetchone()[0]
            seconds = cur.execute(
                "SELECT COALESCE(SUM(CASE WHEN duration > 0 THEN duration ELSE 0 END), 0) "
                "FROM time_entries WHERE deleted_at = 0"
            ).fetchone()[0]
            latest = cur.execute("SELECT MAX(received_at) FROM time_entries").fetchone()[0]
            first = cur.execute(
                "SELECT MIN(start_at) FROM time_entries WHERE deleted_at = 0"
            ).fetchone()[0]
            return {
                "ok": True,
                "entries": total,
                "tracked_seconds": seconds,
                "tracked_hours": round(seconds / 3600.0, 2),
                "first_entry_start": first,
                "last_received_at": latest,
            }
        finally:
            conn.close()

    def export_entries(self):
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(self.path).query)
        since = query.get("since", [None])[0]
        limit = int(query.get("limit", ["1000"])[0])

        sql = "SELECT raw FROM time_entries WHERE deleted_at = 0"
        args = []
        if since:
            sql += " AND received_at >= ?"
            args.append(int(since))
        sql += " ORDER BY received_at DESC LIMIT ?"
        args.append(limit)

        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            ensure_schema(conn)
            rows = conn.execute(sql, args).fetchall()
            return [json.loads(r[0]) for r in rows]
        finally:
            conn.close()


def run(host, port, db_path, tokens, verbose):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)

    Handler.db_path = db_path
    Handler.tokens = tokens
    Handler.verbose = verbose

    # 先把库建好，启动即失败比运行时才失败好排查
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    conn.close()

    server = ThreadingHTTPServer((host, port), Handler)
    log("监听 %s:%d，数据库 %s，鉴权 %s" % (
        host, port, db_path, "开启" if tokens else "关闭"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("收到中断，退出")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Toggl Desktop 时间记录镜像接收服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, default=8080, help="监听端口，默认 8080")
    parser.add_argument("--db", default=os.environ.get("MIRROR_DB", "mirror.db"),
                        help="SQLite 文件路径")
    parser.add_argument("--token", action="append", default=[],
                        help="允许的 api_token，可重复；不传表示不校验")
    parser.add_argument("--quiet", action="store_true", help="不打印每条访问日志")
    args = parser.parse_args()

    run(args.host, args.port, args.db, args.token, not args.quiet)


if __name__ == "__main__":
    main()
