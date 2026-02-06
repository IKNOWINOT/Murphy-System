#!/usr/bin/env python3
"""
Comprehensive tests for UI bug fixes
Tests all critical fixes thoroughly
"""

import time
import pytest

selenium = pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

class UIBugFixTester:
    def __init__(self):
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
        self.driver = None
        
    def setup_driver(self):
        """Setup headless Chrome driver"""
        print("Setting up Chrome driver...")
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            print("✓ Chrome driver initialized")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize Chrome driver: {e}")
            print("  Note: Selenium tests require Chrome/Chromium installed")
            return False
    
    def test_message_spacing(self):
        """Test 1: Messages have proper spacing and don't overlap"""
        print("\n" + "="*80)
        print("TEST 1: Message Spacing")
        print("="*80)
        
        try:
            # Load the page
            self.driver.get("https://murphybos-0004n.app.super.myninja.ai/murphy_ui_fixed_bugs.html")
            time.sleep(2)
            
            # Skip onboarding
            try:
                name_input = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "onboarding-input"))
                )
                name_input.send_keys("Test User")
                next_btn = self.driver.find_element(By.CLASS_NAME, "onboarding-btn")
                next_btn.click()
                time.sleep(0.5)
                
                # Business type
                business_input = self.driver.find_element(By.ID, "onboarding-input")
                time.sleep(0.5)
                next_btn = self.driver.find_element(By.CLASS_NAME, "onboarding-btn")
                next_btn.click()
                time.sleep(0.5)
                
                # Goal
                goal_input = self.driver.find_element(By.ID, "onboarding-input")
                goal_input.send_keys("Testing")
                next_btn = self.driver.find_element(By.CLASS_NAME, "onboarding-btn")
                next_btn.click()
                time.sleep(2)
            except:
                pass
            
            # Get all messages
            messages = self.driver.find_elements(By.CLASS_NAME, "message")
            
            if len(messages) < 2:
                print("  ⚠ Not enough messages to test spacing")
                self.results["warnings"].append("Message spacing: Not enough messages")
                return False
            
            # Check spacing between messages
            overlapping = False
            for i in range(len(messages) - 1):
                msg1 = messages[i]
                msg2 = messages[i + 1]
                
                msg1_bottom = msg1.location['y'] + msg1.size['height']
                msg2_top = msg2.location['y']
                
                spacing = msg2_top - msg1_bottom
                
                print(f"  Message {i} to {i+1} spacing: {spacing}px")
                
                if spacing < 0:
                    overlapping = True
                    print(f"    ✗ OVERLAPPING DETECTED: {spacing}px")
                elif spacing < 5:
                    print(f"    ⚠ Tight spacing: {spacing}px")
                else:
                    print(f"    ✓ Good spacing: {spacing}px")
            
            if not overlapping:
                print("\n✓ TEST PASSED: No message overlapping detected")
                self.results["passed"].append("Message spacing")
                return True
            else:
                print("\n✗ TEST FAILED: Message overlapping detected")
                self.results["failed"].append("Message spacing")
                return False
                
        except Exception as e:
            print(f"\n✗ TEST ERROR: {e}")
            self.results["failed"].append(f"Message spacing: {e}")
            return False
    
    def test_scrolling(self):
        """Test 2: Chat area scrolls properly"""
        print("\n" + "="*80)
        print("TEST 2: Scrolling Functionality")
        print("="*80)
        
        try:
            # Get messages container
            messages_container = self.driver.find_element(By.ID, "messages")
            
            # Check if scrollable
            scroll_height = self.driver.execute_script("return arguments[0].scrollHeight", messages_container)
            client_height = self.driver.execute_script("return arguments[0].clientHeight", messages_container)
            
            print(f"  Scroll height: {scroll_height}px")
            print(f"  Client height: {client_height}px")
            
            if scroll_height > client_height:
                print("  ✓ Container is scrollable")
                
                # Test scrolling
                initial_scroll = self.driver.execute_script("return arguments[0].scrollTop", messages_container)
                print(f"  Initial scroll position: {initial_scroll}px")
                
                # Scroll to top
                self.driver.execute_script("arguments[0].scrollTop = 0", messages_container)
                time.sleep(0.5)
                top_scroll = self.driver.execute_script("return arguments[0].scrollTop", messages_container)
                print(f"  After scroll to top: {top_scroll}px")
                
                # Scroll to bottom
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", messages_container)
                time.sleep(0.5)
                bottom_scroll = self.driver.execute_script("return arguments[0].scrollTop", messages_container)
                print(f"  After scroll to bottom: {bottom_scroll}px")
                
                if bottom_scroll > top_scroll:
                    print("\n✓ TEST PASSED: Scrolling works correctly")
                    self.results["passed"].append("Scrolling functionality")
                    return True
                else:
                    print("\n✗ TEST FAILED: Scrolling not working")
                    self.results["failed"].append("Scrolling functionality")
                    return False
            else:
                print("  ⚠ Not enough content to test scrolling")
                self.results["warnings"].append("Scrolling: Not enough content")
                return True
                
        except Exception as e:
            print(f"\n✗ TEST ERROR: {e}")
            self.results["failed"].append(f"Scrolling: {e}")
            return False
    
    def test_auto_scroll(self):
        """Test 3: Auto-scroll to bottom on new messages"""
        print("\n" + "="*80)
        print("TEST 3: Auto-scroll to Bottom")
        print("="*80)
        
        try:
            messages_container = self.driver.find_element(By.ID, "messages")
            
            # Scroll to top first
            self.driver.execute_script("arguments[0].scrollTop = 0", messages_container)
            time.sleep(0.5)
            
            initial_scroll = self.driver.execute_script("return arguments[0].scrollTop", messages_container)
            print(f"  Initial scroll position: {initial_scroll}px")
            
            # Send a test message
            input_field = self.driver.find_element(By.ID, "user-input")
            input_field.send_keys("Test message for auto-scroll")
            
            submit_btn = self.driver.find_element(By.ID, "submit-btn")
            submit_btn.click()
            
            # Wait for message to appear and auto-scroll
            time.sleep(2)
            
            final_scroll = self.driver.execute_script("return arguments[0].scrollTop", messages_container)
            scroll_height = self.driver.execute_script("return arguments[0].scrollHeight", messages_container)
            client_height = self.driver.execute_script("return arguments[0].clientHeight", messages_container)
            
            print(f"  Final scroll position: {final_scroll}px")
            print(f"  Scroll height: {scroll_height}px")
            print(f"  Client height: {client_height}px")
            
            # Check if scrolled to bottom (within 50px tolerance)
            max_scroll = scroll_height - client_height
            if abs(final_scroll - max_scroll) < 50:
                print("\n✓ TEST PASSED: Auto-scroll to bottom works")
                self.results["passed"].append("Auto-scroll to bottom")
                return True
            else:
                print(f"\n✗ TEST FAILED: Not scrolled to bottom (off by {abs(final_scroll - max_scroll)}px)")
                self.results["failed"].append("Auto-scroll to bottom")
                return False
                
        except Exception as e:
            print(f"\n✗ TEST ERROR: {e}")
            self.results["failed"].append(f"Auto-scroll: {e}")
            return False
    
    def test_no_duplicate_messages(self):
        """Test 4: No duplicate messages"""
        print("\n" + "="*80)
        print("TEST 4: No Duplicate Messages")
        print("="*80)
        
        try:
            # Get all message IDs
            messages = self.driver.find_elements(By.CLASS_NAME, "message")
            message_ids = [msg.get_attribute('id') for msg in messages if msg.get_attribute('id')]
            
            print(f"  Total messages: {len(messages)}")
            print(f"  Messages with IDs: {len(message_ids)}")
            
            # Check for duplicates
            unique_ids = set(message_ids)
            
            if len(message_ids) == len(unique_ids):
                print("  ✓ All message IDs are unique")
                print("\n✓ TEST PASSED: No duplicate messages")
                self.results["passed"].append("No duplicate messages")
                return True
            else:
                duplicates = len(message_ids) - len(unique_ids)
                print(f"  ✗ Found {duplicates} duplicate message IDs")
                print("\n✗ TEST FAILED: Duplicate messages detected")
                self.results["failed"].append("No duplicate messages")
                return False
                
        except Exception as e:
            print(f"\n✗ TEST ERROR: {e}")
            self.results["failed"].append(f"Duplicate messages: {e}")
            return False
    
    def test_css_properties(self):
        """Test 5: CSS properties are correctly applied"""
        print("\n" + "="*80)
        print("TEST 5: CSS Properties")
        print("="*80)
        
        try:
            messages = self.driver.find_elements(By.CLASS_NAME, "message")
            
            if not messages:
                print("  ⚠ No messages to test CSS")
                self.results["warnings"].append("CSS properties: No messages")
                return True
            
            first_message = messages[0]
            
            # Check critical CSS properties
            checks = {
                "display": "block",
                "position": "relative",
                "margin-bottom": "20px"
            }
            
            all_correct = True
            for prop, expected in checks.items():
                actual = first_message.value_of_css_property(prop)
                print(f"  {prop}: {actual} (expected: {expected})")
                
                if prop == "margin-bottom":
                    # Extract numeric value
                    actual_num = float(actual.replace('px', ''))
                    expected_num = float(expected.replace('px', ''))
                    if abs(actual_num - expected_num) > 1:
                        print(f"    ✗ Incorrect value")
                        all_correct = False
                    else:
                        print(f"    ✓ Correct")
                elif actual != expected:
                    print(f"    ✗ Incorrect value")
                    all_correct = False
                else:
                    print(f"    ✓ Correct")
            
            if all_correct:
                print("\n✓ TEST PASSED: CSS properties correctly applied")
                self.results["passed"].append("CSS properties")
                return True
            else:
                print("\n✗ TEST FAILED: Some CSS properties incorrect")
                self.results["failed"].append("CSS properties")
                return False
                
        except Exception as e:
            print(f"\n✗ TEST ERROR: {e}")
            self.results["failed"].append(f"CSS properties: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("="*80)
        print("MURPHY UI BUG FIX TESTING")
        print("="*80)
        
        if not self.setup_driver():
            print("\n⚠ Selenium tests skipped (Chrome not available)")
            print("  Running manual verification tests instead...")
            return self.run_manual_tests()
        
        try:
            # Run all tests
            self.test_message_spacing()
            self.test_scrolling()
            self.test_auto_scroll()
            self.test_no_duplicate_messages()
            self.test_css_properties()
            
        finally:
            if self.driver:
                self.driver.quit()
        
        # Print summary
        self.print_summary()
        
        return len(self.results["failed"]) == 0
    
    def run_manual_tests(self):
        """Run manual verification tests (no Selenium)"""
        print("\n" + "="*80)
        print("MANUAL VERIFICATION TESTS")
        print("="*80)
        
        # Test 1: Check HTML file exists
        print("\nTest 1: HTML file exists")
        try:
            with open('murphy_ui_fixed_bugs.html', 'r') as f:
                content = f.read()
            print("  ✓ murphy_ui_fixed_bugs.html exists")
            self.results["passed"].append("HTML file exists")
        except:
            print("  ✗ murphy_ui_fixed_bugs.html not found")
            self.results["failed"].append("HTML file exists")
            return False
        
        # Test 2: Check CSS fixes are present
        print("\nTest 2: CSS fixes present")
        css_checks = [
            ("margin-bottom: 20px", "Message spacing"),
            ("clear: both", "Clear float"),
            ("display: block", "Block display"),
            ("overflow-y: auto", "Scrolling enabled"),
            ("max-height: calc(100vh - 250px)", "Height constraint"),
        ]
        
        for check, desc in css_checks:
            if check in content:
                print(f"  ✓ {desc}: {check}")
                self.results["passed"].append(desc)
            else:
                print(f"  ✗ {desc}: {check} NOT FOUND")
                self.results["failed"].append(desc)
        
        # Test 3: Check JavaScript fixes
        print("\nTest 3: JavaScript fixes present")
        js_checks = [
            ("messageId", "Unique message IDs"),
            ("setTimeout", "Auto-scroll delay"),
            ("scrollTop = scrollHeight", "Scroll to bottom"),
        ]
        
        for check, desc in js_checks:
            if check in content:
                print(f"  ✓ {desc}: {check}")
                self.results["passed"].append(desc)
            else:
                print(f"  ✗ {desc}: {check} NOT FOUND")
                self.results["failed"].append(desc)
        
        self.print_summary()
        return len(self.results["failed"]) == 0
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total = len(self.results["passed"]) + len(self.results["failed"])
        passed = len(self.results["passed"])
        failed = len(self.results["failed"])
        warnings = len(self.results["warnings"])
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({(passed/total*100) if total > 0 else 0:.1f}%)")
        print(f"Failed: {failed} ({(failed/total*100) if total > 0 else 0:.1f}%)")
        print(f"Warnings: {warnings}")
        
        if self.results["passed"]:
            print("\n✓ PASSED TESTS:")
            for test in self.results["passed"]:
                print(f"  - {test}")
        
        if self.results["failed"]:
            print("\n✗ FAILED TESTS:")
            for test in self.results["failed"]:
                print(f"  - {test}")
        
        if self.results["warnings"]:
            print("\n⚠ WARNINGS:")
            for warning in self.results["warnings"]:
                print(f"  - {warning}")
        
        print("\n" + "="*80)
        
        if failed == 0:
            print("✅ ALL TESTS PASSED")
        else:
            print(f"❌ {failed} TEST(S) FAILED")
        
        print("="*80)

if __name__ == "__main__":
    tester = UIBugFixTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
