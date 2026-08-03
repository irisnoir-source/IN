#!/usr/bin/env python3
"""Canonical structural check for the IrisNoir static site. Run: python verify.py"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parent
VOID = {"meta", "link", "img", "br", "hr", "input", "source"}


def main() -> int:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    fails: list[str] = []

    class Balance(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if not self.stack or self.stack.pop() != tag:
                fails.append(f"tag mismatch near </{tag}>")

    p = Balance()
    p.feed(html)
    if p.stack:
        fails.append(f"unclosed tags: {p.stack}")

    ids = set(re.findall(r'id="([^"]+)"', html))
    used = {c for cl in re.findall(r'class="([^"]+)"', html) for c in cl.split()}
    fails += [f"broken anchor #{h}" for h in re.findall(r'href="#([^"]+)"', html) if h not in ids]
    # strip <script> blocks so dynamic JS string literals aren't scanned as static assets
    scanless = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)

    def check_local(ref: str, where: str) -> None:
        """Validate a local href/src, including cross-page 'page.html#anchor' forms."""
        path, _, frag = ref.partition("#")
        target = ROOT / path
        if not target.exists():
            fails.append(f"missing asset {path} (in {where})")
            return
        if frag and path.endswith(".html"):
            frag_ids = set(re.findall(r'id="([^"]+)"', target.read_text(encoding="utf-8")))
            if frag not in frag_ids:
                fails.append(f"broken cross-page anchor {ref} (in {where})")

    for ref in re.findall(r'(?:src|href)="((?!https?:|mailto:|#)[^"]+)"', scanless):
        check_local(ref, "index.html")

    # Sibling pages get the same treatment — they share the CSS and link back.
    for page in sorted(ROOT.glob("*.html")):
        if page.name == "index.html":
            continue
        ptext = page.read_text(encoding="utf-8")
        pids = set(re.findall(r'id="([^"]+)"', ptext))
        fails += [f"broken anchor #{h} (in {page.name})"
                  for h in re.findall(r'href="#([^"]+)"', ptext) if h not in pids]
        pscanless = re.sub(r"<script\b[^>]*>.*?</script>", "", ptext, flags=re.DOTALL | re.IGNORECASE)
        for ref in re.findall(r'(?:src|href)="((?!https?:|mailto:|#)[^"]+)"', pscanless):
            check_local(ref, page.name)
        # Class coverage is checked against the stylesheets THIS page links
        # PLUS any inline <style> blocks — ugc-portfolio.html styles itself inline.
        sheets = re.findall(r'<link[^>]+href="([^"]+\.css)"', ptext)
        pcss = "".join((ROOT / s).read_text(encoding="utf-8")
                       for s in sheets if (ROOT / s).exists())
        pcss += "".join(re.findall(r"<style[^>]*>(.*?)</style>", ptext, re.DOTALL | re.IGNORECASE))
        pdefined = set(re.findall(r"\.([a-z][a-z0-9-]*)", pcss))
        pused = {c for cl in re.findall(r'class="([^"]+)"', ptext) for c in cl.split()}
        if pused - pdefined:
            fails.append(f"classes with no CSS rule in {page.name}: {pused - pdefined}")

    if css.count("{") != css.count("}"):
        fails.append("CSS brace mismatch")
    defined = set(re.findall(r"\.([a-z][a-z0-9-]*)", css))
    if used - defined:
        fails.append(f"classes with no CSS rule: {used - defined}")
    declared = set(re.findall(r"--([a-z0-9-]+)\s*:", css))
    fails += [f"undeclared CSS var --{v}" for v in set(re.findall(r"var\(--([a-z0-9-]+)", css))
              if v not in declared]

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print(f"PASS: html balanced, {len(ids)} ids, anchors ok, assets ok, css balanced, {len(used)} classes styled, vars ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
