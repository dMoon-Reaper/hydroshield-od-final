#!/usr/bin/env python3
"""
backend/nfc_bridge.py  -  ESP32-S3 USB Serial <-> signed HTTP events
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

DEBOUNCE_S = 3.5


def sign(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def post_signed(url: str, payload: dict, secret: bytes) -> tuple[int, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Signature": sign(secret, body),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except urllib.error.URLError as e:
        return 0, f"backend unreachable: {e.reason}"


def make_payload(uid: str, reader_id: str, **extra) -> dict:
    return {
        "uid": uid.upper(),
        "ts": time.time(),
        "nonce": uuid.uuid4().hex,
        "reader_id": reader_id,
        **extra,
    }


def parse_serial_line(raw_line: str) -> str | None:
    raw_line = raw_line.strip()
    if not raw_line:
        return None
    if raw_line.startswith("{") and raw_line.endswith("}"):
        try:
            data = json.loads(raw_line)
            if "uid" in data:
                return data["uid"].upper()
        except json.JSONDecodeError:
            pass
    return None


def extract_drain_id(response_text: str, fallback: str = "TAG OK") -> str:
    try:
        data = json.loads(response_text)
        return data.get("drain_id") or data.get("asset_id") or fallback
    except Exception:
        return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default=os.getenv("FLOOD_API", "http://127.0.0.1:8000"))
    ap.add_argument("--port", default="COM7", help="Serial port connected to ESP32-S3")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--reader-id", default=os.getenv("COMPUTERNAME", "esp32-node-1"))
    ap.add_argument("--enroll", metavar="DRAIN_ID", help="Bind next tag to drain asset (e.g. DR-01)")
    ap.add_argument("--uid", help="Send one test scan without hardware")
    args = ap.parse_args()

    secret = os.getenv("NFC_HMAC_SECRET", "dev-secret-change-me").encode()
    scan_url = f"{args.server}/api/nfc-scan"
    enroll_url = f"{args.server}/api/nfc-enroll"

    def send(uid: str, ser_conn=None):
        if args.enroll:
            code, text = post_signed(enroll_url, make_payload(uid, args.reader_id, drain_id=args.enroll), secret)
            drain_label = args.enroll.upper()
            ack_mode = "ENROLLED"
        else:
            code, text = post_signed(scan_url, make_payload(uid, args.reader_id), secret)
            drain_label = extract_drain_id(text, fallback="VERIFIED")
            ack_mode = "SCANNED"

        # Send confirmation back to ESP32 OLED so it displays DR-01 / DR-02 for 3.5 seconds
        if ser_conn is not None and ser_conn.is_open:
            ack_msg = f"ACK|{ack_mode}|{drain_label}\n"
            ser_conn.write(ack_msg.encode("utf-8"))
            ser_conn.flush()

        print(f"[{time.strftime('%H:%M:%S')}] UID {uid} ({drain_label}) -> HTTP {code} {text[:160]}")
        return code

    if args.uid:
        sys.exit(0 if send(args.uid) in (200, 201) else 1)

    if serial is None:
        sys.exit("pyserial is not installed. Run: pip install pyserial")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.3)
    except serial.SerialException as err:
        sys.exit(f"Failed to open port {args.port}: {err}")

    print(f"Connected to ESP32-S3 on {args.port}.")
    print(f"Enrolling next tag as {args.enroll}..." if args.enroll else "Listening for taps (Ctrl+C to stop)...")

    last_sent: dict[str, float] = {}
    try:
        while True:
            raw_line = ser.readline().decode("utf-8", errors="ignore")
            uid = parse_serial_line(raw_line)
            if uid:
                now = time.time()
                if now - last_sent.get(uid, 0.0) >= DEBOUNCE_S:
                    last_sent[uid] = now
                    code = send(uid, ser_conn=ser)
                    if args.enroll and code in (200, 201):
                        time.sleep(0.5)  # Allow serial flush before closing
                        sys.exit(0)
    except KeyboardInterrupt:
        print("\nBridge stopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()