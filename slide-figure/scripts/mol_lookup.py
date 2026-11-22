# -*- coding: utf-8 -*-
"""Look up a compound's SMILES on PubChem by name (stdlib only).

    python mol_lookup.py ITIC
    python mol_lookup.py "PC61BM" --property CanonicalSMILES

Why: hand-typing a dye SMILES from memory is how wrong structures get into a
figure. Prefer the database; if the network is down the script fails loudly
instead of inventing something -- fall back to a courseware image, not to a
guess.

Failure here usually means no proxy: this machine reaches domestic mirrors but
not pubchem.ncbi.nlm.nih.gov / pypi.org directly.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/%s/property/%s/JSON"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--property", default="IsomericSMILES")
    ap.add_argument("--timeout", type=float, default=15)
    a = ap.parse_args()

    url = BASE % (urllib.parse.quote(a.name), a.property)
    try:
        with urllib.request.urlopen(url, timeout=a.timeout) as r:
            data = json.load(r)
    except Exception as e:  # URLError, timeout, HTTPError, JSONDecodeError
        sys.exit(
            "PubChem lookup failed for %r: %s\n"
            "-> network blocked or compound name not indexed.\n"
            "-> do NOT hand-type the structure; use a courseware/figure source, "
            "or ask the user to enable the proxy." % (a.name, e))

    props = data.get("PropertyTable", {}).get("Properties", [])
    if not props:
        sys.exit("No record for %r (try the full IUPAC name or a CID)." % a.name)
    for k, v in props[0].items():
        if k != "CID":
            print(v)


if __name__ == "__main__":
    main()
