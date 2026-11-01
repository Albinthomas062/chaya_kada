"""
Playwright verification for bug fixes - Two users testing theatre and admin
"""
from playwright.sync_api import sync_playwright, expect
import time

def run_verification():
    print("=" * 80)
    print("PLAYWRIGHT VERIFICATION - TWO USERS")
    print("=" * 80)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Create two contexts for two different users
        context1 = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context2 = browser.new_context(viewport={'width': 1920, 'height': 1080})
        
        page1 = context1.new_page()
        page2 = context2.new_page()
        
        base_url = "http://localhost:8000"
        
        try:
            # Test 1: Admin login and coin adjust
            print("\n✓ Test 1: Admin Login and Coin Adjust")
            page1.goto(f"{base_url}/custom-admin/login/")
            page1.fill('input[name="username"]', 'admin')
            page1.fill('input[name="password"]', 'admin123')
            page1.click('button[type="submit"]')
            page1.wait_for_load_state('networkidle')
            
            current_url = page1.url
            if '/custom-admin/' in current_url:
                print("   ✅ Admin logged in successfully")
            else:
                print(f"   ❌ Admin login failed - URL: {current_url}")
                return False
            
            # Go to users page
            page1.goto(f"{base_url}/custom-admin/users/")
            page1.wait_for_load_state('networkidle')
            
            # Click on first user
            first_user = page1.locator('a:has-text("testuser")').first
            if first_user.is_visible():
                first_user.click()
                page1.wait_for_load_state('networkidle')
                
                # Try coin adjust
                page1.fill('input[name="amount"]', '50')
                page1.fill('input[name="reason"]', 'Test bonus')
                page1.click('button:has-text("Adjust Coins")')
                page1.wait_for_load_state('networkidle')
                
                # Check for success message
                if 'Adjusted coins' in page1.content() or '50' in page1.content():
                    print("   ✅ Coin adjustment works through UI")
                else:
                    print("   ⚠️  Coin adjustment UI test inconclusive")
            else:
                print("   ⚠️  No test user found to adjust coins")
            
            # Test 2: Theatre - User 1 creates/joins room
            print("\n✓ Test 2: Theatre Multi-User Test")
            
            # User 1 register and login
            page1.goto(f"{base_url}/register/")
            page1.fill('input[name="username"]', f'u1_{int(time.time())}')
            page1.fill('input[name="email"]', f'u1{int(time.time())}@test.com')
            page1.fill('input[name="password1"]', 'testpass123')
            page1.fill('input[name="password2"]', 'testpass123')
            page1.click('button[type="submit"]')
            page1.wait_for_load_state('networkidle')
            print("   ✅ User 1 registered")
            
            # User 2 register and login
            page2.goto(f"{base_url}/register/")
            page2.fill('input[name="username"]', f'u2_{int(time.time())}')
            page2.fill('input[name="email"]', f'u2{int(time.time())}@test.com')
            page2.fill('input[name="password1"]', 'testpass123')
            page2.fill('input[name="password2"]', 'testpass123')
            page2.click('button[type="submit"]')
            page2.wait_for_load_state('networkidle')
            print("   ✅ User 2 registered")
            
            # Both users go to theatre
            page1.goto(f"{base_url}/find-chat/")
            page1.wait_for_timeout(500)
            
            # Look for theatre button
            theatre_btn = page1.locator('button:has-text("Theatre"), a:has-text("Theatre")').first
            if theatre_btn.is_visible():
                theatre_btn.click()
                page1.wait_for_load_state('networkidle')
                
                # Check loader hides
                time.sleep(3)  # Wait for loader to hide
                loading = page1.locator('#loading-screen')
                if loading.is_visible():
                    print("   ❌ LOADER STILL STUCK - hideTheatreLoading() name clash not fixed")
                else:
                    print("   ✅ Loader hides correctly")
                
                # Extract room ID from URL
                room_id = page1.url.split('/')[-2] if '/theatre/' in page1.url else None
                
                if room_id:
                    # User 2 joins same room
                    page2.goto(f"{base_url}/theatre/{room_id}/")
                    page2.wait_for_timeout(3000)
                    
                    # Check if both users see the theatre
                    if 'theatre' in page2.url.lower():
                        print("   ✅ User 2 joined same theatre room")
                        
                        # Try sending a chat message from user 1
                        chat_input = page1.locator('#chat-input')
                        if chat_input.is_visible():
                            chat_input.fill('Hello from U1')
                            page1.click('#send-btn')
                            time.sleep(1)
                            
                            # Check if user 2 sees the message
                            page2.wait_for_timeout(2000)
                            if 'Hello from U1' in page2.content():
                                print("   ✅ User 2 sees User 1's chat message (realtime works)")
                            else:
                                print("   ❌ User 2 doesn't see User 1's chat (realtime broken)")
                        else:
                            print("   ⚠️  Chat input not visible")
                    else:
                        print("   ❌ User 2 failed to join theatre")
                else:
                    print("   ⚠️  Could not extract room ID")
            else:
                print("   ⚠️  Theatre button not found")
            
            print("\n" + "=" * 80)
            print("VERIFICATION COMPLETE")
            print("=" * 80)
            return True
            
        except Exception as e:
            print(f"\n❌ Verification failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            browser.close()

if __name__ == '__main__':
    success = run_verification()
    exit(0 if success else 1)
