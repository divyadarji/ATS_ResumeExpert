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

# Parse Gemini API response
def parse_gemini_response(response_text, action="summarize"):
    try:
        def clean_text(text):
            """Remove unwanted characters like '**', '*' from the text."""
            if text:
                return text.replace("**", "").replace("*", "").strip()
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
            structured_data = {
                "name": clean_text(re.search(r"(?i)\bName:\s*(.+)", response_text).group(1)) if re.search(r"(?i)\bName:\s*(.+)", response_text) else "N/A",
                "email": clean_text(re.search(r"(?i)\bEmail:\s*(.+)", response_text).group(1)) if re.search(r"(?i)\bEmail:\s*(.+)", response_text) else "N/A",
                "qualification": clean_text(re.search(r"(?i)\bQualification:\s*(.+)", response_text).group(1)) if re.search(r"(?i)\bQualification:\s*(.+)", response_text) else "N/A",
                "experience": clean_text(re.search(r"(?i)\bExperience:\s*(.+)", response_text).group(1)) if re.search(r"(?i)\bExperience:\s*(.+)", response_text) else "N/A",
                "skills": clean_text(re.search(r"(?i)\bSkills:\s*(.+)", response_text).group(1)) if re.search(r"(?i)\bSkills:\s*(.+)", response_text) else "N/A",
            }
            evaluation_match = re.search(r"(?i)\bProfessional Evaluation:\s*(.+)", response_text)
            structured_data["evaluation"] = clean_text(evaluation_match.group(1)) if evaluation_match else "N/A"
        return structured_data
    except Exception as e:
        return {"error": f"Error parsing response: {e}"}

# Rate-limited API call to Gemini
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
        Please summarize the following resume with the following details:
        - Name
        - Email
        - Qualification
        - Experience
        - Skills
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
            resume_text = extract_text_from_pdf(resume)

            if not resume_text.strip():
                resume_text = extract_text_with_ocr(resume, lang='hin+guj+eng')  # Example for Hindi + Gujarati + English

            language = detect_language(resume_text)

            if language != 'en':
                resume_text = translate_to_english(resume_text, source_lang=language)

            prompt = prompts["summarize"] if action == "summarize" else prompts["match"]
            input_text = resume_text if action == "summarize" else f"Job Description:\n{job_description}\n\nResume:\n{resume_text}"
            response_text = get_gemini_response(input_text, prompt)

            structured_data = parse_gemini_response(response_text, action=action)

        except Exception as e:
            structured_data = {
                "filename": resume.filename,
                "name": "Error processing resume",
                "email": "N/A",
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
        writer.writerow(["Filename", "Name", "Email", "Qualification", "Experience", "Skills", "Evaluation", "Percentage Match", "Justification", "Lacking"])

        for result in data:
            writer.writerow([
                result.get("filename", ""),
                result.get("name", ""),
                result.get("email", ""),
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
