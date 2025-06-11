import asyncio
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from tools import create_tools

class FormFillAgent:

    def __init__(self, navigator, llm_model):
        self.navigator = navigator
        self.llm_model = llm_model

        # Only use click_element tool for now
        self.tools = create_tools(navigator)
        self.model_with_tools = llm_model.bind_tools(self.tools)

        # Optional: user profile retained for future use
        self.user_profile = {
            "name": "Neel Patel",
            "email": "gayic10347@gotemv.com",
            "phone": "9876543210",
            "country_code": "India (+91)",
            "location": "Ahmedabad, Gujarat, India",
            "university": "Pandit Deendayal Energy University",
            "experience": {
                "python": "2 years",
                "javascript": "1 year",
                "react": "1 year",
                "web_development": "2 years"
            }
        }

    async def get_current_page_state(self):
        """Get elements and HTML for Easy Apply modal if loaded"""
        try:
            elements = await self.navigator.get_page_elements()
            form_html = await self.navigator.extract_easy_apply_modal_html()
            return {
                **elements,
                "form_html": form_html
            }
        except Exception as e:
            print(f"❌ Error extracting page state: {e}")
            return await self.navigator.get_page_elements()

    async def apply_to_job(self):
        """Full flow: Click Easy Apply -> Wait -> Extract Questions"""
        system_message = SystemMessage(content=f"""
        ROLE: LinkedIn Easy Apply Form Interaction Agent

        OBJECTIVE:
        Start the job application by clicking the 'Easy Apply' button on a LinkedIn job post.

        STRATEGY:
        1. Find a button with label like "Easy Apply"
        2. Click it using the click_element tool

        RULES:
        - Only use the click_element tool in this step
        - Ignore buttons like "Apply on company site", "Save", or "Share"
        - If form loads, proceed to extract questions from it in the next step
        """)

        # Load page elements
        page_state = await self.navigator.get_page_elements()

        # Create human message context with buttons
        human_message = HumanMessage(content=f"""
        CURRENT PAGE STATE:

        URL: {page_state.get('current_url')}
        TITLE: {page_state.get('page_title')}

        BUTTONS:
        {page_state.get('buttons', [])}
        """)

        try:
            response = await self.model_with_tools.ainvoke([system_message, human_message])

            # Ensure tool call
            if response.tool_calls:
                click_call = response.tool_calls[0]
                tool_name = click_call['name']
                tool_args = click_call['args']

                tool = next((t for t in self.tools if t.name == tool_name), None)
                if tool:
                    print(f"🖱️ Clicking Easy Apply with args: {tool_args}")
                    await tool.ainvoke(tool_args)
                    print("✅ Easy Apply clicked.")
                else:
                    print(f"❌ Tool {tool_name} not found")
                    return "tool_not_found"
            else:
                print("⚠️ LLM did not make a tool call to click Easy Apply")
                return "no_tool_call"

        except Exception as e:
            print(f"❌ Error during Easy Apply click: {e}")
            return "click_error"

        # Wait for modal to load
        await asyncio.sleep(2)

        # Extract updated form state
        page_state = await self.get_current_page_state()
        questions = await self.extract_questions_only(page_state)

        if questions:
            print("📄 Detected Questions:")
            for q in questions:
                print("-", q)
            return "questions_extracted"

        print("⚠️ No questions found in form after clicking Easy Apply.")
        return "no_questions"

    # def extract_questions_with_regex(self, html_content):
    #     """Fallback method to extract questions using regex patterns"""
    #     questions = []
        
    #     # Pattern for labels (most common)
    #     label_pattern = r'<label[^>]*>([^<]+)</label>'
    #     labels = re.findall(label_pattern, html_content, re.IGNORECASE)
        
    #     # Pattern for placeholder text
    #     placeholder_pattern = r'placeholder="([^"]+)"'
    #     placeholders = re.findall(placeholder_pattern, html_content, re.IGNORECASE)
        
    #     # Pattern for legend text (for fieldsets)
    #     legend_pattern = r'<legend[^>]*>([^<]+)</legend>'
    #     legends = re.findall(legend_pattern, html_content, re.IGNORECASE)
        
    #     # Combine and filter
    #     all_questions = labels + placeholders + legends
        
    #     # Filter out common non-question texts
    #     filter_out = [
    #         'required', 'optional', 'submit', 'cancel', 'next', 'previous',
    #         'save', 'continue', 'back', 'close', 'ok', 'yes', 'no'
    #     ]
        
    #     for question in all_questions:
    #         question = question.strip()
    #         if (len(question) > 3 and 
    #             question.lower() not in filter_out and
    #             not question.startswith('<!--') and
    #             'phone country code' not in question.lower()):
    #             questions.append(question)
        
    #     return list(set(questions))  # Remove duplicates

    # def extract_questions_with_beautifulsoup(self, html_content):
    #     """Extract questions using BeautifulSoup for better HTML parsing"""
    #     questions = []
        
    #     try:
    #         soup = BeautifulSoup(html_content, 'html.parser')
            
    #         # Find all labels
    #         labels = soup.find_all('label')
    #         for label in labels:
    #             text = label.get_text(strip=True)
    #             if text and len(text) > 3:
    #                 questions.append(text)
            
    #         # Find input fields with placeholder
    #         inputs = soup.find_all('input', {'placeholder': True})
    #         for input_field in inputs:
    #             placeholder = input_field.get('placeholder', '').strip()
    #             if placeholder and len(placeholder) > 3:
    #                 questions.append(placeholder)
            
    #         # Find select fields with preceding labels or legends
    #         selects = soup.find_all('select')
    #         for select in selects:
    #             # Look for associated label
    #             select_id = select.get('id')
    #             if select_id:
    #                 label = soup.find('label', {'for': select_id})
    #                 if label:
    #                     text = label.get_text(strip=True)
    #                     if text and len(text) > 3:
    #                         questions.append(text)
            
    #         # Find fieldsets with legends
    #         fieldsets = soup.find_all('fieldset')
    #         for fieldset in fieldsets:
    #             legend = fieldset.find('legend')
    #             if legend:
    #                 text = legend.get_text(strip=True)
    #                 if text and len(text) > 3:
    #                     questions.append(text)
            
    #         # Filter out unwanted items
    #         filtered_questions = []
    #         filter_out = [
    #             'required', 'optional', 'submit', 'cancel', 'next', 'previous',
    #             'save', 'continue', 'back', 'close', 'ok', 'yes', 'no'
    #         ]
            
    #         for question in questions:
    #             question = question.strip()
    #             if (len(question) > 3 and 
    #                 question.lower() not in filter_out and
    #                 'phone country code' not in question.lower()):
    #                 filtered_questions.append(question)
            
    #         return list(set(filtered_questions))  # Remove duplicates
            
    #     except Exception as e:
    #         print(f"❌ BeautifulSoup parsing error: {e}")
    #         return []

    async def extract_questions_only(self, page_state):
        """Extract form questions from modal HTML with multiple fallback methods"""
        form_html = page_state.get("form_html", "")
        
        if not form_html:
            print("⚠️ No form HTML found")
            return []

        # Method 1: Try BeautifulSoup first (most reliable)
        # try:
        #     questions = self.extract_questions_with_beautifulsoup(form_html)
        #     if questions:
        #         print(f"✅ BeautifulSoup extracted {len(questions)} questions")
        #         return questions
        # except Exception as e:
        #     print(f"❌ BeautifulSoup method failed: {e}")

        # # Method 2: Try regex patterns
        # try:
        #     questions = self.extract_questions_with_regex(form_html)
        #     if questions:
        #         print(f"✅ Regex extracted {len(questions)} questions")
        #         return questions
        # except Exception as e:
        #     print(f"❌ Regex method failed: {e}")

        # Method 3: Try LLM with better error handling
        try:
            return await self.extract_questions_with_llm(form_html)
        except Exception as e:
            print(f"❌ LLM method failed: {e}")
            return []

    async def extract_questions_with_llm(self, form_html):
        """Extract questions and their element references using LLM"""

        system_message = SystemMessage(content="""
        ROLE: LinkedIn Easy Apply Form Parser

        TASK: Extract form questions AND their corresponding element identifiers from LinkedIn Easy Apply HTML.

        INSTRUCTIONS:
        1. Find form elements: <input>, <select>, <textarea>
        2. For each element, extract:
        - The question text (from associated <label>, placeholder, or nearby text)
        - The element identifier (id, name, or CSS selector)
        - The element type (input, select, textarea)
        3. IGNORE: Phone country code dropdowns, submit buttons, navigation buttons
        4. ONLY extract elements that require user input

        OUTPUT FORMAT: Return ONLY a valid JSON array of objects. Example:
        [
            {
                "question": "Mobile phone number",
                "element_id": "single-line-text-form-component-formElement-urn-li-jobs-123",
                "element_type": "input",
                "selector": "#single-line-text-form-component-formElement-urn-li-jobs-123"
            },
            {
                "question": "Years of experience with Python",
                "element_id": "numeric-form-component-123",
                "element_type": "select",
                "selector": "#numeric-form-component-123"
            }
        ]

        CRITICAL: Your response must be valid JSON format, nothing else.
        """)

        human_message = HumanMessage(content=f"HTML to analyze:\n{form_html}")

        try:
            response = await self.llm_model.ainvoke([system_message, human_message])
            response_content = response.content.strip()

            # Try JSON extraction
            json_match = re.search(r'\[\s*{.*}\s*\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    form_elements = json.loads(json_str)
                    if isinstance(form_elements, list):
                        print(f"✅ LLM extracted {len(form_elements)} form elements")
                        return form_elements
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parsing error: {e}")
                    print(f"LLM raw response (truncated): {response_content[:300]}...")

            # Fallback: try to parse line-by-line text if JSON failed
            form_elements = []
            lines = response_content.split('\n')
            for i, line in enumerate(lines):
                line = line.strip().strip('"').strip("'")
                if len(line) > 3 and not line.startswith(('```', '#', '-', '*', '1.', '2.')):
                    form_elements.append({
                        "question": line,
                        "element_id": f"unknown-element-{i}",
                        "element_type": "input",
                        "selector": f"[data-question*='{line[:20]}']"
                    })

            if form_elements:
                print(f"✅ LLM fallback extracted {len(form_elements)} elements")
                return form_elements

        except Exception as e:
            print(f"❌ Unexpected error during LLM extraction: {e}")

        return []
