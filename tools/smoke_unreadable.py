"""Exercise unreadable fields in Chromium on a temporary copy of a real OCR PDF."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui import webui
from app.application import PdfOcrReviewerApplication
from app.manifest import load_manifest
from app.review import file_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--expected", type=int)
    parser.add_argument("--screenshot", type=Path, default=Path("/tmp/pdf-reviewer-unreadable.png"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="reviewer-unreadable-") as work:
        folder = Path(work)
        pdf = folder / args.pdf.name
        shutil.copyfile(args.pdf, pdf)
        before = file_sha256(pdf)
        os.environ["PDF_OCR_REVIEWER_STATE_DIR"] = str(folder / "state")
        app = PdfOcrReviewerApplication(folder, pdf.name)
        api = app.api
        window = webui.Window()
        api.bind(window)
        window.set_root_folder(str(ROOT / "ui"))
        webui.set_timeout(60)
        url = window.start_server("index.html")
        assert url
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        driver = subprocess.Popen(["chromedriver", f"--port={port}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        session = None

        def request(method, route, data=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{route}", method=method,
                data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                value = json.load(response)["value"]
            if isinstance(value, dict) and "error" in value:
                raise AssertionError(value)
            return value

        def js(script):
            return request("POST", f"/session/{session}/execute/sync", {"script": script, "args": []})

        def wait_for(script):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if js(f"return Boolean({script})"):
                    return
                time.sleep(.05)
            raise AssertionError(f"Timed out: {script}; {js('return {toast:elements.toastId.textContent,selected:state.selectedIssueId,navigating:state.navigating,focus:document.activeElement?.id,count:state.document?.issues.length}')}")

        try:
            for _ in range(100):
                try:
                    request("GET", "/status")
                    break
                except OSError:
                    time.sleep(.05)
            created = request("POST", "/session", {"capabilities": {"alwaysMatch": {
                "browserName": "chrome", "goog:chromeOptions": {"binary": "/usr/bin/chromium", "args": [
                    "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1480,1000",
                    f"--user-data-dir={folder / 'browser'}"]}, "goog:loggingPrefs": {"browser": "ALL"}}}})
            session = created["sessionId"]
            request("POST", f"/session/{session}/url", {"url": url})
            wait_for("state.selectedIssueId && !state.navigating && document.activeElement === elements.replacementTextId")
            count = js("return state.document.issues.filter(isPlaceholder).length")
            assert count > 1
            if args.expected is not None:
                assert count == args.expected, count
            wait_for("state.pageData.has(selectedIssue().page_index)")
            assert js("return document.getElementById('replacementHintId').textContent") == "Zadejte chybějící část nebo celé výsledné slovo/údaj. Již přítomné okolí se ve výsledku nebude opakovat."
            args.screenshot.write_bytes(base64.b64decode(request("GET", f"/session/{session}/screenshot")))
            # Overlay hides imported markers and their controls, keeping the editor usable.
            assert js("return document.querySelectorAll('.issue-box').length > 0")
            js("elements.overlayId.checked=false;elements.overlayId.dispatchEvent(new Event('change'));refreshIssueViews()")
            assert js("return document.querySelectorAll('.issue-box').length === 0 && !elements.issueEditorId.hidden")
            assert js("return state.document.issues.length") == count
            js("elements.overlayId.checked=true;elements.overlayId.dispatchEvent(new Event('change'))")
            assert js("return document.querySelectorAll('.issue-box').length > 0")
            first = js("return state.selectedIssueId")
            js("elements.nextTranscriptionId.click()")
            wait_for(f"state.selectedIssueId !== {json.dumps(first)}")
            assert load_manifest(folder)["files"][pdf.name]["issues"][0]["replacement_text"] == ""
            second = js("return state.selectedIssueId")
            js("elements.replacementTextId.value='TEST – ruční znění';elements.replacementTextId.dispatchEvent(new Event('input'));elements.replacementTextId.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));")
            wait_for(f"state.selectedIssueId !== {json.dumps(second)} && !state.issueDrafts.size && !state.journalPending")
            saved = load_manifest(folder)["files"][pdf.name]["issues"]
            supplied = next(issue for issue in saved if issue["id"] == second)
            assert supplied["replacement_text"] == "TEST – ruční znění"
            assert supplied["status"] == "open" and supplied["note"] == ""
            js("elements.refreshFolderId.click()")
            wait_for("!state.navigating && state.selectedIssueId && !state.journalPending")
            assert js("return state.document.issues.length") == count
            assert js(f"return state.document.issues.find(i=>i.id==={json.dumps(second)}).replacement_text") == "TEST – ruční znění"
            # Revisit the field for an editable supplied value, also in a narrow viewport.
            js(f"selectIssue({json.dumps(second)})")
            wait_for("elements.replacementTextId.value === 'TEST – ruční znění' && state.pageData.has(selectedIssue().page_index)")
            request("POST", f"/session/{session}/window/rect", {"width": 1000, "height": 760})
            wait_for("window.innerWidth <= 1000")
            js(f"selectIssue({json.dumps(second)})")
            # Wait for smooth centering and progressive page rendering after resize.
            time.sleep(.5)
            wait_for("state.pageData.has(selectedIssue().page_index)")
            narrow = args.screenshot.with_name(args.screenshot.stem + "-narrow.png")
            narrow.write_bytes(base64.b64decode(request("GET", f"/session/{session}/screenshot")))
            assert js("const r=elements.replacementTextId.getBoundingClientRect();return r.width>200 && r.bottom<window.innerHeight")
            errors = request("POST", f"/session/{session}/log", {"type": "browser"})
            assert not [e for e in errors if e["level"] == "SEVERE"], errors
            assert file_sha256(pdf) == before
            print(f"PASS: {count} markers; overlay hide/show, automatic field, skip, Ctrl+Enter, reload, narrow layout; PDF unchanged. Screenshots: {args.screenshot}, {narrow}")
        finally:
            if session:
                request("DELETE", f"/session/{session}")
            driver.terminate()
            driver.wait(timeout=5)
            api.close()
            window.close()
            webui.clean()


if __name__ == "__main__":
    main()
