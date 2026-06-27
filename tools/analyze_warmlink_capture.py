#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, collections, pathlib, glob

def iter_paths(patterns):
    for pat in patterns:
        matches = glob.glob(pat) if any(c in pat for c in '*?[') else [pat]
        for m in matches:
            yield pathlib.Path(m)

def main():
    ap=argparse.ArgumentParser(description='Warmlink RAW Capture events.jsonl zusammenfassen')
    ap.add_argument('paths', nargs='+')
    ns=ap.parse_args()
    frames=collections.Counter(); unknown=[]; anomalies=[]; reconnects=0; rx=tx=0; first=last=None; bursts=[]
    for path in iter_paths(ns.paths):
        with path.open('r',encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                ev=json.loads(line); ts=ev.get('ts'); first=first or ts; last=ts or last
                if ev.get('dir')=='rx': rx+=int(ev.get('len',0) or 0)
                if ev.get('dir')=='tx': tx+=int(ev.get('len',0) or 0)
                if ev.get('parser')=='frame': frames[str(ev.get('frame_type') or ev.get('addr') or '?')]+=1
                if ev.get('parser')=='partial' or ev.get('function') not in (None,'0x03','0x06','0x10'): unknown.append(ev)
                if ev.get('event')=='anomaly': anomalies.append(ev); bursts.append((int(ev.get('totalbytes',0) or ev.get('bytes',0) or 0), ev))
                if 'reconnect' in str(ev.get('kind') or ev.get('event') or '').lower(): reconnects+=1
    print(f'Zeitraum: {first} .. {last}')
    print(f'RX Bytes: {rx}')
    print(f'TX Bytes: {tx}')
    print('Frames nach Typ:')
    for k,v in frames.most_common(): print(f'  {k}: {v}')
    print(f'Unbekannte/partial Events: {len(unknown)}')
    print(f'Anomalien: {len(anomalies)}')
    for ev in anomalies[:20]: print(f"  {ev.get('ts')} {ev.get('kind') or ev.get('event')} bytes={ev.get('totalbytes') or ev.get('bytes')}")
    print('Größte RX-Bursts/Anomalie-Fenster:')
    for n,ev in sorted(bursts, key=lambda x: x[0], reverse=True)[:10]: print(f"  {n} B @ {ev.get('ts')} {ev.get('kind')}")
    print(f'Reconnects: {reconnects}')
if __name__=='__main__': main()
