import google.generativeai as genai
import os
from dotenv import load_dotenv
import os
import json

load_dotenv()


genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel('gemini-1.5-flash-latest',generation_config={"response_mime_type":"application/json"})
response = model.generate_content("Generate 10 science multiple-choice questions in the following format: [{'title': 'question text', 'options': ['option 1', 'option 2', 'option 3'], 'answer': correct_option_number}]. The correct_option_number should be the index (1-based) of the correct answer in the options list")
print(response.text)
# print(response.text[0])

try:
    questions = json.loads(response.text)
except json.JSONDecodeError:
    print("Error: The response is not valid JSON.")
    # Handle the error or take appropriate action


    
# Now `questions` is a Python variable that you can use
print(questions[0]['title'])

