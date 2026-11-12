"""Export real Chromium PDFs from the live forms and check their selectable text.

Requires playwright and pypdf. Install Playwright Chromium, or pass --browser
with the path to a local Chrome executable.
"""
import argparse
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--base-url", default="http://127.0.0.1:18514")
    args.add_argument("--output-dir", required=True, type=Path)
    args.add_argument("--browser")
    args.add_argument("--baseline", action="store_true", help="List PDF defects without stopping")
    cfg = args.parse_args()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = b"Legal Hash Checksum sample evidence for PDF verification.\n"
    digest = sha256(fixtures).hexdigest()
    problems = []
    tested = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=cfg.browser, headless=True
        )
        ctx = browser.new_context(color_scheme="dark", service_workers="block")
        ctx.route(lambda url: urlsplit(url).netloc != urlsplit(cfg.base_url).netloc,
                  lambda route: route.abort())
        ctx.add_init_script("window.printCalls = 0; window.print = () => document.documentElement.dataset.testPrint = String(++window.printCalls);")
        page = ctx.new_page()
        page.set_default_timeout(8000)

        def go(path):
            response = page.goto(cfg.base_url.rstrip("/") + path)
            assert response.ok, (path, response.status)

        def pdf(name, button, required, forbidden=(), page_count=None, min_pages=1):
            nonlocal tested
            before = page.evaluate("window.printCalls")
            page.locator(button).click()
            # Read a numeric marker without changing the page's print CSS.
            expect(page.locator("html")).to_have_attribute("data-test-print", str(before + 1))
            target = cfg.output_dir / f"{name}.pdf"
            page.pdf(path=target, format="A4", prefer_css_page_size=True, print_background=False)
            reader = PdfReader(target)
            texts = [" ".join((p.extract_text() or "").split()) for p in reader.pages]
            joined = " ".join(texts)
            missing = [t for t in required if t.casefold() not in joined.casefold()]
            leaked = [t for t in forbidden if t.casefold() in joined.casefold()]
            blank = [i for i, content in enumerate(texts, 1) if not content]
            shape = [tuple(round(float(v)) for v in (p.mediabox.width, p.mediabox.height))
                     for p in reader.pages]
            print(f"{name}: {len(texts)} pages; sizes {shape}; words {[len(t.split()) for t in texts]}; "
                  f"missing {missing}; unexpected {leaked}; empty pages {blank}")
            if missing or leaked or blank or len(texts) < min_pages or (page_count is not None and len(texts) != page_count):
                problems.append(name)
            tested += 1

        go("/hash")
        page.locator("#fi").set_input_files({"name": "pdf-test-evidence.txt",
                                            "mimeType": "text/plain", "buffer": fixtures})
        page.get_by_role("button", name="Generate Hash Values").click()
        expect(page.locator("#hrows")).to_contain_text(digest, timeout=15000)
        for part in ("A", "B"):
            page.locator(f"#pc-{part}").click()
            key = part.lower()
            page.locator(f"#{key}-nm").fill(f"PDF TEST {part} EXAMPLE")
            page.locator(f"#{key}-dt").fill("2024-08-16")
            page.locator(f"#{key}-tm").fill("13:47")
            page.locator(f"#{key}-pl").fill("SAMPLE & TOWN")
            page.locator(f"#{key}-oth-c").check()
            page.locator(f"#{key}-oth-t").fill("Example secondary algorithm")
            pdf(f"certificate-part-{key}", f"#fp-{part} .bcert",
                (f"PART {part}", f"PDF TEST {part} EXAMPLE", "SAMPLE & TOWN", "16/08/2024",
                 "13:47", "Example secondary algorithm", "Hash Report", "pdf-test-evidence.txt", digest),
                ("Generate Hash Values", "Start with the task"), page_count=2)

        page.set_viewport_size({"width":390,"height":844})
        go("/hash")
        second = b"Different evidence file for the batch PDF."
        second_digest = sha256(second).hexdigest()
        page.locator("#fi").set_input_files([
            {"name":"First sample.txt", "mimeType":"text/plain", "buffer":fixtures},
            {"name":"Second & sample.txt", "mimeType":"text/plain", "buffer":second},
        ])
        page.get_by_role("button", name="Generate Hash Values").click()
        expect(page.locator("#hrows")).to_contain_text(second_digest, timeout=15000)
        page.locator("#cert-file-select").select_option("Second & sample.txt")
        page.locator("#pc-A").click()
        page.locator("#a-nm").fill("PDF TEST BATCH EXAMPLE")
        pdf("certificate-selected-file-mobile", "#fp-A .bcert",
            ("PDF TEST BATCH EXAMPLE", "Second & sample.txt", second_digest),
            ("First sample.txt", digest), page_count=2)
        page.set_viewport_size({"width":1280,"height":720})

        go("/bail-bond")
        for i, name, fields, expected, omitted, n in [
            (0, "form-45", {"accName":"Example Accused", "depName":"Example Deponent", "surName":"Example Surety"},
             ("FORM NO. 45", "Example Accused", "AFFIDAVIT", "Example Deponent"), (), 2),
            (1, "bail-bond", {"bb-caseno-in":"SAMPLE-BOND-11"},
             ("BAIL BOND", "Example Accused", "SAMPLE-BOND-11"), ("FORM NO. 45", "Example Deponent"), 1),
            (2, "surety-bond", {"sb-surWords-in":"Example Surety Amount"},
             ("SURETY BOND", "Example Surety", "Example Surety Amount"), ("FORM NO. 45", "SAMPLE-BOND-11"), 1),
        ]:
            page.locator(".fmt-btn").nth(i).click()
            for field, value in fields.items():
                page.locator(f"#{field}").fill(value)
            pdf(name, ".btn-print", expected, omitted, page_count=n)

        go("/vakalatnama")
        page.locator("#advocate").fill("Example General Advocate")
        page.locator("#client").fill("Example General Client")
        pdf("vakalatnama-general", ".btn-print",
            ("IN THE COURT OF", "Example General Advocate", "Example General Client"),
            ("Example High Court Advocate",), page_count=1)
        page.locator("#fmtAHC").click()
        page.locator("#ahcAdvName").fill("Example High Court Advocate")
        page.locator("#ahcClient").fill("Example High Court Client")
        pdf("vakalatnama-allahabad", ".btn-print",
            ("VAKALATNAMA", "Example High Court Advocate", "Example High Court Client"),
            ("Example General Advocate",), page_count=1)

        go("/memo-appearance")
        page.locator("#advName").fill("Example Memo Advocate")
        page.locator("#inRe").fill("Example Memo Matter")
        pdf("memo-of-appearance", ".btn-print",
            ("Memorandum of Appearance", "Example Memo Advocate", "Example Memo Matter"), page_count=1)

        go("/legal-notice")
        page.locator("#subject").fill("Example Notice Subject")
        page.locator("#recipientName").fill("Example Notice Recipient")
        page.locator("#editor").fill("Example body copy for a printable notice.")
        pdf("legal-notice", ".btn-print",
            ("LEGAL NOTICE", "Example Notice Subject", "Example Notice Recipient",
             "Example body copy for a printable notice."), page_count=1)
        for i, template in enumerate(("Cheque Bounce", "Defamation", "Employment",
                                      "Property", "Consumer", "Money Recovery"), 1):
            page.get_by_role("button", name=template, exact=True).click()
            page.locator("#recipientName").fill("Example Template Recipient")
            body = page.locator("#editor").inner_text()
            words = " ".join(body.split()[:4])
            assert words, template
            pdf(f"notice-template-{i}", ".btn-print", ("Example Template Recipient", words))

        page.locator("#editor").fill("\n".join(
            f"Paragraph {i}. This fictional notice is solely for checking page breaks and printed text."
            for i in range(1, 90)
        ) + "\nEnd of long notice test.")
        pdf("legal-notice-continuation", ".btn-print", ("Paragraph 1.", "End of long notice test."),
            min_pages=2)

        go("/legal-notice-custom")
        page.locator("#subject").fill("Example Custom Subject")
        page.locator("#recipientName").fill("Example Custom Recipient")
        page.locator("#bodyText").fill("<p>Example body with <strong>emphasis</strong>.</p>")
        pdf("custom-legal-notice", ".btn-print",
            ("Example Custom Subject", "Example Custom Recipient", "Example body with emphasis."),
            page_count=1)

        page.locator("#bodyText").fill("".join(
            f"<p>Paragraph {i}. This fictional custom notice is solely for checking page breaks.</p>"
            for i in range(1, 80)
        ) + "<p>End of long custom notice test.</p>")
        pdf("custom-notice-continuation", ".btn-print",
            ("Paragraph 1.", "End of long custom notice test."), min_pages=2)

        go("/billing")
        page.locator("#me_mins").fill("60")
        page.locator("#me_note").fill("Example invoice work")
        page.get_by_role("button", name="Log Time Entry").click()
        page.locator("#qi_firm").fill("Example Billing Firm")
        page.get_by_role("button", name="Generate Invoice", exact=True).click()
        pdf("invoice", "#invoiceSection button[onclick='window.print()']",
            ("INV-0001", "Example Billing Firm", "Example invoice work", "TOTAL DUE"),
            ("Log Time Entry", "Time logged"), page_count=1)
        browser.close()

    print(f"Exported {tested} PDF variants.")
    if problems:
        print("PDF defects:", ", ".join(problems))
        if not cfg.baseline:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
