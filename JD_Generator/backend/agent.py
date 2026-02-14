import os
from groq import Groq
from dotenv import load_dotenv
# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, "../../.env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_jd_ai(data: dict):
    """
    AI Agent to generate a professional, ATS-friendly JD based on structured inputs.
    """
    
    prompt = f"""
    You are an expert HR Specialist and Technical Recruiter. 
    Generate a professional and ATS-friendly Job Description based on the following structured input:

    ----------------------------
    COMPANY DETAILS
    ----------------------------
    Company Name: {data['companyName']}
    Company Type: {data['companyType']}
    Industry: {data['industry']}
    Location: {data['location']}

    ----------------------------
    ROLE IDENTIFICATION
    ----------------------------
    Role Title: {data['roleTitle']}
    Experience Level: {data['experience']}
    Employment Type: {data['employmentType']}
    Work Mode: {data['workMode']}
    Offered Salary: {data['salary']} Lakhs per Annum (LPA)

    ----------------------------
    INTELLIGENT ANALYSIS REQUIREMENTS
    ----------------------------
    - Analyze the role and industry carefully.
    - Automatically determine required Key Skills and modern Tech Stack based on market standards.
    - Do NOT rely on pre-provided skills (infer them from the role title and industry).
    - Adjust responsibilities and tools based on experience level ({data['experience']}).
    - Mention the salary of {data['salary']} LPA clearly as the first point in the compensation section.
    - Ensure the JD is ATS-friendly.

    ----------------------------
    OUTPUT FORMAT (MUST FOLLOW THIS EXACTLY)
    ----------------------------
    1. COMPANY NAME: [Name]
    2. JOB TITLE: [Title] ([Experience])
    3. ROLE SUMMARY: (2-3 lines context)
    4. KEY RESPONSIBILITIES: (5-7 bullet points)
    5. REQUIRED SKILLS: (Bulleted list)
    6. TECH STACK: (Separately mentioned list)
    7. PREFERRED SKILLS: (Bulleted list)
    8. COMPENSATION & BENEFITS (MANDATORY: Include "{data['salary']} LPA"): (Include Salary and other perks)
    9. CLOSING LINE: (Professional call to action)

    CONSTRAINTS:
    - YOU MUST INCLUDE THE SALARY OF {data['salary']} LPA IN SECTION 8.
    - Keep it concise (under 250 words total).
    - Use professional, punchy language.
    - Maintain the numbered structure (1-9).
    - Response should only contain the JD text.
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a professional JD writer robot."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating JD: {str(e)}"
