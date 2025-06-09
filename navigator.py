import asyncio
import json
from playwright.async_api import async_playwright
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Dict, Any, List, Optional
from config import TARGET_URL, GEMINI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from llm_action import ask_llm_for_action_with_tools

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    google_api_key=GEMINI_API_KEY,
    temperature=0.1
) if GEMINI_API_KEY else None

class LinkedInJobsNavigator:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.current_step = "initial"
        self.human_intervention_needed = False
        self.playwright = None
        self.page_elements = {}
        self.action_history = []
        self.max_history = 10
        
    async def setup_browser(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1000)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()   
        
    async def check_page_state(self):
        """Check if page is still valid and accessible"""
        try:
            if not self.page or self.page.is_closed():
                return False
            await self.page.evaluate("() => document.readyState")
            return True
        except Exception as e:
            print(f"Page state check failed: {e}")
            return False
    
    async def wait_for_page_stable(self, timeout=10):
        """Wait for page to be stable and ready for interaction"""
        try:
            await self.page.wait_for_load_state('domcontentloaded', timeout=timeout*1000)
            await asyncio.sleep(2)
            return True
        except Exception as e:
            print(f"Page stability wait failed: {e}")
            return False
        
    async def get_page_elements(self):
        """Extract page elements and return structured data with error handling"""
        try:
            if not await self.check_page_state():
                print("Page is not accessible, waiting for stability...")
                if not await self.wait_for_page_stable():
                    raise Exception("Page became inaccessible")
            
            await asyncio.sleep(3)
            
            current_url = self.page.url
            page_title = await self.page.title()
            
            button_data = []
            link_data = []
            input_data = []
            
            # Get buttons with error handling
            try:
                buttons = await self.page.query_selector_all('button')
                for i, button in enumerate(buttons):
                    try:
                        text = await button.text_content()
                        onclick = await button.get_attribute('onclick')
                        css_class = await button.get_attribute('class')
                        if text and text.strip():
                            button_data.append({
                                'index': i+1,
                                'text': text.strip(),
                                'onclick': onclick,
                                'class': css_class
                            })
                    except Exception as e:
                        print(f"Error processing button {i}: {e}")
                        continue    # Define tools for the LLM to use
            except Exception as e:
                print(f"Error getting buttons: {e}")
                buttons = []
                
            # Get links with error handling
            try:
                links = await self.page.query_selector_all('a')
                for i, link in enumerate(links):
                    try:
                        text = await link.text_content()
                        href = await link.get_attribute('href')
                        if text and text.strip():
                            link_data.append({
                                'index': i+1,
                                'text': text.strip(),
                                'href': href
                            })
                    except Exception as e:
                        print(f"Error processing link {i}: {e}")
                        continue
            except Exception as e:
                print(f"Error getting links: {e}")
                links = []
                
            # Get inputs with error handling
            try:
                inputs = await self.page.query_selector_all('input')
                for i, input_elem in enumerate(inputs):
                    try:
                        input_type = await input_elem.get_attribute('type')
                        placeholder = await input_elem.get_attribute('placeholder')
                        name = await input_elem.get_attribute('name')
                        id_attr = await input_elem.get_attribute('id')
                        is_visible = await input_elem.is_visible()
                        is_enabled = await input_elem.is_enabled()
                        
                        input_data.append({
                            'index': i+1,
                            'type': input_type,
                            'placeholder': placeholder,
                            'name': name,
                            'id': id_attr,
                            'visible': is_visible,
                            'enabled': is_enabled
                        })
                    except Exception as e:
                        print(f"Error processing input {i}: {e}")
                        continue
            except Exception as e:
                print(f"Error getting inputs: {e}")
                inputs = []
            
            elements_info = {
                'current_url': current_url,
                'page_title': page_title,
                'buttons': button_data,
                'links': link_data,
                'inputs': input_data,
                'total_buttons': len(buttons) if 'buttons' in locals() else 0,
                'total_links': len(links) if 'links' in locals() else 0,
                'total_inputs': len(inputs) if 'inputs' in locals() else 0
            }
            
            # Store for tool access
            self.page_elements = elements_info
            return elements_info
            
        except Exception as e:
            print(f"Critical error in get_page_elements: {e}")
            try:
                current_url = self.page.url if self.page else "unknown"
                page_title = await self.page.title() if self.page else "unknown"
            except:
                current_url = "unknown"
                page_title = "unknown"
                
            error_info = {
                'current_url': current_url,
                'page_title': page_title,
                'buttons': [],
                'links': [],
                'inputs': [],
                'total_buttons': 0,
                'total_links': 0,
                'total_inputs': 0,
                'error': str(e)
            }
            self.page_elements = error_info
            return error_info

    def is_verification_page(self, elements_info):
        """Check if current page is security verification/challenge page"""
        current_url = elements_info['current_url']
        page_title = elements_info['page_title'].lower()
        
        verification_indicators = [
            'checkpoint' in current_url,
            'challenge' in current_url,
            'verification' in current_url,
            'captcha' in current_url,
            'security verification' in page_title,
            'challenge' in page_title,
            'verify' in page_title,
            'robot' in page_title
        ]
        
        return any(verification_indicators)

    async def wait_for_human_verification(self, elements_info):
        """Handle human verification step"""
        print("\n" + "="*80)
        print("SECURITY VERIFICATION DETECTED")
        print("="*80)
        
        input("\nPress ENTER after completing verification manually...")
        
        print("\nContinuing automation...")
        self.human_intervention_needed = False
        
        await self.wait_for_page_stable(timeout=15)
        return True

    def add_to_history(self, action_type, details, result):
        """Add an action to history with timestamp"""
        history_entry = {
            'step': len(self.action_history) + 1,
            'action_type': action_type,
            'details': details,
            'result': result,
            'current_step': self.current_step
        }
        self.action_history.append(history_entry)
        
        # Keep only recent history
        if len(self.action_history) > self.max_history:
            self.action_history = self.action_history[-self.max_history:]
    
    async def navigate_to_jobs(self):
        """Main navigation flow with tool calling"""
        await self.setup_browser()
        
        try:
            print(f"Starting navigation to {TARGET_URL}")
            await self.page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=60000)
            await self.wait_for_page_stable()
            
            max_steps = 25
            step_count = 0
            consecutive_errors = 0
            
            while step_count < max_steps and consecutive_errors < 3:
                step_count += 1
                print(f"\n{'='*20}")
                print(f"STEP {step_count}")
                print(f"{'='*20}")
                
                try:
                    # Extract current page elements
                    elements_info = await self.get_page_elements()
                    
                    if 'error' in elements_info:
                        print(f"Page extraction error: {elements_info['error']}")
                        consecutive_errors += 1
                        await asyncio.sleep(5)
                        continue
                    
                    print(f"Current URL: {elements_info['current_url']}")
                    print(f"Page Title: {elements_info['page_title']}")
                    print(f"Found: {elements_info['total_buttons']} buttons, {elements_info['total_links']} links, {elements_info['total_inputs']} inputs")
                    
                    current_url = elements_info['current_url']
                    
                    if "linkedin.com/jobs/search" in current_url:
                        if "f_AL=true" in current_url:
                            if self.current_step != "Applying_Jobs":
                                print("🚀 Easy Apply filter applied — ready to start applying to jobs.")
                                self.current_step = "Applying_Jobs"
                        else:
                            if self.current_step != "filter_easy_apply":
                                print("✅ Reached LinkedIn Jobs Search Results page — ready for Easy Apply filter.")
                                self.current_step = "filter_easy_apply"

                    elif "linkedin.com/jobs" in current_url:
                        if self.current_step != "jobs_section":
                            print("🎉 Reached LinkedIn Jobs landing page.")
                            self.current_step = "jobs_section"

                    elif "linkedin.com/feed" in current_url or "linkedin.com/home" in current_url:
                        if self.current_step != "homepage":
                            print("🏠 At LinkedIn homepage.")
                            self.current_step = "homepage"

                    else:
                        print(f"🌐 Unknown page context for URL: {current_url}")

                    # Handle verification page
                    if self.is_verification_page(elements_info):
                        await self.wait_for_human_verification(elements_info)
                        continue
                    
                    goal = (
                        "Navigate LinkedIn from the homepage to the Jobs section. "
                        "First, sign in using the provided email and password by filling the login form. "
                        "Then, in the Jobs section, use the fill_input_field tool to enter the job title and location. "
                        "After filling both fields, if a visible and enabled search button is found, use click_element tool to click it. "
                        "If no such button is found or clickable, simulate pressing the Enter key in the input field instead to trigger the search. "
                        "After triggering the search, wait for the search results page to load. "
                        "Then, look for the Easy Apply Filter button and press it to apply the filter for searched jobs. "
                        "Once the Easy Apply filter is successfully applied (confirmed by f_AL=true in the URL), proceed to the next step: start applying to jobs. "
                        "Do not ask the user for any inputs. Use tools for all actions."
                    )


                    print("")
                    print("Current Step", self.current_step)

                    # Use LLM with tools
                    print("\n🤖 Asking LLM to determine next action...")
                    action_result = await ask_llm_for_action_with_tools(
                        self,
                        elements_info, 
                        goal, 
                        self.current_step
                    )
                    
                    if action_result == "human_verification":
                        await self.wait_for_human_verification(elements_info)
                    elif action_result in ["tool_executed", "fallback_executed"]:
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                    
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"Error in step {step_count}: {e}")
                    consecutive_errors += 1
                    await asyncio.sleep(5)
                    continue
            
            if consecutive_errors >= 3:
                print("Too many consecutive errors, stopping navigation.")
            elif step_count >= max_steps:
                print("Maximum steps reached, stopping navigation.")
            else:
                print(f"\n🎉 Navigation completed after {step_count} steps!")
            
            print("Browser will remain open for 60 seconds for inspection...")
            await asyncio.sleep(60)
            
        except KeyboardInterrupt:
            print("\nNavigation interrupted by user")
        except Exception as e:
            print(f"Critical error in navigation: {e}")
        finally:
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
