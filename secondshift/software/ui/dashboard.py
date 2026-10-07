"""
Local Status Dashboard - last completed qualification (observability only)
Project: RMK-REVOLT / SECONDShift Platform

Zero-dependency stdlib HTTP server.
  /                 one-page HTML dashboard (industrial test-station HMI)
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
from typing import Any, Dict

try:
    from secondshift.software.ui import status_adapter
except ImportError:  # running as a script: sibling module is on sys.path
    import status_adapter

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
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));background:var(--dark2);border-top:1px solid #3a4852}
.sc{padding:6px 12px;border-right:1px solid #33424d;min-width:0}
.sc:last-child{border-right:0}
.sl{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:#91a0aa}
.sv{display:block;font:700 13px/1.35 var(--mono);color:#fff;overflow-wrap:anywhere}
.sv.na{color:#91a0aa}.sv.tn-ok{color:#5fd9ee}.sv.tn-warn{color:#e0a84b}.sv.tn-bad{color:#ff8a80}

/* shell */
.shell{display:grid;grid-template-columns:168px minmax(0,1fr);min-height:calc(100vh - 118px)}
.rail{background:var(--pn);border-right:1px solid var(--ln);padding:10px 0}
.rail .grp{font:700 9px/1 var(--mono);letter-spacing:.14em;color:var(--mut);padding:6px 16px}
.nv{display:block;width:100%;text-align:left;font:700 11px/1 var(--mono);letter-spacing:.07em;color:var(--mut);background:transparent;border:0;border-left:3px solid transparent;padding:11px 16px;cursor:pointer;transition:background .15s,color .15s}
.nv:hover{background:var(--hd);color:var(--fg)}
.nv[aria-selected="true"]{color:var(--cyd);background:var(--cys);border-left-color:var(--cy)}
.nv:focus-visible{outline:2px solid var(--cy);outline-offset:-2px}
.main{padding:12px;min-width:0}
.ws[hidden]{display:none}
.alarm{margin:0 0 10px;padding:10px 14px;background:#fdecea;border:2px solid var(--bad);border-radius:6px;color:#5a1a14}
.alarm[hidden]{display:none}
.alarm .a1{font:800 20px/1.2 var(--mono);color:var(--bad);letter-spacing:.06em}
.alarm .a2{font:12px/1.4 var(--mono);margin-top:4px;overflow-wrap:anywhere}
.foot{border-top:1px solid var(--ln);background:var(--pn);padding:6px 14px;display:flex;gap:14px;align-items:center}
.foot p{margin:0;font:11px/1.4 var(--mono);color:var(--mut)}

/* panels */
.pn{background:var(--pn);border:1px solid var(--ln);border-radius:6px;box-shadow:0 1px 4px rgba(20,35,45,.06);min-width:0;overflow:hidden}
.pn>h2{margin:0;padding:6px 12px;background:var(--hd);border-bottom:1px solid var(--ln);font:700 10px/1.3 var(--mono);letter-spacing:.13em;color:var(--mut);display:flex;justify-content:space-between;gap:8px}
.pn>h2 .tag{color:var(--pur)}
.pb{padding:12px}
.ov{display:grid;grid-template-columns:minmax(270px,1fr) minmax(0,1.5fr);gap:10px;align-items:start}
.col{display:grid;gap:10px;min-width:0}
.pn.safe{border-top:3px solid var(--accent,var(--cy))}

/* readouts */
.lcd{background:var(--hd);border:1px solid var(--ln);border-radius:4px;padding:5px 10px 6px;margin-bottom:6px}
.lcd .l{font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.lcd .n{font:600 30px/1.1 var(--mono);text-align:right;color:var(--fg);overflow-wrap:anywhere}
.lcd .n.na{color:var(--neutral)}
.n .u{font-size:13px;font-weight:400;color:var(--cyd);margin-left:5px}
.t{display:grid;grid-template-columns:auto minmax(0,1fr);gap:3px 12px;font:12px/1.35 var(--mono);margin-top:8px}
.t .k{color:var(--mut);font-size:10px;letter-spacing:.07em;align-self:center}
.t .v{text-align:right;overflow-wrap:anywhere}
.t hr{grid-column:1/-1;border:0;border-top:1px solid var(--ln);margin:4px 0;width:100%}
.sbig{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--ln);border-left:5px solid var(--accent);border-radius:4px;background:var(--hd);margin-bottom:8px}
.sbig .led{width:14px;height:14px}
.sbig .sv2{font:800 21px/1.1 var(--mono);color:var(--accent)}
.sbig .sl{color:var(--mut)}
.sbig.trip{background:#fdecea;border-color:var(--bad)}
.note{font:11px/1.45 var(--mono);color:var(--mut);margin:8px 0 0}

/* graph */
.tabs{display:flex;flex-wrap:wrap;border-bottom:1px solid var(--ln);background:var(--hd)}
.tab{font:700 10px/1 var(--mono);letter-spacing:.08em;color:var(--mut);background:transparent;border:0;border-right:1px solid var(--ln);padding:10px 14px;cursor:pointer}
.tab:hover{color:var(--fg)}
.tab[aria-selected="true"]{color:var(--cyd);background:var(--pn);box-shadow:inset 0 -2px 0 var(--cy)}
.tab:focus-visible{outline:2px solid var(--cy);outline-offset:-2px}
.gbox{min-height:340px;background-color:#fff;background-image:linear-gradient(#edf1f4 1px,transparent 1px),linear-gradient(90deg,#edf1f4 1px,transparent 1px);background-size:32px 32px;display:flex;align-items:center;justify-content:center}
.gmsg{text-align:center;padding:20px;max-width:520px}
.gmsg .g1{font:700 13px/1.4 var(--mono);letter-spacing:.06em;color:var(--warn)}
.gmsg .g2{font:12px/1.5 var(--mono);color:var(--mut);margin-top:8px}
.gmsg .g3{font:600 22px/1.2 var(--mono);color:var(--cyd);margin-top:12px}
.chart{width:100%;height:auto;display:block}
.chart .gl{stroke:#e2e8ed;stroke-width:1}
.chart .ax{stroke:#8a98a4;stroke-width:1}
.chart .ln{fill:none;stroke:var(--cy);stroke-width:2}
.chart .pt{fill:var(--cyd);stroke:#fff;stroke-width:1}
.chart text{font:10px var(--mono);fill:var(--mut)}
.chart text.vl{fill:var(--fg)}
.gfoot{padding:6px 12px;border-top:1px solid var(--ln);font:10px/1.4 var(--mono);color:var(--mut)}

/* decision engine */
.stg{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px;margin-bottom:12px}
.stage{border:1px solid var(--ln);border-top:3px solid var(--accent);border-radius:4px;background:var(--hd);padding:6px 8px;min-width:0}
.stage .sn{font:700 10px/1.3 var(--mono);letter-spacing:.06em;display:flex;align-items:center;gap:6px}
.stage .ss{font:10px/1.3 var(--mono);color:var(--mut);margin-top:2px;overflow-wrap:anywhere}
.dgrid{display:grid;grid-template-columns:minmax(170px,230px) minmax(0,1fr);gap:12px}
.dbig{border:1px solid var(--ln);border-left:5px solid var(--accent);border-radius:4px;background:var(--hd);padding:8px 12px}
.dbig .l{font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.dbig .d{font:800 32px/1.1 var(--mono);color:var(--accent);overflow-wrap:anywhere}
.dbig .d.na{color:var(--neutral)}
.dbig .d.vetoed{text-decoration:line-through;color:var(--neutral)}
.dbig .veto{font:700 11px/1.3 var(--mono);color:var(--bad);margin-top:4px}
.why{margin-top:8px;padding:6px 8px;border:1px solid var(--ln);border-radius:4px;background:var(--hd);font:12px/1.45 var(--mono);overflow-wrap:anywhere}
.why .l{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut);margin-bottom:2px}

/* trace */
.tl{list-style:none;margin:0;padding:0}
.tl li{position:relative;padding:0 0 12px 20px;border-left:2px solid var(--ln);margin-left:5px}
.tl li:last-child{padding-bottom:0;border-left-color:transparent}
.tl li::before{content:"";position:absolute;left:-6px;top:3px;width:10px;height:10px;border-radius:50%;background:var(--accent,var(--neutral))}
.tl .st{font:700 10px/1.3 var(--mono);letter-spacing:.08em;color:var(--mut)}
.tl .dc{font:700 14px/1.3 var(--mono);color:var(--accent,var(--fg))}
.tl .meta{font:11px/1.4 var(--mono);color:var(--mut)}
.tl .rs{font:12px/1.4 var(--sans);margin-top:2px;overflow-wrap:anywhere}

/* historical benchmarks: dashed = recorded, not live */
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

/* v2 additions: verdict, tiles, pipeline, bars, rail badge */
.nv{display:flex;align-items:center;gap:8px}
.nv svg{width:14px;height:14px;flex:none;fill:none;stroke:currentColor;stroke-width:1.6}
.bdg{margin-left:auto;background:var(--bad);color:#fff;font:700 9px/1.4 var(--mono);padding:1px 5px;border-radius:3px}
.bdg[hidden]{display:none}
.verdict{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--ln);border-top:4px solid var(--accent,var(--neutral));border-radius:6px;background:var(--pn);box-shadow:0 1px 4px rgba(20,35,45,.06)}
.vc{padding:10px 16px;border-right:1px solid var(--ln);min-width:0}
.vc:last-child{border-right:0}
.vc .l{display:block;font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.vc .big{display:block;font:800 24px/1.2 var(--mono);color:var(--accent,var(--neutral));overflow-wrap:anywhere}
.vc .big.na{color:var(--neutral)}
.tiles{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.tile{background:var(--pn);border:1px solid var(--ln);border-radius:6px;padding:10px 14px;box-shadow:0 1px 4px rgba(20,35,45,.06)}
.tile .th{display:flex;justify-content:space-between;align-items:center;gap:8px}
.tile .l{font:700 9px/1.2 var(--mono);letter-spacing:.12em;color:var(--mut)}
.vchip{font:700 9px/1.4 var(--mono);padding:1px 6px;border:1px solid var(--ln);border-radius:3px;color:var(--neutral)}
.vchip.tn-ok{border-color:var(--ok)}.vchip.tn-bad{border-color:var(--bad)}
.tile .n{font:600 40px/1.1 var(--mono);text-align:left;color:var(--fg);margin-top:4px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.tile .n.na{color:var(--neutral)}
.tile .n .u{font-size:16px}
.stg{display:flex;flex-wrap:wrap;gap:16px}
.stage{flex:1 1 120px;position:relative}
.stage:not(:last-child)::after{content:"\25B6";position:absolute;right:-13px;top:50%;transform:translateY(-50%);font-size:9px;color:var(--neutral)}
.stage.hw{border:2px solid var(--dark);border-top:4px solid var(--accent)}
.stage .hwt{margin-left:auto;background:var(--dark);color:#fff;font:700 8px/1.5 var(--mono);padding:0 4px;border-radius:2px}
.bars{display:grid;gap:12px;margin-top:14px}
.bh{display:flex;justify-content:space-between;gap:8px;font:700 10px/1.3 var(--mono);letter-spacing:.08em;color:var(--mut)}
.bh span+span{color:var(--fg)}
.trk{position:relative;height:12px;background:var(--hd);border:1px solid var(--ln);border-radius:3px;margin-top:4px;overflow:hidden}
.fill{position:absolute;left:0;top:0;bottom:0;width:0;background:var(--cy);transition:width .3s}
.fill.risk{background:var(--warn)}
.band{position:absolute;top:0;bottom:0;left:0;width:0;background:rgba(15,138,166,.4);border-left:1px solid var(--cyd);border-right:1px solid var(--cyd)}
.chart .pt{cursor:crosshair}.chart .pt:hover{fill:var(--cy)}
@media (max-width:700px){.verdict,.tiles{grid-template-columns:minmax(0,1fr)}.vc{border-right:0;border-bottom:1px solid var(--ln)}}
@media (max-width:1000px){
  .ov{grid-template-columns:minmax(0,1fr)}
  .shell{grid-template-columns:minmax(0,1fr)}
  .rail{display:flex;overflow-x:auto;padding:0;border-right:0;border-bottom:1px solid var(--ln)}
  .rail .grp{display:none}
  .nv{width:auto;white-space:nowrap;border-left:0;border-bottom:3px solid transparent}
  .nv[aria-selected="true"]{border-bottom-color:var(--cy)}
}
@media (max-width:700px){
  .main{padding:8px}
  .dgrid{grid-template-columns:minmax(0,1fr)}
  .bm summary{grid-template-columns:minmax(0,1fr) 54px}
  .bm summary .bobj{grid-column:1/-1;order:3}
  .bm summary .bdec{display:none}
  .bbody{grid-template-columns:minmax(0,1fr)}
  .lcd .n{font-size:24px}
}
</style>
</head>
<body>
<header class="top">
  <div class="ttl">
    <span class="logo">SECOND<b>Shift</b></span>
    <span class="ttl2">BATTERY QUALIFICATION SYSTEM</span>
    <span class="sp"></span>
    <span class="live" id="online" data-tone="none"><i class="led"></i><span id="online-t">CONNECTING</span></span>
    <span class="chip">DATA: LAST COMPLETED QUALIFICATION</span>
    <span class="chip" id="upd">UPDATED: N/A</span>
  </div>
  <div class="strip">
    <div class="sc"><span class="sl">STATION</span><span class="sv na">NOT REPORTED</span></div>
    <div class="sc"><span class="sl">CHANNEL</span><span class="sv na">NOT REPORTED</span></div>
    <div class="sc"><span class="sl">CELL</span><span class="sv na" id="s-cell">N/A</span></div>
    <div class="sc"><span class="sl">CHEMISTRY</span><span class="sv na" id="s-chem">N/A</span></div>
    <div class="sc"><span class="sl">MODE</span><span class="sv na" id="s-mode">N/A</span></div>
    <div class="sc"><span class="sl">CONNECTION</span><span class="sv na" id="s-conn">N/A</span></div>
    <div class="sc"><span class="sl">SYSTEM</span><span class="sv na" id="s-sys">N/A</span></div>
    <div class="sc"><span class="sl">HARDWARE STATE</span><span class="sv na">N/A</span></div>
  </div>
</header>

<div class="shell">
  <nav class="rail" aria-label="Workspaces">
    <div class="grp">WORKSPACE</div>
    <button class="nv" type="button" data-ws="overview"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z"/></svg>OVERVIEW<span class="bdg" id="nv-badge" hidden>TRIP</span></button>
    <button class="nv" type="button" data-ws="trend"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 14V2M2 14h12M4 10l3-3 2 2 4-5"/></svg>TEST GRAPH</button>
    <button class="nv" type="button" data-ws="trace"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3v10M3 4h9M3 8h6M3 12h8"/></svg>DECISION TRACE</button>
    <button class="nv" type="button" data-ws="bench"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2h10v12H3zM6 6h4M6 9h4"/></svg>BENCHMARKS</button>
  </nav>

  <main class="main">
    <div class="alarm" id="alarm" hidden role="alert">
      <div class="a1">SAFETY TRIP</div>
      <div class="a2" id="alarm-why"></div>
      <div class="a2" id="alarm-sys"></div>
    </div>

    <section class="ws ov" id="ws-overview">
      <div class="verdict" id="verdict" data-tone="none" aria-label="Verdict">
        <div class="vc" data-tone="none"><span class="l">SAFETY BARRIER</span><span class="big na" id="vd-safe">N/A</span></div>
        <div class="vc" data-tone="none"><span class="l">FINAL DECISION</span><span class="big na" id="vd-dec">N/A</span></div>
        <div class="vc" data-tone="none"><span class="l">SYSTEM STATE</span><span class="big na" id="vd-sys">N/A</span></div>
      </div>
      <div class="tiles" aria-label="Live measurements">
        <div class="tile"><div class="th"><span class="l">VOLTAGE</span><span class="vchip">N/A</span></div><div class="n na" id="volt">N/A</div></div>
        <div class="tile"><div class="th"><span class="l">CURRENT</span><span class="vchip">N/A</span></div><div class="n na" id="curr">N/A</div></div>
        <div class="tile"><div class="th"><span class="l">TEMPERATURE</span><span class="vchip">N/A</span></div><div class="n na" id="temp">N/A</div></div>
      </div>
      <div class="col">
        <section class="pn safe" id="safepn" data-tone="none" aria-label="Safety barrier"><h2><span>HARD SAFETY BARRIER</span><span>AUTHORITATIVE</span></h2>
          <div class="pb">
            <div class="sbig" id="sbig" data-tone="none"><i class="led"></i><div><div class="l sl">SAFETY STATE</div><div class="sv2" id="sf-state">N/A</div></div></div>
            <div class="t" style="margin-top:0">
              <span class="k">CELL VOLTAGE</span><span class="v" id="sf-v">N/A</span>
              <span class="k">CURRENT</span><span class="v" id="sf-i">N/A</span>
              <span class="k">TEMPERATURE</span><span class="v" id="sf-t">N/A</span>
              <span class="k">LIMITS</span><span class="v na">NOT REPORTED</span>
              <hr>
              <span class="k">TELEMETRY CHECK</span><span class="v na" id="sf-valid">N/A</span>
              <span class="k">MARGINAL RISK</span><span class="v na" id="sf-risk">N/A</span>
              <span class="k">TRIP COUNT</span><span class="v na">N/A</span>
              <span class="k">LAST EVENT</span><span class="v na" id="sf-last">N/A</span>
            </div>
            <p class="note">Per-channel limits and trip count are not part of the status snapshot, so none are displayed. Safety state is the recorded trip flag of the last completed run. The safety barrier is independent of the decision engine.</p>
          </div>
        </section>

        <section class="pn" aria-label="Channel status"><h2><span>CELL UNDER TEST</span><span>CH-01</span></h2>
          <div class="pb">
            <div class="t">
              <span class="k">CELL ID</span><span class="v na" id="c-cell">N/A</span>
              <span class="k">CHEMISTRY</span><span class="v na" id="c-chem">N/A</span>
              <span class="k">CONFIDENCE</span><span class="v na" id="c-conf">N/A</span>
              <span class="k">SOH</span><span class="v na" id="c-soh">N/A</span>
              <span class="k">SOH UNCERT.</span><span class="v na" id="c-sohu">N/A</span>
              <span class="k">R0</span><span class="v na" id="c-r0">N/A</span>
              <span class="k">STATE</span><span class="v na" id="c-fsm">N/A</span>
              <hr>
              <span class="k">TELEMETRY</span><span class="v na" id="c-valid">N/A</span>
              <span class="k">QUALITY</span><span class="v na" id="c-qual">N/A</span>
              <span class="k">FRAME SEQ</span><span class="v na" id="c-seq">N/A</span>
              <span class="k">TESTS RUN</span><span class="v na" id="c-tests">N/A</span>
              <span class="k">ELAPSED</span><span class="v na" id="c-elapsed">N/A</span>
              <span class="k">COMMAND ID</span><span class="v na" id="c-cmd">N/A</span>
            </div>
          </div>
        </section>
      </div>

      <section class="pn" aria-label="SECONDShift decision engine"><h2><span>SECONDShift DECISION ENGINE</span><span class="tag">MODEL-DERIVED</span></h2>
        <div class="pb">
          <div class="stg" id="stg"></div>
          <div class="dgrid">
            <div>
              <div class="dbig" id="dbig" data-tone="none">
                <div class="l">FINAL DECISION</div>
                <div class="d na" id="d-dec">N/A</div>
                <div class="veto" id="d-veto" hidden>OVERRIDDEN BY SAFETY TRIP</div>
              </div>
              <div class="t">
                <span class="k">ACTUATION INTENT</span><span class="v na" id="d-intent">N/A</span>
                <span class="k">(REQUESTED)</span><span class="v na">NOT CONFIRMED</span>
              </div>
            </div>
            <div>
              <div class="t" style="margin-top:0">
                <span class="k">MARGINAL FAILURE RISK</span><span class="v na" id="d-risk">N/A</span>
                <span class="k">RISK THRESHOLD</span><span class="v na">N/A</span>
                <span class="k">SOH</span><span class="v na" id="d-soh">N/A</span>
                <span class="k">R0</span><span class="v na" id="d-r0">N/A</span>
                <span class="k">HERMES</span><span class="v na">N/A</span>
              </div>
              <div class="why"><span class="l">REASON</span><span id="d-why" class="na">N/A</span></div>
            </div>
          </div>
          <div class="bars">
            <div class="br"><div class="bh"><span>SOH ESTIMATE (BAND = UNCERTAINTY)</span><span id="bar-soh-v">N/A</span></div><div class="trk"><div class="fill" id="bar-soh"></div><div class="band" id="bar-sohu"></div></div></div>
            <div class="br"><div class="bh"><span>MARGINAL FAILURE RISK (0-100% SCALE, NO THRESHOLD REPORTED)</span><span id="bar-risk-v">N/A</span></div><div class="trk"><div class="fill risk" id="bar-risk"></div></div></div>
          </div>
          <p class="note">Stage indicators are derived from the recorded decision trace of the last completed run. They are not live stage state. No HERMES or hardware source is connected, so actuation is shown as requested intent only.</p>
        </div>
      </section>
    </section>

    <section class="ws pn" id="ws-trend" aria-label="Test graph" hidden><h2><span>TEST GRAPH</span><span>LAST COMPLETED QUALIFICATION</span></h2>
      <div class="tabs" role="tablist" id="tabs"></div>
      <div class="gbox" id="gbox"></div>
      <div class="gfoot" id="gfoot"></div>
    </section>

    <section class="ws pn" id="ws-trace" aria-label="Decision trace" hidden><h2><span>TEST SEQUENCE / DECISION TRACE</span><span>RECORDED</span></h2>
      <div class="pb"><ol class="tl" id="trace"><li class="na">N/A</li></ol></div>
    </section>

    <section class="ws pn hist" id="ws-bench" hidden><h2><span>HISTORICAL BENCHMARK RESULTS</span><span>NOT LIVE PHYSICAL VALIDATION</span></h2>
      <div class="pb">
        <div class="sl" style="color:var(--mut)" id="bench-title">Historical Recorded Qualification Results</div>
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
var tab = "risk";
var TABS = [["v","VOLTAGE"],["i","CURRENT"],["t","TEMPERATURE"],["risk","MARGINAL RISK"],["soh","SOH"],["r0","R0"]];
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
  if (/RETIRE|ISOLATE|FAULT|REJECT|TRIPPED|UNSAFE|LOCKOUT|FAIL/.test(x)) return "bad";
  if (/^(DERATE|HOLD|TEST)/.test(x)) return "warn";
  if (/^(OPERATE|ACCEPT|PASS|SAFE|CLEAR)/.test(x)) return "ok";
  return "none";
}
function put(id, val, tn){
  var e = $(id);
  e.textContent = val;
  e.className = e.className.replace(/\b(na|tn-\w+)\b/g, "").replace(/\s+/g, " ").trim();
  if (val === NA) e.className += " na";
  else if (tn && tn !== "none") e.className += " tn-" + tn;
}
function putNum(id, v, digits, unit){
  var e = $(id); e.textContent = "";
  if (isn(v)){
    e.classList.remove("na");
    e.appendChild(document.createTextNode(v.toFixed(digits)));
    if (unit) e.appendChild(el("span", "u", unit));
  } else { e.classList.add("na"); e.textContent = NA; }
}
function numStr(v, digits, unit){ return isn(v) ? v.toFixed(digits) + " " + unit : NA; }

/* ---- workspace navigation (presentation only) ---- */
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
  var W = 640, H = 300, L = 62, R = 18, T = 18, B = 48;
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
  s.appendChild(svg("text", {x: -(T + (H - T - B) / 2), y: 12, transform: "rotate(-90)", "text-anchor": "middle"}, ylab || ""));
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
  s.appendChild(svg("text", {x: (L + W - R) / 2, y: H - 8, "text-anchor": "middle"}, "DECISION ITERATION (RECORDED TRACE) - NOT TIME"));
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
  var tr = (ok && last.decision_trace) || [];
  var tel = (ok && last.telemetry) || {};
  var m = {v: ["VOLTAGE", tel.voltage_v, 3, "V"], i: ["CURRENT", tel.current_a, 3, "A"], t: ["TEMPERATURE", tel.temperature_c, 1, "\u00b0C"]}[tab];
  if (m){
    var g = el("div", "gmsg");
    g.appendChild(el("div", "g1", "TELEMETRY TREND - NO TIME SERIES AVAILABLE"));
    g.appendChild(el("div", "g2", "The status snapshot holds a single telemetry frame, so no curve is drawn. The last evaluated frame is shown as a value only."));
    g.appendChild(el("div", "g3", m[0] + ": " + numStr(m[1], m[2], m[3])));
    box.appendChild(g);
    foot.textContent = "SOURCE: LAST EVALUATED TELEMETRY FRAME" + (isn(tel.sequence_number) ? " (SEQ " + tel.sequence_number + ")" : "");
    return;
  }
  var cfg = {risk: ["marginal_risk", function(v){ return (v * 100).toFixed(2) + "%"; }, true, "MARGINAL RISK (%)"],
             soh: ["soh_estimate", function(v){ return (v * 100).toFixed(1) + "%"; }, false, "SOH (%)"],
             r0: ["r0_mohm", function(v){ return v.toFixed(2) + " m\u03a9"; }, false, "R0 (m\u03a9)"]}[tab];
  var chart = ok ? drawChart(buildSeries(tr, cfg[0]), cfg[1], cfg[2], cfg[3]) : null;
  if (!chart){
    var e = el("div", "gmsg"); e.appendChild(el("div", "g1", "NO DATA RECORDED FOR THIS QUANTITY"));
    e.appendChild(el("div", "g2", "The recorded decision trace has no values for it."));
    box.appendChild(e); foot.textContent = "SOURCE: RECORDED DECISION TRACE"; return;
  }
  box.appendChild(chart);
  foot.textContent = "SOURCE: RECORDED DECISION TRACE OF THE LAST COMPLETED QUALIFICATION. NOT A LIVE OR TIME-BASED MEASUREMENT.";
}

/* ---- decision engine stages (derived from recorded trace only) ---- */
function renderStages(ok, d, tr){
  var box = $("stg"); box.textContent = "";
  var tri = tr.filter(function(x){ return /TRIAGE/i.test(x.stage || ""); })[0];
  var loops = tr.filter(function(x){ return /LOOP/i.test(x.stage || ""); });
  var hasSigma = loops.some(function(x){ return isn(x.soh_uncertainty); });
  var hasSoh = loops.some(function(x){ return isn(x.soh_estimate); });
  var hasRisk = loops.some(function(x){ return isn(x.marginal_risk); });
  var tripped = ok && d.safety_tripped === true;
  var list = [
    ["TRIAGE", ok && tri ? "EVALUATED" : "NOT RECORDED", tri ? txt(tri.decision) : ""],
    ["UNCERTAINTY", ok && hasSigma ? "EVALUATED" : "NOT RECORDED", ""],
    ["BAYESIAN", ok && hasSoh ? "EVALUATED" : "NOT RECORDED", ""],
    ["SAFETY BARRIER", tripped ? "TRIPPED" : (ok && hasRisk ? "EVALUATED" : "NOT RECORDED"), ""],
    ["ADAPTIVE DECISION", ok && has(d.final_decision) ? "DECIDED" : "NOT RECORDED", ok ? txt(d.final_decision) : ""],
    ["HERMES", "N/A", "NO SOURCE"]
  ];
  list.forEach(function(s){
    var st = s[1], tn = st === "TRIPPED" ? "bad" : ((st === "EVALUATED" || st === "DECIDED") ? "ok" : "none");
    var c = el("div", "stage"); c.setAttribute("data-tone", tn);
    if (s[0] === "SAFETY BARRIER") c.className += " hw";
    var n = el("div", "sn"); n.appendChild(el("i", "led")); n.appendChild(document.createTextNode(s[0]));
    if (s[0] === "SAFETY BARRIER") n.appendChild(el("span", "hwt", "HARD"));
    c.appendChild(n); c.appendChild(el("div", "ss", st + (s[2] ? " / " + s[2] : "")));
    box.appendChild(c);
  });
}

function renderTrace(trace){
  var ol = $("trace"); ol.textContent = "";
  if (!trace || !trace.length){ ol.appendChild(el("li", "na", NA)); return; }
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
  var e = $(id); e.textContent = val; e.className = "big" + (val === NA ? " na" : "");
  e.parentNode.setAttribute("data-tone", val === NA ? "none" : tn);
}
function render(s){
  last = s;
  var ok = !!(s && s.available === true);
  var d = (ok && s.decision) || {}, b = (ok && s.bayesian) || {}, c = (ok && s.chemistry) || {}, t = (ok && s.telemetry) || {};
  var tr = (ok && s.decision_trace) || [];
  var tripped = d.safety_tripped === true;
  var dTone = tripped ? "bad" : tone(d.final_decision);
  var mode = ok && has(s.mode) ? String(s.mode).toUpperCase() : NA;
  var conn = mode === "MOCK" ? "SIMULATED" : (mode === "REPLAY" ? "REPLAY (NO LIVE LINK)" : (mode === "SERIAL" ? "SERIAL (LINK STATE NOT REPORTED)" : NA));

  /* header */
  put("s-cell", ok ? txt(s.cell_id) : NA);
  put("s-chem", txt(c.final_chemistry));
  put("s-mode", mode);
  put("s-conn", conn);
  put("s-sys", has(d.system_state) ? String(d.system_state).toUpperCase() : NA, tripped ? "bad" : tone(d.system_state));
  $("upd").textContent = "UPDATED: " + (ok ? txt(s.updated_at) : NA);

  var m = $("msg");
  if (!ok) m.textContent = (s && s.message) ? s.message : "No status data available.";
  else if (mode === "SERIAL") m.textContent = "Serial mode: values come from the connected device at the time of the last run. Actuation is shown as requested intent only.";
  else m.textContent = "Mode " + mode + ": simulated or replayed data. This is not physical hardware validation.";

  /* alarm */
  var al = $("alarm");
  al.hidden = !(ok && tripped);
  if (ok && tripped){
    $("alarm-why").textContent = "REASON: " + txt(d.reason);
    $("alarm-sys").textContent = "SYSTEM STATE: " + txt(d.system_state) + "   |   ACTUATION INTENT (REQUESTED, NOT CONFIRMED): " + txt(d.actuation_intent);
  }

  /* channel */
  putNum("volt", t.voltage_v, 3, "V"); putNum("curr", t.current_a, 3, "A"); putNum("temp", t.temperature_c, 1, "\u00b0C");
  put("c-cell", ok ? txt(s.cell_id) : NA); put("c-chem", txt(c.final_chemistry)); put("c-conf", txt(c.final_chem_confidence));
  put("c-soh", pct(b.soh_estimate, 1));
  put("c-sohu", isn(b.soh_uncertainty) ? "\u00b1" + pct(b.soh_uncertainty, 1) : NA);
  put("c-r0", numStr(b.r0_mohm, 2, "m\u03a9"));
  put("c-fsm", txt(d.system_state), tripped ? "bad" : tone(d.system_state));
  put("c-valid", t.is_valid === true ? "VALID" : (t.is_valid === false ? "INVALID" : NA), t.is_valid === true ? "ok" : (t.is_valid === false ? "bad" : ""));
  put("c-qual", txt(t.quality)); put("c-seq", txt(t.sequence_number));
  put("c-tests", txt(d.tests_executed_count));
  put("c-elapsed", isn(d.elapsed_time_s) ? d.elapsed_time_s.toFixed(3) + " s" : NA);
  put("c-cmd", txt(d.command_id));

  /* safety barrier */
  var sTone = !ok ? "none" : (tripped ? "bad" : (d.safety_tripped === false ? "ok" : "none"));
  var sb = $("sbig");
  sb.setAttribute("data-tone", sTone);
  $("safepn").setAttribute("data-tone", sTone);
  sb.classList.toggle("trip", ok && tripped);
  put("sf-state", !ok ? NA : (tripped ? "SAFETY TRIP" : (d.safety_tripped === false ? "CLEAR (NO TRIP)" : NA)));
  $("sf-state").className = "sv2";
  $("verdict").setAttribute("data-tone", sTone);
  vset("vd-safe", !ok ? NA : (tripped ? "TRIP" : (d.safety_tripped === false ? "CLEAR" : NA)), sTone);
  vset("vd-dec", txt(d.final_decision), dTone);
  vset("vd-sys", has(d.system_state) ? String(d.system_state).toUpperCase() : NA, tripped ? "bad" : tone(d.system_state));
  $("nv-badge").hidden = !(ok && tripped);
  var chipT = t.is_valid === true ? "VALID" : (t.is_valid === false ? "INVALID" : NA);
  Array.prototype.forEach.call(document.querySelectorAll(".vchip"), function(e){
    e.textContent = chipT; e.className = "vchip" + (t.is_valid === true ? " tn-ok" : (t.is_valid === false ? " tn-bad" : ""));
  });
  put("sf-v", numStr(t.voltage_v, 3, "V")); put("sf-i", numStr(t.current_a, 3, "A")); put("sf-t", numStr(t.temperature_c, 1, "\u00b0C"));
  put("sf-valid", t.is_valid === true ? "VALID" : (t.is_valid === false ? "INVALID" : NA), t.is_valid === true ? "ok" : (t.is_valid === false ? "bad" : ""));
  var lastRisk = null;
  tr.forEach(function(x){ if (isn(x.marginal_risk)) lastRisk = x.marginal_risk; });
  put("sf-risk", pct(lastRisk, 2));
  var lastEv = NA;
  if (t.errors && t.errors.length) lastEv = String(t.errors[0]);
  else if (tr.length) lastEv = shortStage(tr[tr.length - 1].stage) + ": " + txt(tr[tr.length - 1].decision);
  put("sf-last", lastEv);

  /* decision engine */
  renderStages(ok, d, tr);
  $("dbig").setAttribute("data-tone", ok ? dTone : "none");
  put("d-dec", txt(d.final_decision));
  $("d-dec").className = "d" + (has(d.final_decision) ? "" : " na") + (ok && tripped ? " vetoed" : "");
  $("d-veto").hidden = !(ok && tripped);
  put("d-intent", txt(d.actuation_intent));
  put("d-risk", pct(lastRisk, 2));
  put("d-soh", isn(b.soh_estimate) ? pct(b.soh_estimate, 1) + (isn(b.soh_uncertainty) ? " \u00b1" + pct(b.soh_uncertainty, 1) : "") : NA);
  put("d-r0", numStr(b.r0_mohm, 2, "m\u03a9"));
  put("d-why", txt(d.reason));
  var sohOk = isn(b.soh_estimate);
  $("bar-soh").style.width = sohOk ? Math.max(0, Math.min(100, b.soh_estimate * 100)) + "%" : "0";
  if (sohOk && isn(b.soh_uncertainty)){
    var lo = Math.max(0, (b.soh_estimate - b.soh_uncertainty) * 100), hi = Math.min(100, (b.soh_estimate + b.soh_uncertainty) * 100);
    $("bar-sohu").style.left = lo + "%"; $("bar-sohu").style.width = (hi - lo) + "%";
  } else { $("bar-sohu").style.width = "0"; }
  $("bar-soh-v").textContent = $("d-soh").textContent;
  $("bar-risk").style.width = isn(lastRisk) ? Math.max(0, Math.min(100, lastRisk * 100)) + "%" : "0";
  $("bar-risk-v").textContent = pct(lastRisk, 2);

  renderTrace(ok ? tr : null);
  renderGraph();
}

function online(up){
  $("online").setAttribute("data-tone", up ? "ok" : "bad");
  $("online-t").textContent = up ? "SYSTEM ONLINE" : "STATUS UNREACHABLE";
}
function poll(){
  fetch("/api/status", {cache: "no-store"})
    .then(function(r){ if (!r.ok) throw new Error("http " + r.status); return r.json(); })
    .then(function(s){ online(true); render(s); })
    .catch(function(){ online(false); render(null); });
}

function loadBenchmarks(){
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
poll(); loadBenchmarks(); setInterval(poll, 3000);
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
            self._json(status_adapter.read_status_snapshot(STATUS_PATH))
        elif path == "/api/benchmarks":
            self._json(load_benchmarks(BENCHMARK_PATH))
        elif path in ("/", "/index.html"):
            self._send(200, HTML_TEMPLATE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json({"error": "not found"}, 404)


def run_dashboard_server(port: int = DEFAULT_PORT, host: str = "127.0.0.1"):
    with http.server.ThreadingHTTPServer((host, port), DashboardHandler) as httpd:
        print(f"\n[DASHBOARD ONLINE] Serving SECONDShift Dashboard on http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[DASHBOARD STOPPED]")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_dashboard_server(port)