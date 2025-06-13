import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tools import create_tools
from config import GEMINI_API_KEY, RESUME_PATH
import re
from form_fill_agent import FormFillAgent
from form_fill_sub_agent import FormFillSubAgent
from Form_Value_Filler_Agent import FormValueFillerAgent

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

    tools = create_tools(navigator, RESUME_PATH)
    model_click = gemini_model_1.bind_tools(tools)

    print("Filtering Job links ....")
    job_links = await filter_job_links_with_llm(elements_info)
    if not job_links:
        print("⚠️ No job links found after filtering.")
        return "no_jobs_found"

    print("Total Job Links Found Before Filtering locally : ", len(job_links))
    job_links = filter_job_links_locally(job_links)
    print("Total Job Links Found After Filtering locally : ", len(job_links))

    # Import the form filling LLM
    form_agent = FormFillAgent(navigator, gemini_model_2)

    for job_idx, job_link in enumerate(job_links):
        print(f"\n➡️ Processing job #{job_idx + 1}: {job_link}")

        # --- LLM 1: Navigate to job detail page ---
        system_message_click = SystemMessage(content=f"""
            ROLE: Navigation Agent for Job Details

            OBJECTIVE:
            Navigate to a LinkedIn job detail page using the provided URL.

            STRATEGY:
            - Navigate to provided Job Link or URL.     
            - Do NOT attempt to click anything except navigation.
            - Do not apply to the job — only open the job detail page.

            CONSTRAINTS:
            - Use one tool call per response.
            - Do NOT reply with explanations or summaries.

            TARGET JOB LINK:
            {job_link}
        """)

        human_message_click = HumanMessage(content="Navigate to the job detail page.")

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
                        print(f"✅ Navigated to job: {job_link}")
                    except Exception as e:
                        print(f"❌ Failed to navigate to job: {e}")
                        continue
            else:
                print("❌ No tool call made for navigation.")
                continue
        except Exception as e:
            print(f"❌ Error in model_click invocation: {e}")
            continue

        await asyncio.sleep(3)  # Wait for page to load


        user_profile = None   # Questions will be asked to user for creating profile
        result = await form_agent.apply_to_job()
        
        if result == "questions_extracted":
            questions = form_agent.last_extracted_questions
            print("\n" + "="*60)
            print("📋 EXTRACTED QUESTIONS:")
            print("="*60)
            
            # Print the extracted questions first
            for i, q in enumerate(questions, 1):
                print(f"{i}. Question: {q.get('question', 'Unknown')}")
                print(f"   Element ID: {q.get('element_id', 'Unknown')}")
                print(f"   Type: {q.get('element_type', 'Unknown')}")
                if q.get('options'):
                    print(f"   Options: {q.get('options')}")
                print("-" * 40)
            
            print("="*60)
            
            # Initialize and run the simplified form filler
            form_filler = FormFillSubAgent(navigator, gemini_model_2, RESUME_PATH, user_profile)
            answers, analysis_result = await form_filler.answer_and_fill(questions)
            
            print("\nAnswers extracted:")
            for answer in answers:
                print(f"  - {answer.get('question', 'Unknown')}: {answer.get('value', 'None')}")

            form_value_filler = FormValueFillerAgent(navigator, gemini_model_2, RESUME_PATH)
            
            if analysis_result:
                print("\n✅ Form analysis completed successfully")
                
                print("\n🤖 Starting automated form filling and submission...")
                
                completion_success = await form_value_filler.complete_form_process(answers)
                
                if completion_success:
                    print(f"🎉 Successfully completed application for job #{job_idx + 1}")
                else:
                    print(f"❌ Failed to complete application for job #{job_idx + 1}")

            else:
                print("\n❌ Form analysis failed")
            
            
        else:
            print("✅ Application completed or no further form questions.")
            break

        # Wait before processing next job
        await asyncio.sleep(5)

    print(f"\n🏁 Finished processing {len(job_links)} jobs")
    return "processing_complete"