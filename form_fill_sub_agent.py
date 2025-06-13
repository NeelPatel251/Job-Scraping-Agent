import json
import re
import os
import asyncio
from config import RESUME_PATH
from langchain_core.messages import SystemMessage, HumanMessage
from utils import extract_text_from_resume


class FormFillSubAgent:
    def __init__(self, navigator, llm_model, resume_path, user_profile=None):
        print("🚀 Initializing FormFillSubAgent...")
        self.navigator = navigator
        self.llm_model = llm_model
        self.resume_path = resume_path
        self.user_profile = user_profile or {}
        
        print(f"📄 Resume path: {resume_path}")
        print(f"👤 User profile keys: {list(self.user_profile.keys())}")
        print("✅ FormFillSubAgent initialized successfully")

    async def answer_and_fill(self, questions):
        """Main function: Generate answers and check field status"""
        print("\n" + "="*80)
        print("🎯 Starting form analysis process...")
        print("="*80)
        
        print("\n📖 Step 1: Extracting resume content...")
        try:
            resume_text = extract_text_from_resume(self.resume_path)
            print(f"✅ Resume extracted successfully ({len(resume_text)} characters)")
        except Exception as e:
            print(f"❌ Error reading resume: {e}")
            return False

        print("\n🤖 Step 2: Generating answers with LLM...")
        answers = await self._generate_answers(questions, resume_text)

        print("\n🎉 Form analysis completed!")
        print("="*80)
        return answers, True

    async def _generate_answers(self, questions, resume_text):
        """Generate answers using LLM"""
        print("🤖 Asking LLM to generate answers...")
        
        system_prompt = SystemMessage(content="""
        ROLE: LinkedIn Form Answer Generator

        OBJECTIVE: Generate accurate answers for form questions using resume data.

        INSTRUCTIONS:
        - Match resume details to form questions
        - Return JSON array with element_id, question, and value
        - Use appropriate data types and formats
        - Set value to null if no relevant information found
        - Skip only:
            • Email fields (e.g., label includes "email")
            • Phone **country code** fields (e.g., dropdowns for country dialing codes)
        - DO NOT skip fields asking for phone numbers or mobile numbers
        - For multiple choice / radio button fields:
            • Select the option whose **label best matches or approximates** the answer
            • Return the **value field** (not the label) in the final JSON
            • If no perfect match, choose the **closest reasonable match**


        OUTPUT FORMAT:
        [
            {
                "element_id": "form-element-123", 
                "question": "Full Name",
                "value": "John Doe"
            },
            {
                "element_id": "form-element-456", 
                "question": "Current Position",
                "value": "Software Engineer"
            }
        ]

        CRITICAL: Output ONLY valid JSON array, no extra text.
        """)

        # Prepare questions data for LLM
        questions_data = []
        for q in questions:
            element_type = q.get('element_type')
            
            # Include options for both 'select' and 'radio'/'multipleChoice' types
            include_options = element_type in ['select', 'radio', 'multipleChoice']
            
            questions_data.append({
                "element_id": q.get('element_id'),
                "question": q.get('question'),
                "element_type": element_type,
                "options": q.get('options', []) if include_options else None
            })

        human_prompt = HumanMessage(content=json.dumps({
            "resume_text": resume_text[:15000],  # Truncate to avoid token limits
            "user_profile": self.user_profile,
            "form_questions": questions_data
        }, indent=2))

        try:
            response = await self.llm_model.ainvoke([system_prompt, human_prompt])
            print(f"📥 LLM response received ({len(response.content)} characters)")
            
            # Extract JSON from response
            answer_json = re.search(r'\[\s*{.*}\s*\]', response.content, re.DOTALL)
            
            if not answer_json:
                print("❌ No valid JSON found in LLM response")
                print("Raw response preview:", response.content[:500])
                return []
                
            answers = json.loads(answer_json.group(0))
            print(f"✅ Successfully parsed {len(answers)} answers")
            return answers
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            return []
        except Exception as e:
            print(f"❌ Error generating answers: {e}")
            return []
        