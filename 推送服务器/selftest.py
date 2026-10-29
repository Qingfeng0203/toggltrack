#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自检脚本：完全按 Toggl Desktop 客户端的方式发请求（gzip + chunked + Basic Auth），
验证接收端能正确解包、落库、幂等更新、导出。部署后可以拿它在服务器上跑一遍。

    python3 selftest.py --port 8080 --token <你的 api_token>
"""

import argparse
import base64
import gzip
import json
import socket
import sys
import time


def send_chunked(host, port, payload, token, gzipped=True):
    body = json.dumps(payload, ensure_ascii=False, indent=3).encode("utf-8")
    headers = [
        "POST /v1/time_entries HTTP/1.1",
        "Host: %s:%d" % (host, port),
        "User-Agent: TogglDesktop/selftest",
        "Content-Type: application/json",
        "X-Toggl-Client: desktop",
        "Authorization: Basic " + base64.b64encode(
            ("%s:api_token" % token).encode()).decode(),
        "Transfer-Encoding: chunked",
    ]
    if gzipped:
        body = gzip.compress(body)
        headers.append("Content-Encoding: gzip")
    request = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8")
    request += ("%X\r\n" % len(body)).encode("ascii") + body + b"\r\n0\r\n\r\n"

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(request)
        sock.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default="selftest-token")
    args = ap.parse_args()

    entry = {
        "id": 9001,
        "description": "自检记录 / selftest",
        "workspace_id": 1,
        "guid": "selftest-guid-0001",
        "project_id": None,
        "task_id": None,
        "start": "2026-10-19T09:00:00+08:00",
        "stop": "2026-10-19T10:30:00+08:00",
        "duration": 5400,
        "billable": False,
        "duronly": False,
        "ui_modified_at": int(time.time()),
        "created_with": "TogglDesktop",
        "tags": ["自检"],
    }

    print("1) 第一次推送（应为 created=1）")
    print(send_chunked(args.host, args.port, entry, args.token))

    print("2) 再推一次同一条（应为 updated=1，说明幂等）")
    entry["description"] = "自检记录（已修改）"
    print(send_chunked(args.host, args.port, entry, args.token))

    print("3) 统计与导出")
    with socket.create_connection((args.host, args.port), timeout=10) as sock:
        req = ("GET /v1/stats HTTP/1.1\r\nHost: %s:%d\r\n"
               "Authorization: Basic %s\r\nConnection: close\r\n\r\n") % (
            args.host, args.port,
            base64.b64encode(("%s:api_token" % args.token).encode()).decode())
        sock.sendall(req.encode())
        out = b""
        while True:
            data = sock.recv(65536)
            if not data:
                break
            out += data
    print(out.decode("utf-8", "replace"))


if __name__ == "__main__":
    sys.exit(main())
