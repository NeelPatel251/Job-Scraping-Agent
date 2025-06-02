import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GEMINI_API_KEY, JOB_LOCATION, JOB_TITLE
from tools import create_tools

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    google_api_key=GEMINI_API_KEY,
    temperature=0.1
) if GEMINI_API_KEY else None


async def ask_llm_for_action_with_tools(navigator_instance, elements_info, goal, current_step):
    """Router: Dispatches to the appropriate sub-agent based on current_step"""
    if navigator_instance.is_verification_page(elements_info):
        return "human_verification"

    if not model:
        print("No LLM available, using fallback logic...")
        return await navigator_instance.execute_fallback_action(elements_info, current_step)

    try:
        if current_step.startswith("login") or current_step.startswith("fill") or current_step == "submit_login":
            return await ask_login_agent(navigator_instance, elements_info, goal, current_step)
        elif current_step.startswith("jobs_section"):
            return await ask_jobs_agent(navigator_instance, elements_info, goal, current_step)
        elif current_step.startswith("search_jobs") or current_step in ["fill_job_title", "fill_location", "search_submitted"]:
            return await ask_search_agent(navigator_instance, elements_info, goal, current_step)
        elif current_step == "filter_easy_apply":
            return await ask_filter_agent(navigator_instance, elements_info, goal, current_step)
        elif current_step.startswith("easy_apply"):
            return await ask_easy_apply_agent(navigator_instance, elements_info, goal, current_step)
        else:
            return await ask_generic_agent(navigator_instance, elements_info, goal, current_step)

    except Exception as e:
        print(f"❌ Sub-agent error: {e}")
        return await navigator_instance.execute_fallback_action(elements_info, current_step)


async def ask_login_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="LoginAgent",
        extra_instruction="""
        1. Fill email input field first.
        2. Then fill password.
        3. Finally, click the "Sign in" button.
        4. Never click 'Continue with Google' or similar.
        """
    )

async def ask_jobs_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="JobsSectionAgent",
        extra_instruction="""
        Your goal is to detect whether we are in the Jobs section and help transition to the 'search_jobs' step.
        If already in Jobs section, set current_step to 'search_jobs'.
        """
    )

async def ask_search_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="SearchAgent",
        extra_instruction=f"""
        JOB SEARCH PARAMETERS:
        - Job Title: {JOB_TITLE}
        - Location: {JOB_LOCATION}

        Use 'fill_input_field' for both fields, then simulate pressing Enter by clicking a search button.
        Do not ask the user for these values.
        """
    )

async def ask_filter_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="FilterAgent",
        extra_instruction="""
        Your task is to enable the 'Easy Apply' filter on the job search results page.

        STEPS:
        - Look for buttons or links with labels like "Easy Apply", "Easy apply", or containing the word "easy".
        - If a button labeled "Easy Apply" is found, click it using the appropriate tool.
        - Only apply the filter once.

        If the filter is already active, return without clicking anything.
        """
    )

async def ask_easy_apply_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="EasyApplyAgent",
        extra_instruction="""
            You are an intelligent LinkedIn Easy Apply agent, capable of reasoning from full page structure.

            🎯 GOAL:
            Apply to jobs one by one using the "Easy Apply" process ONLY. You must inspect the current page to determine what to do next.

            🧠 BEHAVIOR:
            - Read the full DOM and decide your next step toward applying for a job.
            - If on the job listings page, look for links to job postings and click one.
            - If on a job detail view (same URL), search for the 'Easy Apply' button.
            - If found, click it and complete the form in multiple steps.
            - If no Easy Apply is found, return to the job list.

            🏗️ RECOGNIZE THESE DOM CUES:
            - Easy Apply button: text = "Easy Apply", aria-label includes "Easy Apply", or id = "jobs-apply-button-id"
            - Application form: look for buttons like "Next", "Continue", "Review", or "Submit"
            - Confirmation: look for a button that says "Done"

            ⛔ RULES:
            - Do NOT click multiple job links at once.
            - Do NOT leave a job before deciding if it's skippable or apply-able.
            - Do NOT repeat the same job.
            - Only ONE tool per turn — continue application across multiple turns if needed.

            Think step-by-step like a helpful assistant trying to finish each job application before moving to the next.
        """
    )

async def ask_generic_agent(navigator, elements_info, goal, step):
    return await _invoke_llm_tool_use(
        navigator, elements_info, goal, step,
        agent_role="GenericAgent",
        extra_instruction="""
        Use your best judgment to determine the next action using available tools.
        Do not perform login or job search actions unless clearly required.
        Make progress toward the overall goal.
        """
    )


async def _invoke_llm_tool_use(navigator, elements_info, goal, step, agent_role, extra_instruction=""):
    tools = create_tools(navigator)
    model_with_tools = model.bind_tools(tools)

    # Construct action history
    history = ""
    if navigator.action_history:
        history = "RECENT ACTIONS:\n" + "\n".join([
            f"Step {a['step']}: {a['action_type']} - {a['details']} -> {a['result']}"
            for a in navigator.action_history[-5:]
        ]) + "\nDo not repeat successful actions.\n"

    # System prompt
    system_message = SystemMessage(content=f"""
    You are {agent_role}, responsible for the step: {step}
    
    GOAL: {goal}
    CURRENT STEP: {step}
    CURRENT URL: {elements_info['current_url']}
    PAGE TITLE: {elements_info['page_title']}
    
    {extra_instruction}
    {history}
    If a tool call results in an error (e.g., clicking the Search button fails or the button is not found or visible),
    try calling another appropriate tool such as pressing Enter on the input field instead.

    AVAILABLE PAGE ELEMENTS:
    BUTTONS ({elements_info['total_buttons']}):
    {json.dumps(elements_info['buttons'], indent=2)}
    
    LINKS ({elements_info['total_links']}):
    {json.dumps(elements_info['links'], indent=2)}
    
    INPUTS ({elements_info['total_inputs']} total):
    {json.dumps(elements_info['inputs'], indent=2)}

    RULES:
    - Use ONE tool call per response
    - Always use tools, never respond conversationally
    """)

    human_message = HumanMessage(content=f"What action should I take next? Step: {step}")

    response = model_with_tools.invoke([system_message, human_message])

    if response.tool_calls:
        tool_name = response.tool_calls[0]['name']
        tool_args = response.tool_calls[0]['args']
        print(f"🤖 Tool selected: {tool_name}, Args: {tool_args}")
        for tool in tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args) if hasattr(tool, 'ainvoke') else tool.invoke(tool_args)
                    print(f"🔧 Tool result: {result}")

                    return "tool_executed"
                except Exception as tool_err:
                    print(f"⚠️ Tool failed: {tool_err}")
                    return await navigator.execute_fallback_action(elements_info, step)

    print(f"🤖 No tool used. Response: {response.content}")
    return await navigator.execute_fallback_action(elements_info, step)
