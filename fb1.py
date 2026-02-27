import os
import sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def open_url_manual_input():
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    links_file = os.path.join(script_dir, "links.txt")
    friends_list_file = os.path.join(script_dir, "friends_list.txt")
    
    url = input("이동할 주소를 입력하세요 (예: google.com): ").strip()
    
    if not url:
        print("Error: 주소가 입력되지 않았습니다.")
        return

    # Add protocol if missing
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    with sync_playwright() as p:
        # Launch browser in headed mode so user can see
        # Fixed window position to left monitor (0,0) and defined size for better compatibility
        browser = p.chromium.launch(headless=False, args=["--window-position=1500,0", "--window-size=1280,800"])
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

        # 1. Extract all links with their text using BeautifulSoup
        def get_all_links():
            try:
                # Get current page source
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Get the current base URL for resolving relative links
                base_url = page.url
                
                unique = {}
                # Extract all <a> tags
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True)
                    
                    # Convert relative URL to absolute
                    full_url = urljoin(base_url, href)
                    
                    if full_url.startswith('http'):
                        if full_url not in unique:
                            unique[full_url] = text
                return unique
            except Exception as e:
                print(f"BeautifulSoup extraction error: {e}")
                return {}

        print("Extracting links...")
        unique_links = get_all_links()
        
        # Helper to find "친구" link explicitly
        def find_target_explicitly():
            try:
                # Search for any element containing the text "친구"
                target_elements = page.get_by_text("친구")
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

        # Robust search for "친구" (Page A)
        print("Searching for '친구' link...")
        target_url = find_target_explicitly()
        
        if not target_url:
            # Fallback to general extraction
            unique_links = get_all_links()
            for href, text in unique_links.items():
                if "친구" in text:
                    target_url = href
                    break
        else:
            print(f"Aggressive detection found '친구' link: {target_url}")

        if not target_url:
            print("'친구' link not found initially. Scrolling to load more content...")
            for i in range(5):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1500)
                
                target_url = find_target_explicitly()
                if target_url:
                    print(f"Found '친구' after scrolling (Step {i+1}): {target_url}")
                    break
                
                current_links = get_all_links()
                unique_links.update(current_links)
                for href, text in current_links.items():
                    if "친구" in text:
                        target_url = href
                        print(f"Found '친구' in general extraction after scrolling (Step {i+1}): {target_url}")
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
            print(f"Navigating to prioritized '친구' link: {target_url}")
            try:
                page.goto(target_url)
                print("Successfully moved to '친구' link.")
                
                # Secondary Navigation: On Page B, move to the first friend profile
                print("Performing secondary navigation (reaching profile)...")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000) # Increased wait for friend list
                
                def get_friend_profiles():
                    try:
                        # Use BeautifulSoup to parse the current page content
                        html = page.content()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        profile_links = []
                        exclude = [
                            '/home', '/friends', '/groups', '/marketplace', 
                            '/events', '/notifications', '/watch', '/messages', 
                            '/ads', '/settings', '/checkpoint', '/login', '/recover',
                            '/pages', '/gaming', '/saved', '/memories'
                        ]
                        
                        # Aggressively collect all matching <a> tags
                        for a in soup.find_all('a', href=True):
                            href = a['href']
                            text = a.get_text(strip=True)
                            
                            # Basic profile patterns heuristic
                            if not href or not href.startswith('http'):
                                continue
                                
                            # Exclude common navigation/feature links
                            if any(pattern in href for pattern in exclude):
                                continue
                                
                            # Profiles usually have some text (the name)
                            if len(text) > 0:
                                profile_links.append((href, text))
                        
                        return profile_links
                    except Exception as e:
                        print(f"BeautifulSoup extraction error: {e}")
                        return []

                print("Starting friend profile extraction with scrolling...")
                all_profiles = {}
                
                # Scrolling phase to load as many friends as possible
                for i in range(10): # Scroll up to 10 times to load content
                    current_batch = get_friend_profiles()
                    for href, text in current_batch:
                        if href not in all_profiles:
                            all_profiles[href] = text
                    
                    print(f"Scrolling and collecting... (Step {i+1}, Unique Profiles: {len(all_profiles)})")
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(2500) # Wait for content to load

                if all_profiles:
                    print(f"Extracted {len(all_profiles)} friend profiles.")
                    # Save profiles to friends_list.txt
                    with open(friends_list_file, "w", encoding="utf-8") as f:
                        for href, text in sorted(all_profiles.items(), key=lambda x: x[1]): # Sort by name
                            f.write(f"{text} | {href}\n")
                    print(f"Saved friend list to {friends_list_file}")

                    # New Interactive Navigation Loop
                    print("\n" + "="*50)
                    print("친구 프로필 순차 탐색을 시작합니다.")
                    print("Enter: 이동 | n: 건너뛰기 | q: 종료")
                    print("="*50 + "\n")

                    profiles_list = sorted(all_profiles.items(), key=lambda x: x[1])
                    for i, (href, name) in enumerate(profiles_list):
                        print(f"[{i+1}/{len(profiles_list)}] 친구 이름: {name}")
                        choice = input("이동하려면 Enter, 다음으로 넘어가려면 'n', 종료하려면 'q'를 입력하세요: ").lower().strip()
                        
                        if choice == 'q':
                            print("탐색을 종료합니다.")
                            break
                        elif choice == 'n':
                            print(f"{name}님을 건너뜜니다.")
                            continue
                        else:
                            print(f"{name}님의 프로필로 이동합니다: {href}")
                            try:
                                page.goto(href)
                                page.wait_for_load_state("networkidle")
                                
                                # Extract links from the friend's profile
                                print(f"{name}님의 프로필에서 링크 추출 중...")
                                profile_links = get_all_links()
                                
                                # Sanitize name for filename
                                safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
                                profile_file = os.path.join(script_dir, f"profile_links_{safe_name}.txt")
                                
                                with open(profile_file, "w", encoding="utf-8") as f:
                                    for p_href, p_text in sorted(profile_links.items()):
                                        f.write(f"{p_text} | {p_href}\n")
                                
                                print(f"추출 완료: {len(profile_links)}개의 링크를 {profile_file}에 저장했습니다.")
                                input("다음에 계속하려면 터미널에서 Enter를 누르세요...")
                            except Exception as e:
                                print(f"이동 또는 추출 중 오류 발생: {e}")
                else:
                    print("No friend profiles could be extracted from the secondary page.")
                    
            except Exception as e:
                print(f"Failed during extraction flow: {e}")
        elif unique_links:
            # Fallback
            first_url = sorted(unique_links.keys())[0]
            print(f"'친구' link not found. Navigating to first available link: {first_url}")
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
#test
if __name__ == "__main__":
    open_url_manual_input()
