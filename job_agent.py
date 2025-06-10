# import asyncio
# import json
# from langchain_core.messages import HumanMessage, SystemMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
# from tools import create_tools
# from config import GEMINI_API_KEY
# import re

# # Two separate LLM instances using Gemini
# gemini_model_1 = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash-preview-04-17", 
#     google_api_key=GEMINI_API_KEY,
#     temperature=0.1
# ) if GEMINI_API_KEY else None

# gemini_model_2 = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash-preview-04-17", 
#     google_api_key=GEMINI_API_KEY,
#     temperature=0.1
# ) if GEMINI_API_KEY else None

# async def filter_job_links_with_llm(elements_info):
#     if not gemini_model_1:
#         print("No Gemini model available for filtering links.")
#         return []

#     links = elements_info.get("links", [])

#     model = gemini_model_1

#     system_msg = SystemMessage(content="""
#         You are a smart filtering assistant.

#         TASK: Given a list of hyperlinks from a LinkedIn job search results page, return **only** those URLs that point to individual job listings.

#         INCLUDE:
#         - Links to job detail pages (usually contain '/jobs/view/' in the path).

#         EXCLUDE:
#         - Navigation links
#         - Company profile links
#         - Category or location filters
#         - Sign-in, help, or menu pages

#         FORMAT: Return the list of job URLs as a JSON array of strings.
#         IMPORTANT: Do NOT wrap it in markdown or code blocks like ```json.
#     """)

#     human_msg = HumanMessage(content=f"""
#         Here are the raw page links:

#         {json.dumps(links, indent=2)}

#         Return ONLY job links as a JSON array of hrefs (like ["/jobs/view/...", ...]).
#         Do NOT wrap the output in triple backticks.
#     """)

#     try:
#         response = await model.ainvoke([system_msg, human_msg])
#         raw_output = response.content.strip()

#         # Remove markdown code block if present (Gemini often adds these)
#         if raw_output.startswith("```"):
#             raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
#             raw_output = re.sub(r"\s*```$", "", raw_output)

#         filtered = json.loads(raw_output)
#         return filtered if isinstance(filtered, list) else []

#     except Exception as e:
#         print(f"❌ Failed to parse filtered links: {e}")
#         print(f"🔎 Raw output was: {repr(response.content)}")
#         return []

# def filter_job_links_locally(raw_links: list[str]) -> list[str]:
#     seen = set()
#     job_links = []

#     for link in raw_links:
#         if not isinstance(link, str):
#             continue

#         if link.startswith("/jobs/view/"):
#             full_url = f"https://www.linkedin.com{link}"
#         elif link.startswith("https://www.linkedin.com/jobs/view/"):
#             full_url = link
#         else:
#             continue  

#         if full_url not in seen:
#             seen.add(full_url)
#             job_links.append(full_url)

#     return job_links

# def format_history(history):
#     return "\n".join(
#         f"{idx + 1}. Tool: {entry['tool']} | Args: {entry['args']}" 
#         for idx, entry in enumerate(history)
#     )

# async def apply_jobs_with_integrated_gemini(navigator, elements_info, job_list_url):

#     if not gemini_model_1 or not gemini_model_2:
#         print("Gemini models not available.")
#         return "no_model"

#     tools = create_tools(navigator)
#     model_click = gemini_model_1.bind_tools(tools)
#     model_apply = gemini_model_2.bind_tools(tools)

#     print("Filtering Job links ....")
#     job_links = await filter_job_links_with_llm(elements_info)
#     if not job_links:
#         print("⚠️ No job links found after filtering.")
#         return "no_jobs_found"

#     print("Total Job Links Found Before Filtering locally : ", len(job_links))
#     job_links = filter_job_links_locally(job_links)
#     print("Total Job Links Found After Filtering locally : ", len(job_links))

#     for job_idx, job_link in enumerate(job_links):
#         print(f"\n➡️ Processing job #{job_idx + 1}")

#         # --- LLM 1: Click the job link ---
#         system_message_click = SystemMessage(content=f"""
#             ROLE: Navigation Agent for Job Details

#             OBJECTIVE:
#             Navigate to a LinkedIn job detail page using the provided URL.

#             STRATEGY:
#             - Navigate to provided Job Link or URL.     
#             - Do NOT attempt to click anything.
#             - Do not apply to the job — only open the job detail page.

#             CONSTRAINTS:
#             - Use one tool call per response.
#             - Do NOT reply with explanations or summaries.

#             TARGET JOB LINK:
#             {job_link}
#         """)

#         human_message_click = HumanMessage(content="Click the job card to open job detail page.")

#         try:
#             response_click = await model_click.ainvoke([system_message_click, human_message_click])
#             if response_click.tool_calls:
#                 tool_call = response_click.tool_calls[0]
#                 tool_name = tool_call['name']
#                 tool_args = tool_call['args']

#                 tool = next((t for t in tools if t.name == tool_name), None)
#                 if tool:
#                     try:
#                         await tool.ainvoke(tool_args)
#                         print(f"✅ Job link clicked: {job_link}")
#                     except Exception as e:
#                         print(f"❌ Failed to click job link: {e}")
#                         continue
#             else:
#                 print("❌ No tool call made for clicking job.")
#                 continue
#         except Exception as e:
#             print(f"❌ Error in model_click invocation: {e}")
#             continue

#         await asyncio.sleep(2)

#         # --- LLM 2: Apply to the job with FormFillAgent ---

import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tools import create_tools
from config import GEMINI_API_KEY
import re

# Two separate LLM instances using Gemini
gemini_model_1 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17", 
    google_api_key=GEMINI_API_KEY,
    temperature=0.1
) if GEMINI_API_KEY else None

gemini_model_2 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17", 
    google_api_key=GEMINI_API_KEY,
    temperature=0.1
) if GEMINI_API_KEY else None

async def filter_job_links_with_llm(elements_info):
    if not gemini_model_1:
        print("No Gemini model available for filtering links.")
        return []

    links = elements_info.get("links", [])

    model = gemini_model_1

    system_msg = SystemMessage(content="""
        You are a smart filtering assistant.

        TASK: Given a list of hyperlinks from a LinkedIn job search results page, return **only** those URLs that point to individual job listings.

        INCLUDE:
        - Links to job detail pages (usually contain '/jobs/view/' in the path).

        EXCLUDE:
        - Navigation links
        - Company profile links
        - Category or location filters
        - Sign-in, help, or menu pages

        FORMAT: Return the list of job URLs as a JSON array of strings.
        IMPORTANT: Do NOT wrap it in markdown or code blocks like ```json.
    """)

    human_msg = HumanMessage(content=f"""
        Here are the raw page links:

        {json.dumps(links, indent=2)}

        Return ONLY job links as a JSON array of hrefs (like ["/jobs/view/...", ...]).
        Do NOT wrap the output in triple backticks.
    """)

    try:
        response = await model.ainvoke([system_msg, human_msg])
        raw_output = response.content.strip()

        # Remove markdown code block if present (Gemini often adds these)
        if raw_output.startswith("```"):
            raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
            raw_output = re.sub(r"\s*```$", "", raw_output)

        filtered = json.loads(raw_output)
        return filtered if isinstance(filtered, list) else []

    except Exception as e:
        print(f"❌ Failed to parse filtered links: {e}")
        print(f"🔎 Raw output was: {repr(response.content)}")
        return []

def filter_job_links_locally(raw_links: list[str]) -> list[str]:
    seen = set()
    job_links = []

    for link in raw_links:
        if not isinstance(link, str):
            continue

        if link.startswith("/jobs/view/"):
            full_url = f"https://www.linkedin.com{link}"
        elif link.startswith("https://www.linkedin.com/jobs/view/"):
            full_url = link
        else:
            continue  

        if full_url not in seen:
            seen.add(full_url)
            job_links.append(full_url)

    return job_links

def format_history(history):
    return "\n".join(
        f"{idx + 1}. Tool: {entry['tool']} | Args: {entry['args']}" 
        for idx, entry in enumerate(history)
    )

async def apply_jobs_with_integrated_gemini(navigator, elements_info, job_list_url):

    if not gemini_model_1 or not gemini_model_2:
        print("Gemini models not available.")
        return "no_model"

    tools = create_tools(navigator)
    model_click = gemini_model_1.bind_tools(tools)
    model_apply = gemini_model_2.bind_tools(tools)

    print("Filtering Job links ....")
    job_links = await filter_job_links_with_llm(elements_info)
    if not job_links:
        print("⚠️ No job links found after filtering.")
        return "no_jobs_found"

    print("Total Job Links Found Before Filtering locally : ", len(job_links))
    job_links = filter_job_links_locally(job_links)
    print("Total Job Links Found After Filtering locally : ", len(job_links))

    for job_idx, job_link in enumerate(job_links):
        print(f"\n➡️ Processing job #{job_idx + 1}")

        # --- LLM 1: Click the job link ---
        system_message_click = SystemMessage(content=f"""
            ROLE: Navigation Agent for Job Details

            OBJECTIVE:
            Navigate to a LinkedIn job detail page using the provided URL.

            STRATEGY:
            - Navigate to provided Job Link or URL.     
            - Do NOT attempt to click anything.
            - Do not apply to the job — only open the job detail page.

            CONSTRAINTS:
            - Use one tool call per response.
            - Do NOT reply with explanations or summaries.

            TARGET JOB LINK:
            {job_link}
        """)

        human_message_click = HumanMessage(content="Click the job card to open job detail page.")

        try:
            response_click = await model_click.ainvoke([system_message_click, human_message_click])
            if response_click.tool_calls:
                tool_call = response_click.tool_calls[0]
                tool_name = tool_call['name']
                tool_args = tool_call['args']

                tool = next((t for t in tools if t.name == tool_name), None)
                if tool:
                    try:
                        await tool.ainvoke(tool_args)
                        print(f"✅ Job link clicked: {job_link}")
                    except Exception as e:
                        print(f"❌ Failed to click job link: {e}")
                        continue
            else:
                print("❌ No tool call made for clicking job.")
                continue
        except Exception as e:
            print(f"❌ Error in model_click invocation: {e}")
            continue

        await asyncio.sleep(2)

        # --- LLM 2: Apply to the job with FormFillAgent ---
        
        system_message_apply = SystemMessage(content=f"""
            ROLE: LinkedIn Easy Apply FormFill Agent

            OBJECTIVE:
            Complete a LinkedIn Easy Apply job application by:
            1. Click the "Easy Apply" button
            2. Fill out all form fields using the form_fill_tool
            3. Upload resume if needed using upload_resume_tool
            4. Navigate through form pages using click_element_tool (Next/Review/Submit)
            5. Submit the final application

            USER PROFILE DATA:
            - Name: Neel Patel
            - Email: gayic10347@gotemv.com
            - Phone: 9876543210
            - Country Code: India (+91)
            - Location: Ahmedabad, Gujarat, India
            - University: Pandit Deendayal Energy University
            - Experience: Python (2 years), JavaScript (1 year), React (1 year) etc

            STRATEGY:
            1. First click "Easy Apply" button using click_element_tool
            2. Use form_fill_tool to fill all visible form fields
            3. Use upload_resume_tool if resume upload is required
            4. Use click_element_tool to click Next/Review/Submit buttons
            5. Repeat until application is submitted

            FORM FILLING RULES:
            - Email fields: gayic10347@gotemv.com
            - Phone fields: 9876543210
            - Country code: India (+91)
            - Name fields: Neel Patel
            - Location: Ahmedabad, Gujarat, India
            - University: Pandit Deendayal Energy University
            - Experience questions: Answer based on years (Python: 2, JavaScript: 1, React: 1)
            - Text areas: Provide brief professional responses
            - Yes/No questions: Answer appropriately based on context

            CONSTRAINTS:
            - Use one tool call per response
            - Focus on completing the application step by step
            - Handle each form page sequentially
        """)

        # Start the application process
        application_history = []
        max_steps = 15  # Prevent infinite loops
        step_count = 0
        application_completed = False

        while step_count < max_steps and not application_completed:
            step_count += 1
            print(f"📝 Application step {step_count}")

            # Get current page state
            current_page_elements = await navigator.get_page_elements()
            
            # Create context for current step
            step_context = f"""
            STEP {step_count} - Current Page State:
            
            URL: {current_page_elements.get('current_url', 'Unknown')}
            Page Title: {current_page_elements.get('page_title', 'Unknown')}
            
            Available Elements:
            - Buttons: {json.dumps([btn for btn in current_page_elements.get('buttons', [])[:8]], indent=2)}
            - Input Fields: {json.dumps([inp for inp in current_page_elements.get('inputs', [])[:8]], indent=2)}
            
            Previous Actions: {format_history(application_history)}
            
            INSTRUCTIONS:
            Analyze the current page and take the next appropriate action:
            - If you see "Easy Apply" button, click it
            - If you see form fields, fill them using form_fill_tool
            - If you see file upload for resume, use upload_resume_tool
            - If you see Next/Review/Submit buttons, click them using click_element_tool
            - Focus on one action at a time
            """

            human_message_apply = HumanMessage(content=step_context)

            try:
                response_apply = await model_apply.ainvoke([system_message_apply, human_message_apply])
                
                if response_apply.tool_calls:
                    tool_call = response_apply.tool_calls[0]
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    # Record the action
                    application_history.append({
                        'step': step_count,
                        'tool': tool_name,
                        'args': tool_args
                    })

                    tool = next((t for t in tools if t.name == tool_name), None)
                    if tool:
                        try:
                            result = await tool.ainvoke(tool_args)
                            print(f"✅ Step {step_count}: {tool_name} executed")
                            
                            # Check if application was submitted
                            if ("submit" in str(result).lower() and "application" in str(result).lower()) or \
                               ("successfully" in str(result).lower() and "submitted" in str(result).lower()):
                                print("🎉 Application submitted successfully!")
                                application_completed = True
                                break
                                
                        except Exception as e:
                            print(f"❌ Step {step_count}: Failed to execute {tool_name}: {e}")
                            
                    else:
                        print(f"❌ Step {step_count}: Tool {tool_name} not found")
                        
                else:
                    print(f"❌ Step {step_count}: No tool call made")
                    break

                # Wait between steps
                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ Error in step {step_count}: {e}")
                break

        # Summary of application attempt
        if application_completed:
            print(f"✅ Job application completed successfully in {step_count} steps")
        else:
            print(f"⚠️ Job application process stopped after {step_count} steps")
            
        print(f"📋 Application Summary for job #{job_idx + 1}:")
        for action in application_history[-3:]:  # Show last 3 actions
            print(f"  - Step {action['step']}: {action['tool']} - {action['args']}")

        # Wait before processing next job
        await asyncio.sleep(3)

    print(f"\n🏁 Finished processing {len(job_links)} jobs")
    return "processing_complete"
