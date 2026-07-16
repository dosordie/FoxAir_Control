#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import socket

HOST = "127.0.0.1"
PORT = 8766


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"FoxAir UDP-Diagnose auf {HOST}:{PORT}")
    try:
        while True:
            data, _addr = sock.recvfrom(65535)
            text = data.decode("utf-8", errors="replace")
            try:
                obj = json.loads(text)
                print(json.dumps(obj, ensure_ascii=False))
            except Exception:
                print(text)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == "__main__":
    main()
