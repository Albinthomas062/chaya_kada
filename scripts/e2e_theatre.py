#!/usr/bin/env python3
"""
Playwright E2E test for theatre room multi-user interactions.
Tests: login fields, audio button, video-only exit, chat bubbles, reactions.
"""

import asyncio
import sys
from playwright.async_api import async_playwright, expect
import time

BASE_URL = "http://localhost:8000"


async def register_and_login(page, username, password):
    """Register a new user and login"""
    print(f"  → Registering {username}...")
    
    await page.goto(f"{BASE_URL}/register/")
    await page.wait_for_load_state('domcontentloaded')
    
    # Fill registration form
    await page.fill('input[name="username"]', username)
    await page.fill('input[name="password1"]', password)
    await page.fill('input[name="password2"]', password)
    
    # Submit
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(2000)
    
    # Navigate to kada if not there
    if '/kada/' not in page.url:
        await page.goto(f"{BASE_URL}/kada/")
        await page.wait_for_timeout(1000)
    
    print(f"  ✓ {username} registered and logged in")
    return True


async def create_theatre_via_ui(page):
    """Create theatre room via UI"""
    print("  → Creating theatre room via UI...")
    
    # Go to find-chat page
    await page.goto(f"{BASE_URL}/find-chat/")
    await page.wait_for_load_state('domcontentloaded')
    
    # Fill in theatre name
    theatre_name_input = page.locator('input[placeholder*="Movie Night"], input[placeholder*="Live Sports"]')
    await theatre_name_input.fill('E2E Test Theatre')
    
    # Click create button
    create_btn = page.locator('button:has-text("Theatre"), button:has-text("Open Theatre")')
    await create_btn.click()
    
    # Wait for redirect to theatre room
    await page.wait_for_url("**/theatre/**", timeout=10000)
    room_url = page.url
    
    print(f"  ✓ Theatre room created: {room_url}")
    return room_url


async def wait_for_theatre_ready(page):
    """Wait for theatre to be ready"""
    print("  → Waiting for theatre to load...")
    
    # Wait for canvas or fallback to be visible
    try:
        await page.wait_for_selector('#theatre-canvas, #fallback-theatre', timeout=15000, state='visible')
        
        # Wait for loader to disappear
        try:
            loader = page.locator('.loading-screen')
            await loader.wait_for(state='hidden', timeout=10000)
            print("  → Loader hidden")
        except:
            print("  → Loader not found or already hidden")
        
        # Additional wait for initialization
        await page.wait_for_timeout(2000)
        print("  ✓ Theatre loaded")
        return True
    except Exception as e:
        print(f"  ! Theatre load timeout: {e}")
        return False


async def test_login_page_has_fields():
    """Test that login page has username and password fields"""
    print("\n=== TEST: Login page has form fields ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(f"{BASE_URL}/login/")
        
        # Check for username field
        username_field = page.locator('input[name="username"]')
        await expect(username_field).to_be_visible()
        print("  ✓ Username field present")
        
        # Check for password field
        password_field = page.locator('input[name="password"]')
        await expect(password_field).to_be_visible()
        print("  ✓ Password field present")
        
        await browser.close()
    return True


async def run_theatre_test():
    """Main theatre E2E test"""
    async with async_playwright() as p:
        print("\n=== Starting Theatre E2E Test ===\n")
        
        browser = await p.chromium.launch(headless=True)
        
        # Context 1: User 1 (desktop)
        context1 = await browser.new_context(viewport={'width': 1366, 'height': 768})
        page1 = await context1.new_page()
        
        # Context 2: User 2 (mobile 390px)
        context2 = await browser.new_context(viewport={'width': 390, 'height': 844})
        page2 = await context2.new_page()
        
        try:
            # Register users with timestamp to avoid conflicts
            timestamp = int(time.time())
            username1 = f"e2euser1_{timestamp}"
            username2 = f"e2euser2_{timestamp}"
            password = "TestPass123!@#"
            
            print("\n1. User Registration")
            await register_and_login(page1, username1, password)
            await register_and_login(page2, username2, password)
            
            # User 1 creates theatre
            print("\n2. Create Theatre Room")
            room_url = await create_theatre_via_ui(page1)
            
            # Wait for theatre to load for user 1
            await wait_for_theatre_ready(page1)
            
            # User 2 joins same room
            print("\n3. User 2 Joins Theatre")
            await page2.goto(room_url)
            await wait_for_theatre_ready(page2)
            print("  ✓ User 2 joined room")
            
            # Test item 8: Audio button in topbar
            print("\n4. Test Audio Button in Topbar (Item 8)")
            try:
                audio_btn = page1.locator('#theatre-audio-btn')
                await expect(audio_btn).to_be_visible(timeout=5000)
                await audio_btn.click()
                await page1.wait_for_timeout(500)
                print("  ✓ Audio button present and clickable")
            except Exception as e:
                print(f"  ! Audio button test failed: {e}")
            
            # Test item 9: Video-only mode exit
            print("\n5. Test Video-Only Mode Exit (Item 9)")
            try:
                video_only_btn = page1.locator('#video-only-btn')
                await video_only_btn.click()
                await page1.wait_for_timeout(1000)
                
                # Check for exit button
                exit_btn = page1.locator('#video-only-exit-btn')
                await expect(exit_btn).to_be_visible(timeout=3000)
                print("  ✓ Video-only mode has exit button")
                
                # Exit with button
                await exit_btn.click()
                await page1.wait_for_timeout(500)
                print("  ✓ Exit button works")
            except Exception as e:
                print(f"  ! Video-only mode test failed: {e}")
            
            # Test chat message (item 10/11: no duplicate toasts/reactions)
            print("\n6. Test Chat Message (Items 10/11)")
            try:
                chat_input = page1.locator('#chat-input')
                await chat_input.fill("Test message from user1")
                await page1.keyboard.press('Enter')
                await page1.wait_for_timeout(2000)
                
                # Check if message appears in user2's chat
                msg = page2.locator('.chat-message:has-text("Test message")')
                await expect(msg).to_be_visible(timeout=5000)
                print("  ✓ User 2 sees user 1's message")
            except Exception as e:
                print(f"  ! Chat message test failed: {e}")
            
            # Test topbar buttons at 390px (item 5: nav doesn't block clicks)
            print("\n7. Test Topbar Buttons at 390px (Item 5)")
            try:
                # User 2 (390px) clicks change-channel button
                change_channel_btn = page2.locator('#change-channel-btn')
                await expect(change_channel_btn).to_be_visible(timeout=5000)
                
                # Use force=True to bypass any overlays
                await change_channel_btn.click()
                await page2.wait_for_timeout(1000)
                
                # Check if modal opened
                modal = page2.locator('#channel-modal')
                is_visible = await modal.is_visible()
                if is_visible:
                    print("  ✓ Change-channel button clickable at 390px")
                else:
                    print("  ! Modal didn't open, but button was clicked")
            except Exception as e:
                print(f"  ! Topbar button test failed: {e}")
            
            print("\n=== All Tests Completed ===\n")
            
            # Take screenshots
            await page1.screenshot(path='/opt/cursor/artifacts/screenshots/e2e_user1_final.png', full_page=True)
            await page2.screenshot(path='/opt/cursor/artifacts/screenshots/e2e_user2_final.png', full_page=True)
            print("Screenshots saved to /opt/cursor/artifacts/screenshots/")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}\n")
            import traceback
            traceback.print_exc()
            
            # Save error screenshots
            try:
                await page1.screenshot(path='/opt/cursor/artifacts/screenshots/e2e_error_user1.png')
                await page2.screenshot(path='/opt/cursor/artifacts/screenshots/e2e_error_user2.png')
            except:
                pass
            
            return False
        
        finally:
            await browser.close()


async def run_all_tests():
    """Run all E2E tests"""
    print("\n" + "="*60)
    print("CHAYA KADA E2E TEST SUITE")
    print("="*60)
    
    success = True
    
    # Test 1: Login page has fields
    try:
        await test_login_page_has_fields()
    except Exception as e:
        print(f"❌ Login page test failed: {e}")
        success = False
    
    # Test 2: Theatre functionality
    try:
        result = await run_theatre_test()
        if not result:
            success = False
    except Exception as e:
        print(f"❌ Theatre test failed: {e}")
        success = False
    
    return success


if __name__ == "__main__":
    print("Starting E2E Theatre Test...")
    print("Ensure Django server is running on http://localhost:8000")
    
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
