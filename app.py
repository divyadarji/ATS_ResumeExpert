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

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize Flask app
app = Flask(__name__)

# Utility to extract text from PDF (regular PDFs)
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



def parse_gemini_response(response_text, action="summarize"):
    try:
        def clean_text(text):
            """Remove unwanted characters like '**', '*', '-', extra spaces, and new lines."""
            if text:
                return text.replace("**", "").replace("*", "").replace("-", "").strip()
            return text

        structured_data = {}

        if action == "match":
            percentage_match = re.search(r"(?i)\s*-?\s*Percentage\s*Match\s*[:\s]*([\d]+%)", response_text)
            justification = re.search(r"(?i)\bJustification\s*[:\s]*(.*)", response_text)
            lacking = re.search(r"(?i)\bLacking\s*[:\s]*(.*)", response_text)

            structured_data["percentage_match"] = clean_text(percentage_match.group(1)) if percentage_match else "N/A"
            structured_data["justification"] = clean_text(justification.group(1)) if justification else "N/A"
            structured_data["lacking"] = clean_text(lacking.group(1)) if lacking else "N/A"

        else:
            name_match = re.search(r"(?i)(?:Name|Full Name)[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["name"] = clean_text(name_match.group(1)) if name_match else "N/A"

            email_match = re.search(r"(?i)(?:\*\*)?Email[:\s]*(?:\*\*)?([\w\.\-]+@[\w\.\-]+)", response_text)
            structured_data["email"] = clean_text(email_match.group(1)) if email_match else "N/A"

            mobile_match = re.search(
            r"(?i)(?:\*\*)?(?:\bMobile\s*Number\b|\bM\s*No\b|\bPhone\b|\bContact\b|\bCell\b|\bMobile\b|Contact\s*NO)?[\s:\-]*"
            r"(\+?\(?\d{1,4}\)?[\s-]?\d{4,5}[\s-]?\d{5}|"  # (+91) 72858 68035 or +91-72858-68035
            r"\d{10}|"  # Standard 10-digit format (7285868035)
            r"\d{5}[\s-]?\d{5}|"  # Split format (72858 68035 or 72858-68035)
            r"\d{4}[\s-]?\d{3}[\s-]?\d{3}|"  # 4-3-3 format (1234-567-890)
            r"\d{4}[\s-]?\d{4}[\s-]?\d{2}"  # 4-4-2 format (1234-5678-90)
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

        return structured_data

    except Exception as e:
        return {"error": f"Error parsing response: {e}"}

def get_gemini_response(input_text, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    time.sleep(2)  # Adjust delay based on API's rate limits

    response = model.generate_content([input_text, prompt])
    return response.text



# Routes
@app.route("/")
def index():
    return render_template("index.html")

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
        - Justification: [1-2 concise sentences explaining the match percentage]
        - Lacking: [only list of skills that lacks or qualifications missing from the resume for e.g.,this person lacks experince or skills that are required for the job description]
        Ensure the response strictly follows this format.
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
            print(f"\n📄 Extracted Text from {resume.filename}:\n{resume_text}\n")

            language = detect_language(resume_text)

            if language != 'en':
                resume_text = translate_to_english(resume_text, source_lang=language)

            prompt = prompts["summarize"] if action == "summarize" else prompts["match"]
            input_text = resume_text if action == "summarize" else f"Job Description:\n{job_description}\n\nResume:\n{resume_text}"

            # 🔹 Call Gemini API
            response_text = get_gemini_response(input_text, prompt)

            # 🔹 Print API Response for Debugging
            print(f"\n🔍 Gemini API Response for {resume.filename}:\n{response_text}\n")

            # 🔹 Parse API Response
            structured_data = parse_gemini_response(response_text, action=action)

            # 🔹 Print Parsed Structured Data
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


