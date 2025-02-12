from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
import os
import io
import csv
from PyPDF2 import PdfReader
import re
import time
from io import StringIO
import google.generativeai as genai
from langdetect import detect
from googletrans import Translator
import pytesseract
from PIL import Image
import unicodedata  # For Unicode normalization

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)

def extract_text_from_pdf(uploaded_file):
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text.strip()

def extract_text_with_ocr(uploaded_file, lang='eng'):
    return pytesseract.image_to_string(Image.open(uploaded_file), lang=lang)

def detect_language(text):
    return detect(text)

def translate_to_english(text, source_lang):
    translator = Translator()
    return translator.translate(text, src=source_lang, dest='en').text


def clean_text(text):
    if text:
        return re.sub(r'\*\*|\*|__|_', '', text).strip()
    return text


def parse_gemini_response(response_text, action="summarize"):
    structured_data = {}
    response_text = response_text.replace('\u2022', '-')  # Convert bullet points to hyphens

    try:
        if action == "match":
            # Decode and Normalize
            response_text = response_text.encode('utf-8').decode('utf-8')
            response_text = unicodedata.normalize('NFKC', response_text)

            # More Flexible Regex for Percentage Match
            # Updated regex for percentage_match
            percentage_match = re.search(
                r'(?i)(?:[\*\s-]*Percentage Match[\*\s-]*:?)\s*(.*?)(?=\n\s*\n|$|\n\s*-?\s*[\*\w-]+:)',
                response_text
            )

            if percentage_match:
                percentage = percentage_match.group(1)
                cleaned_percentage = clean_text(percentage)
                structured_data["percentage_match"] = cleaned_percentage
            else:
                structured_data["percentage_match"] = "N/A"

            justification = re.search(
                r'(?i)(?:[\*\s-]*Justification[\*\s-]*:?)\s*(.*?)(?=\n\s*\n|$|\n\s*[\*\w-]+:)',
                response_text,
                re.DOTALL
            )
            structured_data["justification"] = clean_text(justification.group(1)) if justification else "N/A"

            lacking = re.search(
                r'(?i)(?:[\*\s-]*Lacking[\*\s-]*:?)\s*((?:[\*\s-]*.*(?:\n|$))+)',
                response_text,
                re.DOTALL
            )
            lacking_text = lacking.group(1) if lacking else "N/A"
            structured_data["lacking"] = clean_text(lacking_text).replace('\n', '<br>') if lacking_text != "N/A" else "N/A"

        else:  # Default action (summarize)
            name_match = re.search(r"(?i)(?:Name|Full Name)[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["name"] = clean_text(name_match.group(1)) if name_match else "N/A"

            email_match = re.search(r"(?i)(?:\*\*)?Email[:\s]*(?:\*\*)?([\w\.\-]+@[\w\.\-]+)", response_text)
            structured_data["email"] = clean_text(email_match.group(1)) if email_match else "N/A"

            mobile_match = re.search(
                r"(?i)(?:\*\*)?(?:\bMobile\s*Number\b|\bM\s*No\b|\bPhone\b|\bContact\b|\bCell\b|\bMobile\b|Contact\s*NO)?[\s:\-]*"
                r"(\+?\d{1,3}[\s-]?"
                r"\(?\d{1,4}\)?[\s-]?"
                r"\d{2,4}[\s-]?\d{2,4}[\s-]?\d{2,4}|"
                r"\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}"
                r")", response_text)
            structured_data["phone"] = clean_text(mobile_match.group(1)) if mobile_match else "N/A"

            qualification_match = re.search(r"(?i)(?:Qualification|Education)[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["qualification"] = clean_text(qualification_match.group(1)) if qualification_match else "N/A"

            experience_matches = re.findall(r"(?i)(?:\*\*)?(?:Experience|Work Experience|Career|Employment History|Professional Experience|Career History|Job Experience|Work History|Technical Experience)(?:\*\*)?[^:]*:?\s*(?:\*\*)?([\s\S]+?)(?:\*\*)?\n*(?=\n|$)", response_text)
            structured_data["experience"] = clean_text("\n".join(experience_matches)) if experience_matches else "N/A"

            skills_match = re.search(r"(?i)Skills[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["skills"] = clean_text(skills_match.group(1)) if skills_match else "N/A"

            evaluation_match = re.search(r"(?i)Professional Evaluation[\s]*[:\-]?\s*(.*)", response_text, re.DOTALL)
            structured_data["evaluation"] = clean_text(evaluation_match.group(1)) if evaluation_match else "N/A"

    except Exception as e:
        return {"error": f"Error parsing response: {e}"}

    return structured_data

def get_gemini_response(input_text, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    time.sleep(2)  # Adjust delay based on API's rate limits

    response = model.generate_content([input_text, prompt])
    return response.text



# Routes
@app.route("/")
def index():
    return render_template("index.html")
@app.route('/generate_jd', methods=['POST'])
def generate_jd():
    data = request.get_json()
    job_role = data.get("job_role", "").strip()

    if not job_role:
        return jsonify({"error": "Job role is required"}), 400

    try:
        # Initialize the Gemini AI model correctly
        model = genai.GenerativeModel("gemini-pro")  # Use a valid model name
        response = model.generate_content(f"Generate a Professional job description for {job_role} do not include company name or location")

        # Debugging: Log the raw response
        print("Gemini API Raw Response:", response)

        # Ensure response is valid and contains text
        if not response or not hasattr(response, "text"):
            print("Error: Gemini API response missing 'text'")
            return jsonify({"error": "Invalid AI response"}), 500  

        raw_jd = response.text
        cleaned_jd = clean_text(raw_jd)  # Apply text cleaning

        return jsonify({"job_description": cleaned_jd})

    except Exception as e:
        print("Full Error Traceback:", str(e))  # Print error to console
        return jsonify({"error": str(e)}), 500

@app.route("/process_resumes", methods=["POST"])
def process_resumes():
    if "resumes" not in request.files:
        return jsonify({"error": "Missing resumes."}), 400

    job_description = request.form.get("job_description", "").strip()
    resumes = request.files.getlist("resumes")
    action = request.form["action"]

    if action == "match" and not job_description:
        return jsonify({"alert": "Job description is required to process matching action. Please provide a job description to proceed."}), 200

    prompts = {
        "summarize": """
        always extract text with lables like below.
        - Name: [Full Name]
        - Email: [Email Address]
        - Contact NO: [Contact Number /  Mobile number]
        - Qualification: [Highest Qualification] with college
        - Experience: - [Company Name], [Job Title], [Duration] ,[add all experince companies details like this]
        - Skills: [List of skills]
        - Professional Evaluation: [Professional Evaluation]
        Ensure that Experience is formatted as 'Company Name, Role, Duration' that's it no other things should be extracted.  
        Provide a professional evaluation in 1-2 concise sentences at the end.
        """,
        "match": """
        Given the resume and the job description, evaluate the match and provide:
        - Percentage Match: [e.g., 80%]
        - Justification: - Explain and Justify **why** the candidate is a e.g., 80% match for the job in 1-2 line only positive points.  
                           Focus **only on matching skills, strengths and alignment** with the JD.  
                          **Do NOT mention lacking details or missing skills** in this section.
        - Lacking: List **only** the most critical missing skills.  
                - **If the match is above 80%**, list **only 1-2 key gaps** (do not exceed 2).  
                - **If the match is between 60-80%**, list **exactly 2-4 missing skills**.  
                - **If the match is below 60%**, list **4-6 missing skills**, focusing only on major gaps.  
                **Do not list more than the specified limit. Ensure the output strictly follows this rule.**

        """
    }

    results = []
    for resume in resumes:
        try:
            # 🔹 Extract text from PDF
            resume_text = extract_text_from_pdf(resume)

            if not resume_text.strip():
                resume_text = extract_text_with_ocr(resume, lang='hin+guj+eng')  # Example for Hindi + Gujarati + English

            # 🔹 Print extracted text to check if parsing works
            # print(f"\n📄 Extracted Text from {resume.filename}:\n{resume_text}\n")

            language = detect_language(resume_text)

            if language != 'en':
                resume_text = translate_to_english(resume_text, source_lang=language)

            prompt = prompts["summarize"] if action == "summarize" else prompts["match"]
            input_text = resume_text if action == "summarize" else f"Job Description:\n{job_description}\n\nResume:\n{resume_text}"

            # 🔹 Call Gemini API
            response_text = get_gemini_response(input_text, prompt)

            print(f"\n🔍 Gemini API Response for {resume.filename}:\n{response_text}\n")

            structured_data = parse_gemini_response(response_text, action=action)

            print(f"\n✅ Parsed Data for {resume.filename}:\n{structured_data}\n")

        except Exception as e:
            structured_data = {
                "filename": resume.filename,
                "name": "Error processing resume",
                "email": "N/A",
                "phone": "N/A",
                "qualification": "N/A",
                "experience": "N/A",
                "skills": "N/A",
                "percentage_match": "N/A" if action == "match" else None,
                "justification": "N/A" if action == "match" else None,
                "lacking": "N/A" if action == "match" else None,
                "evaluation": str(e),
            }

        results.append({
            "filename": resume.filename,
            **structured_data
        })

    return jsonify(results)

@app.route("/download_csv", methods=["POST"])
def download_csv():
    try:
        data = request.json.get("summarized_data")
        if not data:
            return jsonify({"error": "No summarized data provided."}), 400

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Filename", "Name", "Email", "phone", "Qualification", "Experience", "Skills", "Evaluation", "Percentage Match", "Justification", "Lacking"])

        for result in data:
            writer.writerow([
                result.get("filename", ""),
                result.get("name", ""),
                result.get("email", ""),
                result.get("phone", ""),
                result.get("qualification", ""),
                result.get("experience", ""),
                result.get("skills", ""),
                result.get("evaluation", ""),
                result.get("percentage_match", ""),
                result.get("justification", ""),
                result.get("lacking", ""),
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=summary.csv"}
        )
    except Exception as e:
        return jsonify({"error": f"Error creating CSV: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)


