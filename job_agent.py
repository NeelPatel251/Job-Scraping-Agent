import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tools import create_tools
from config import OPENAI_API_KEY

# Two separate LLM instances
gpt4_model_1 = ChatOpenAI(model="gpt-4.1", api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
gpt4_model_2 = ChatOpenAI(model="gpt-4.1", api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

async def filter_job_links_with_llm(elements_info):
    if not gpt4_model_1:
        print("No GPT-4 model available for filtering links.")
        return []

    links = elements_info.get("links", [])
    model = gpt4_model_1

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
    """)

    human_msg = HumanMessage(content=f"""
        Here are the raw page links:

        {json.dumps(links, indent=2)}

        Return ONLY job links as a JSON array of hrefs.
    """)

    response = model.invoke([system_msg, human_msg])

    try:
        filtered = json.loads(response.content)
        return filtered if isinstance(filtered, list) else []
    except Exception as e:
        print(f"❌ Failed to parse filtered links: {e}")
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

async def apply_jobs_with_integrated_gpt4(navigator, elements_info, job_list_url):

    if not gpt4_model_1 or not gpt4_model_2:
        print("GPT-4 models not available.")
        return "no_model"

    tools = create_tools(navigator)
    model_click = gpt4_model_1.bind_tools(tools)
    model_apply = gpt4_model_2.bind_tools(tools)

    print("Filtering Job links ....")
    job_links = await filter_job_links_with_llm(elements_info)
    if not job_links:
        print("⚠️ No job links found after filtering.")
        return "no_jobs_found"

    job_links = filter_job_links_locally(job_links)

    print("Total Job Links Found : ", len(job_links))

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

        response_click = model_click.invoke([system_message_click, human_message_click])
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

        await asyncio.sleep(2)

        # --- LLM 2: Apply to the job ---
        history = []
        while True:
            elements_info = await navigator.get_page_elements()

            recent_tool_history = "\n".join(history[-3:]) or "None"

            system_message_apply = SystemMessage(content=f"""
                ROLE: Job Application Agent

                OBJECTIVE:
                Your task is to complete the 'Easy Apply' job application flow if the button is available.

                STRATEGY:
                1. Look for a button labeled "Easy Apply".
                2. If available, click it to begin the application.
                3. If not present, return to the job list page at: {job_list_url}.
                4. If you begin the application, proceed step-by-step (Next, Submit, etc.).
                5. When application completes or cannot proceed, return to job list page.

                TOOL USAGE INSTRUCTIONS:
                - Use one tool per response.
                - Do NOT provide explanations.
                - If a tool action fails (e.g., click_element fails), try using a different tool to overcome the issue.
                - Be adaptive: retry with a different approach if the first one didn’t work.

                CONTEXT:
                - Tool failures will be reported below for your reasoning.
                - Recent tool history:
                {recent_tool_history or "None"}

                RULES:
                - Each response must make exactly one tool call.
                - Be robust to missing buttons or unexpected content.
                - When you're back on the job list page, stop this job and proceed to next.

                CURRENT JOB: #{job_idx + 1}
                CURRENT PAGE: Job Detail Page or Application Modal
            """)

            human_message_apply = HumanMessage(content=f"DOM snapshot: {json.dumps(elements_info)[:6000]}")

            response_apply = await model_apply.ainvoke([system_message_apply, human_message_apply])
            if not response_apply.tool_calls:
                print("⚠️ No tool call made — stopping Easy Apply flow.")
                break

            tool_call = response_apply.tool_calls[0]
            tool_name = tool_call['name']
            tool_args = tool_call['args']

            print("LLM Decision:")
            print(f"🤖 Tool selected: {tool_name}, Args: {tool_args}")

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

    return "done_applying"
