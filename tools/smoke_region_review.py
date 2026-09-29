"""Optional end-to-end smoke test using installed Chromium + ChromeDriver.

Run with the project venv: python tools/smoke_region_review.py [--pdf input.pdf]
Only temporary copies are annotated. No extra Python test dependencies required.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pymupdf
from app.manifest import manifest_revision
from webui import webui

from app.api import BackendApi
from app.manifest import MANIFEST_FILENAME, load_manifest, save_manifest
from app.review import file_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--screenshot", type=Path, default=Path("/tmp/pdf-ocr-reviewer-smoke.png"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ocr-region-smoke-") as work:
        folder = Path(work)
        pdf = folder / "sample-ocr.pdf"
        if args.pdf:
            shutil.copyfile(args.pdf, pdf)
        else:
            with pymupdf.open() as doc:
                page = doc.new_page(width=600, height=850)
                for index in range(30):
                    page.insert_text((50, 80 + index * 20), f"OCR review sample line {index + 1}", fontsize=12)
                doc.save(pdf)
        os.environ["PDF_OCR_REVIEWER_STATE_DIR"] = str(folder / "local-state")
        api = BackendApi(folder)
        window = webui.Window()
        api.bind(window)
        window.set_root_folder(str(ROOT / "ui"))
        webui.set_timeout(60)
        url = window.start_server("index.html")
        assert url, "WebUI server did not start"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        driver = subprocess.Popen(["chromedriver", f"--port={port}", "--allowed-ips=127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        session = None

        def request(method, route, data=None):
            body = json.dumps(data).encode() if data is not None else None
            req = urllib.request.Request(f"http://127.0.0.1:{port}{route}", data=body, method=method, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                value = json.load(response)["value"]
            if isinstance(value, dict) and "error" in value:
                raise AssertionError(value)
            return value

        def command(route, data=None):
            return request("POST", f"/session/{session}{route}", data or {})

        def js(script):
            return command("/execute/sync", {"script": script, "args": []})

        def wait_for(script, seconds=15):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if js(f"return Boolean({script});"):
                    return
                time.sleep(0.05)
            raise AssertionError(f"Timed out: {script}; state: {js('return {count:state.document?.issues.length,selected:state.selectedIssueId,marking:state.marking,journal:state.journalPending,drafts:[...state.draftRecords.values()],toast:elements.toastId.textContent};')}")

        def click(selector):
            element = command("/element", {"using": "css selector", "value": selector})
            command(f"/element/{element['element-6066-11e4-a52e-4f735466cecf']}/click")

        def pointer(x, y, end=None):
            actions = [{"type": "pointerMove", "duration": 0, "x": round(x), "y": round(y)}, {"type": "pointerDown", "button": 0}]
            if end:
                actions.append({"type": "pointerMove", "duration": 120, "x": round(end[0]), "y": round(end[1])})
            actions.append({"type": "pointerUp", "button": 0})
            command("/actions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": actions}]})

        try:
            for _ in range(100):
                try:
                    request("GET", "/status")
                    break
                except OSError:
                    time.sleep(0.05)
            created = request("POST", "/session", {"capabilities": {"alwaysMatch": {
                "browserName": "chrome", "goog:chromeOptions": {"args": ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1480,1000", f"--user-data-dir={folder / 'browser'}"]},
                "goog:loggingPrefs": {"browser": "ALL"},
            }}})
            session = created["sessionId"]
            command("/url", {"url": url})
            wait_for("typeof state !== 'undefined' && state.files.length === 1")
            click(".file-item")
            wait_for("state.pageData.has(0)")
            click("#markIssueId")
            js("elements.issueKindId.value='oversized';elements.issueKindId.dispatchEvent(new Event('change')); ")
            assert js("return elements.issueKindId.selectedOptions[0].textContent;") == "Špatná velikost boxu"
            point = js("const o=state.pageData.get(0).header.ocr; const w=o.layout_items[0]; const p=document.querySelector('.scan-pane').getBoundingClientRect(); return [p.left+(w.x0+w.x1)/2/o.page_width*p.width,p.top+(w.y0+w.y1)/2/o.page_height*p.height];")
            pointer(*point)
            wait_for("state.document?.issues.length === 1")
            assert js("return state.document.issues[0].kind;") == "oversized"
            first_id = js("return state.selectedIssueId;")
            js("elements.issueNoteId.value='Text je správně; zmenšit box.'; elements.issueNoteId.dispatchEvent(new Event('input',{bubbles:true}));")
            wait_for("state.issueDrafts.size === 0 && state.document.issues[0].note.includes('zmenšit')")
            # Drag a blank region: this also supports missing OCR with no selectable word.
            rect = js("const r=document.querySelector('.scan-pane').getBoundingClientRect();return [r.left+15,r.top+20,r.left+85,r.top+45];")
            pointer(rect[0], rect[1], rect[2:])
            wait_for("state.document?.issues.length === 2")
            second_id = js("return state.selectedIssueId;")
            assert load_manifest(folder)["files"][pdf.name]["issues"][1]["targets"] == []
            # Changing render settings must not accumulate pointer handlers.
            js("elements.overlayId.click();elements.overlayId.click();")
            time.sleep(0.3)
            js("elements.zoomId.value='120';elements.zoomId.dispatchEvent(new Event('change')); ")
            wait_for("state.pageData.has(0)")
            rect = js("const r=document.querySelector('.scan-pane').getBoundingClientRect();return [r.left+160,r.top+15,r.left+220,r.top+30];")
            pointer(rect[0], rect[1], rect[2:])
            wait_for("state.document?.issues.length === 3")
            third_id = js("return state.selectedIssueId;")
            # The on-box cross also works on an unselected issue without changing selection.
            js(f"selectIssue({json.dumps(second_id)}, false);")
            wait_for("state.selectedIssueId === " + json.dumps(second_id))
            click(f'.scan-pane .issue-box[data-issue-id="{third_id}"] .issue-box-dismiss')
            wait_for("state.document?.issue_counts.dismissed === 1")
            assert js("return state.selectedIssueId;") == second_id
            js("state.issueFilter='archived';elements.issueFilterId.value='archived';renderIssueSidebar();")
            click(".issue-list-item")
            click("#reopenIssueId")
            wait_for("state.document?.issue_counts.dismissed === 0")
            # It also works in reading mode without entering marking mode or the editor.
            js("setMarking(false);")
            click(f'.scan-pane .issue-box[data-issue-id="{third_id}"] .issue-box-dismiss')
            wait_for("state.document?.issue_counts.dismissed === 1")
            assert js("return state.document.issues.length;") == 3
            js("state.issueFilter='active';elements.issueFilterId.value='active';renderIssueSidebar();elements.zoomId.value='100';elements.zoomId.dispatchEvent(new Event('change')); ")
            wait_for("state.pageData.has(0)")
            js("setMarking(false);")
            before = file_sha256(pdf)
            manifest = load_manifest(folder)
            for issue in manifest["files"][pdf.name]["issues"]:
                if issue["status"] == "dismissed":
                    continue
                issue["status"] = "fixed"
                issue["result"] = {"summary": "Test: geometrie opravena", "before_sha256": before, "after_sha256": before, "at": "2026-09-25T20:00:00+02:00"}
                issue["history"].append({"at": issue["result"]["at"], "action": "fixed", "from": "open", "to": "fixed"})
            save_manifest(folder, manifest, expected_revision=manifest_revision(folder))
            external_bytes = (folder / MANIFEST_FILENAME).read_bytes()
            js("scheduleSaveCurrentPage();")
            time.sleep(0.65)
            assert (folder / MANIFEST_FILENAME).read_bytes() == external_bytes, "UI overwrote external repair"
            click("#refreshFolderId")
            wait_for("state.document?.issue_counts.fixed === 2 && state.pageData.has(0)")
            assert js("return state.issueKind;") == "oversized"
            # Satisfied: delete the blue mark directly on its box. The other blue
            # mark remains eligible without a confirm/reopen action.
            click(f'.scan-pane .issue-box[data-issue-id="{second_id}"] .issue-box-dismiss')
            wait_for("state.document?.issue_counts.fixed === 1 && state.document.issue_counts.dismissed === 2")
            assert js("return Boolean(document.querySelector('.scan-pane .issue-fixed'));")
            assert not js("return Boolean(document.querySelector('#verifyIssueId, #reviewRepairsId'));")
            js("document.activeElement.blur();")
            command("/actions", {"actions": [{"type": "key", "id": "keyboard", "actions": [{"type": "keyDown", "value": "j"}, {"type": "keyUp", "value": "j"}]}]})
            wait_for("state.selectedIssueId === " + json.dumps(first_id))
            command("/actions", {"actions": [{"type": "key", "id": "keyboard", "actions": [{"type": "keyDown", "value": "n"}, {"type": "keyUp", "value": "n"}]}]})
            assert js("return document.activeElement.id;") == "issueNoteId"
            # All typed data survives refresh and version-3 instructions are first.
            click("#refreshFolderId")
            wait_for("state.pageData.has(0) && state.document.issue_counts.fixed === 1")
            assert next(iter(json.loads((folder / MANIFEST_FILENAME).read_text()))) == "repair_instructions"
            assert js("return state.document.issues.find(i => i.id === " + json.dumps(first_id) + ").note;") == "Text je správně; zmenšit box."
            wait_for("!state.navigating && state.journalPending === 0")
            # Durable draft survives a browser restart and a conflicting external note.
            external = load_manifest(folder)
            external["files"][pdf.name]["issues"][0]["note"] = "External note retained until explicit recovery"
            save_manifest(folder, external, expected_revision=manifest_revision(folder))
            js(f"selectIssue({json.dumps(first_id)}, false);")
            wait_for("state.selectedIssueId === " + json.dumps(first_id))
            js("elements.issueNoteId.value='Recovered after restart';elements.issueNoteId.dispatchEvent(new Event('input')); ")
            wait_for("state.journalPending === 0 && [...state.draftRecords.values()].some(d => d.note === 'Recovered after restart' && d.durable)")
            time.sleep(0.6)
            command("/refresh")
            wait_for("state.document?.issues.length === 3 && !elements.draftRecoveryId.hidden")
            click("#refreshFolderId")
            wait_for("!state.navigating && state.document?.issues[0].note.startsWith('External note')")
            js("elements.draftRecoveryId.open=true;")
            assert "External note" in js("return elements.draftRecoveryListId.textContent;")
            assert api.drafts.list(folder)[0]["note"] == "Recovered after restart"
            click(".recovery-row button")
            wait_for("state.document?.issues[0].note === 'Recovered after restart' && state.journalPending === 0")
            assert api.drafts.list(folder) == []
            click("#backupsId")
            wait_for("elements.backupDialogId.open && elements.backupSelectId.options.length > 0")
            click("#closeBackupsId")
            # A later external pass includes the retained blue mark, but never
            # the deleted marks. The app itself only loads the external result.
            wait_for("!state.navigating && state.journalPending === 0")
            second = folder / "second-ocr.pdf"
            shutil.copyfile(pdf, second)
            builder = BackendApi(folder)
            opened = builder.open_document(second.name)
            box = load_manifest(folder)["files"][pdf.name]["issues"][0]["bbox"]
            response = builder.add_issue(second.name, {"page_index": 0, "bbox": box, "kind": "position", "expected_sha256": opened["ocr_sha256"]})
            second_issue = response["issue_id"]
            builder.close()
            batch = load_manifest(folder)
            eligible = batch["repair_instructions"]["workflow"]["eligible_statuses"]
            chosen = [(name, issue) for name, entry in batch["files"].items()
                      for issue in entry["issues"] if issue["status"] in eligible]
            assert {issue["id"] for _, issue in chosen} == {first_id, second_issue}
            for name, issue in chosen:
                sha = file_sha256(folder / name)
                previous = issue.get("result")
                issue["history"].append({"action": "fixed", "from": issue["status"], "to": "fixed",
                                         "previous_result": previous, "summary": "Simulated external pass 2"})
                issue["status"] = "fixed"
                issue["result"] = {"summary": "Simulated external pass 2", "before_sha256": sha, "after_sha256": sha, "at": "2026-09-29T12:00:00+02:00"}
            save_manifest(folder, batch, expected_revision=manifest_revision(folder))
            click("#refreshFolderId")
            wait_for("!state.navigating && state.files.length === 2 && state.document?.issue_counts.fixed === 1 && state.pageData.has(0)")
            assert js("return state.document.issues[0].history.at(-1).from;") == "fixed"
            assert js("return state.document.issues[0].history.at(-1).previous_result.summary;") == "Test: geometrie opravena"
            js("elements.fileIssueFilterId.value='active';elements.fileIssueFilterId.dispatchEvent(new Event('change')); ")
            assert js("return document.querySelectorAll('.file-item').length;") == 2
            click(f'.scan-pane .issue-box[data-issue-id="{first_id}"] .issue-box-dismiss')
            wait_for("state.document.issue_counts.fixed === 0 && !state.issueBusy")
            assert js("return document.querySelectorAll('.file-item').length;") == 1
            assert js("return document.querySelector('.file-item').dataset.fileId;") == second.name
            click(".file-item")
            wait_for("state.activeFileId === 'second-ocr.pdf' && state.pageData.has(0) && !state.navigating")
            click("#refreshFolderId")
            wait_for("state.activeFileId === 'second-ocr.pdf' && state.pageData.has(0) && !state.navigating")
            assert js("return state.document.issues[0].status;") == "fixed"
            assert file_sha256(pdf) == before, "Reviewer changed PDF bytes"
            shot = request("GET", f"/session/{session}/screenshot")
            args.screenshot.write_bytes(base64.b64decode(shot))
            errors = command("/log", {"type": "browser"})
            severe = [e for e in errors if e["level"] == "SEVERE"]
            assert not severe, severe
            print(f"PASS: real WebUI transport, click/drag, autosave, external edit protection, reload, delete/restore, retained blue marks across external passes, durable draft recovery, backup selection and multi-PDF filters. Screenshot: {args.screenshot}", flush=True)
        finally:
            if session:
                request("DELETE", f"/session/{session}")
            driver.terminate()
            driver.wait(timeout=10)
            window.destroy()
            api.close()


if __name__ == "__main__":
    main()
