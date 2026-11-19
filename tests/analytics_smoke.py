"""Check real UI analytics with Google scripts intercepted: no hits reach GA."""
import argparse
from hashlib import sha256
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

GA = "https://legalhashchecksum.com"
PRIVATE = "private-client@example.test"
FILE_BYTES = b"Analytics regression fixture."
DIGEST = sha256(FILE_BYTES).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--base-url", default="http://127.0.0.1:18515")
    cli.add_argument("--browser")
    args = cli.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.browser, headless=True)
        ctx = browser.new_context(service_workers="block")
        tags, errors = [], []
        feedback = {"ok":False}
        ctx.add_init_script("""
          window.print = () => {
            window.dispatchEvent(new Event('beforeprint'));
            window.dispatchEvent(new Event('afterprint'));
          };
        """)

        def route(request):
            parts = urlsplit(request.request.url)
            if parts.hostname == "www.googletagmanager.com":
                tags.append(request.request.url)
                request.fulfill(status=200, content_type="text/javascript", body="")
            elif parts.hostname == "legalhashchecksum.com":
                if parts.path == "/feedback":
                    request.fulfill(status=200 if feedback["ok"] else 503, json=feedback)
                elif parts.path == "/api/judgments/stats":
                    request.fulfill(status=200, json={"total":0,"by_area":[],"by_court":[],"last_updated":None})
                elif parts.path == "/api/judgments":
                    request.fulfill(status=200, json={"total":0,"pages":0,"judgments":[]})
                else:
                    response = request.fetch(url=args.base_url + parts.path +
                                             (("?" + parts.query) if parts.query else ""))
                    request.fulfill(response=response)
            elif parts.netloc == urlsplit(args.base_url).netloc:
                request.continue_()
            else:
                request.abort()
        ctx.route("**/*", route)
        page = ctx.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def entries():
            return page.evaluate("() => (window.dataLayer || []).map(e => Array.from(e))")

        def events(name):
            return [row[2] for row in entries() if row[:2] == ["event",name]]

        def go(path):
            response = page.goto(GA + path)
            assert response.ok
            expect(page.locator("script[src*='googletagmanager']")).to_have_count(1)
            configs = [row for row in entries() if row[0]=="config"]
            assert len(configs)==1
            assert configs[0][2]["page_title"]

        go("/hash?utm_source=pilot&utm_medium=email&q=" + PRIVATE)
        configs=[row for row in entries() if row[0]=="config"]
        assert configs[0][2]["page_location"] == GA+"/hash?utm_source=pilot&utm_medium=email"
        page.add_script_tag(url=GA+"/static/analytics.js")
        assert len([row for row in entries() if row[0]=="config"])==1
        assert len(tags)==1
        page.locator("#fi").set_input_files({
            "name":PRIVATE+".txt", "mimeType":"text/plain", "buffer":FILE_BYTES
        })
        assert events("file_selected")==[{"tool":"hash_checksum","file_count":1}]
        page.get_by_role("button", name="Generate Hash Values").click()
        expect(page.locator("#hrows")).to_contain_text(DIGEST, timeout=18000)
        assert len(events("hash_completed"))==1
        assert events("hash_completed")[0]["result"]=="complete"
        page.locator("#pc-A").click()
        page.locator("#a-nm").fill(PRIVATE)
        page.locator("#fp-A .bcert").click()
        assert len(events("certificate_prepared"))==1
        assert len(events("print_requested"))==1
        assert events("print_requested")[0]["part"]=="A"
        assert not events("generate_certificate") and not events("print_document")
        page.locator("#fp-A .bcert").click()
        assert len(events("print_requested"))==2
        assert PRIVATE not in str(entries()) and DIGEST not in str(entries())
        page.evaluate("""() => {
          const file = new File(['Drop fixture'], 'private-dropped-file.txt');
          const data = new DataTransfer();
          data.items.add(file);
          document.querySelector('#dz').dispatchEvent(new DragEvent('drop',
              {bubbles:true,cancelable:true,dataTransfer:data}));
        }""")
        assert len(events("file_selected"))==2
        page.locator("#fi").set_input_files([
            {"name":"first.txt","mimeType":"text/plain","buffer":FILE_BYTES},
            {"name":"second.txt","mimeType":"text/plain","buffer":b"Other fixture"},
        ])
        assert len(events("file_selected"))==3
        page.get_by_role("button", name="Generate Hash Values").click()
        expect(page.locator("#hbtn")).to_be_enabled(timeout=15000)
        assert len(events("hash_completed"))==2
        assert events("hash_completed")[-1]["file_count"]==2
        page.evaluate("() => { window.hashInWorker = () => Promise.reject(new Error('Simulated worker failure')); }")
        page.get_by_role("button", name="Generate Hash Values").click()
        expect(page.locator("#hbtn")).to_be_enabled(timeout=15000)
        assert len(events("hash_failed"))==1 and len(events("hash_completed"))==2

        go("/court-fee")
        button=page.get_by_role("button",name="Calculate Court Fee",exact=True)
        button.click()
        assert events("calculate")==[]
        page.locator("#amount").fill("543210")
        assert events("calculate")==[]
        button.click()
        assert events("calculate")==[{"tool":"court_fee_calculator"}]
        page.locator(".fb-btn").click()
        assert len(events("calculate"))==1
        assert "543210" not in str(entries())

        go("/limitation-calculator")
        button=page.get_by_role("button",name="Calculate Last Date to File")
        button.click()
        assert events("calculate")==[]
        page.locator("#suitType").select_option(index=1)
        page.locator("#coaDate").fill("2026-01-01")
        button.click()
        assert events("calculate")==[{"tool":"limitation_calculator"}]

        go("/law-converter")
        page.locator(".law-tab").nth(1).click()
        assert events("select_law")==[{"tool":"law_converter","law":"ipc"}]
        go("/legal-dictionary")
        page.get_by_role("button",name="Criminal Law",exact=True).click()
        assert events("filter_category")==[{"tool":"legal_dictionary","category":"criminal"}]

        go("/tools?q="+PRIVATE)
        assert PRIVATE not in page.url
        page.get_by_role("searchbox").fill("memo")
        expect(page.locator("#result-count")).to_have_text("1 tool")
        # A condition on the app event queue, not an arbitrary sleep.
        page.wait_for_function("""() => new Promise(resolve => {
          const timer=setInterval(() => {
            if((window.dataLayer||[]).some(e=>e[0]==='event' && e[1]==='tool_search')){
              clearInterval(timer);resolve(true);
            }
          },20);
        })""")
        assert events("tool_search")==[{"tool":"tools","has_query":True}]
        assert PRIVATE not in str(entries())
        page.get_by_role("button",name="Send feedback").click()
        form=page.locator("#feedback-form")
        form.locator("textarea").fill("Private feedback body")
        form.locator("input[type=email]").fill(PRIVATE)
        form.locator("button[type=submit]").click()
        expect(page.locator("#feedback-status")).to_contain_text("Could not send")
        assert events("feedback_sent")==[]
        feedback["ok"]=True
        form.locator("button[type=submit]").click()
        expect(page.locator("#feedback-status")).to_contain_text("Your feedback was sent")
        assert events("feedback_sent")==[{"tool":"tools","has_email":True}]
        assert "Private feedback body" not in str(entries()) and PRIVATE not in str(entries())
        page.locator("#feedback-close").click()
        page.locator(".directory-card:not([hidden])").evaluate(
            "card => card.addEventListener('click',event=>event.preventDefault(),{once:true})")
        page.locator(".directory-card:not([hidden])").click()
        assert events("tool_open")==[{"tool":"tools","destination":"memo_appearance"}]
        go("/memo-appearance")
        # Browser print events also support the keyboard/menu print route.
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        assert len(events("print_requested"))==1
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")

        go("/verify")
        page.locator("#fileInput").set_input_files({
            "name":"verify-private.txt","mimeType":"text/plain","buffer":FILE_BYTES
        })
        expect(page.locator("#computedBox")).to_be_visible()
        assert events("file_loaded")==[{"tool":"verify"}]
        page.locator("#expectedHash").fill("abc")
        assert events("hash_verified")==[]
        page.locator("#expectedHash").fill(DIGEST)
        assert events("hash_verified")==[{"tool":"verify","result":"match"}]
        page.evaluate("verifyHash()")
        assert len(events("hash_verified"))==1

        go("/judgments?q="+PRIVATE)
        page.locator("#searchInput").fill(PRIVATE)
        page.evaluate("""() => gaEvent('j_filter', {
            q:'private query',email:'private@example.test',has_query:true,area:'civil'
        })""")
        assert PRIVATE not in str(entries()) and "private query" not in str(entries())
        assert events("j_filter")[-1]["has_query"]
        assert not page.evaluate("gaEvent('purchase',{value:499})")
        assert errors==[], errors

        before=len(tags)
        page.goto(args.base_url+"/hash")
        assert not page.evaluate("LHCAnalytics.enabled")
        assert page.evaluate("(window.dataLayer||[]).length")==0
        assert not page.evaluate("gaEvent('calculate')")
        assert len(tags)==before
        # Blocking the optional first-party analytics script must not break the calculator.
        blocked=browser.new_context(service_workers="block")
        blocked.route("**/*",lambda r:r.abort() if urlsplit(r.request.url).path=="/static/analytics.js" else route(r))
        no_tracking=blocked.new_page()
        blocked_errors=[]
        no_tracking.on("pageerror",lambda error:blocked_errors.append(str(error)))
        no_tracking.goto(GA+"/court-fee")
        no_tracking.locator("#amount").fill("100000")
        no_tracking.get_by_role("button",name="Calculate Court Fee",exact=True).click()
        expect(no_tracking.locator("#resultBox")).to_have_class("result-box show")
        assert not blocked_errors,blocked_errors
        blocked.close()
        ctx.close()
        browser.close()
    print("PASS: production-only single bootstrap; chosen/dropped files; hash success/failure; "
          "print request deduplication; valid calculations once; private query suppression; "
          "verification deduplication; filter identifiers; feedback success/failure; "
          "blocked analytics resilience; local previews excluded. No GA hits were sent.")


if __name__ == "__main__":
    main()
