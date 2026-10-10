# Browser walkthrough used during testing. Needs: pip install playwright && playwright install chromium
# Run with the backend serving the built frontend on :8000 and the demo account seeded.
import asyncio
from playwright.async_api import async_playwright
results=[]
def check(name, ok):
    results.append(("PASS" if ok else "FAIL", name)); print(results[-1][0], name, flush=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1280,"height":900})
        errors=[]; pg.on("console", lambda m: m.type=="error" and errors.append(m.text))
        await pg.goto("http://localhost:8000/"); await pg.wait_for_timeout(600)
        # login validation
        await pg.click("button.btn-primary"); check("Login: empty form shows field errors", await pg.locator(".field-error").count()==2)
        await pg.fill("input[type=email]","demo@cashpilot.app"); await pg.fill("input[type=password]","wrong-password")
        await pg.click("button.btn-primary"); await pg.wait_for_timeout(500)
        check("Login: wrong password shows message", "don't match" in (await pg.inner_text(".error-note")))
        await pg.fill("input[type=password]","demo-password"); await pg.click("button.btn-primary"); await pg.wait_for_timeout(1200)
        check("Login: correct password opens Overview", "books" in await pg.inner_text("h1"))
        # keyboard: first Tab reaches skip link
        await pg.keyboard.press("Tab"); check("Keyboard: first Tab focuses 'Skip to content'", (await pg.evaluate("document.activeElement.textContent")).strip()=="Skip to content")
        await pg.keyboard.press("Tab"); check("Keyboard: Tab reaches sidebar nav", "Overview" in await pg.evaluate("document.activeElement.textContent"))
        await pg.keyboard.press("Tab"); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(1200)
        check("Keyboard: Enter on nav opens Transactions", "Transactions" in await pg.inner_text("h1"))
        check("Focus moves to page heading after navigation", await pg.evaluate("document.activeElement.tagName")=="H1")
        # add form weird inputs
        await pg.goto("http://localhost:8000/#/transactions"); await pg.wait_for_timeout(1000)
        await pg.click("text=Add transaction"); await pg.click("text=Save transaction")
        check("Add form: empty submit shows 2 errors", await pg.locator(".add-form .field-error").count()==2)
        await pg.fill(".add-form label:has-text('Amount') input","abc"); await pg.fill(".add-form label:has-text('Merchant') input","   ")
        await pg.click("text=Save transaction"); check("Add form: 'abc' amount rejected", await pg.locator("#err-amount").count()==1)
        check("Add form: errors linked via aria-describedby", await pg.get_attribute(".add-form label:has-text('Amount') input","aria-describedby")=="err-amount")
        await pg.fill(".add-form label:has-text('Merchant') input","Client lunch"); await pg.fill(".add-form label:has-text('Amount') input","$1,200.50")
        await pg.click("text=Save transaction"); await pg.wait_for_timeout(800)
        check("Add form: '$1,200.50' accepted and saved", "−$1,200.50" in await pg.inner_text(".txn-list"))
        # search wildcard
        await pg.fill("input[type=search]","%"); await pg.wait_for_timeout(800)
        check("Search: '%' shows no false matches", await pg.locator(".txn").count()==0)
        await pg.fill("input[type=search]","Client"); await pg.wait_for_timeout(800)
        check("Search: finds new transaction", await pg.locator(".txn").count()==1)
        # category correction
        await pg.select_option(".txn .cat-select","Meals"); await pg.wait_for_timeout(600)
        check("Category change shows saved message", "Future charges" in await pg.inner_text(".ok-note"))
        # delete
        pg.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.click(".txn .link-danger"); await pg.wait_for_timeout(700)
        check("Delete removes transaction", await pg.locator(".txn").count()==0)
        await pg.fill("input[type=search]","")
        # review toggle + confirm
        await pg.check("text=Only show items to check"); await pg.wait_for_timeout(700)
        n=await pg.locator(".txn").count(); await pg.click(".txn >> text=Looks right"); await pg.wait_for_timeout(600)
        check("'Looks right' removes item from review list", await pg.locator(".txn").count()==n-1)
        # CSV bad file
        await pg.set_input_files("input[type=file]", files=[{"name":"notes.txt","mimeType":"text/plain","buffer":b"hello"}]); await pg.wait_for_timeout(500)
        check("Import: non-CSV file rejected with message", "Choose a .csv" in await pg.inner_text(".error-note"))
        await pg.set_input_files("input[type=file]", "/home/claude/cashpilot/samples/sample-bank-export.csv"); await pg.wait_for_selector(".ok-note:has-text('Imported')")
        check("Import: sample CSV imported", "Imported " in await pg.inner_text(".ok-note"))
        await pg.set_input_files("input[type=file]", "/home/claude/cashpilot/samples/sample-bank-export.csv"); await pg.wait_for_selector(".ok-note:has-text('skipped')")
        check("Import: re-import skips duplicates", "skipped 10" in await pg.inner_text(".ok-note"))
        # receipt fake file
        await pg.goto("http://localhost:8000/#/receipt"); await pg.wait_for_timeout(800)
        await pg.set_input_files("input[type=file]", files=[{"name":"r.jpg","mimeType":"image/jpeg","buffer":b"not really a jpeg"}]); await pg.wait_for_timeout(1000)
        check("Receipt: fake image rejected", "isn't a real image" in await pg.inner_text(".error-note"))
        # ask
        await pg.goto("http://localhost:8000/#/ask"); await pg.wait_for_timeout(800)
        await pg.click(".ask-box button"); check("Ask: empty question shows message", "Type a question" in await pg.inner_text(".error-note"))
        await pg.fill(".ask-box input","How much on software?"); await pg.click(".ask-box button"); await pg.wait_for_timeout(800)
        check("Ask: no AI key shows clear setup message", "AI isn't set up" in await pg.inner_text(".error-note"))
        # forecast settings weird
        await pg.goto("http://localhost:8000/#/forecast"); await pg.wait_for_timeout(1000)
        check("Forecast: chart renders", await pg.locator(".chart svg").count()==1)
        await pg.click("summary:has-text('Change balance')")
        await pg.fill("details .settings-form label:has-text('Current') input","lots"); await pg.click("details >> text=Update forecast")
        check("Forecast: non-number balance rejected", "as a number" in await pg.inner_text(".error-note"))
        await pg.fill("details .settings-form label:has-text('Current') input","4,500"); await pg.click("details >> text=Update forecast"); await pg.wait_for_timeout(1000)
        check("Forecast: '4,500' accepted, starts at $4,500", "$4,500" in await pg.inner_text(".forecast-figures"))
        await pg.click("text=Explain this in plain English"); await pg.wait_for_timeout(700)
        check("Forecast explain: clear message without AI", "AI isn't set up" in await pg.inner_text(".explain"))
        # mobile size
        await pg.set_viewport_size({"width":375,"height":740}); await pg.goto("http://localhost:8000/#/transactions"); await pg.wait_for_timeout(1000)
        check("Mobile 375px: bottom tab bar visible", await pg.locator(".tabbar").is_visible())
        check("Mobile 375px: no sideways scrolling", await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        await pg.set_viewport_size({"width":768,"height":1024}); await pg.goto("http://localhost:8000/#/forecast"); await pg.wait_for_timeout(800)
        check("Tablet 768px: no sideways scrolling", await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        check("No CSP or JavaScript errors in console", not [e for e in errors if "Failed to load resource" not in e])
        # sign out
        await pg.set_viewport_size({"width":1280,"height":900}); await pg.click("text=Sign out"); await pg.wait_for_timeout(500)
        check("Sign out returns to sign-in screen", await pg.locator(".auth-card").count()==1)
        await b.close()
    print(sum(r[0]=="PASS" for r in results),"/",len(results),"passed"); print("console:",errors[:5])
asyncio.run(main())
