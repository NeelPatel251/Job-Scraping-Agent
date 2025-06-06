import asyncio
from langchain_core.tools import tool
from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, JOB_LOCATION, JOB_TITLE


def create_tools(self):
    """Create tools that the LLM can call"""
    
    @tool
    async def click_element(element_type: str, identifier: str, description: str = "") -> str:
        """
        Click on a web element (button, link, etc.)
        
        Args:
            element_type: Type of element ('button', 'link')
            identifier: Text content or unique identifier of the element
            description: Optional description of why clicking this element
        
        Returns:
            Success/failure message
        """
        try:
            if not await self.check_page_state():
                return "Error: Page not accessible"
            
            print(f"🔧 Tool: Clicking {element_type} - {identifier}")
            if description:
                print(f"   Reason: {description}")
            
            if element_type == "link":
                links = await self.page.query_selector_all('a')
                if identifier.isdigit():
                    index = int(identifier)
                    if index < len(links):
                        await links[index].click()
                        await self.wait_for_page_stable()
                        return f"Successfully clicked link at index {index}"
                    return f"Error: No link found at index {index}"
                else:
                    for link in links:
                        text = await link.text_content()
                        href = await link.get_attribute('href')
                        if (text and identifier.lower() in text.lower()) or (href and identifier in href):
                            await link.click()
                            await self.wait_for_page_stable()
                            return f"Successfully clicked link: {text or href}"

            
            elif element_type == "button":
                buttons = await self.page.query_selector_all('button')

                if identifier.isdigit():
                    index = int(identifier)
                    if index < len(buttons):
                        await buttons[index].click()
                        await self.wait_for_page_stable()
                        return f"Successfully clicked button at index {index}"
                    return f"Error: No button found at index {index}"
                
                # First try exact match
                for button in buttons:
                    text = await button.text_content()
                    if text and text.strip().lower() == identifier.lower():
                        await button.click()
                        await self.wait_for_page_stable()
                        return f"Successfully clicked button: {text}"
                
                # Then try substring match (excluding third-party)
                for button in buttons:
                    text = await button.text_content()
                    aria = await button.get_attribute("aria-label") or ""
                    role = await button.get_attribute("role") or ""
                    btn_id = await button.get_attribute("id") or ""

                    if text and identifier.lower() in text.lower():
                        text_lower = text.lower()

                        # Exclude third-party auth buttons
                        if any(third_party in text_lower for third_party in ['apple', 'google', 'facebook', 'microsoft', 'sso', 'continue with']):
                            continue

                        # Prioritize Easy Apply filter buttons
                        if (
                            "easy apply" in text_lower 
                            or "easy apply" in aria.lower()
                            or "searchFilter_applyWithLinkedin" in btn_id
                        ) and role == "radio":
                            await button.click()
                            await self.wait_for_page_stable()
                            self.add_to_history("click_element", f"button: {identifier}", "success")
                            return f"Successfully clicked Easy Apply filter button: {text or aria}"

                        # Fallback to other matches
                        await button.click()
                        await self.wait_for_page_stable()
                        self.add_to_history("click_element", f"button: {identifier}", "success")
                        return f"Successfully clicked button: {text}"
            
            error_msg = f"Error: Could not find {element_type} with identifier '{identifier}'"
            self.add_to_history("click_element", f"{element_type}: {identifier}", "failed")
            return error_msg
            
        except Exception as e:
            return f"Error clicking {element_type}: {str(e)}"

    @tool
    async def fill_input_field(field_identifier: str, value: str, field_type: str = "") -> str:
        """
        Fill an input field with a value
        
        Args:
            field_identifier: ID, name, or type of the input field
            value: Value to fill in the field
            field_type: Type of field (email, password, job_title, location, etc.)
        
        Returns:
            Success/failure message
        """
        try:
            if not await self.check_page_state():
                return "Error: Page not accessible"

            # Handle common autofill cases
            id_lower = field_identifier.lower()
            field_type_lower = field_type.lower()

            if field_type_lower == "email" or "email" in id_lower:
                value = LINKEDIN_EMAIL
                print(f"Value set to {value}")

            if field_type_lower == "password" or "password" in id_lower:
                value = LINKEDIN_PASSWORD
                print(f"Value set to {value}")

            if field_type_lower in ["job_title", "title", "role", "skill", "company"] or any(kw in id_lower for kw in ["job", "title", "skill", "company"]):
                value = JOB_TITLE  
                print(f"Value set to {value}")

            if field_type_lower == "location" or "location" in id_lower:
                value = JOB_LOCATION  
                print(f"Value set to {value}")

            print(f"🔧 Tool: Filling input field - {field_identifier}")
            print(f"   Value: {'*' * len(value) if 'password' in id_lower else value}")

            input_elem = None

            # Try multiple selector strategies
            selectors_to_try = [
                f'#{field_identifier}',
                f'[name="{field_identifier}"]',
                f'[placeholder*="{field_identifier}"]',
                f'[aria-label*="{field_identifier}"]'
            ]

            # Add known selectors for login and job search inputs
            if "email" in id_lower or "username" in id_lower:
                selectors_to_try.extend(['#username', '#session_key', '[name="session_key"]', 'input[type="email"]', '#email'])
            elif "password" in id_lower:
                selectors_to_try.extend(['#password', '[name="session_password"]', 'input[type="password"]'])
            elif field_type_lower in ["job_title", "title", "role", "skill", "company"] or any(kw in id_lower for kw in ["job", "title", "skill", "company"]):
                selectors_to_try.extend([
                    '[id*="search-box-keyword-id"]',
                    '[aria-label*="Search jobs"]',
                    '[placeholder*="Search jobs"]',
                    'input.jobs-search-box__text-input[role="combobox"]'
                ])

            elif "location" in id_lower or field_type_lower == "location":
                selectors_to_try.extend([
                    'input[placeholder*="Location"]',
                    '[aria-label*="Search location"]',
                    '[id*="search-box-location"]',
                    'input[id*="jobs-search-box-location"]'])

            for selector in selectors_to_try:
                try:
                    input_elem = await self.page.query_selector(selector)
                    if input_elem and await input_elem.is_visible():
                        break
                except:
                    continue

            if input_elem:
                await input_elem.click()
                await asyncio.sleep(0.5)
                await input_elem.fill(value)
                await asyncio.sleep(1)
                self.add_to_history("fill_input", f"{field_identifier} ({field_type})", "success")
                return f"Successfully filled input field: {field_identifier}"
            else:
                error_msg = f"Error: Could not find input field '{field_identifier}'"
                self.add_to_history("fill_input", f"{field_identifier} ({field_type})", "failed")
                return error_msg

        except Exception as e:
            return f"Error filling input field: {str(e)}"

    @tool
    async def press_enter_on_input(identifier: str, description: str = "") -> str:
        """
        Press the Enter key inside an input field (e.g. job title or location field).
        
        Args:
            identifier: A unique attribute of the input (e.g. id, placeholder, aria-label)
            description: Optional reason for pressing Enter

        Returns:
            Success/failure message
        """
        try:
            print(f"🔧 Tool: Pressing Enter in input: {identifier}")
            if description:
                print(f"   Reason: {description}")
            
            inputs = await self.page.query_selector_all('input')
            for input_elem in inputs:
                id_attr = await input_elem.get_attribute("id")
                aria_label = await input_elem.get_attribute("aria-label")
                placeholder = await input_elem.get_attribute("placeholder")

                if any(identifier.lower() in (val or "").lower() for val in [id_attr, aria_label, placeholder]):
                    await input_elem.focus()
                    await self.page.keyboard.press("Enter")
                    await self.wait_for_page_stable()
                    return f"Pressed Enter on input with identifier '{identifier}'"

            return f"Error: No input found matching identifier '{identifier}'"
        except Exception as e:
            return f"Error pressing Enter: {str(e)}"
    
    @tool
    async def navigate_to_url(url: str, description: str = "") -> str:
        """
        Navigate directly to a URL
        
        Args:
            url: URL to navigate to
            description: Optional description of why navigating to this URL
        
        Returns:
            Success/failure message
        """
        try:
            print(f"🔧 Tool: Navigating to URL - {url}")
            if description:
                print(f"   Reason: {description}")
            
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await self.wait_for_page_stable()
            return f"Successfully navigated to: {url}"
            
        except Exception as e:
            return f"Error navigating to URL: {str(e)}"

    @tool
    async def wait_and_observe(seconds: int = 5, reason: str = "") -> str:
        """
        Wait for a specified number of seconds and observe page changes
        
        Args:
            seconds: Number of seconds to wait
            reason: Optional reason for waiting
        
        Returns:
            Status message
        """
        print(f"🔧 Tool: Waiting {seconds} seconds")
        if reason:
            print(f"   Reason: {reason}")
        
        await asyncio.sleep(seconds)
        return f"Waited {seconds} seconds"

    @tool
    async def check_page_status() -> str:
        """
        Check current page status and return information
        
        Returns:
            Current page information
        """
        try:
            current_url = self.page.url
            page_title = await self.page.title()
            
            status = f"Current URL: {current_url}\nPage Title: {page_title}"
            
            # Check if we're in jobs section
            if 'jobs' in current_url.lower() and 'linkedin.com' in current_url:
                status += "\n✅ Successfully reached LinkedIn Jobs section!"
            elif 'linkedin.com' in current_url and '/login' not in current_url:
                status += "\n✅ Successfully logged into LinkedIn"
            elif 'login' in current_url:
                status += "\n📝 On LinkedIn login page"
            
            return status
            
        except Exception as e:
            return f"Error checking page status: {str(e)}"

    return [click_element, fill_input_field, navigate_to_url, wait_and_observe, check_page_status, press_enter_on_input]
