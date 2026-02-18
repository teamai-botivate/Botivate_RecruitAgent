import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, "../../.env"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_aptitude_questions(jd_text: str):
    """
    Analyzes the Job Description and generates 25 MCQ questions and 4 Coding questions.
    """
    
    prompt = f"""
    Create a recruitment assessment JSON for the following Job Description.
    
    REQUIRED JSON STRUCTURE:
    {{
      "mcqs": [
        {{
          "id": "Q1",
          "question": "text",
          "options": ["A", "B", "C", "D"],
          "answer": "correct option text"
        }}
      ],
      "coding_questions": [
        {{
          "title": "Title of DSA Problem",
          "description": "Clear problem statement and requirements",
          "constraints": "Complexity and input limits",
          "example_input": "sample input string",
          "example_output": "sample output string",
          "test_cases": [
            {{"input": "in1", "output": "out1"}},
            {{"input": "in2", "output": "out2"}}
          ]
        }}
      ]
    }}

    RULES:
    1. Generate 25 MCQs.
    2. If the JD is technical (CS/IT), generate 4 Coding Questions. Otherwise, "coding_questions" must be [].
    3. Coding questions must be role-agnostic DSA (MNC style).
    4. OUTPUT ONLY THE JSON. NO EXPLANATION.

    JOB DESCRIPTION:
    {jd_text}
    """

    print(f"\n--- 🚀 AGENT START: Analysing Job Description ---")
    try:
        print(f"Step 1: Connecting to OpenAI (GPT-4o)...")
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a JSON-only generator. You honeslty follow the requested schema and never omit fields."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=4000,
            response_format={ "type": "json_object" }
        )
        
        print(f"Step 2: Receiving AI response and parsing JSON...")
        response_content = completion.choices[0].message.content
        data = json.loads(response_content)
        
        # Log keys for verification
        if data.get("coding_questions") and len(data["coding_questions"]) > 0:
            print(f"DEBUG: Coding Question Keys: {list(data['coding_questions'][0].keys())}")
        
        mcqs = data.get("mcqs", [])
        coding = data.get("coding_questions", [])
        
        print(f"✅ SUCCESS: Generated {len(mcqs)} professional MCQs and {len(coding)} Coding questions.")
        return {"mcqs": mcqs, "coding_questions": coding}

    except Exception as e:
        print(f"❌ AGENT ERROR: {e}")
        raise e

def evaluate_code(problem_text: str, user_code: str, language: str, test_cases: list):
    """
    Evaluates the user's code against the problem statement and test cases using AI.
    """
    prompt = f"""
    Evaluate the following coding assessment submission.
    
    PROBLEM DESCRIPTION:
    {problem_text}
    
    TEST CASES:
    {json.dumps(test_cases, indent=2)}
    
    CANDIDATE CODE ({language}):
    {user_code}
    
    INSTRUCTIONS:
    1. Analyze the code for logic, correctness, and adherence to constraints.
    2. Check if the code would pass the provided test cases.
    3. Return a JSON object with:
       - "success": boolean (true if logic is correct and passes test cases)
       - "output": string (compiler-style output or explanation of errors)
       - "passed_count": number of test cases passed
       - "total_count": total number of test cases provided
    
    OUTPUT ONLY THE JSON.
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a code execution and evaluation agent. Be strict and accurate."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={ "type": "json_object" }
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ EVALUATION ERROR: {e}")
        return {"success": False, "output": f"Evaluation Error: {str(e)}", "passed_count": 0, "total_count": len(test_cases)}
