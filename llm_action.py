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
    """Ask LLM to use tools to perform actions"""

    if navigator_instance.is_verification_page(elements_info):
        return "human_verification"

    if not model:
        print("No LLM available, using fallback logic...")
        return await navigator_instance.execute_fallback_action(elements_info, current_step)

    try:
        tools = create_tools(navigator_instance)
        model_with_tools = model.bind_tools(tools)

        history_summary = ""
        if navigator_instance.action_history:
            history_summary = "RECENT ACTIONS TAKEN:\n"
            for action in navigator_instance.action_history[-5:]:
                history_summary += f"Step {action['step']}: {action['action_type']} - {action['details']} -> {action['result']}\n"
            history_summary += "\nIMPORTANT: Do not repeat actions that were already successful!\n"

        system_message = SystemMessage(content=f"""
            You are an AI assistant helping navigate LinkedIn to reach the Jobs section.

            CURRENT STEP: {current_step}
            GOAL: {goal}
            CURRENT URL: {elements_info['current_url']}
            PAGE TITLE: {elements_info['page_title']}

            {history_summary}

            AVAILABLE PAGE ELEMENTS:
            BUTTONS ({elements_info['total_buttons']} total, showing first 15):
            {json.dumps(elements_info['buttons'], indent=2)}

            LINKS ({elements_info['total_links']} total, showing first 20):
            {json.dumps(elements_info['links'], indent=2)}

            INPUTS ({elements_info['total_inputs']} total):
            {json.dumps(elements_info['inputs'], indent=2)}

            Note:
            Do not go to Job link before sign up

            CRITICAL RULES:
                1. Check the action history - do not repeat successful actions!
                2. If email was already filled successfully, move to password
                3. If both email and password were filled, click sign in button
                4. Never click third-party login buttons (Google, Apple, etc.)
                5. Always use tools to fill input fields when step is "search_jobs" – never ask the user for input.
                6. After filling both job title and location fields, always simulate Enter keypress using press_enter_on_input on the location input


            NAVIGATION WORKFLOW:
                1. If on homepage and not signed in -> click "Sign in" link
                2. If on login page -> fill email field first, then password field, then click sign in button
                3. If signed in -> navigate to Jobs section
                4. If in Jobs section and step is "jobs_section" -> advance to step "search_jobs"
                5. If step is "search_jobs" -> use the fill_input_field tool to fill both the job title and the location inputs. Then simulate pressing Enter by clicking the search button or sending Enter key event.
                6. If step is "fill_job_title" -> fill job title field only
                7. If step is "fill_location" -> fill location field only
                8. If step is "search_submitted" -> click on first job link
                9. If step is "browse_jobs" -> look for "Easy Apply" button and click it

            Use the available tools to perform the next logical action. Choose ONE action at a time.
        """)

        human_message = HumanMessage(content=f"Based on the current page state, what action should I take next to reach the LinkedIn Jobs section? Current step: {current_step}")

        response = model_with_tools.invoke([system_message, human_message])

        if response.tool_calls:
            print(f"🤖 LLM decided to use tool: {response.tool_calls[0]['name']}")
            print(f"   Arguments: {response.tool_calls[0]['args']}")

            tool_name = response.tool_calls[0]['name']
            tool_args = response.tool_calls[0]['args']

            for tool in tools:
                if tool.name == tool_name:
                    try:
                        result = await tool.ainvoke(tool_args) if hasattr(tool, 'ainvoke') else tool.invoke(tool_args)
                        print(f"🔧 Tool result: {result}")

                        # Step logic
                        if tool_name == "fill_input_field":
                            field_type = (tool_args.get("field_type") or "").lower()
                            if "email" in field_type:
                                navigator_instance.current_step = "fill_password"
                            elif "password" in field_type:
                                navigator_instance.current_step = "submit_login"
                            elif "job_title" in field_type or "title" in field_type:
                                navigator_instance.current_step = "fill_location"
                            elif "location" in field_type:
                                navigator_instance.current_step = "search_submitted"

                        elif tool_name == "click_element":
                            details = str(tool_args).lower()
                            if "sign in" in details:
                                if "link" in details:
                                    navigator_instance.current_step = "login_page"
                                elif "button" in details:
                                    navigator_instance.current_step = "logged_in"
                            elif "job" in details:
                                navigator_instance.current_step = "jobs_section"

                        elif tool_name == "navigate_to_url" and "jobs" in str(tool_args).lower():
                            navigator_instance.current_step = "jobs_section"

                        return "tool_executed"

                    except Exception as tool_error:
                        print(f"Error executing tool {tool_name}: {tool_error}")
                        return await navigator_instance.execute_fallback_action(elements_info, current_step)

        else:
            print(f"🤖 LLM response (no tool): {response.content}")
            return await navigator_instance.execute_fallback_action(elements_info, current_step)

    except Exception as e:
        print(f"Error with LLM tool calling: {e}")
        return await navigator_instance.execute_fallback_action(elements_info, current_step)
