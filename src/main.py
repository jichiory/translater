#!/usr/bin/env python3
import os
import json
import shutil
import collections
import argostranslate.package
import argostranslate.translate

# ---------- Utils ----------
def log(msg):
    print(f"[TRANSLATOR] {msg}", flush=True)

def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        log(f"Could not create directory {path}: {e}")

# ---------- Config from env ----------
SRC = os.environ.get("SOURCE_LANG", "fr")
DST = os.environ.get("TARGET_LANG", "en")
INPUT_DIR = os.environ.get("INPUT_DIR", "/app/input")
TMP_OUTPUT = os.environ.get("TMP_OUTPUT", "/tmp/output")
FINAL_OUTPUT = os.environ.get("OUTPUT_DIR", "/app/output")
# Optional: prioritized pivot list, comma separated (e.g. "en,fr,de")
PIVOT_ORDER_ENV = os.environ.get("PIVOT_ORDER", "")
PIVOT_PREFERRED = [p.strip() for p in PIVOT_ORDER_ENV.split(",") if p.strip()]

# ---------- Prepare folders ----------
safe_makedirs(TMP_OUTPUT)
safe_makedirs(FINAL_OUTPUT)

log("---- START ----")
log(f"Requested: {SRC} -> {DST}")
if PIVOT_PREFERRED:
    log(f"Preferred pivot order: {PIVOT_PREFERRED}")

# ---------- Load available packages (remote index) ----------
log("Updating package index...")
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
log(f"Available packages count: {len(available)}")

# ---------- Build directed graph of available translations ----------
# nodes are language codes; edges exist if a package from->to available
graph = {}
for p in available:
    graph.setdefault(p.from_code, set()).add(p.to_code)

def neighbors(lang):
    return graph.get(lang, set())

# ---------- Helper: find path using BFS, but favor preferred pivots ----------
def find_path(src, dst, preferred_pivots=None):
    """
    Find shortest path from src to dst using available directed edges.
    If preferred_pivots is provided, tries paths that include those pivots earlier.
    Returns list of nodes [src, ..., dst] or None.
    """
    if src == dst:
        return [src]
    # BFS with optional ordering of neighbors to prefer pivots
    q = collections.deque([[src]])
    seen = {src}
    while q:
        path = q.popleft()
        node = path[-1]
        nbrs = list(neighbors(node))
        # If preferred pivots available, order neighbors so they are enqueued earlier
        if preferred_pivots:
            def score(n):
                try:
                    # lower score = higher priority (appear earlier)
                    return preferred_pivots.index(n)
                except ValueError:
                    return len(preferred_pivots) + 1
            nbrs.sort(key=score)
        for n in nbrs:
            if n in seen:
                continue
            new_path = path + [n]
            if n == dst:
                return new_path
            seen.add(n)
            q.append(new_path)
    return None

# If user provided a pivot order, convert it into preference list for BFS:
preferred = PIVOT_PREFERRED if PIVOT_PREFERRED else None

# ---------- Determine translation route ----------
path = find_path(SRC, DST, preferred)
if path:
    log(f"Direct path found: {' -> '.join(path)}")
else:
    # try one-step pivot attempts using preferred pivots explicitly
    if preferred:
        log("No direct path; trying explicit pivot candidates from PIVOT_ORDER...")
        for pivot in preferred:
            p = find_path(SRC, DST, [pivot])
            if p:
                path = p
                log(f"Path via preferred pivot found: {' -> '.join(path)}")
                break
    # last attempt: try automatic via common pivots (e.g., en)
    if not path:
        COMMON_PIVOTS = ["en", "fr", "de", "es"]
        log("No path found yet; trying automatic common pivots...")
        for pivot in COMMON_PIVOTS:
            if pivot == SRC or pivot == DST: 
                continue
            # try SRC -> pivot and pivot -> DST
            if (pivot in neighbors(SRC)) and (DST in neighbors(pivot)):
                path = [SRC, pivot, DST]
                log(f"Found path via common pivot '{pivot}': {' -> '.join(path)}")
                break

if not path:
    log("❌ No translation path found. Listing available edges for debugging:")
    log(f"Available from {SRC}: {sorted(neighbors(SRC))}")
    log(f"Available to   {DST}: {[p.from_code for p in available if p.to_code==DST]}")
    raise SystemExit(1)

# ---------- Ensure required models installed (install missing ones on the path edges) ----------
# Build list of needed pairs
needed_pairs = list(zip(path[:-1], path[1:]))
log(f"Needed pairs to install: {needed_pairs}")

# Determine already installed languages (codes)
installed_langs = argostranslate.translate.load_installed_languages()
installed_pairs = set()
for src_lang in installed_langs:
    for to_lang in installed_langs:
        if src_lang.code != to_lang.code:
            # try to get translation object; if it exists, assume pair available
            try:
                trans = src_lang.get_translation(to_lang)
                if trans:
                    installed_pairs.add((src_lang.code, to_lang.code))
            except Exception:
                pass

def install_pair(src, dst):
    if (src, dst) in installed_pairs:
        log(f"Pair {src} -> {dst} already installed")
        return True
    pkg = next((p for p in available if p.from_code == src and p.to_code == dst), None)
    if not pkg:
        log(f"Package not available for {src}->{dst}")
        return False
    log(f"Downloading package {src} -> {dst} ...")
    path_pkg = pkg.download()
    log(f"Installing {path_pkg} ...")
    argostranslate.package.install_from_path(path_pkg)
    # refresh installed_langs
    try:
        new_installed = argostranslate.translate.load_installed_languages()
        # update installed_pairs accordingly (quick update)
        for src_lang in new_installed:
            for to_lang in new_installed:
                if src_lang.code != to_lang.code:
                    try:
                        if src_lang.get_translation(to_lang):
                            installed_pairs.add((src_lang.code, to_lang.code))
                    except Exception:
                        pass
    except Exception:
        pass
    return (src, dst) in installed_pairs

all_installed = True
for s, d in needed_pairs:
    ok = install_pair(s, d)
    if not ok:
        log(f"❌ Failed to install model for {s}->{d}")
        all_installed = False

if not all_installed:
    raise SystemExit(1)

# ---------- Translation function (chain if needed) ----------
def translate_text(text, route):
    # route is list of language codes e.g. ['fr','en','es']
    current = text
    for i in range(len(route)-1):
        a = route[i]
        b = route[i+1]
        current = argostranslate.translate.translate(current, a, b)
    return current

# ---------- Process files: write into TMP_OUTPUT first ----------
log(f"Reading input dir: {INPUT_DIR}")
files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".arb")]
log(f"Found files: {files}")

for fname in files:
    in_path = os.path.join(INPUT_DIR, fname)
    out_tmp = os.path.join(TMP_OUTPUT, fname)
    out_final = os.path.join(FINAL_OUTPUT, fname)

    log(f"Processing '{fname}'")
    with open(in_path, "r", encoding="utf-8") as rf:
        data = json.load(rf)

    result = {}
    for k, v in data.items():
        if k == "@@locale":
            result[k] = DST
        elif isinstance(v, str):
            try:
                translated = translate_text(v, path)
            except Exception as e:
                log(f"Translation error for key {k}: {e}")
                translated = v
            result[k] = translated
            log(f"  {k}: {v} -> {translated}")
        else:
            result[k] = v

    # write in tmp output
    with open(out_tmp, "w", encoding="utf-8") as wf:
        json.dump(result, wf, ensure_ascii=False, indent=2)
    log(f"Wrote tmp output: {out_tmp}")

# ---------- Copy from TMP_OUTPUT to FINAL_OUTPUT (volume) ----------
log("Syncing tmp -> final output (overwriting)...")
for f in os.listdir(TMP_OUTPUT):
    srcp = os.path.join(TMP_OUTPUT, f)
    dstp = os.path.join(FINAL_OUTPUT, f)
    try:
        shutil.copy2(srcp, dstp)
        log(f"Copied {srcp} -> {dstp}")
    except Exception as e:
        log(f"Failed to copy {srcp} -> {dstp}: {e}")

log("---- DONE ----")
