"""Verify versioned scripts remain available when the public directory is offline."""
import argparse
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18515")
    parser.add_argument("--browser")
    args = parser.parse_args()
    # This test registers a worker and must use an isolated local app instance.
    assert urlsplit(args.base_url).hostname in ("localhost", "127.0.0.1")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.browser, headless=True)
        ctx = browser.new_context(service_workers="allow")
        ctx.route(lambda url: urlsplit(url).netloc != urlsplit(args.base_url).netloc,
                  lambda route: route.abort())
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        assert page.goto(args.base_url + "/billing").ok
        page.wait_for_function("() => Boolean(navigator.serviceWorker.controller)", timeout=20000)
        worker = page.evaluate("navigator.serviceWorker.controller.scriptURL")
        assert "?v=" in worker
        assert "no-cache" in ctx.request.get(worker).headers["cache-control"]
        ctx.set_offline(True)
        assert page.goto(args.base_url + "/tools?category=documents").ok
        expect(page.get_by_role("searchbox")).to_be_visible()
        page.get_by_role("searchbox").fill("memo")
        expect(page.locator("#result-count")).to_have_text("1 tool")
        assert page.locator('script[src*="directory.js?v="]').count() == 1
        assert not errors, errors
        ctx.close()
        browser.close()
    print("PASS: versioned service worker, revalidation headers, offline directory scripts and filters.")


if __name__ == "__main__":
    main()
