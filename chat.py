from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Load .env
load_dotenv()

# Initialize model
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

# Ask question
response = llm.invoke([
    HumanMessage(content="What is the capital of India?")
])

print(response.content)
