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

    print("===================================================================================================================")
    for i in links:
        print("")
        print(i)
        print("")

    print("===================================================================================================================")
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

        # --- LLM 2: Apply to the job ---
        history = []
        while True:
            elements_info = await navigator.get_page_elements()

            resume_file_path = "/home/neel/Desktop/HyperLink/Automatic Job Selection/Linked IN/Agents/rendercv-engineeringresumes-theme.pdf"

            system_message_apply = SystemMessage(content=f"""
                ROLE: Job Application Agent

                OBJECTIVE:
                Your task is to complete the 'Easy Apply' job application flow for the current job post.

                STRATEGY:
                Look at history and begin from remaining steps, adapting to how many steps the form has (could be 1 or 10). After each action, record which **step** was completed in the history. Use this to resume properly if interrupted.

                STEPS:
                1. Detect and click the "Easy Apply" button to open the application modal.
                2. On the first page:
                    - Fill known fields like:
                        - Mobile Phone Number → via `fill_input_field`
                                                 
                3. Click the "Next" button to proceed.
                4. If asked to upload a resume:
                    - Use the `upload_resume` tool.
                    - Upload file from:
                        - Path: {resume_file_path}
                    - Then click "Next".
                5. On subsequent pages, handle all other input questions:
                    - Use `fill_dynamic_input_field` to type answers into text fields.
                    - Use logical defaults when answers aren't specified:
                        - "Are you legally authorized to work?" → Yes
                        - "Do you need visa sponsorship?" → No
                        - "Are you okay with onsite work?" → Yes
                6. Continue pressing "Next" after completing each step.
                7. When there's no "Next" but a "Review" button, click "Review".
                8. Finally, click "Submit" to finish the application.
                9. Then return to the job list at: {job_list_url}

                TOOL USAGE RULES:
                - Only one tool call per response.
                - Do NOT explain your reasoning.
                - If a tool fails (e.g., `click_element`), try another (e.g., scroll, then retry).
                - Use `post_click_selector` to wait after clicks when necessary.
                - For resume upload:
                    - First click "Upload Resume" using `click_element`, then call `upload_resume`.
                - For unknown questions or custom input fields:
                    - Use `fill_dynamic_input_field(field_label, answer)` — infer answers if needed.
                - Log your progress step-by-step in history:
                    - Example:
                        - Step 1: Clicked Easy Apply → Success
                        - Step 2: Filled phone/email → Success
                        - Step 3: Clicked Next → Success
                - Resume based on this history log.
                    - If a step is done, skip it.
                    - If a step failed, retry or adapt — do NOT go backward.

                CONTEXT:
                - Recent tool call history:
                    {history or "None"}
                - According to history, do not repeat successful steps.
                - If a step has an error, recover intelligently and proceed.

                RULES:
                - Be robust to DOM changes and dynamic fields.
                - If steps are skipped or merged on one page, adapt accordingly.
                - If application is submitted or you return to the job list, end the loop.

                CURRENT JOB: #{job_idx + 1}
                CURRENT PAGE: Job Detail Page or Application Modal
            """)

            human_message_apply = HumanMessage(content=f"DOM snapshot: {json.dumps(elements_info)[:6000]}")

            try:
                response_apply = await model_apply.ainvoke([system_message_apply, human_message_apply])
                if not response_apply.tool_calls:
                    print("⚠️ No tool call made — stopping Easy Apply flow.")
                    break

                tool_call = response_apply.tool_calls[0]
                tool_name = tool_call['name']
                tool_args = tool_call['args']

                print("")
                print(f"LLM Decision: 🤖 Tool selected: {tool_name}, Args: {tool_args}")
                print("")

                tool = next((t for t in tools if t.name == tool_name), None)
                if tool:
                    try:
                        result = await tool.ainvoke(tool_args)
                        print(f"🔧 Tool result: {result}")
                        print(f"✅ Tool executed: {tool_name}")
                        history.append(f"{tool_name}({tool_args}) → {result}")
                        
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"❌ Tool execution failed: {e}")
                        history.append(f"{tool_name}({tool_args}) → ERROR: {str(e)}")
                        break

                    # Check if we've navigated back to job list
                    if tool_name == "navigate_to_url" and job_list_url in tool_args.get("url", ""):
                        print("🔁 Back on job list page.")
                        break
                else:
                    print(f"❌ Tool not found: {tool_name}")
                    history.append(f"{tool_name}({tool_args}) → ERROR: Tool not found")
                    break
            except Exception as e:
                print(f"❌ Error in model_apply invocation: {e}")
                history.append(f"ERROR: Model invocation failed: {str(e)}")
                break

    return "done_applying"