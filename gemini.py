import google.generativeai as genai
import os
from dotenv import load_dotenv
import os

load_dotenv()


genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel('gemini-1.5-flash-latest')
response = model.generate_content("Generate 10 indian history mcq based questions in json formate")
print(response.text)