import os
import sys
from playwright.sync_api import sync_playwright

def open_url_manual_input():
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    links_file = os.path.join(script_dir, "links.txt")
    
    url = input("이동할 주소를 입력하세요 (예: google.com): ").strip()
    
    if not url:
        print("Error: 주소가 입력되지 않았습니다.")
        return

    # Add protocol if missing
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    with sync_playwright() as p:
        # Launch browser in headed mode so user can see
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        page.goto(url)
        
        # Wait for the page to load initial elements
        print("Detecting login page...")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000) # Additional small wait for JS-rendered forms
        
        # Comprehensive login detection logic
        login_indicators = [
            "input[type='password']",
            "input[name*='pass']",
            "input[name*='login']",
            "input[name*='user']",
            "input[type='email']",
            "input[placeholder*='아이디']",
            "input[placeholder*='비밀번호']",
            "button:has-text('로그인')",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "a:has-text('로그인')",
            "a:has-text('Login')"
        ]
        
        is_login_page = False
        for indicator in login_indicators:
            try:
                if page.locator(indicator).count() > 0:
                    print(f"Login indicator detected: {indicator}")
                    is_login_page = True
                    break
            except:
                continue

        if is_login_page:
            print("\n*** 로그인 화면이 감지되었습니다. ***")
            print("브라우저 창에서 로그인을 진행해 주세요.")
            input("로그인을 마치셨다면 터미널에서 Enter 키를 눌러주세요...")
            print("로그인 확인 후 작업을 계속합니다.\n")
            
            # Stabilization wait after manual login
            print("Stabilizing page after login...")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000) # Give it a bit more time to settle

        # 1. Extract all links with their text
        def get_all_links():
            try:
                data = page.locator("a").evaluate_all(
                    "list => list.map(a => ({href: a.href, text: a.innerText.trim()}))"
                )
                unique = {}
                for item in data:
                    href = item['href']
                    text = item['text']
                    if href and href.startswith('http'):
                        if href not in unique:
                            unique[href] = text
                return unique
            except Exception as e:
                print(f"Extraction error: {e}")
                return {}

        print("Extracting links...")
        unique_links = get_all_links()
        
        # Helper to find "모든 친구" link explicitly
        def find_target_explicitly():
            try:
                # Search for any element containing the text "모든 친구"
                target_elements = page.get_by_text("모든 친구")
                count = target_elements.count()
                for i in range(count):
                    elem = target_elements.nth(i)
                    # Try to find the closest clickable <a> parent
                    try:
                        href = elem.evaluate(
                            "node => { let a = node.closest('a'); return a ? a.href : null; }"
                        )
                        if href and href.startswith('http'):
                            return href
                    except: continue
            except: pass
            return None

        # Robust search for "모든 친구" (Page A)
        print("Searching for '모든 친구' link...")
        target_url = find_target_explicitly()
        
        if not target_url:
            # Fallback to general extraction
            unique_links = get_all_links()
            for href, text in unique_links.items():
                if "모든 친구" in text:
                    target_url = href
                    break
        else:
            print(f"Aggressive detection found '모든 친구' link: {target_url}")

        if not target_url:
            print("'모든 친구' link not found initially. Scrolling to load more content...")
            for i in range(5):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1500)
                
                target_url = find_target_explicitly()
                if target_url:
                    print(f"Found '모든 친구' after scrolling (Step {i+1}): {target_url}")
                    break
                
                current_links = get_all_links()
                unique_links.update(current_links)
                for href, text in current_links.items():
                    if "모든 친구" in text:
                        target_url = href
                        print(f"Found '모든 친구' in general extraction after scrolling (Step {i+1}): {target_url}")
                        break
                if target_url: break
        else:
            # If found explicitly, still extract others for the file
            unique_links = get_all_links()

        # 3. Save discovered links to file
        with open(links_file, "w", encoding="utf-8") as f:
            for href, text in sorted(unique_links.items()):
                f.write(f"{text} | {href}\n")
        
        print(f"Successfully saved {len(unique_links)} links to {links_file}")
        
        # 4. Navigate
        if target_url:
            print(f"Navigating to prioritized '모든 친구' link: {target_url}")
            try:
                page.goto(target_url)
                print("Successfully moved to '모든 친구' link.")
                
                # Secondary Navigation: On Page B, move to the first friend profile
                print("Performing secondary navigation (reaching profile)...")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000) # Increased wait for friend list
                
                def get_friend_profiles():
                    try:
                        # Heuristic: Find links that are likely profile links
                        # We extract both href and text to be sure
                        data = page.locator("a").evaluate_all("""
                            list => list.map(a => ({href: a.href, text: a.innerText.trim()}))
                                .filter(item => {
                                    const href = item.href;
                                    const text = item.text;
                                    // Basic profile patterns
                                    if (!href || !href.startsWith('http')) return false;
                                    
                                    // Exclude common navigation/feature links
                                    const exclude = [
                                        '/home', '/friends', '/groups', '/marketplace', 
                                        '/events', '/notifications', '/watch', '/messages', 
                                        '/ads', '/settings', '/checkpoint', '/login', '/recover',
                                        '/pages', '/gaming', '/saved', '/memories'
                                    ];
                                    if (exclude.some(pattern => href.includes(pattern))) return false;
                                    
                                    // Profiles usually don't have many query params other than 'id' or 'sk'
                                    // and usually have some text (the name)
                                    return text.length > 0;
                                })
                        """)
                        return [item['href'] for item in data]
                    except: return []

                new_links = get_friend_profiles()
                if not new_links:
                    print("No profile links found on Page B. Scrolling to load friend list...")
                    for i in range(5):
                        page.mouse.wheel(0, 1500)
                        page.wait_for_timeout(2000)
                        new_links = get_friend_profiles()
                        if new_links: 
                            print(f"Found profiles after scrolling (Step {i+1}).")
                            break
                
                if new_links:
                    final_url = new_links[0]
                    print(f"Secondary navigation to friend profile: {final_url}")
                    page.goto(final_url)
                    print("Successfully reached the friend's profile page.")
                else:
                    print("Could not identify any friend profiles on the secondary page.")
                    
            except Exception as e:
                print(f"Failed during navigation flow: {e}")
        elif unique_links:
            # Fallback
            first_url = sorted(unique_links.keys())[0]
            print(f"'모든 친구' link not found. Navigating to first available link: {first_url}")
            try:
                page.goto(first_url)
            except Exception as e:
                print(f"Failed to navigate: {e}")
        else:
            print("No links found on the page to follow.")
        
        print("Browser will remain open. Press Ctrl+C in this terminal to close.")
        # Keep the script running so the browser doesn't close immediately
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\nClosing browser...")
            browser.close()

if __name__ == "__main__":
    open_url_manual_input()
