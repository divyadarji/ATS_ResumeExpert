from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import base64
import os
import io
from PIL import Image
import pdf2image
import google.generativeai as genai
from PyPDF2 import PdfReader
import re

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)

# Utility to process PDF
def input_pdf_setup(uploaded_file):
    pdf_parts = []
    images = pdf2image.convert_from_bytes(uploaded_file.read())
    for page in images:
        img_byte_arr = io.BytesIO()
        page.save(img_byte_arr, format='JPEG')
        pdf_parts.append({
            "mime_type": "image/jpeg",
            "data": base64.b64encode(img_byte_arr.getvalue()).decode()
        })
    return pdf_parts

# Parse Gemini API response
def parse_gemini_response(response_text, action="summarize"):
    """
    Parse the Gemini response to extract structured data.
    """
    try:
        structured_data = {
            "name": re.search(r"(?i)\bName:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bName:\s*(.+)", response_text) else "N/A",
            "email": re.search(r"(?i)\bEmail:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bEmail:\s*(.+)", response_text) else "N/A",
            "qualification": re.search(r"(?i)\bQualification:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bQualification:\s*(.+)", response_text) else "N/A",
            "experience": re.search(r"(?i)\bExperience:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bExperience:\s*(.+)", response_text) else "N/A",
            "skills": re.search(r"(?i)\bSkills:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bSkills:\s*(.+)", response_text) else "N/A",
        }

        if action == "match":
            structured_data["percentage_match"] = re.search(r"(?i)\bPercentage match:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bPercentage match:\s*(.+)", response_text) else "N/A"
            structured_data["missing_keywords"] = re.search(r"(?i)\bMissing keywords:\s*(.+)", response_text).group(1) if re.search(r"(?i)\bMissing keywords:\s*(.+)", response_text) else "N/A"

        evaluation_match = re.search(r"(?i)\bProfessional Evaluation:\s*(.+)", response_text)
        structured_data["evaluation"] = evaluation_match.group(1).strip() if evaluation_match else "Evaluation not provided."

        return structured_data
    except Exception as e:
        raise ValueError(f"Error parsing response: {e}")

# Get Gemini API response
def get_gemini_response(input_text, pdf_content, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input_text, pdf_content[0], prompt])
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

    prompts = {
        "summarize": """
        Please summarize the resume with the following details:
        - Name
        - Email
        - Qualification
        - Experience
        - Skills

        assume that you are HR Exclude these details in the professional evaluation. Provide a concise 1-2 sentence analysis of unique strengths or achievements.
        """,
        "match": """
       Please match the resume with the job description and provide the following details give answer in one or two
        """
    }

    results = []
    for resume in resumes:
        pdf_parts = input_pdf_setup(resume)
        prompt = prompts["summarize"] if action == "summarize" else prompts["match"]

        # Send job description only for "match"
        job_input = job_description if action == "match" else ""

        try:
            response_text = get_gemini_response(job_input, pdf_parts, prompt)
            structured_data = parse_gemini_response(response_text, action=action)
        except Exception as e:
            structured_data = {
                "name": "Error processing resume",
                "email": "N/A",
                "qualification": "N/A",
                "experience": "N/A",
                "skills": "N/A",
                "percentage_match": "N/A" if action == "match" else None,
                "missing_keywords": "N/A" if action == "match" else None,
                "evaluation": str(e),
            }

        results.append({
            "filename": resume.filename,
            **structured_data
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
