import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

try:
    # Use a known model (gemini-1.5-flash is current as of 2025; gemini-2.0-flash may not exist)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Generate a Professional job description for Software Engineer do not include company name or location")
    print(response.text)
except Exception as e:
    print(f"Error: {str(e)}")