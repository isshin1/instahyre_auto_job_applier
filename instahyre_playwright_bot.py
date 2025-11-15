"""
Playwright bot for Instahyre (Chromium) - Python version (updated)

.env example:
INSTAHYRE_EMAIL=you@example.com
INSTAHYRE_PASSWORD=yourpassword
HEADLESS=true      # set to "false" for headed mode
SLOW_MO=0          # optional: number (ms) to slow down actions
MAX_APPLIES=100    # optional limit

Usage: python instahyre_playwright_bot.py

Notes:
- Uses synchronous Playwright API for simplicity.
- Uses high-level Playwright locators (get_by_role, get_by_text, locator(has_text=...)).
- Detects the "no matching opportunities" message and exits cleanly.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
import os
import time

load_dotenv()

EMAIL = os.getenv('INSTAHYRE_EMAIL')
PASSWORD = os.getenv('INSTAHYRE_PASSWORD')
HEADLESS = os.getenv('HEADLESS', 'true').lower() != 'false'
SLOW_MO = int(os.getenv('SLOW_MO', '0'))
MAX_APPLIES = int(os.getenv('MAX_APPLIES', '100'))
OPPORTUNITIES_URL = 'https://www.instahyre.com/candidate/opportunities/?matching=true'

if not EMAIL or not PASSWORD:
    raise SystemExit('Please set INSTAHYRE_EMAIL and INSTAHYRE_PASSWORD in your .env file.')


def handle_possible_close_popup(page):
    # Look for a "follow us on social media" text and try to close the modal
    try:
        popup = page.get_by_text("follow us on social media", exact=False)
        if popup.count() > 0:
            print('Detected "follow us on social media" popup — attempting to close it')
            # Try common close button patterns
            close_btn = None
            if page.get_by_role("button", name="Close").count() > 0:
                close_btn = page.get_by_role("button", name="Close").first
            elif page.get_by_text("×").count() > 0:
                close_btn = page.get_by_text("×").first
            else:
                # Generic close selectors using locator (has_text fallback)
                cand = page.locator("button, a").filter(has_text="Close")
                if cand.count() > 0:
                    close_btn = cand.first

            if close_btn:
                close_btn.click(force=True)
                time.sleep(0.4)
    except Exception as e:
        print('Error while handling close popup:', e)


def handle_possible_confirm_apply_popup(page):
    # Look for a confirmation dialog that says "want to apply at t***" (loose match) and click Apply
    try:
        want_apply = page.get_by_text("want to apply at t", exact=False)
        if want_apply.count() > 0:
            print('Detected "want to apply at t..." popup — clicking its Apply button')
            # Try role-based apply button first
            if page.get_by_role("button", name="Apply").count() > 0:
                page.get_by_role("button", name="Apply").first.click(force=True)
                time.sleep(0.5)
                return
            if page.get_by_text("Apply", exact=False).count() > 0:
                page.get_by_text("Apply", exact=False).first.click(force=True)
                time.sleep(0.5)
                return

        # fallback: find any dialog role with an Apply button
        modal_apply = page.locator('div[role="dialog"] button').filter(has_text="Apply")
        if modal_apply.count() > 0:
            print('Detected modal with Apply button — clicking it')
            modal_apply.first.click(force=True)
            time.sleep(0.4)
    except Exception as e:
        print('Error while handling confirm-apply popup:', e)


def check_no_opportunities_and_exit(page):
    # Look for a message indicating no matching opportunities
    # User message example: "Hey candidate_name, no matching opportunities found at the moment. and some other"
    # We'll search for a unique phrase fragment "no matching opportunities" case-insensitive
    try:
        no_ops = page.get_by_text("no matching opportunities", exact=False)
        if no_ops.count() > 0:
            # Found the no-opportunities message
            print('No matching opportunities found — exiting.')
            return True
        # also check for possible alternative phrasing
        alt = page.get_by_text("no opportunities found", exact=False)
        if alt.count() > 0:
            print('No opportunities found (alternate text) — exiting.')
            return True
    except Exception:
        pass
    return False



ua = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def create_browser_context(p, headless, slow_mo):
    # common args that help in many environments (no-sandbox on many linux CI/Docker systems)
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
    ]

    browser = p.chromium.launch(headless=headless, slow_mo=slow_mo, args=launch_args)

    context = browser.new_context(
        user_agent=ua,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        java_script_enabled=True,
    )

    # Only add stealth-ish init script in headless mode
    if headless:
        context.add_init_script(
            """
            // reduce WebDriver fingerprint
            Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true });
            window.chrome = window.chrome || { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            // permissions shim
            const _orig = navigator.permissions && navigator.permissions.query;
            if (_orig) {
              navigator.permissions.query = (params) => {
                if (params && params.name === 'notifications') {
                  return Promise.resolve({ state: Notification.permission });
                }
                return _orig(params);
              };
            }
            """
        )

    return browser, context

with sync_playwright() as p:
    # browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
    # context = browser.new_context()
    # page = context.new_page()

    browser, context = create_browser_context(p, HEADLESS, SLOW_MO)
    page = context.new_page()


    try:
        print('Navigating to Instahyre login...')
        page.goto('https://www.instahyre.com/login', wait_until='networkidle')

        # Defensive selectors for email and password
        email_selector = 'input[type="email"], input[name*=email], input[id*=email], input[placeholder*=Email], input[placeholder*=email]'
        password_selector = 'input[type="password"], input[name*=password], input[id*=password], input[placeholder*=Password], input[placeholder*=password]'

        email_el = page.query_selector(email_selector)
        password_el = page.query_selector(password_selector)

        if not email_el or not password_el:
            print('Warning: could not find standard email/password inputs with primary selectors; trying fallbacks')
            # attempt looser selectors
            email_el = page.query_selector('input[name], input[id], input[placeholder]')
            password_el = page.query_selector('input[type="password"]')

            if not email_el or not password_el:
                raise SystemExit('Could not find email/password fields on the login page. Update selectors.')

        email_el.fill(EMAIL)
        password_el.fill(PASSWORD)

        # Try to find a submit button, otherwise press Enter
        submit_btn = page.query_selector('button[type="submit"], button:has-text("Login"), button:has-text("Sign in"), button:has-text("Sign In")')
        if submit_btn:
            # click and wait for navigation or networkidle
            submit_btn.click()
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except PlaywrightTimeoutError:
                pass
        else:
            # press Enter on password field
            password_el.press('Enter')
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except PlaywrightTimeoutError:
                pass

        print('Logged in (or attempted login). Navigating to opportunities page...')
        page.goto(OPPORTUNITIES_URL, wait_until='networkidle')

        # small wait to allow cards to render
        time.sleep(1.5)

        applied = 0

        for i in range(MAX_APPLIES):
            # Check for no-opportunities message first
            if check_no_opportunities_and_exit(page):
                break

            try:
                # Prefer accessible role for "View" button
                view_btn = None
                role_loc = page.get_by_role("button", name="View")
                if role_loc.count() > 0:
                    view_btn = role_loc.first
                else:
                    text_loc = page.get_by_text("View", exact=False)
                    if text_loc.count() > 0:
                        view_btn = text_loc.first

                if not view_btn:
                    print('No more "View" buttons found. Exiting loop.')
                    break

                print(f'Clicking View for job #{i+1}...')
                view_btn.click(force=True)
                time.sleep(0.7)

                # Wait for Apply to be present in the job description
                apply_btn = None
                # Try role-based locator first
                role_apply = page.get_by_role("button", name="Apply")
                if role_apply.count() > 0:
                    try:
                        role_apply.wait_for(state="visible", timeout=7000)
                        apply_btn = role_apply.first
                    except PlaywrightTimeoutError:
                        apply_btn = None

                # Fallback to text match
                if not apply_btn:
                    text_apply = page.get_by_text("Apply", exact=False)
                    if text_apply.count() > 0:
                        try:
                            text_apply.wait_for(state="visible", timeout=3000)
                            apply_btn = text_apply.first
                        except PlaywrightTimeoutError:
                            apply_btn = None

                if not apply_btn:
                    print('Apply button did not appear in time — skipping this job')
                    # After skipping, check again for no-opportunities (in case the page updated)
                    if check_no_opportunities_and_exit(page):
                        break
                    continue

                # click the found apply element
                apply_btn.click(force=True)

                # handle known popups
                handle_possible_close_popup(page)
                handle_possible_confirm_apply_popup(page)

                # small delay to allow the next description to open or UI to update
                time.sleep(1.2)

                applied += 1
                print(f'Applied to {applied} job(s) so far')

                # After applying, it's possible the list refreshed — check for no-opportunities
                if check_no_opportunities_and_exit(page):
                    break

            except Exception as inner_e:
                print('Error while processing a job card:', inner_e)
                time.sleep(1)
                continue

        print(f'Done. Total applied: {applied}')

    except Exception as e:
        print('Fatal error:', e)

    finally:
        try:
            context.close()
            browser.close()
        except Exception:
            pass
