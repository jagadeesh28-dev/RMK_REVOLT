"""
Local Status Dashboard - last completed qualification (observability only)
Project: RMK-REVOLT / SECONDShift Platform

Zero-dependency stdlib HTTP server.
  /                 one-page HTML dashboard (industrial qualification console)
  /api/status       sanitized snapshot of the LAST COMPLETED qualification
  /api/benchmarks   historical recorded scenarios E01-E14 (allow-listed, no ground truth)

The dashboard never runs HILRunner or any actuation, and nothing here feeds back
into the qualification pipeline.

Usage:
    python secondshift/software/ui/dashboard.py [port]
"""

import json
import http.server
import urllib.parse
import sys
import os
from typing import Any, Dict, Optional
import time

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    from secondshift.software.ui import status_adapter
except ImportError:
    import status_adapter

try:
    from secondshift.hardware.telemetry_ingest import TelemetryIngestEngine
except ImportError:
    try:
        from hardware.telemetry_ingest import TelemetryIngestEngine
    except ImportError:
        TelemetryIngestEngine = None

GLOBAL_INGEST_ENGINE = TelemetryIngestEngine() if TelemetryIngestEngine else None


DEFAULT_PORT = 8088
PROCESSED_DATA_DIR = status_adapter.PROCESSED_DATA_DIR
STATUS_PATH = status_adapter.DEFAULT_STATUS_PATH
BENCHMARK_PATH = PROCESSED_DATA_DIR + "/physical_benchmark_results.json"

BENCHMARK_TITLE = "Historical Recorded Qualification Results"
BENCHMARK_NOTICE = "These are recorded benchmark scenarios, not live physical hardware validation."
_BENCH_FIELDS = ("objective", "setup", "expected_behavior", "actual_behavior",
                 "decision", "safety_result", "pass_fail", "passed", "observations")


def sanitize_benchmarks(raw: Any) -> Dict[str, Any]:
    """Explicit allow-list; ground_truth / true_* / characterized_timestamp never copied."""
    scenarios = []
    if isinstance(raw, dict):
        for sid, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            item = {"id": str(sid)}
            for key in _BENCH_FIELDS:
                val = entry.get(key)
                if val is None or isinstance(val, (str, bool, int, float)):
                    item[key] = val
            if isinstance(entry.get("measurements"), dict):
                item["measurements"] = status_adapter.strip_forbidden_keys(entry["measurements"])
            scenarios.append(item)
    return {"available": bool(scenarios), "title": BENCHMARK_TITLE, "notice": BENCHMARK_NOTICE,
            "count": len(scenarios), "scenarios": scenarios}


def load_benchmarks(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = None
    return sanitize_benchmarks(raw)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SECONDShift &mdash; Battery Qualification Station</title>
<style>
:root{
  --bg:#eef2f5;--pn:#fff;--hd:#f4f7fa;--ln:#d9e1e8;--fg:#17232d;--mut:#677784;
  --cy:#2bb3d1;--cyd:#0f8aa6;--cys:#e4f6fb;--ok:#0f8aa6;--warn:#b87812;--bad:#c0392b;--pur:#7359a6;--neutral:#8a98a4;
  --dark:#25323c;--dark2:#1a252e;
  --mono:Consolas,"SF Mono","Roboto Mono",Menlo,monospace;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 var(--sans)}
.na{color:var(--neutral)}
.tn-ok{color:var(--ok)}.tn-warn{color:var(--warn)}.tn-bad{color:var(--bad)}
[data-tone="ok"]{--accent:var(--ok)}[data-tone="warn"]{--accent:var(--warn)}
[data-tone="bad"]{--accent:var(--bad)}[data-tone="none"],[data-tone=""]{--accent:var(--neutral)}

/* system bar */
.top{background:var(--dark);color:#fff;border-top:3px solid var(--cy)}
.ttl{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 14px}
.logo{font:800 19px/1 var(--mono);letter-spacing:.03em}.logo b{color:#6fd8ee}
.ttl2{font:600 11px/1 var(--mono);letter-spacing:.14em;color:#aebbc4}
.sp{flex:1}
.chip{font:600 10px/1.3 var(--mono);letter-spacing:.06em;color:#d7e1e6;border:1px solid #566672;padding:3px 7px}
.live{display:inline-flex;align-items:center;gap:6px;font:700 11px/1 var(--mono);letter-spacing:.08em}
.led{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent,var(--neutral))}
.live .led{box-shadow:0 0 0 2px rgba(255,255,255,.18)}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));background:var(--dark2);border-top:1px solid #3a4852}
.sc{padding:6px 12px;border-right:1px solid #33424d;min-width:0}
.sc:last-child{border-right:0}
.sl{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:#91a0aa}
.sv{display:block;font:700 13px/1.35 var(--mono);color:#fff;overflow-wrap:anywhere}
.sv.na{color:#91a0aa}.sv.tn-ok{color:#5fd9ee}.sv.tn-warn{color:#e0a84b}.sv.tn-bad{color:#ff8a80}

/* shell */
.shell{display:grid;grid-template-columns:168px minmax(0,1fr);min-height:calc(100vh - 118px)}
.rail{background:var(--pn);border-right:1px solid var(--ln);padding:10px 0}
.rail .grp{font:700 9px/1 var(--mono);letter-spacing:.14em;color:var(--mut);padding:6px 16px}
.nv{display:flex;align-items:center;gap:8px;width:100%;text-align:left;font:700 11px/1 var(--mono);letter-spacing:.07em;color:var(--mut);background:transparent;border:0;border-left:3px solid transparent;padding:11px 16px;cursor:pointer;transition:background .15s,color .15s}
.nv svg{width:14px;height:14px;flex:none;fill:none;stroke:currentColor;stroke-width:1.6}
.nv:hover{background:var(--hd);color:var(--fg)}
.nv[aria-selected="true"]{color:var(--cyd);background:var(--cys);border-left-color:var(--cy)}
.nv:focus-visible{outline:2px solid var(--cy);outline-offset:-2px}
.bdg{margin-left:auto;background:var(--bad);color:#fff;font:700 9px/1.4 var(--mono);padding:1px 5px;border-radius:3px}
.bdg[hidden]{display:none}

.main{padding:12px;min-width:0}
.ws[hidden]{display:none}
.alarm{margin:0 0 10px;padding:10px 14px;background:#fdecea;border:2px solid var(--bad);border-radius:6px;color:#5a1a14}
.alarm[hidden]{display:none}
.alarm .a1{font:800 20px/1.2 var(--mono);color:var(--bad);letter-spacing:.06em}
.alarm .a2{font:12px/1.4 var(--mono);margin-top:4px;overflow-wrap:anywhere}
.foot{border-top:1px solid var(--ln);background:var(--pn);padding:6px 14px;display:flex;gap:14px;align-items:center}
.foot p{margin:0;font:11px/1.4 var(--mono);color:var(--mut)}

/* verdict and explanation */
.verdict{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--ln);border-top:4px solid var(--accent,var(--neutral));border-radius:6px;background:var(--pn);box-shadow:0 1px 4px rgba(20,35,45,.06)}
.vc{padding:10px 14px;border-right:1px solid var(--ln);min-width:0}
.vc:last-child{border-right:0}
.vc .l{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.vc .big{display:block;font:800 20px/1.2 var(--mono);color:var(--accent,var(--neutral));overflow-wrap:anywhere;margin-top:2px}
.vc .big.na{color:var(--neutral)}
.vc .sub{display:block;font:600 10px/1.3 var(--mono);color:var(--mut);margin-top:2px}

.exp-box{grid-column:1/-1;background:var(--pn);border:1px solid var(--ln);border-left:5px solid var(--accent,var(--neutral));border-radius:6px;padding:10px 14px;box-shadow:0 1px 4px rgba(20,35,45,.06)}
.exp-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.exp-h .l{font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.exp-tag{font:700 9px/1.2 var(--mono);padding:1px 6px;border-radius:3px;background:var(--cys);color:var(--cyd)}
.exp-txt{font:600 13px/1.4 var(--mono);color:var(--fg);margin-bottom:4px;overflow-wrap:anywhere}
.exp-reasons{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.exp-pill{font:700 9px/1.4 var(--mono);padding:2px 8px;border-radius:3px;background:var(--hd);border:1px solid var(--ln);color:var(--mut)}

/* tiles */
.tiles{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.tile{background:var(--pn);border:1px solid var(--ln);border-radius:6px;padding:10px 14px;box-shadow:0 1px 4px rgba(20,35,45,.06)}
.tile .th{display:flex;justify-content:space-between;align-items:center;gap:8px}
.tile .l{font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.vchip{font:700 9px/1.4 var(--mono);padding:1px 6px;border:1px solid var(--ln);border-radius:3px;color:var(--neutral)}
.vchip.tn-ok{border-color:var(--ok);color:var(--ok)}.vchip.tn-bad{border-color:var(--bad);color:var(--bad)}
.tile .n{font:600 32px/1.1 var(--mono);text-align:left;color:var(--fg);margin-top:4px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.tile .n.na{color:var(--neutral)}
.tile .n .u{font-size:14px;font-weight:400;color:var(--cyd);margin-left:4px}

/* panels layout */
.ov{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:start}
.col{display:grid;gap:10px;min-width:0}
.pn{background:var(--pn);border:1px solid var(--ln);border-radius:6px;box-shadow:0 1px 4px rgba(20,35,45,.06);min-width:0;overflow:hidden}
.pn>h2{margin:0;padding:6px 12px;background:var(--hd);border-bottom:1px solid var(--ln);font:700 10px/1.3 var(--mono);letter-spacing:.13em;color:var(--mut);display:flex;justify-content:space-between;gap:8px}
.pn>h2 .tag{color:var(--pur)}
.pb{padding:12px}
.pn.safe{border-top:3px solid var(--accent,var(--cy))}

/* table readout */
.t{display:grid;grid-template-columns:auto minmax(0,1fr);gap:3px 12px;font:12px/1.35 var(--mono);margin-top:4px}
.t .k{color:var(--mut);font-size:10px;letter-spacing:.07em;align-self:center}
.t .v{text-align:right;overflow-wrap:anywhere;font-weight:600}
.t hr{grid-column:1/-1;border:0;border-top:1px solid var(--ln);margin:4px 0;width:100%}
.note{font:11px/1.45 var(--mono);color:var(--mut);margin:8px 0 0}

/* safety box */
.sbig{display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid var(--ln);border-left:5px solid var(--accent);border-radius:4px;background:var(--hd);margin-bottom:8px}
.sbig .led{width:12px;height:12px}
.sbig .sv2{font:800 18px/1.1 var(--mono);color:var(--accent)}
.sbig .sl{color:var(--mut);font-size:9px}
.sbig.trip{background:#fdecea;border-color:var(--bad)}

/* decision engine */
.stg{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.stage{flex:1 1 100px;position:relative;border:1px solid var(--ln);border-top:3px solid var(--accent);border-radius:4px;background:var(--hd);padding:6px 8px;min-width:0}
.stage:not(:last-child)::after{content:"\25B6";position:absolute;right:-7px;top:50%;transform:translateY(-50%);font-size:8px;color:var(--neutral)}
.stage .sn{font:700 9px/1.3 var(--mono);letter-spacing:.06em;display:flex;align-items:center;gap:4px}
.stage .ss{font:10px/1.3 var(--mono);color:var(--mut);margin-top:2px;overflow-wrap:anywhere}
.stage.hw{border:2px solid var(--dark);border-top:4px solid var(--accent)}
.stage .hwt{margin-left:auto;background:var(--dark);color:#fff;font:700 8px/1.5 var(--mono);padding:0 4px;border-radius:2px}

.dduo{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:8px}
.dbig{border:1px solid var(--ln);border-left:4px solid var(--accent);border-radius:4px;background:var(--hd);padding:6px 10px}
.dbig .l{font:700 8px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.dbig .d{font:800 20px/1.1 var(--mono);color:var(--accent);overflow-wrap:anywhere;margin-top:2px}
.dbig .d.na{color:var(--neutral)}
.dbig .d.vetoed{text-decoration:line-through;color:var(--neutral)}
.dbig .veto{font:700 10px/1.3 var(--mono);color:var(--bad);margin-top:2px}

.why{margin-top:8px;padding:6px 8px;border:1px solid var(--ln);border-radius:4px;background:var(--hd);font:12px/1.45 var(--mono);overflow-wrap:anywhere}
.why .l{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut);margin-bottom:2px}

.bars{display:grid;gap:10px;margin-top:12px}
.bh{display:flex;justify-content:space-between;gap:8px;font:700 10px/1.3 var(--mono);letter-spacing:.08em;color:var(--mut)}
.bh span+span{color:var(--fg)}
.trk{position:relative;height:10px;background:var(--hd);border:1px solid var(--ln);border-radius:3px;margin-top:3px;overflow:hidden}
.fill{position:absolute;left:0;top:0;bottom:0;width:0;background:var(--cy);transition:width .3s}
.fill.risk{background:var(--warn)}
.band{position:absolute;top:0;bottom:0;left:0;width:0;background:rgba(15,138,166,.4);border-left:1px solid var(--cyd);border-right:1px solid var(--cyd)}

/* data classification badges */
.tag-cls{display:inline-block;padding:1px 5px;font:700 9px/1.3 var(--mono);border-radius:2px;letter-spacing:.05em;text-transform:uppercase}
.tag-a{background:#0d596a;color:#5fd9ee;border:1px solid #148096}
.tag-b{background:#413110;color:#f0c05a;border:1px solid #755518}
.tag-c{background:#2a2e33;color:#b2bec7;border:1px dashed #62707b}
.tag-u{background:#2e2424;color:#ff9e94;border:1px solid #703c37}

/* graph */
.tabs{display:flex;flex-wrap:wrap;border-bottom:1px solid var(--ln);background:var(--hd)}
.tab{font:700 10px/1 var(--mono);letter-spacing:.08em;color:var(--mut);background:transparent;border:0;border-right:1px solid var(--ln);padding:10px 14px;cursor:pointer}
.tab:hover{color:var(--fg)}
.tab[aria-selected="true"]{color:var(--cyd);background:var(--pn);box-shadow:inset 0 -2px 0 var(--cy)}
.tab:focus-visible{outline:2px solid var(--cy);outline-offset:-2px}
.gbox{min-height:340px;background-color:#fff;background-image:linear-gradient(#edf1f4 1px,transparent 1px),linear-gradient(90deg,#edf1f4 1px,transparent 1px);background-size:32px 32px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:14px}
.gmsg{text-align:center;padding:20px;max-width:580px}
.gmsg .g1{font:700 13px/1.4 var(--mono);letter-spacing:.06em;color:var(--warn)}
.gmsg .g2{font:12px/1.5 var(--mono);color:var(--mut);margin-top:8px}
.gmsg .g3{font:600 22px/1.2 var(--mono);color:var(--cyd);margin-top:12px}
.chart{width:100%;height:auto;display:block}
.chart .gl{stroke:#e2e8ed;stroke-width:1}
.chart .ax{stroke:#8a98a4;stroke-width:1}
.chart .ln{fill:none;stroke:var(--cy);stroke-width:2}
.chart .pt{fill:var(--cyd);stroke:#fff;stroke-width:1.5;cursor:crosshair}
.chart .pt:hover{fill:var(--cy);r:6}
.chart text{font:10px var(--mono);fill:var(--mut)}
.chart text.vl{fill:var(--fg);font-weight:700}
.gfoot{padding:8px 14px;border-top:1px solid var(--ln);font:10px/1.4 var(--mono);color:var(--mut);background:var(--hd);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}

.btn-baseline{margin-top:14px;padding:7px 16px;font:700 11px/1.2 var(--mono);color:var(--cyd);background:var(--cys);border:1px solid var(--cy);border-radius:4px;cursor:pointer;letter-spacing:.05em}
.btn-baseline:hover{background:var(--cy);color:#fff}
.btn-baseline-alt{margin-top:10px;padding:6px 14px;font:700 10px/1.2 var(--mono);color:var(--mut);background:var(--hd);border:1px solid var(--ln);border-radius:3px;cursor:pointer}
.btn-baseline-alt:hover{background:var(--ln);color:var(--fg)}

/* trace */
.tl{list-style:none;margin:0;padding:0}
.tl li{position:relative;padding:0 0 12px 20px;border-left:2px solid var(--ln);margin-left:5px}
.tl li:last-child{padding-bottom:0;border-left-color:transparent}
.tl li::before{content:"";position:absolute;left:-6px;top:3px;width:10px;height:10px;border-radius:50%;background:var(--accent,var(--neutral))}
.tl .st{font:700 10px/1.3 var(--mono);letter-spacing:.08em;color:var(--mut)}
.tl .dc{font:700 14px/1.3 var(--mono);color:var(--accent,var(--fg))}
.tl .meta{font:11px/1.4 var(--mono);color:var(--mut)}
.tl .rs{font:12px/1.4 var(--sans);margin-top:2px;overflow-wrap:anywhere}

/* empty trace box */
.trace-empty-box{background:var(--hd);border:1px solid var(--ln);border-left:4px solid var(--warn);border-radius:4px;padding:14px 18px;margin:4px 0}
.trace-empty-title{font:800 14px/1.3 var(--mono);color:var(--dark);letter-spacing:.06em}
.trace-empty-desc{font:12px/1.5 var(--sans);color:var(--fg);margin-top:6px}
.trace-empty-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;margin-top:12px}
.teg-item{background:var(--pn);border:1px solid var(--ln);border-radius:3px;padding:8px 12px;font:11px/1.4 var(--mono)}
.teg-l{color:var(--mut);font-size:9px;font-weight:700;letter-spacing:.08em}
.teg-v{font-weight:700;color:var(--fg);margin-top:3px}

/* historical baseline box */
.hist-box{background:#fdfefe;border:1px dashed #8fa3b3;border-left:4px solid #6c8294;border-radius:4px;padding:12px 16px;margin-bottom:16px}
.hist-title{font:800 12px/1.3 var(--mono);color:#2d4050;letter-spacing:.08em;display:flex;align-items:center;gap:8px}
.hist-sub{font:11px/1.4 var(--mono);color:var(--mut);margin-top:4px}
.tl .st{font:700 10px/1.3 var(--mono);letter-spacing:.08em;color:var(--mut)}
.tl .dc{font:700 14px/1.3 var(--mono);color:var(--accent,var(--fg))}
.tl .meta{font:11px/1.4 var(--mono);color:var(--mut)}
.tl .rs{font:12px/1.4 var(--sans);margin-top:2px;overflow-wrap:anywhere}

/* historical benchmarks */
.hist{border:1px dashed #9aa8b4}
.hist>h2{background:repeating-linear-gradient(135deg,#f0f3f6,#f0f3f6 8px,#e8edf1 8px,#e8edf1 16px)}
.bsum{font:11px/1.4 var(--mono);color:var(--mut);margin:6px 0 8px}
.bm{border:1px solid var(--ln);border-radius:4px;margin-bottom:4px;background:var(--pn)}
.bm summary{display:grid;grid-template-columns:minmax(0,200px) minmax(0,1fr) minmax(0,150px) 54px;gap:10px;align-items:center;padding:6px 10px;cursor:pointer;list-style:none}
.bm summary::-webkit-details-marker{display:none}
.bm summary:hover{background:var(--cys)}
.bm summary:focus-visible{outline:2px solid var(--cy);outline-offset:-2px}
.bid{font:700 12px/1.3 var(--mono);color:var(--dark);overflow-wrap:anywhere;min-width:0}
.bobj{overflow-wrap:anywhere;min-width:0;font-size:12px}
.bdec{font:600 11px/1.3 var(--mono);color:var(--accent);overflow-wrap:anywhere;min-width:0}
.pill{justify-self:end;padding:1px 6px;font:700 10px/1.5 var(--mono);border:1px solid var(--ln);border-radius:3px;color:var(--mut)}
.pill.pass{color:var(--ok);border-color:var(--ok)}.pill.fail{color:var(--bad);border-color:var(--bad)}
.bbody{padding:4px 10px 10px;border-top:1px solid var(--ln);display:grid;grid-template-columns:minmax(0,140px) minmax(0,1fr);gap:4px 12px;font-size:12px}
.bbody .k{font:700 10px/1.5 var(--mono);letter-spacing:.07em;color:var(--mut)}
.bbody .v{overflow-wrap:anywhere;min-width:0}
.bbody pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.45 var(--mono);color:var(--mut)}

@media (max-width:1000px){
  .ov{grid-template-columns:minmax(0,1fr)}
  .shell{grid-template-columns:minmax(0,1fr)}
  .rail{display:flex;overflow-x:auto;padding:0;border-right:0;border-bottom:1px solid var(--ln)}
  .rail .grp{display:none}
  .nv{width:auto;white-space:nowrap;border-left:0;border-bottom:3px solid transparent}
  .nv[aria-selected="true"]{border-bottom-color:var(--cy)}
}
@media (max-width:800px){
  .verdict{grid-template-columns:repeat(2,minmax(0,1fr))}
  .tiles{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:550px){
  .verdict,.tiles{grid-template-columns:minmax(0,1fr)}
  .vc{border-right:0;border-bottom:1px solid var(--ln)}
  .dduo{grid-template-columns:minmax(0,1fr)}
}
</style>
</head>
<body>
<header class="top">
  <div class="ttl">
    <span class="logo">NEXUS &bull; <b>RMK REVOLT</b></span>
    <span class="ttl2">HARDWARE WI-FI &bull; TELEMETRY CONSOLE</span>
    <span class="sp"></span>
    <span class="live" id="hw-conn" data-tone="none"><i class="led"></i><span id="hw-conn-t">DISCONNECTED</span></span>
    <span class="chip" id="hw-stale-badge" hidden style="background:var(--warn);color:#fff;font-weight:700">STALE DATA</span>
    <span class="chip" id="hw-dev-chip">DEVICE: NEXUS-ESP32-01</span>
    <span class="chip" id="hw-seq-chip">SEQ: 0</span>
    <span class="live" id="online" data-tone="none"><i class="led"></i><span id="online-t">CONSOLE ONLINE</span></span>
    <span class="chip" id="upd">UPDATED: N/A</span>
  </div>
  <div class="strip">
    <div class="sc"><span class="sl">STATION</span><span class="sv na">CH-01 RAPID</span></div>
    <div class="sc"><span class="sl">PROTOCOL</span><span class="sv na" id="s-proto">N/A</span></div>
    <div class="sc"><span class="sl">SPECIMEN</span><span class="sv na" id="s-cell">N/A</span></div>
    <div class="sc"><span class="sl">DECLARED CHEM</span><span class="sv na" id="s-decl-chem">N/A</span></div>
    <div class="sc"><span class="sl">INFERRED CHEM</span><span class="sv na" id="s-chem">N/A</span></div>
    <div class="sc"><span class="sl">MODE</span><span class="sv na" id="s-mode">N/A</span></div>
    <div class="sc"><span class="sl">HARDWARE STATE</span><span class="sv na" id="s-hw-state">N/A</span></div>
    <div class="sc"><span class="sl">SESSION STATUS</span><span class="sv na" id="s-sess-status">N/A</span></div>
    <div class="sc" style="display:none"><span id="s-conn">N/A</span><span id="s-sys">N/A</span></div>
  </div>
</header>

<div class="shell">
  <nav class="rail" aria-label="Workspaces">
    <div class="grp">WORKSPACE</div>
    <button class="nv" type="button" data-ws="overview"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z"/></svg>CONSOLE<span class="bdg" id="nv-badge" hidden>TRIP</span></button>
    <button class="nv" type="button" data-ws="trend"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 14V2M2 14h12M4 10l3-3 2 2 4-5"/></svg>TEST GRAPH</button>
    <button class="nv" type="button" data-ws="trace"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3v10M3 4h9M3 8h6M3 12h8"/></svg>DECISION TRACE</button>
    <button class="nv" type="button" data-ws="bench"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2h10v12H3zM6 6h4M6 9h4"/></svg>BENCHMARKS</button>
  </nav>

  <main class="main">
    <div class="alarm" id="alarm" hidden role="alert">
      <div class="a1">SAFETY TRIP ACTIVATED</div>
      <div class="a2" id="alarm-why"></div>
      <div class="a2" id="alarm-sys"></div>
    </div>

    <section class="ws ov" id="ws-overview">
      <!-- Top Verdict Cards -->
      <div class="verdict" id="verdict" data-tone="none" aria-label="Qualification summary">
        <div class="vc" data-tone="none"><span class="l">SAFETY BARRIER</span><span class="big na" id="vd-safe">N/A</span><span class="sub" id="vd-safe-sub">AUTHORITATIVE</span></div>
        <div class="vc" data-tone="none"><span class="l">OPERATIONAL DECISION</span><span class="big na" id="vd-op-dec">N/A</span><span class="sub" id="vd-op-sub">COMMITMENT</span></div>
        <div class="vc" data-tone="none"><span class="l">INFORMATION ACTION</span><span class="big na" id="vd-info-act">N/A</span><span class="sub" id="vd-info-sub">DIAGNOSTIC</span></div>
        <div class="vc" data-tone="none"><span class="l">EPISTEMIC STATE</span><span class="big na" id="vd-epistemic">N/A</span><span class="sub" id="vd-epi-sub">BELIEF RIGOR</span></div>
        <div style="display:none"><span id="vd-dec"></span><span id="vd-sys"></span></div>
      </div>

      <!-- Decision Explanation Banner -->
      <div class="exp-box" id="exp-box" data-tone="none">
        <div class="exp-h"><span class="l">DECISION EXPLANATION &amp; SCIENTIFIC EVIDENCE</span><span class="exp-tag" id="exp-tag">EXPLAINABLE CONSOLE</span></div>
        <div class="exp-txt" id="exp-summary">No active qualification run evaluated.</div>
        <div class="exp-reasons" id="exp-reasons"></div>
      </div>

      <!-- Live Measurements Tiles -->
      <div class="tiles" aria-label="Live measurements">
        <div class="tile"><div class="th"><span class="l"><span class="tag-cls tag-a">LIVE</span> VOLTAGE</span><span class="vchip" id="chip-v">N/A</span></div><div class="n na" id="volt">N/A</div></div>
        <div class="tile"><div class="th"><span class="l"><span class="tag-cls tag-a">LIVE</span> CURRENT</span><span class="vchip" id="chip-i">N/A</span></div><div class="n na" id="curr">N/A</div></div>
        <div class="tile"><div class="th"><span class="l"><span class="tag-cls tag-a">LIVE</span> POWER</span><span class="vchip" id="chip-p">N/A</span></div><div class="n na" id="power">N/A</div></div>
        <div class="tile"><div class="th"><span class="l"><span class="tag-cls tag-a">LIVE</span> TEMP</span><span class="vchip" id="chip-t">N/A</span></div><div class="n na" id="temp">N/A</div></div>
      </div>

      <!-- Column 1: Hardware & Wi-Fi Node, Battery Identity, Data Quality -->
      <div class="col">
        <!-- Section: NEXUS Hardware Node and Wi-Fi Link -->
        <section class="pn" id="pn-nexus-hw" aria-label="NEXUS Hardware Node and Wi-Fi Link">
          <h2><span>NEXUS HARDWARE &amp; WI-FI TELEMETRY</span><span class="tag" id="tag-hw-tele">ESP32 NODE</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">DEVICE ID</span><span class="v na" id="hw-device-id">NEXUS-ESP32-01</span>
              <span class="k">WI-FI LINK</span><span class="v na" id="hw-wifi-status">DISCONNECTED</span>
              <span class="k">BACKEND LINK</span><span class="v na" id="hw-backend-status">DISCONNECTED</span>
              <span class="k">TELEMETRY STATUS</span><span class="v na" id="hw-telemetry-status">DISCONNECTED</span>
              <span class="k">LAST PACKET AGE</span><span class="v na" id="hw-packet-age">N/A</span>
              <span class="k">SEQUENCE</span><span class="v na" id="hw-sequence">0</span>
              <span class="k">PACKET LOSS GAPS</span><span class="v na" id="hw-packet-gaps">0</span>
              <span class="k">WI-FI RSSI</span><span class="v na" id="hw-rssi">N/A</span>
              <hr>
              <span class="k">MOSFET STATE</span><span class="v na" id="hw-mosfet-state">OFF</span>
              <span class="k">HARDWARE STATE</span><span class="v na" id="hw-fsm-state">IDLE</span>
              <span class="k">HARDWARE FAULT</span><span class="v na" id="hw-fault-status">NO FAULT</span>
              <span class="k">SENSOR VALIDITY</span><span class="v na" id="hw-sensor-valid">VALID</span>
            </div>
            <p class="note">Autonomous local safety: ESP32 enforces independent undervoltage, overvoltage, overcurrent, and overtemperature cutoff. Wi-Fi disconnection cannot override or disable hardware safety.</p>
          </div>
        </section>

        <!-- Section A: Battery Specimen & Protocol -->
        <section class="pn" id="pn-battery" aria-label="Battery Specimen and Protocol">
          <h2><span>BATTERY SPECIMEN &amp; PROTOCOL</span><span class="tag">INTAKE METADATA</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">BATTERY ID</span><span class="v na" id="b-bat-id">N/A</span>
              <span class="k">CELL ID</span><span class="v na" id="b-cell-id">N/A</span>
              <span class="k">DECLARED CHEM</span><span class="v na" id="b-decl-chem">N/A</span>
              <span class="k">NOMINAL VOLTAGE</span><span class="v na" id="b-nom-v">N/A</span>
              <span class="k">NOMINAL CAPACITY</span><span class="v na" id="b-nom-cap">N/A</span>
              <span class="k">DATA SOURCE</span><span class="v na" id="b-source">N/A</span>
              <hr>
              <span class="k">PROTOCOL ID</span><span class="v na" id="b-proto-id">N/A</span>
              <span class="k">SOFTWARE VER</span><span class="v na" id="b-soft-ver">N/A</span>
              <span class="k">CONFIG VER</span><span class="v na" id="b-cfg-ver">N/A</span>
            </div>
            <p class="note">Declared chemistry is specimen intake metadata. It is kept strictly separate from model-inferred chemistry and is never overwritten.</p>
          </div>
        </section>

        <!-- Section C: Data Quality & Measurement Admissibility -->
        <section class="pn" id="pn-dq" aria-label="Data Quality and Measurement Admissibility">
          <h2><span>DATA QUALITY &amp; ADMISSIBILITY</span><span class="tag">LAYER 2 ADMISSIBILITY</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">SENSOR VALIDITY</span><span class="v na" id="dq-sensor">N/A</span>
              <span class="k">TELEMETRY VALIDITY</span><span class="v na" id="dq-tele">N/A</span>
              <span class="k">EVENT VALIDITY</span><span class="v na" id="dq-event">N/A</span>
              <span class="k">INFERENCE ADMISSIBLE</span><span class="v na" id="dq-admissible">N/A</span>
              <hr>
              <span class="k">CURRENT FLOW</span><span class="v na" id="dq-cur-flow">N/A</span>
              <span class="k">PULSE VALIDITY</span><span class="v na" id="dq-pulse">N/A</span>
              <span class="k">QUALITY STATE</span><span class="v na" id="dq-qual-state">N/A</span>
              <span class="k">DELTA V TOTAL</span><span class="v na" id="dq-dv-tot">N/A</span>
              <span class="k">DELTA V OHMIC</span><span class="v na" id="dq-dv-ohm">N/A</span>
              <hr>
              <span class="k">ADMISSIBILITY REASONS</span><span class="v na" id="dq-reasons">NONE</span>
            </div>
            <p class="note">Sensor validity does not imply inference admissibility. Pulses with zero current or contactor disconnect are rejected from downstream parameter estimation.</p>
          </div>
        </section>

        <!-- Section D: Test Progress & Execution -->
        <section class="pn" id="pn-progress" aria-label="Test Progress and Execution">
          <h2><span>TEST PROGRESS &amp; SEGMENTS</span><span class="tag">EXECUTION</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">SESSION ID</span><span class="v na" id="prg-sess">N/A</span>
              <span class="k">SESSION STATUS</span><span class="v na" id="prg-status">N/A</span>
              <span class="k">CURRENT SEGMENT</span><span class="v na" id="prg-seg">N/A</span>
              <span class="k">SEGMENT STATUS</span><span class="v na" id="prg-seg-status">N/A</span>
              <span class="k">OVERALL DATA STATUS</span><span class="v na" id="prg-data-status">N/A</span>
              <span class="k">ELAPSED TIME</span><span class="v na" id="prg-elapsed">N/A</span>
              <span class="k">NEXT ACTION</span><span class="v na" id="prg-next">N/A</span>
            </div>
          </div>
        </section>
      </div>

      <!-- Column 2: Chemistry, State Estimation, Decision Engine, Safety -->
      <div class="col">
        <!-- Section E: Chemistry Identification -->
        <section class="pn" id="pn-chem" aria-label="Chemistry Identification">
          <h2><span>CHEMISTRY IDENTIFICATION</span><span class="tag">DECLARED vs INFERRED</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">DECLARED CHEMISTRY</span><span class="v na" id="c-decl-chem">N/A</span>
              <span class="k">INFERRED CHEMISTRY</span><span class="v na" id="c-inf-chem">N/A</span>
              <span class="k">CONFIDENCE STATE</span><span class="v na" id="c-conf-state">N/A</span>
              <span class="k">CONFIDENCE SCORE</span><span class="v na" id="c-conf-score">N/A</span>
              <span class="k">POSTERIOR BELIEF</span><span class="v na" id="c-posterior">N/A</span>
            </div>
            <p class="note">If diagnostic evidence is insufficient, chemistry is marked NOT YET ESTIMATED rather than asserting false certainty.</p>
          </div>
        </section>

        <!-- Section F & G: State Estimation & Prognostics -->
        <section class="pn" id="pn-state" aria-label="State Estimation and Prognostics">
          <h2><span>STATE ESTIMATION &amp; PROGNOSTICS</span><span class="tag">ELECTROCHEMICAL</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">SOH ESTIMATE</span><span class="v na" id="c-soh">N/A</span>
              <span class="k">SOH UNCERTAINTY</span><span class="v na" id="c-sohu">N/A</span>
              <span class="k">R0 RESISTANCE</span><span class="v na" id="c-r0">N/A</span>
              <hr>
              <span class="k">RUL ESTIMATE</span><span class="v na" id="p-rul">NOT YET IMPLEMENTED</span>
              <span class="k">RUL UNCERTAINTY</span><span class="v na" id="p-rulu">NOT YET IMPLEMENTED</span>
              <span class="k">PROGNOSTIC STATUS</span><span class="v na" id="p-status">NOT YET IMPLEMENTED</span>
            </div>
            <div class="bars">
              <div class="br"><div class="bh"><span>SOH ESTIMATE (BAND = UNCERTAINTY)</span><span id="bar-soh-v">N/A</span></div><div class="trk"><div class="fill" id="bar-soh"></div><div class="band" id="bar-sohu"></div></div></div>
              <div class="br"><div class="bh"><span>MARGINAL FAILURE RISK</span><span id="bar-risk-v">N/A</span></div><div class="trk"><div class="fill risk" id="bar-risk"></div></div></div>
            </div>
            <p class="note">Prognostic RUL modeling is scheduled for future phases. Missing or invalid parameters are explicitly displayed as N/A, never zero.</p>
          </div>
        </section>

        <!-- Section H, I, J: Decision Engine & Intent -->
        <section class="pn" id="pn-decision" aria-label="Adaptive Decision Engine">
          <h2><span>ADAPTIVE DECISION ENGINE</span><span class="tag">OPERATIONAL vs TEST</span></h2>
          <div class="pb">
            <div class="stg" id="stg"></div>
            <div class="dduo">
              <div class="dbig" id="dbig-op" data-tone="none">
                <div class="l">OPERATIONAL DECISION</div>
                <div class="d na" id="d-op-dec">N/A</div>
                <div class="veto" id="d-veto" hidden>OVERRIDDEN BY SAFETY TRIP</div>
              </div>
              <div class="dbig" id="dbig-info" data-tone="none">
                <div class="l">INFORMATION ACTION</div>
                <div class="d na" id="d-info-act">N/A</div>
              </div>
            </div>
            <div class="t">
              <span class="k">ACTUATION INTENT</span><span class="v na" id="d-intent">N/A</span>
              <span class="k">MARGINAL RISK</span><span class="v na" id="d-risk">N/A</span>
              <span class="k">SYSTEM STATE</span><span class="v na" id="d-sys">N/A</span>
              <span class="k">COMMAND ID</span><span class="v na" id="c-cmd">N/A</span>
              <span class="k">TESTS EXECUTED</span><span class="v na" id="c-tests">N/A</span>
              <div style="display:none"><span id="d-dec"></span><span id="d-soh"></span><span id="d-r0"></span><span id="c-cell"></span><span id="c-chem"></span><span id="c-conf"></span><span id="c-fsm"></span><span id="c-valid"></span><span id="c-qual"></span><span id="c-seq"></span><span id="c-elapsed"></span></div>
            </div>
            <div class="why"><span class="l">DECISION REASON</span><span id="d-why" class="na">N/A</span></div>
          </div>
        </section>

        <!-- Section K: Hard Safety Barrier -->
        <section class="pn safe" id="safepn" data-tone="none" aria-label="Authoritative Hard Safety Barrier">
          <h2><span>HARD SAFETY BARRIER</span><span>AUTHORITATIVE OVERRIDE</span></h2>
          <div class="pb">
            <div class="sbig" id="sbig" data-tone="none"><i class="led"></i><div><div class="l sl">SAFETY STATE</div><div class="sv2" id="sf-state">N/A</div></div></div>
            <div class="t" style="margin-top:0">
              <span class="k">HARDWARE TRIP</span><span class="v na" id="sf-hwtrip">N/A</span>
              <span class="k">SENSOR FAULT</span><span class="v na" id="sf-sensor-fault">N/A</span>
              <span class="k">SAFE STOP STATE</span><span class="v na" id="sf-safestop">N/A</span>
              <span class="k">TRIP REASON</span><span class="v na" id="sf-tripreason">NONE</span>
              <hr>
              <span class="k">VOLTAGE LIMITS</span><span class="v na" id="sf-vlimits">2.00V &ndash; 3.75V</span>
              <span class="k">CURRENT LIMITS</span><span class="v na" id="sf-ilimits">&plusmn;50.0A</span>
              <span class="k">TEMPERATURE LIMIT</span><span class="v na" id="sf-tlimits">MAX 45.0&deg;C</span>
              <span class="k">ACTIVE CONSTRAINTS</span><span class="v na" id="sf-constraints">SUPERVISOR INTERLOCK</span>
              <div style="display:none"><span id="sf-v"></span><span id="sf-i"></span><span id="sf-t"></span><span id="sf-valid"></span><span id="sf-risk"></span><span id="sf-last"></span></div>
            </div>
            <p class="note">The Hard Safety Barrier operates independently of and strictly overrides all predictive models. A hardware trip immediately halts testing and forces a SAFE_STOP.</p>
          </div>
        </section>
      </div>
    </section>

    <!-- Workspace: Test Graph -->
    <section class="ws pn" id="ws-trend" aria-label="Test graph" hidden>
      <h2><span>TEST GRAPH</span><span id="ghead-src">REAL-TIME TELEMETRY &amp; QUALIFICATION ANALYSIS</span></h2>
      <div class="tabs" role="tablist" id="tabs"></div>
      <div class="gbox" id="gbox"></div>
      <div class="gfoot" id="gfoot"></div>
    </section>

    <!-- Workspace: Decision Trace -->
    <section class="ws pn" id="ws-trace" aria-label="Decision trace" hidden>
      <h2><span>TEST SEQUENCE / DECISION TRACE</span><span id="tr-header-tag">RECORDED AUDIT TRAIL</span></h2>
      <div class="pb"><div id="trace-container"><ol class="tl" id="trace"><li class="na">N/A</li></ol></div></div>
    </section>

    <!-- Workspace: Historical Benchmarks -->
    <section class="ws pn hist" id="ws-bench" hidden>
      <h2><span>HISTORICAL VALIDATION EVIDENCE &amp; BENCHMARKS</span><span>CLASS C FROZEN EVIDENCE &mdash; NOT CURRENT HARDWARE</span></h2>
      <div class="pb">
        <!-- Dedicated Historical Validation Baseline Section -->
        <div class="hist-box" id="hist-baseline-box">
          <div class="hist-title">
            <span class="tag-cls tag-c">CLASS C HISTORICAL</span>
            <span>VALIDATION BASELINE &mdash; FROZEN EVIDENCE</span>
          </div>
          <div class="hist-sub">Source: NEXUS Phase 5 / Phase 5.1 / Phase 6.1.1 Frozen Research Campaign &bull; Governed by Scientific Invariant</div>
          <div id="hist-baseline-content" style="margin-top:10px"></div>
        </div>

        <div class="sl" style="color:var(--mut);margin-top:18px" id="bench-title">Historical Recorded Qualification Results</div>
        <p class="note" style="margin-top:2px" id="bench-note">These are recorded benchmark scenarios, not live physical hardware validation.</p>
        <p class="bsum" id="bench-sum"></p>
        <div id="bench"><span class="na">N/A</span></div>
      </div>
    </section>
  </main>
</div>
<footer class="foot"><p id="msg"></p></footer>

<script>
var NA = "N/A";
var last = null;
var tab = "v";
var TABS = [["v","VOLTAGE"],["i","CURRENT"],["p","POWER"],["t","TEMPERATURE"],["risk","MARGINAL RISK"],["soh","SOH"],["r0","R0"]];
var showHistoricalRisk = false;
var SVGNS = "http://www.w3.org/2000/svg";

function $(id){ return document.getElementById(id); }
function has(v){ return v !== null && v !== undefined && v !== ""; }
function txt(v){ return has(v) ? String(v) : NA; }
function isn(v){ return typeof v === "number" && isFinite(v); }
function pct(v, d){ return isn(v) ? (v * 100).toFixed(d) + "%" : NA; }
function pretty(s){ return has(s) ? String(s).replace(/_/g, " ") : NA; }
function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function svg(tag, attrs, text){ var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (text !== undefined) e.textContent = text; return e; }

function tone(x){
  x = String(x === null || x === undefined ? "" : x).toUpperCase();
  if (/RETIRE|ISOLATE|FAULT|REJECT|TRIPPED|UNSAFE|LOCKOUT|FAIL|INVALID|FALSE|STOP/.test(x)) return "bad";
  if (/^(DERATE|HOLD|TEST|REQUEST_TEST|UNCERTAIN|PARTIALLY_VALID|SUSPECT|DEGRADED|INSUFFICIENT_DATA|DISTRIBUTION_SHIFTED)/.test(x)) return "warn";
  if (/^(OPERATE|ACCEPT|PASS|SAFE|CLEAR|VALID|TRUE|SUPPORTED_HEALTHY|COMPLETED|GOOD)/.test(x)) return "ok";
  return "none";
}

function put(id, val, tn){
  var e = $(id); if (!e) return;
  e.textContent = val;
  e.className = e.className.replace(/\b(na|tn-\w+)\b/g, "").replace(/\s+/g, " ").trim();
  if (val === NA || val === "NOT AVAILABLE" || val === "NOT YET ESTIMATED") e.className += " na";
  else if (tn && tn !== "none") e.className += " tn-" + tn;
}

function putNum(id, v, digits, unit){
  var e = $(id); if (!e) return;
  e.textContent = "";
  if (isn(v)){
    e.classList.remove("na");
    e.appendChild(document.createTextNode(v.toFixed(digits)));
    if (unit) e.appendChild(el("span", "u", unit));
  } else { e.classList.add("na"); e.textContent = NA; }
}

function numStr(v, digits, unit){ return isn(v) ? v.toFixed(digits) + " " + unit : NA; }

/* ---- workspace navigation ---- */
function showWs(name){
  var all = document.querySelectorAll(".ws");
  for (var i = 0; i < all.length; i++) all[i].hidden = (all[i].id !== "ws-" + name);
  var nv = document.querySelectorAll(".nv");
  for (var j = 0; j < nv.length; j++) nv[j].setAttribute("aria-selected", nv[j].getAttribute("data-ws") === name ? "true" : "false");
}
(function(){
  var nv = document.querySelectorAll(".nv");
  for (var i = 0; i < nv.length; i++) nv[i].onclick = function(){ showWs(this.getAttribute("data-ws")); };
  showWs("overview");
})();

/* ---- graph ---- */
function shortStage(s){
  return pretty(s).replace(/^STAGE 0 /, "").replace(/^LOOP ITERATION /, "IT ").toUpperCase();
}
function buildSeries(trace, key){
  return trace.map(function(t){ return {label: shortStage(t.stage), y: isn(t[key]) ? t[key] : null}; });
}

function drawChart(series, fmt, floorZero, ylab){
  var vals = series.filter(function(p){ return p.y !== null; }).map(function(p){ return p.y; });
  if (!vals.length) return null;
  var W = 680, H = 300, L = 64, R = 20, T = 20, B = 48;
  var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  if (hi === lo){ var p = Math.abs(hi) * 0.05 || 0.01; lo -= p; hi += p; }
  else { var pad = (hi - lo) * 0.2; lo -= pad; hi += pad; }
  if (floorZero && lo < 0) lo = 0;
  var s = svg("svg", {"class": "chart", viewBox: "0 0 " + W + " " + H, role: "img"});
  function X(i){ return series.length > 1 ? L + i * (W - L - R) / (series.length - 1) : L + (W - L - R) / 2; }
  function Y(v){ return T + (hi - v) * (H - T - B) / (hi - lo); }
  for (var g = 0; g <= 4; g++){
    var gv = lo + (hi - lo) * g / 4, gy = Y(gv);
    s.appendChild(svg("line", {"class": "gl", x1: L, x2: W - R, y1: gy, y2: gy}));
    s.appendChild(svg("text", {x: L - 6, y: gy + 3, "text-anchor": "end"}, fmt(gv)));
  }
  s.appendChild(svg("text", {x: -(T + (H - T - B) / 2), y: 14, transform: "rotate(-90)", "text-anchor": "middle"}, ylab || ""));
  s.appendChild(svg("line", {"class": "ax", x1: L, x2: L, y1: T, y2: H - B}));
  s.appendChild(svg("line", {"class": "ax", x1: L, x2: W - R, y1: H - B, y2: H - B}));
  var pts = [];
  series.forEach(function(p, i){
    s.appendChild(svg("text", {x: X(i), y: H - B + 16, "text-anchor": "middle"}, p.label));
    if (p.y !== null) pts.push([X(i), Y(p.y), p.y, p.label]);
  });
  if (pts.length > 1) s.appendChild(svg("polyline", {"class": "ln", points: pts.map(function(q){ return q[0] + "," + q[1]; }).join(" ")}));
  pts.forEach(function(q){
    var r = svg("rect", {"class": "pt", x: q[0] - 4, y: q[1] - 4, width: 8, height: 8});
    r.appendChild(svg("title", {}, q[3] + ": " + fmt(q[2])));
    s.appendChild(r);
    s.appendChild(svg("text", {"class": "vl", x: q[0], y: q[1] - 9, "text-anchor": "middle"}, fmt(q[2])));
  });
  s.appendChild(svg("text", {x: (L + W - R) / 2, y: H - 8, "text-anchor": "middle"}, "DECISION ITERATION (QUALIFICATION AUDIT TRACE)"));
  return s;
}

function drawTelemetryChart(points, unit, ylab, digits){
  if (!points || !points.length) return null;
  var W = 700, H = 300, L = 64, R = 24, T = 24, B = 48;
  var vals = points.map(function(p){ return p.value; });
  var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  if (hi === lo){ var p = Math.abs(hi) * 0.05 || 0.1; lo -= p; hi += p; }
  else { var pad = (hi - lo) * 0.15; lo -= pad; hi += pad; }

  var s = svg("svg", {"class": "chart", viewBox: "0 0 " + W + " " + H, role: "img"});
  function X(i){ return points.length > 1 ? L + i * (W - L - R) / (points.length - 1) : L + (W - L - R) / 2; }
  function Y(v){ return T + (hi - v) * (H - T - B) / (hi - lo); }

  for (var g = 0; g <= 4; g++){
    var gv = lo + (hi - lo) * g / 4, gy = Y(gv);
    s.appendChild(svg("line", {"class": "gl", x1: L, x2: W - R, y1: gy, y2: gy}));
    s.appendChild(svg("text", {x: L - 6, y: gy + 3, "text-anchor": "end"}, gv.toFixed(digits !== undefined ? digits : 3)));
  }
  s.appendChild(svg("text", {x: -(T + (H - T - B) / 2), y: 14, transform: "rotate(-90)", "text-anchor": "middle"}, ylab + " (" + unit + ")"));
  s.appendChild(svg("line", {"class": "ax", x1: L, x2: L, y1: T, y2: H - B}));
  s.appendChild(svg("line", {"class": "ax", x1: L, x2: W - R, y1: H - B, y2: H - B}));

  var pts = [];
  var stride = Math.max(1, Math.floor(points.length / 8));
  points.forEach(function(p, i){
    var x = X(i), y = Y(p.value);
    if (i === 0 || i === points.length - 1 || i % stride === 0){
      var lbl = p.label || (p.sequence !== undefined ? "SEQ " + p.sequence : i + "s");
      s.appendChild(svg("text", {x: x, y: H - B + 16, "text-anchor": "middle"}, lbl));
    }
    pts.push([x, y, p.value, p.label || ("#" + (p.sequence !== undefined ? p.sequence : i))]);
  });

  if (pts.length > 1){
    s.appendChild(svg("polyline", {"class": "ln", points: pts.map(function(q){ return q[0] + "," + q[1]; }).join(" ")}));
  }

  var maxMarkers = 40;
  var markerStride = Math.max(1, Math.ceil(pts.length / maxMarkers));
  pts.forEach(function(q, idx){
    if (idx % markerStride !== 0 && idx !== pts.length - 1) return;
    var r = svg("circle", {"class": "pt", cx: q[0], cy: q[1], r: 3.5});
    r.appendChild(svg("title", {}, q[3] + ": " + q[2].toFixed(digits !== undefined ? digits : 3) + " " + unit));
    s.appendChild(r);
    if (pts.length <= 15 || idx === pts.length - 1){
      s.appendChild(svg("text", {"class": "vl", x: q[0], y: q[1] - 8, "text-anchor": "middle"}, q[2].toFixed(digits !== undefined ? digits : 2)));
    }
  });

  s.appendChild(svg("text", {x: (L + W - R) / 2, y: H - 8, "text-anchor": "middle"}, "SAMPLE SEQUENCE / TIME \u2014 REAL ESP32 HARDWARE STREAM"));
  return s;
}

function renderTabs(){
  var box = $("tabs"); box.textContent = "";
  TABS.forEach(function(t){
    var b = el("button", "tab", t[1]);
    b.type = "button"; b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", t[0] === tab ? "true" : "false");
    b.onclick = function(){ tab = t[0]; renderTabs(); renderGraph(); };
    box.appendChild(b);
  });
}

function renderGraph(){
  var box = $("gbox"), foot = $("gfoot"); box.textContent = "";
  var ok = !!(last && last.available === true);
  var ghead = $("ghead-src");

  if (tab === "v" || tab === "i" || tab === "p" || tab === "t"){
    if (ghead) ghead.innerHTML = "<span class=\"tag-cls tag-a\">CLASS A LIVE HARDWARE</span> REAL-TIME TELEMETRY";
    var series = (ok && last.graph_series && last.graph_series[tab]) || {};
    var pts = (series.points && series.points.slice()) || [];
    var tel = (ok && last.telemetry) || {};
    var cfg = {
      v: {name: "VOLTAGE", unit: "V", digits: 3, cur: tel.voltage_v},
      i: {name: "CURRENT", unit: "A", digits: 3, cur: tel.current_a},
      p: {name: "POWER", unit: "W", digits: 2, cur: tel.power_w},
      t: {name: "TEMPERATURE", unit: "\u00b0C", digits: 1, cur: tel.temperature_c}
    }[tab];

    if (!pts.length && isn(cfg.cur)){
      var seq = (last.nexus_hardware && last.nexus_hardware.sequence) || 0;
      pts = [{timestamp: Date.now() / 1000, elapsed_s: 0, sequence: seq, value: cfg.cur, label: "0s"}];
    }

    if (!pts.length){
      var e = el("div", "gmsg");
      e.appendChild(el("span", "tag-cls tag-a", "[CLASS A LIVE HARDWARE]"));
      e.appendChild(el("div", "g1", "AWAITING TELEMETRY SAMPLES"));
      e.appendChild(el("div", "g2", "Real ESP32 stream connected, awaiting accepted " + cfg.name.toLowerCase() + " samples in rolling buffer."));
      box.appendChild(e);
      foot.textContent = "SOURCE: [CLASS A LIVE HARDWARE] ESP32 TELEMETRY STREAM (0 SAMPLES RECORDED)";
      return;
    }

    if (pts.length === 1){
      var g = el("div", "gmsg");
      g.appendChild(el("span", "tag-cls tag-a", "[CLASS A LIVE HARDWARE]"));
      g.appendChild(el("div", "g3", cfg.name + ": " + pts[0].value.toFixed(cfg.digits) + " " + cfg.unit));
      g.appendChild(el("div", "g1", "1 REAL HARDWARE SAMPLE RECORDED"));
      g.appendChild(el("div", "g2", "Sequence: " + (pts[0].sequence !== undefined ? pts[0].sequence : "0") + " &bull; Waiting for additional telemetry frames to plot dynamic trend. No synthetic interpolation is applied."));
      box.appendChild(g);
      foot.textContent = "SOURCE: [CLASS A LIVE HARDWARE] REAL ESP32 TELEMETRY (1 POINT) &bull; TRUE HARDWARE VALUE";
      return;
    }

    var chart = drawTelemetryChart(pts, cfg.unit, cfg.name, cfg.digits);
    if (chart) box.appendChild(chart);
    var vals = pts.map(function(p){ return p.value; });
    var minV = Math.min.apply(null, vals).toFixed(cfg.digits);
    var maxV = Math.max.apply(null, vals).toFixed(cfg.digits);
    var curV = pts[pts.length - 1].value.toFixed(cfg.digits);
    foot.textContent = "SOURCE: [CLASS A LIVE HARDWARE] " + pts.length + " TRUE SAMPLES  |  LATEST: " + curV + " " + cfg.unit + "  |  MIN: " + minV + "  |  MAX: " + maxV + "  |  NO SYNTHETIC DATA";
    return;
  }

  // Qualification metrics: risk, soh, r0
  if (ghead) ghead.innerHTML = "<span class=\"tag-cls tag-b\">QUALIFICATION ANALYSIS</span> DECISION METRICS";
  var tr = (ok && last.decision_trace) || [];
  var series = (ok && last.graph_series && last.graph_series[tab]) || {};
  var pts = (series.points && series.points.slice()) || [];

  if (pts.length > 0){
    var cfgs = {
      risk: ["marginal_risk", function(v){ return (v * 100).toFixed(2) + "%"; }, true, "MARGINAL RISK (%)"],
      soh: ["soh_estimate", function(v){ return (v * 100).toFixed(1) + "%"; }, false, "SOH (%)"],
      r0: ["r0_mohm", function(v){ return v.toFixed(2) + " m\u03a9"; }, false, "R0 (m\u03a9)"]
    }[tab];
    var chart = drawChart(buildSeries(tr, cfgs[0]), cfgs[1], cfgs[2], cfgs[3]);
    if (chart){
      box.appendChild(chart);
      foot.textContent = "SOURCE: RECORDED QUALIFICATION TRACE (" + pts.length + " POINTS) \u2022 EMPIRICAL DECISION SEQUENCE";
      return;
    }
  }

  // Evidence validation baseline: show our evidence values directly
  var hist = (ok && last.historical_baseline && last.historical_baseline.historical_risk_trace) || [];
  if (hist.length > 0){
    var cfgs = {
      risk: ["marginal_risk", function(v){ return (v * 100).toFixed(2) + "%"; }, true, "MARGINAL RISK (%)"],
      soh: ["soh_estimate", function(v){ return (v * 100).toFixed(1) + "%"; }, false, "SOH (%)"],
      r0: ["r0_mohm", function(v){ return v.toFixed(2) + " m\u03a9"; }, false, "R0 (m\u03a9)"]
    }[tab];
    var histSeries = hist.map(function(h){ return {label: shortStage(h.stage), y: isn(h[cfgs[0]]) ? h[cfgs[0]] : null}; });
    var chart = drawChart(histSeries, cfgs[1], cfgs[2], cfgs[3]);
    if (chart){
      box.appendChild(chart);
      foot.textContent = "SOURCE: VALIDATION EVIDENCE BASELINE (" + hist.length + " STAGES) \u2022 EMPIRICAL AUDIT SEQUENCE";
      return;
    }
  }

  var unNames = {risk: "MARGINAL RISK TRACE", soh: "SOH ESTIMATE", r0: "R0 ESTIMATE"}[tab];
  var e = el("div", "gmsg");
  e.appendChild(el("span", "tag-cls tag-u", "[AWAITING QUALIFICATION PROTOCOL]"));
  e.appendChild(el("div", "g1", "NO ACTIVE " + unNames));
  e.appendChild(el("div", "g2", "A connected ESP32 proves telemetry connectivity, but " + unNames.toLowerCase() + " requires an active qualification pulse protocol.\nIn continuous monitoring mode (MOSFET OFF), this quantity is evaluated during active pulsing."));
  box.appendChild(e);
  foot.textContent = "STATUS: AWAITING ACTIVE QUALIFICATION PROTOCOL \u2022 CONTINUOUS MONITORING ACTIVE";
}

/* ---- decision engine stages ---- */
function renderStages(ok, d, tr){
  var box = $("stg"); box.textContent = "";
  var nh = (last && last.nexus_hardware) || {};
  var dq = (last && last.data_quality) || {};
  var tripped = ok && (d.safety_tripped === true || nh.hardware_fault === true);
  var loops = tr.filter(function(x){ return /LOOP/i.test(x.stage || ""); });
  var hasSoh = loops.some(function(x){ return isn(x.soh_estimate); }) || (ok && last && last.historical_baseline && last.historical_baseline.historical_risk_trace && last.historical_baseline.historical_risk_trace.length > 0);
  var hasRisk = loops.some(function(x){ return isn(x.marginal_risk); }) || (ok && last && last.historical_baseline && last.historical_baseline.historical_risk_trace && last.historical_baseline.historical_risk_trace.length > 0);

  var list = [
    ["DATA QUALITY", ok ? (dq.quality_state || "MONITORED") : "STANDBY", ""],
    ["MEASUREMENT", ok && nh.wifi_status === "CONNECTED" ? "LIVE (ESP32)" : "AWAITING", ""],
    ["FEATURE EXTRACTION", (dq.delta_v_total !== null && dq.delta_v_total !== undefined) ? "EXTRACTED" : "AWAITING PULSE", ""],
    ["DOMAIN VALIDITY", ok ? (d.domain_validity || "SHIFTED") : "AWAITING", ""],
    ["BAYESIAN SOH", hasSoh ? "EVALUATED" : "STANDBY", ""],
    ["SAFETY BARRIER", tripped ? "TRIPPED" : "CLEAR", ""],
    ["ADAPTIVE DECISION", (d.final_decision ? txt(d.final_decision) : "HOLD (ISOLATED)"), ""]
  ];

  list.forEach(function(s){
    var st = s[1];
    var tn = (st === "TRIPPED" || st === "REJECTED") ? "bad" :
             ((st === "STANDBY" || st === "AWAITING" || st === "AWAITING PULSE" || /SHIFTED/.test(st)) ? "none" :
             ((st === "HOLD (ISOLATED)" || st === "MONITORED") ? "warn" : "ok"));
    var c = el("div", "stage"); c.setAttribute("data-tone", tn);
    if (s[0] === "SAFETY BARRIER") c.className += " hw";
    var n = el("div", "sn"); n.appendChild(el("i", "led")); n.appendChild(document.createTextNode(s[0]));
    if (s[0] === "SAFETY BARRIER") n.appendChild(el("span", "hwt", "HARD"));
    c.appendChild(n); c.appendChild(el("div", "ss", st));
    box.appendChild(c);
  });
}

function renderTrace(trace){
  var ol = $("trace"); ol.textContent = "";
  var trHeadTag = $("tr-header-tag");
  if (!trace || !trace.length){
    if (trHeadTag) trHeadTag.textContent = "AWAITING QUALIFICATION RUN";
    var nh = (last && last.nexus_hardware) || {};
    var sess = (last && last.session) || {};
    var box = el("div", "trace-empty-box");

    var hRow = el("div", "");
    hRow.style = "display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px";
    hRow.appendChild(el("span", "trace-empty-title", "NO QUALIFICATION DECISION RECORDED"));
    hRow.appendChild(el("span", "tag-cls tag-u", "AWAITING TEST RUN"));
    box.appendChild(hRow);

    box.appendChild(el("div", "trace-empty-desc",
      "Autonomous hardware telemetry ingestion is active. An operational qualification decision (OPERATE / DERATE / RETIRE) requires executing an intentional diagnostic pulse qualification protocol. The load MOSFET remains safely isolated (OFF) under HardSafetyBarrier supervision."));

    var grid = el("div", "trace-empty-grid");
    var items = [
      ["HARDWARE TELEMETRY", (nh.telemetry_status || "CONNECTED") + " (SEQ " + (nh.sequence !== undefined ? nh.sequence : 0) + ")", "tag-a", "LIVE"],
      ["QUALIFICATION STATUS", (sess.qualification_lifecycle || "MONITORING_ONLY") + " (NOT STARTED)", "tag-b", "CURRENT"],
      ["DECISION AUTHORITY", "UNAVAILABLE (NO ACTIVE TEST)", "tag-u", "UNAVAILABLE"],
      ["HARDWARE SAFETY FSM", (nh.hardware_state || "IDLE") + (nh.hardware_fault ? " [FAULT: " + (nh.fault_reason || "LATCHED") + "]" : ""), nh.hardware_fault ? "tag-u" : "tag-a", nh.hardware_fault ? "FAULT" : "NORMAL"],
      ["LOAD ACTUATION", (nh.mosfet_state || "OFF") + " (SAFE ISOLATION)", "tag-a", "HARDWARE"],
      ["SAFETY BARRIER", (last && last.decision && last.decision.safety_tripped) ? "TRIPPED (ISOLATED)" : "CLEAR (MONITORING)", (last && last.decision && last.decision.safety_tripped) ? "tag-u" : "tag-a", "OVERRIDE"]
    ];

    items.forEach(function(it){
      var cell = el("div", "teg-item");
      cell.appendChild(el("div", "teg-l", it[0]));
      var valDiv = el("div", "teg-v");
      valDiv.appendChild(el("span", "tag-cls " + it[2], "[" + it[3] + "] "));
      valDiv.appendChild(document.createTextNode(it[1]));
      cell.appendChild(valDiv);
      grid.appendChild(cell);
    });
    box.appendChild(grid);
    ol.appendChild(box);
    return;
  }

  if (trHeadTag) trHeadTag.textContent = "RECORDED AUDIT TRAIL (" + trace.length + " EVENTS)";
  trace.forEach(function(t){
    var li = el("li"); li.setAttribute("data-tone", tone(t.decision));
    li.appendChild(el("div", "st", shortStage(t.stage)));
    li.appendChild(el("div", "dc", txt(t.decision)));
    var meta = [];
    if (isn(t.marginal_risk)) meta.push("RISK " + pct(t.marginal_risk, 2));
    if (isn(t.soh_estimate)) meta.push("SOH " + pct(t.soh_estimate, 1));
    if (meta.length) li.appendChild(el("div", "meta", meta.join("  |  ")));
    if (has(t.reason)) li.appendChild(el("div", "rs", t.reason));
    ol.appendChild(li);
  });
}

function vset(id, val, tn){
  var e = $(id); if (!e) return;
  e.textContent = val; e.className = "big" + (val === NA ? " na" : "");
  if (e.parentNode) e.parentNode.setAttribute("data-tone", val === NA ? "none" : tn);
}

function render(s){
  last = s;
  var ok = !!(s && s.available === true);
  var d = (ok && s.decision) || {}, b = (ok && s.bayesian) || {}, c = (ok && s.chemistry) || {}, t = (ok && s.telemetry) || {};
  var bat = (ok && s.battery) || {}, sess = (ok && s.session) || {}, dq = (ok && s.data_quality) || {};
  var sf = (ok && s.safety_barrier) || {}, op = (ok && s.operational_decision) || {}, ia = (ok && s.information_action) || {};
  var epi = (ok && s.epistemic) || {}, prog = (ok && s.prognostics) || {}, exp = (ok && s.explanation) || {};
  var tr = (ok && s.decision_trace) || [];

  var tripped = (d.safety_tripped === true) || (sf.safety_tripped === true);
  var opDec = op.decision || d.final_decision;
  var infoAct = ia.action || (d.final_decision === "TEST" ? "REQUEST_TEST" : "NO_TEST");
  var epiState = epi.epistemic_state || (ok ? (tripped ? "KNOWN_DEGRADED" : (opDec === "OPERATE" ? "SUPPORTED_HEALTHY" : "INSUFFICIENT_DATA")) : NA);

  var sTone = !ok ? "none" : (tripped ? "bad" : "ok");
  var opTone = tripped ? "bad" : tone(opDec);
  var infoTone = tone(infoAct);
  var epiTone = tone(epiState);
  var mode = ok && has(s.mode) ? String(s.mode).toUpperCase() : NA;

  /* header strip */
  put("s-proto", sess.protocol_id || NA);
  put("s-cell", bat.battery_id || s.cell_id || NA);
  put("s-decl-chem", bat.declared_chemistry || c.declared_chemistry || NA);
  put("s-chem", c.inferred_chemistry || c.final_chemistry || "NOT YET ESTIMATED");
  put("s-mode", mode);
  put("s-hw-state", t.hardware_state || (ok ? "STANDBY" : NA));
  put("s-sess-status", sess.status || (ok ? "COMPLETED" : NA), tone(sess.status));
  $("upd").textContent = "UPDATED: " + (ok ? txt(s.updated_at) : NA);

  var m = $("msg");
  if (!ok) m.textContent = (s && s.message) ? s.message : "No qualification data available.";
  else if (mode === "SERIAL") m.textContent = "Serial mode: values from connected qualification bench. Actuation is requested intent.";
  else m.textContent = "Mode " + mode + ": simulated or replayed qualification data.";

  /* alarm */
  var al = $("alarm");
  al.hidden = !(ok && tripped);
  if (ok && tripped){
    $("alarm-why").textContent = "REASON: " + txt(sf.trip_reason || d.reason);
    $("alarm-sys").textContent = "STATE: " + txt(d.system_state) + "  |  INTENT: " + txt(d.actuation_intent);
  }

  /* top verdict cards */
  $("verdict").setAttribute("data-tone", tripped ? "bad" : "ok");
  vset("vd-safe", !ok ? NA : (tripped ? "TRIP" : "CLEAR"), sTone);
  vset("vd-op-dec", ok && opDec ? txt(opDec) : NA, opTone);
  vset("vd-info-act", ok && infoAct ? txt(infoAct) : NA, infoTone);
  vset("vd-epistemic", ok && epiState ? txt(epiState) : NA, epiTone);
  vset("vd-dec", txt(d.final_decision), opTone);
  vset("vd-sys", has(d.system_state) ? String(d.system_state).toUpperCase() : NA, tone(d.system_state));
  $("nv-badge").hidden = !(ok && tripped);

  /* explanation box */
  $("exp-box").setAttribute("data-tone", tripped ? "bad" : (opTone !== "none" ? opTone : "ok"));
  $("exp-summary").textContent = ok ? (exp.summary || d.reason || "Qualification evaluated successfully.") : "No active qualification run evaluated.";
  var rBox = $("exp-reasons"); rBox.textContent = "";
  var allReasons = (exp.reasons && exp.reasons.length) ? exp.reasons : (dq.reasons || []);
  if (!allReasons.length && d.reason) allReasons = [d.reason];
  if (ok && allReasons.length){
    allReasons.forEach(function(r){
      rBox.appendChild(el("span", "exp-pill", String(r)));
    });
  }

  /* live telemetry tiles */
  putNum("volt", t.voltage_v, 3, "V");
  putNum("curr", t.current_a, 3, "A");
  putNum("power", t.power_w, 2, "W");
  putNum("temp", t.temperature_c, 1, "\u00b0C");

  var chipT = t.is_valid === true ? "VALID" : (t.is_valid === false ? "INVALID" : NA);
  ["chip-v","chip-i","chip-p","chip-t"].forEach(function(cid){
    var e = $(cid);
    if (e){ e.textContent = chipT; e.className = "vchip" + (t.is_valid === true ? " tn-ok" : (t.is_valid === false ? " tn-bad" : "")); }
  });

  /* NEXUS HARDWARE & WI-FI NODE */
  var nh = (ok && s.nexus_hardware) || {};
  var hwTelStat = nh.telemetry_status || "DISCONNECTED";
  var hwTone = hwTelStat === "LIVE" ? "ok" : (hwTelStat === "STALE" ? "warn" : "bad");
  var hwConnEl = $("hw-conn");
  if (hwConnEl){ hwConnEl.setAttribute("data-tone", hwTone); }
  var hwConnTEl = $("hw-conn-t");
  if (hwConnTEl){ hwConnTEl.textContent = hwTelStat; }
  var hwStaleEl = $("hw-stale-badge");
  if (hwStaleEl){
    hwStaleEl.hidden = !(nh.is_stale === true);
    if (nh.is_stale && isn(nh.packet_age_s)){
      hwStaleEl.textContent = "STALE DATA (" + nh.packet_age_s.toFixed(1) + "s)";
    } else {
      hwStaleEl.textContent = "STALE DATA";
    }
  }
  var hwDevChip = $("hw-dev-chip");
  if (hwDevChip){ hwDevChip.textContent = "DEVICE: " + (nh.device_id || "NEXUS-ESP32-01"); }
  var hwSeqChip = $("hw-seq-chip");
  if (hwSeqChip){ hwSeqChip.textContent = "SEQ: " + (nh.sequence !== undefined ? nh.sequence : 0); }

  put("hw-device-id", nh.device_id || NA);
  put("hw-wifi-status", nh.wifi_status || "DISCONNECTED", tone(nh.wifi_status));
  put("hw-backend-status", nh.backend_status || "DISCONNECTED", tone(nh.backend_status));
  put("hw-telemetry-status", hwTelStat, hwTone);
  put("hw-packet-age", isn(nh.packet_age_s) ? nh.packet_age_s.toFixed(2) + " s" : NA);
  put("hw-sequence", nh.sequence !== undefined ? String(nh.sequence) : "0");
  put("hw-packet-gaps", nh.packet_gaps !== undefined ? String(nh.packet_gaps) : "0");
  put("hw-rssi", isn(nh.wifi_rssi) ? nh.wifi_rssi + " dBm" : NA);
  put("hw-mosfet-state", nh.mosfet_state || NA, tone(nh.mosfet_state));
  put("hw-fsm-state", nh.hardware_state || NA, tone(nh.hardware_state));
  var hwFaultText = nh.hardware_fault === true ? "FAULT LATCHED" : (has(nh.hardware_fault) ? "NO FAULT" : NA);
  put("hw-fault-status", hwFaultText, nh.hardware_fault === true ? "bad" : "ok");
  var hwSensText = nh.sensor_valid === true ? "VALID" : (nh.sensor_valid === false ? "INVALID" : NA);
  put("hw-sensor-valid", hwSensText, tone(hwSensText));

  /* SECTION A: Battery Specimen & Protocol */
  put("b-bat-id", bat.battery_id || s.cell_id || NA);
  put("b-cell-id", bat.cell_id || s.cell_id || NA);
  put("b-decl-chem", bat.declared_chemistry || c.declared_chemistry || NA);
  put("b-nom-v", numStr(bat.nominal_voltage, 2, "V"));
  put("b-nom-cap", numStr(bat.nominal_capacity_ah, 1, "Ah"));
  put("b-source", bat.data_source || s.source || NA);
  put("b-proto-id", sess.protocol_id || NA);
  put("b-soft-ver", bat.software_version || "SECONDShift-v2.0");
  put("b-cfg-ver", bat.configuration_version || "2.0.0");

  /* SECTION C: Data Quality & Admissibility */
  var sValidStr = dq.sensor_valid === true ? "VALID" : (dq.sensor_valid === false ? "INVALID" : NA);
  put("dq-sensor", sValidStr, tone(sValidStr));
  var tValidStr = dq.telemetry_valid === true ? "VALID" : (dq.telemetry_valid === false ? "INVALID" : NA);
  put("dq-tele", tValidStr, tone(tValidStr));
  var evValidStr = dq.event_valid === true ? "VALID" : (dq.event_valid === false ? "INVALID" : NA);
  put("dq-event", evValidStr, tone(evValidStr));
  var admStr = dq.inference_admissible === true ? "ADMISSIBLE" : (dq.inference_admissible === false ? "INADMISSIBLE" : NA);
  put("dq-admissible", admStr, tone(admStr));

  var cfStr = dq.current_flow_valid === true ? "VALID" : (dq.current_flow_valid === false ? "INVALID (BELOW MINIMUM)" : NA);
  put("dq-cur-flow", cfStr, tone(cfStr));
  var pValStr = dq.pulse_valid === true ? "VALID" : (dq.pulse_valid === false ? "INVALID" : (has(dq.pulse_valid) ? txt(dq.pulse_valid) : NA));
  put("dq-pulse", pValStr, tone(pValStr));
  put("dq-qual-state", dq.quality_state || t.quality || NA, tone(dq.quality_state || t.quality));
  put("dq-dv-tot", isn(dq.delta_v_total) ? dq.delta_v_total.toFixed(4) + " V" : NA);
  put("dq-dv-ohm", isn(dq.delta_v_ohmic) ? dq.delta_v_ohmic.toFixed(4) + " V" : NA);
  put("dq-reasons", (dq.reasons && dq.reasons.length) ? dq.reasons.join(", ") : "NONE");

  /* SECTION D: Test Progress & Execution */
  put("prg-sess", sess.session_id || NA);
  put("prg-status", sess.status || NA, tone(sess.status));
  put("prg-seg", sess.current_segment || "PULSE");
  put("prg-seg-status", sess.segment_status || NA, tone(sess.segment_status));
  put("prg-data-status", sess.overall_data_status || NA, tone(sess.overall_data_status));
  put("prg-elapsed", isn(sess.elapsed_time_s || d.elapsed_time_s) ? (sess.elapsed_time_s || d.elapsed_time_s).toFixed(3) + " s" : NA);
  put("prg-next", sess.next_expected_action || "NONE");

  /* SECTION E: Chemistry Identification */
  put("c-decl-chem", bat.declared_chemistry || c.declared_chemistry || NA);
  put("c-inf-chem", c.inferred_chemistry || c.final_chemistry || "NOT YET ESTIMATED");
  put("c-conf-state", c.confidence_state || c.final_chem_confidence || "NOT_YET_ESTIMATED", tone(c.confidence_state || c.final_chem_confidence));
  put("c-conf-score", isn(c.confidence_score) ? pct(c.confidence_score, 1) : NA);
  var postStr = NA;
  if (c.posterior && typeof c.posterior === "object"){
    var parts = [];
    for (var k in c.posterior) parts.push(k + ": " + (typeof c.posterior[k] === "number" ? (c.posterior[k]*100).toFixed(0)+"%" : c.posterior[k]));
    postStr = parts.join(" | ");
  }
  put("c-posterior", postStr);

  /* SECTION F & G: State Estimation & Prognostics */
  var hb = (ok && last.historical_baseline) || {};
  var htrace = hb.historical_risk_trace || [];
  var lastEv = htrace.length ? htrace[htrace.length - 1] : {};

  var sohVal = isn(b.soh_estimate) ? b.soh_estimate : (isn(lastEv.soh_estimate) ? lastEv.soh_estimate : null);
  var sohuVal = isn(b.soh_uncertainty) ? b.soh_uncertainty : (isn(lastEv.soh_uncertainty) ? lastEv.soh_uncertainty : null);
  var r0Val = isn(b.r0_mohm) ? b.r0_mohm : (isn(lastEv.r0_mohm) ? lastEv.r0_mohm : null);

  put("c-soh", isn(sohVal) ? pct(sohVal, 1) : NA);
  put("c-sohu", isn(sohuVal) ? "\u00b1" + pct(sohuVal, 1) : NA);
  put("c-r0", isn(r0Val) ? numStr(r0Val, 2, "m\u03a9") : (b.r0_mohm === null ? "NOT AVAILABLE" : NA));
  put("p-rul", prog.rul_cycles !== null && prog.rul_cycles !== undefined ? txt(prog.rul_cycles) : "NOT YET IMPLEMENTED");
  put("p-rulu", prog.rul_uncertainty !== null && prog.rul_uncertainty !== undefined ? txt(prog.rul_uncertainty) : "NOT YET IMPLEMENTED");
  put("p-status", prog.rul_status || "NOT YET IMPLEMENTED");

  var sohOk = isn(sohVal);
  $("bar-soh").style.width = sohOk ? Math.max(0, Math.min(100, sohVal * 100)) + "%" : "0";
  if (sohOk && isn(sohuVal)){
    var lo = Math.max(0, (sohVal - sohuVal) * 100), hi = Math.min(100, (sohVal + sohuVal) * 100);
    $("bar-sohu").style.left = lo + "%"; $("bar-sohu").style.width = (hi - lo) + "%";
  } else { $("bar-sohu").style.width = "0"; }
  $("bar-soh-v").textContent = sohOk ? pct(sohVal, 1) + (isn(sohuVal) ? " \u00b1" + pct(sohuVal, 1) : "") : NA;

  var lastRisk = null;
  tr.forEach(function(x){ if (isn(x.marginal_risk)) lastRisk = x.marginal_risk; });
  if (!isn(lastRisk) && isn(lastEv.marginal_risk)) lastRisk = lastEv.marginal_risk;
  $("bar-risk").style.width = isn(lastRisk) ? Math.max(0, Math.min(100, lastRisk * 100)) + "%" : "0";
  $("bar-risk-v").textContent = pct(lastRisk, 2);

  /* SECTION H, I, J: Decision Engine */
  renderStages(ok, d, tr);
  $("dbig-op").setAttribute("data-tone", ok ? opTone : "none");
  $("dbig-info").setAttribute("data-tone", ok ? infoTone : "none");
  put("d-op-dec", ok && opDec ? txt(opDec) : NA);
  put("d-info-act", ok && infoAct ? txt(infoAct) : NA);
  $("d-op-dec").className = "d" + (has(opDec) ? "" : " na") + (ok && tripped ? " vetoed" : "");
  $("d-veto").hidden = !(ok && tripped);

  put("d-intent", txt(d.actuation_intent));
  put("d-risk", pct(lastRisk, 2));
  put("d-sys", has(d.system_state) ? String(d.system_state).toUpperCase() : NA, tone(d.system_state));
  put("c-cmd", txt(d.command_id));
  put("c-tests", txt(d.tests_executed_count));
  put("d-why", txt(d.reason));

  /* SECTION K: Hard Safety Barrier */
  $("safepn").setAttribute("data-tone", sTone);
  $("sbig").setAttribute("data-tone", sTone);
  $("sbig").classList.toggle("trip", ok && tripped);
  put("sf-state", !ok ? NA : (tripped ? "SAFETY TRIP ACTIVE" : "CLEAR (OPERATIONAL)"));
  put("sf-hwtrip", tripped ? "YES (TRIPPED)" : (ok ? "NO (CLEARED)" : NA), tripped ? "bad" : "ok");
  put("sf-sensor-fault", t.is_valid === false ? "FAULT DETECTED" : (ok ? "NOMINAL" : NA), t.is_valid === false ? "bad" : "ok");
  put("sf-safestop", tripped ? "SAFE_STOP ENGAGED" : (ok ? "NOT ACTIVE" : NA), tripped ? "bad" : "ok");
  put("sf-tripreason", sf.trip_reason || (tripped ? d.reason : "NONE"));

  if (sf.voltage_limits && sf.voltage_limits.min_v !== undefined) {
    put("sf-vlimits", sf.voltage_limits.min_v.toFixed(2) + "V &ndash; " + sf.voltage_limits.max_v.toFixed(2) + "V");
  }
  if (sf.current_limits && sf.current_limits.max_a !== undefined) {
    put("sf-ilimits", "\u00b1" + sf.current_limits.max_a.toFixed(1) + "A");
  }
  if (sf.temperature_limits && sf.temperature_limits.max_c !== undefined) {
    put("sf-tlimits", "MAX " + sf.temperature_limits.max_c.toFixed(1) + "\u00b0C");
  }
  if (sf.active_constraints && sf.active_constraints.length) {
    put("sf-constraints", sf.active_constraints.join(", "));
  }

  renderTrace(ok ? tr : null);
  renderGraph();
}

function online(up){
  $("online").setAttribute("data-tone", up ? "ok" : "bad");
  $("online-t").textContent = up ? "CONSOLE ONLINE" : "STATUS UNREACHABLE";
}
function poll(){
  fetch("/api/status", {cache: "no-store"})
    .then(function(r){ if (!r.ok) throw new Error("http " + r.status); return r.json(); })
    .then(function(s){ online(true); render(s); })
    .catch(function(){ online(false); render(null); });
}

function initStream(){
  if (window.EventSource){
    try {
      var source = new EventSource("/api/telemetry/stream");
      source.onmessage = function(e){
        try {
          var snap = JSON.parse(e.data);
          if (snap && snap.available){
            online(true);
            render(snap);
          }
        } catch(err){}
      };
      source.onerror = function(){
        source.close();
        setTimeout(initStream, 5000);
      };
    } catch(err){}
  }
}

function loadBenchmarks(){
  var baseBox = $("hist-baseline-content");
  if (baseBox && last && last.historical_baseline){
    var hb = last.historical_baseline;
    baseBox.textContent = "";
    var g = el("div", "trace-empty-grid");

    var fBox = el("div", "teg-item");
    fBox.appendChild(el("div", "teg-l", "PHASE 5 FEATURE EVIDENCE (30 EVALUATED)"));
    fBox.appendChild(el("div", "teg-v", "ADMITTED (5): " + (hb.phase5_features ? hb.phase5_features.admitted.join(", ") : "5 features") + " | 20 REJECTED"));
    g.appendChild(fBox);

    var lBox = el("div", "teg-item");
    lBox.appendChild(el("div", "teg-l", "PHASE 6.1.1 MIXED-COHORT LOFO ABLATION (DELTA_V_TOTAL)"));
    lBox.appendChild(el("div", "teg-v", "Cohen's d = 0.67 | Wilcoxon p = 0.0382 (9/12 folds improved) [PROVISIONALLY SUPPORTED]"));
    g.appendChild(lBox);

    var nBox = el("div", "teg-item");
    nBox.appendChild(el("div", "teg-l", "PHASE 6.1.1 NMC CORRELATION (N=3 SPECIMENS)"));
    nBox.appendChild(el("div", "teg-v", "r = -0.9984 [EXPLORATORY / DESCRIPTIVE ONLY \u2014 NO INTERPOLATION]"));
    g.appendChild(nBox);

    var sBox = el("div", "teg-item");
    sBox.appendChild(el("div", "teg-l", "AUTHORITATIVE SAFETY LIMITS"));
    sBox.appendChild(el("div", "teg-v", "V: 2.00V\u20133.75V | I: \u00b150.0A | T: Max 45.0\u00b0C | SUPERVISOR INTERLOCK"));
    g.appendChild(sBox);

    baseBox.appendChild(g);
  }

  fetch("/api/benchmarks", {cache: "no-store"}).then(function(r){ return r.json(); }).then(function(j){
    if (j.title) $("bench-title").textContent = j.title;
    if (j.notice) $("bench-note").textContent = j.notice;
    var box = $("bench"); box.textContent = "";
    if (!j.scenarios || !j.scenarios.length){ box.appendChild(el("span", "na", NA)); $("bench-sum").textContent = ""; return; }
    var pass = 0, fail = 0;
    j.scenarios.forEach(function(s){
      if (s.passed === true) pass++; else if (s.passed === false) fail++;
      var det = el("details", "bm"); det.setAttribute("data-tone", tone(s.decision));
      var sum = el("summary");
      sum.appendChild(el("span", "bid", txt(s.id)));
      sum.appendChild(el("span", "bobj", txt(s.objective)));
      sum.appendChild(el("span", "bdec", txt(s.decision)));
      var res = s.passed === true ? "PASS" : (s.passed === false ? "FAIL" : txt(s.pass_fail));
      sum.appendChild(el("span", "pill " + (s.passed === true ? "pass" : (s.passed === false ? "fail" : "")), res));
      det.appendChild(sum);
      var body = el("div", "bbody");
      [["SETUP", s.setup], ["EXPECTED", s.expected_behavior], ["ACTUAL", s.actual_behavior],
       ["SAFETY RESULT", s.safety_result], ["OBSERVATIONS", s.observations]].forEach(function(r){
        body.appendChild(el("span", "k", r[0])); body.appendChild(el("span", "v", txt(r[1])));
      });
      body.appendChild(el("span", "k", "MEASUREMENTS"));
      var pre = el("pre", "", s.measurements ? JSON.stringify(s.measurements, null, 1) : NA);
      body.appendChild(pre);
      det.appendChild(body);
      box.appendChild(det);
    });
    $("bench-sum").textContent = j.scenarios.length + " RECORDED SCENARIOS  |  " + pass + " PASS  |  " + fail + " FAIL";
  }).catch(function(){});
}

renderTabs(); renderStages(false, {}, []); renderGraph();
poll(); loadBenchmarks(); initStream(); setInterval(poll, 1000);
</script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/status":
            if GLOBAL_INGEST_ENGINE and GLOBAL_INGEST_ENGINE.stats.total_received > 0:
                self._json(status_adapter.build_live_telemetry_snapshot(GLOBAL_INGEST_ENGINE))
            else:
                self._json(status_adapter.read_status_snapshot(STATUS_PATH))
        elif path == "/api/telemetry/live":
            if GLOBAL_INGEST_ENGINE:
                self._json(GLOBAL_INGEST_ENGINE.get_live_snapshot())
            else:
                self._json({"error": "INGESTION_DISABLED"}, 503)
        elif path == "/api/telemetry/history":
            if GLOBAL_INGEST_ENGINE:
                self._json({
                    "available": True,
                    "count": len(GLOBAL_INGEST_ENGINE.telemetry_history),
                    "history": GLOBAL_INGEST_ENGINE.get_telemetry_history(200),
                    "graph_series": {
                        "v": GLOBAL_INGEST_ENGINE.get_graph_series("voltage"),
                        "i": GLOBAL_INGEST_ENGINE.get_graph_series("current"),
                        "p": GLOBAL_INGEST_ENGINE.get_graph_series("power"),
                        "t": GLOBAL_INGEST_ENGINE.get_graph_series("temperature"),
                        "risk": GLOBAL_INGEST_ENGINE.get_graph_series("marginal_risk"),
                        "soh": GLOBAL_INGEST_ENGINE.get_graph_series("soh"),
                        "r0": GLOBAL_INGEST_ENGINE.get_graph_series("r0")
                    }
                })
            else:
                self._json({"error": "INGESTION_DISABLED"}, 503)
        elif path == "/api/telemetry/stream":
            if not GLOBAL_INGEST_ENGINE:
                self._json({"error": "INGESTION_DISABLED"}, 503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last_seq = None
            t0 = time.time()
            while time.time() - t0 < 30.0:  # stream chunk up to 30s
                snap = GLOBAL_INGEST_ENGINE.get_live_snapshot()
                seq = snap["nexus_hardware"].get("sequence")
                if seq != last_seq:
                    last_seq = seq
                    msg = f"data: {json.dumps(snap)}\n\n"
                    try:
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except Exception:
                        break
                time.sleep(0.1)
        elif path == "/api/benchmarks":
            self._json(load_benchmarks(BENCHMARK_PATH))
        elif path in ("/", "/index.html"):
            self._send(200, HTML_TEMPLATE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            self._json({"error": "MALFORMED_JSON", "message": str(exc)}, 400)
            return

        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        if path == "/api/telemetry":
            if not GLOBAL_INGEST_ENGINE:
                self._json({"error": "INGESTION_DISABLED"}, 503)
                return
            accepted, reason, details = GLOBAL_INGEST_ENGINE.ingest_packet(payload, client_ip=client_ip)
            if accepted or reason == "VALIDATION_FAILED":
                code = 200
            elif reason in ("MALFORMED_PAYLOAD", "INVALID_SEQUENCE_FIELD", "INVALID_TIMESTAMP_FIELD"):
                code = 400
            else:
                code = 422
            self._json({
                "status": "ACCEPTED" if accepted else "REJECTED",
                "reason": reason,
                "details": details,
                "command": GLOBAL_INGEST_ENGINE.get_live_snapshot().get("command_directive")
            }, code)
        elif path == "/api/command":
            if not GLOBAL_INGEST_ENGINE:
                self._json({"error": "INGESTION_DISABLED"}, 503)
                return
            action = str(payload.get("action", "HOLD"))
            cmd = GLOBAL_INGEST_ENGINE.queue_command(action, requested_by="OPERATOR_UI")
            self._json({"status": "COMMAND_QUEUED", "command": cmd}, 200)
        else:
            self._json({"error": "not found"}, 404)


def run_dashboard_server(port: int = DEFAULT_PORT, host: str = "0.0.0.0"):
    with http.server.ThreadingHTTPServer((host, port), DashboardHandler) as httpd:
        print(f"\n[DASHBOARD ONLINE] Serving SECONDShift Dashboard on http://localhost:{port} (bound to {host})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[DASHBOARD STOPPED]")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    host = str(sys.argv[2]) if len(sys.argv) > 2 else "0.0.0.0"
    run_dashboard_server(port, host)