#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Colloquial text normalization for toxic-comment moderation (Objective 2).

Pipeline per comment:
  1) detect colloquial tokens using a colloquial lexicon + light rules
  2) replace them with their formal equivalents
  3) hand the normalized text to the downstream toxicity detector (moderation)

This script runs the detection + normalization and MEASURES real timing.
It produces the test-case table and the latency table for the paper.
"""
import re, time, json, statistics

# ---------------------------------------------------------------------------
#  Colloquial -> formal lexicon  (curated; conservative, context-safe entries)
# ---------------------------------------------------------------------------
LEXICON = {
    "gonna":"going to", "wanna":"want to", "gotta":"got to", "gimme":"give me",
    "lemme":"let me", "dunno":"do not know", "kinda":"kind of", "sorta":"sort of",
    "outta":"out of", "lotta":"lot of", "cuz":"because", "cos":"because",
    "coz":"because", "ain't":"is not", "aint":"is not", "y'all":"you all",
    "yall":"you all", "u":"you", "ur":"your", "r":"are", "pls":"please",
    "plz":"please", "thx":"thanks", "ty":"thank you", "idk":"I do not know",
    "idc":"I do not care", "imma":"I am going to", "ima":"I am going to",
    "tryna":"trying to", "nvm":"never mind", "tbh":"to be honest",
    "btw":"by the way", "asap":"as soon as possible", "b4":"before",
    "gr8":"great", "wat":"what", "wut":"what", "smth":"something",
    "cmon":"come on", "sucha":"such a", "dont":"do not", "cant":"cannot",
    "wont":"will not", "im":"I am", "ive":"I have", "youre":"you are",
    "thats":"that is", "whats":"what is", "wanna't":"want to",
}
# multi-word / apostrophe forms handled before token split
PHRASE_LEXICON = {
    "going to":"going to",  # placeholder to keep structure
}

TOKEN_RE = re.compile(r"[A-Za-z']+|[^A-Za-z']", re.UNICODE)

def detect_colloquial(text):
    """Return list of (token, formal) colloquial hits found in text (lowercased match)."""
    hits = []
    for m in re.finditer(r"[A-Za-z0-9']+", text):
        w = m.group(0)
        key = w.lower()
        if key in LEXICON:
            hits.append((w, LEXICON[key]))
    return hits

def normalize(text):
    """Replace colloquial tokens with formal equivalents, preserving non-word chars."""
    def repl(m):
        w = m.group(0); key = w.lower()
        if key in LEXICON:
            formal = LEXICON[key]
            # preserve capitalization of first letter
            if w[:1].isupper():
                formal = formal[:1].upper() + formal[1:]
            return formal
        return w
    return re.sub(r"[A-Za-z0-9']+", repl, text)

# ---------------------------------------------------------------------------
#  Test comments (realistic colloquial user comments; a mix of benign + toxic)
# ---------------------------------------------------------------------------
TEST = [
    "u r gonna regret this i swear",
    "lemme tell u smth, ur such an idiot",
    "tbh idk wut ur talkin about",
    "gimme that back or imma lose it",
    "cmon dont be sucha jerk",
    "thx for the help u r gr8",
    "yall gotta stop postin this cuz its dumb",
    "idc wat u think, u wont win",
]

def time_fn(fn, text, iters=20000):
    """Average wall-clock time per call in microseconds (stable over many iters)."""
    t0 = time.perf_counter()
    for _ in range(iters):
        fn(text)
    return (time.perf_counter()-t0)/iters*1e6   # microseconds

if __name__ == "__main__":
    rows, det_times, norm_times = [], [], []
    for s in TEST:
        hits = detect_colloquial(s)
        norm = normalize(s)
        dt = time_fn(detect_colloquial, s)
        nt = time_fn(normalize, s)
        det_times.append(dt); norm_times.append(nt)
        rows.append({
            "original": s,
            "colloquial_words": ", ".join(sorted({h[0].lower() for h in hits})),
            "n_colloquial": len(hits),
            "normalized": norm,
            "detect_us": round(dt,2),
            "normalize_us": round(nt,2),
            "total_us": round(dt+nt,2),
        })

    print("="*100)
    print("TEST-CASE TABLE (original -> colloquial words -> normalized)")
    print("="*100)
    for r in rows:
        print(f"\nOriginal : {r['original']}")
        print(f"Detected : {r['colloquial_words']}  ({r['n_colloquial']} words)")
        print(f"Formal   : {r['normalized']}")
        print(f"Time     : detect {r['detect_us']} us | normalize {r['normalize_us']} us | total {r['total_us']} us")

    print("\n"+"="*100)
    print("TIMING SUMMARY (per comment, microseconds)")
    print("="*100)
    def stats(x): return f"mean={statistics.mean(x):.2f}  min={min(x):.2f}  max={max(x):.2f}  stdev={statistics.pstdev(x):.2f}"
    print("Detection   :", stats(det_times))
    print("Normalization:", stats(norm_times))
    tot = [d+n for d,n in zip(det_times,norm_times)]
    print("Total       :", stats(tot))
    print(f"\nLexicon size: {len(LEXICON)} colloquial->formal mappings")
    print(f"Throughput  : ~{1e6/statistics.mean(tot):,.0f} comments/second (single thread)")

    json.dump({"rows":rows,
               "summary":{"detect_us":statistics.mean(det_times),
                          "normalize_us":statistics.mean(norm_times),
                          "total_us":statistics.mean(tot),
                          "lexicon_size":len(LEXICON)}},
              open("normalization_results.json","w"), indent=2)
    print("\nsaved normalization_results.json")
