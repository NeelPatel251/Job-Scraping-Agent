import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tools import create_tools
from config import OPENAI_API_KEY

gpt4_model = ChatOpenAI(
    model="gpt-4.1", 
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

async def filter_job_links_with_llm(elements_info):
    if not gpt4_model:
        print("No GPT-4 model available for filtering links.")
        return []

    links = elements_info.get("links", [])
    model = gpt4_model

    system_msg = SystemMessage(content="""
        You are a filtering assistant. Your task is to examine all hyperlinks on a LinkedIn job search page and identify only those that correspond to **individual job listings**.

        RULES:
        - Include links that lead directly to job detail views.
        - Exclude any navigation links, profile links, menu items, or anything that is not a job card.
        - Do not include links that point to company pages, sign-in pages, or general categories.
        - Return only valid job links in a JSON array.
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

    print(job_list_url)

    if not gpt4_model:
        print("No GPT-4 model available for applying jobs.")
        return "no_model"

    tools = create_tools(navigator)
    model_with_tools = gpt4_model.bind_tools(tools)

    print("Filtering Job links ....")
    job_links = await filter_job_links_with_llm(elements_info)
    if not job_links:
        print("⚠️ No job links found after filtering.")
        return "no_jobs_found"

    print("Completed Filtering the Job links.")
    job_links = filter_job_links_locally(job_links)
    print(job_links)

    for job_idx, job_link in enumerate(job_links):
        print(f"➡️ Visiting job #{job_idx + 1}")

        # Click on the job card link
        system_message = SystemMessage(content=f"""
                                       
            You are ApplyAgent, responsible for executing the 'Applying_Jobs' step in an autonomous job application workflow.

            GOAL:
            Apply to jobs that offer 'Easy Apply' on LinkedIn.

            CURRENT OBJECTIVE:
            You are currently processing job #{job_idx + 1}.

            STRATEGY:
            1. Click the provided job link to open its detail view.
            2. Wait for the detail page to load.
            3. On the job detail page, look for a button labeled 'Easy Apply' or similar.
            4. If the 'Easy Apply' button is present, click it to begin the application process.
            5. If the button is not present, skip this job and return to the job list page.
            6. Do not attempt to apply if 'Easy Apply' is not available.
            7. After handling this job, return to the job list URL so you can continue with the next job.

            CONSTRAINTS:
            - Do not apply to the same job twice.
            - Only use tools (e.g., click, go_to_url); do not generate text responses.
            - Use only one tool call per LLM response.
            - Be robust to missing elements (e.g., if button click fails, move on).

            IMPORTANT VARIABLES:
            - JOB LIST PAGE URL (to return to after each job): {job_list_url}
            - CURRENT JOB LINK: {json.dumps(job_link)}
        """)

        human_message = HumanMessage(content="Click this job card to view job details.")
        response = model_with_tools.invoke([system_message, human_message])

        if response.tool_calls:
            tool_name = response.tool_calls[0]['name']
            tool_args = response.tool_calls[0]['args']
            print(f"🤖 Tool selected: {tool_name}, Args: {tool_args}")
            for tool in tools:
                if tool.name == tool_name:
                    try:
                        await tool.ainvoke(tool_args)
                        print(f"✅ Opened job #{job_idx + 1}")
                    except Exception as e:
                        print(f"❌ Failed to open job: {e}")
                        continue
        else:
            print("❌ No tool selected to open job.")
            continue

        await asyncio.sleep(2)  # Let the job page load

        # Detect and click Easy Apply
        elements_info = await navigator.get_page_elements()

        apply_buttons = []
        for button in elements_info.get("buttons", []):
            text = button.get("text", "").lower()
            aria_label = button.get("aria_label", "").lower()
            alt_text = button.get("alt", "").lower()
            title = button.get("title", "").lower()

            if any("easy apply" in val for val in [text, aria_label, alt_text, title]):
                apply_buttons.append(button)


        if apply_buttons:
            button = apply_buttons[0]
            try:
                print("🟢 Clicking Easy Apply...")
                for tool in tools:
                    if tool.name == "click":
                        await tool.ainvoke({"element": button, "description": "Clicking Easy Apply to start the job application."})
                        print("✅ Easy Apply clicked.")
                        break
            except Exception as e:
                print(f"⚠️ Could not click Easy Apply: {e}")
        else:
            print("⚠️ No Easy Apply button found.")

        print(f"🔁 Returning to job list page: {job_list_url}")
        for tool in tools:
            if tool.name == "navigate_to_url":
                try:
                    await tool.ainvoke({
                        "url": job_list_url,
                        "description": "Returning to job list page after checking a job."
                    })
                    await asyncio.sleep(1.5)
                    elements_info = await navigator.get_page_elements()
                    break
                except Exception as e:
                    print(f"❌ Failed to return to job list: {e}")
                    return "navigation_failed"

    return "done_applying"