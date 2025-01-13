from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
import base64
import os
import io
import csv
from PIL import Image
import pdf2image
import google.generativeai as genai
from PyPDF2 import PdfReader
import re
from io import StringIO

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
    try:
        structured_data = {}
        if action == "match":
            percentage_match = re.search(r"(?i)\s*-?\s*Percentage\s*Match\s*[:\s]*([\d]+%)", response_text)
            justification = re.search(r"(?i)\bJustification\s*[:\s]*(.*)", response_text)
            structured_data["percentage_match"] = percentage_match.group(1).strip() if percentage_match else "N/A"
            structured_data["justification"] = justification.group(1).strip() if justification else "N/A"
        else:
            structured_data = {
                "name": re.search(r"(?i)\bName:\s*(.+)", response_text).group(1).strip() if re.search(r"(?i)\bName:\s*(.+)", response_text) else "N/A",
                "email": re.search(r"(?i)\bEmail:\s*(.+)", response_text).group(1).strip() if re.search(r"(?i)\bEmail:\s*(.+)", response_text) else "N/A",
                "qualification": re.search(r"(?i)\bQualification:\s*(.+)", response_text).group(1).strip() if re.search(r"(?i)\bQualification:\s*(.+)", response_text) else "N/A",
                "experience": re.search(r"(?i)\bExperience:\s*(.+)", response_text).group(1).strip() if re.search(r"(?i)\bExperience:\s*(.+)", response_text) else "N/A",
                "skills": re.search(r"(?i)\bSkills:\s*(.+)", response_text).group(1).strip() if re.search(r"(?i)\bSkills:\s*(.+)", response_text) else "N/A",
            }
            evaluation_match = re.search(r"(?i)\bProfessional Evaluation:\s*(.+)", response_text)
            structured_data["evaluation"] = evaluation_match.group(1).strip() if evaluation_match else "N/A"
        return structured_data
    except Exception as e:
        return {"error": f"Error parsing response: {e}"}

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

    if action == "match" and not job_description:
        return jsonify({"alert": "Job description is required to process matching action. Please provide a job description to proceed."}), 200

    prompts = {
        "summarize": """
        Please summarize the resume with the following details:
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
        Ensure the response strictly follows this format.
        """
    }

    results = []
    for resume in resumes:
        pdf_parts = input_pdf_setup(resume)
        prompt = prompts["summarize"] if action == "summarize" else prompts["match"]
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
                "justification": "N/A" if action == "match" else None,
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
        writer.writerow(["Filename", "Name", "Email", "Qualification", "Experience", "Skills", "Evaluation", "Percentage Match", "Justification"])

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
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=summary.csv"},
        )
    except Exception as e:
        return jsonify({"error": f"Error generating CSV: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
