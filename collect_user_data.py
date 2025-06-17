import json
import os

# Define the questions to ask
USER_PROFILE_QUESTIONS = [
    {"field": "notice_period", "question": "What is your notice period?"},
    {"field": "current_ctc", "question": "What is your current CTC (in INR)?"},
    {"field": "expected_ctc", "question": "What is your expected CTC (in INR)?"},
    {"field": "preferred_location", "question": "What is your preferred job location?"},
    {"field": "work_authorization", "question": "Are you authorized to work in India? (Yes/No)"},
    {"field": "relocation_willingness", "question": "Are you willing to relocate if required? (Yes/No)"},
]

PROFILE_PATH = "user_profile.json"


def collect_user_profile() -> dict:
    print("\n📋 Let's build your job application profile.")
    profile = {}

    for item in USER_PROFILE_QUESTIONS:
        response = input(f"👉 {item['question']} ").strip()
        profile[item["field"]] = response

    # Save to file
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"\n✅ Profile saved to `{PROFILE_PATH}`")
    return profile


def load_user_profile() -> dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r") as f:
            return json.load(f)
    return {}
