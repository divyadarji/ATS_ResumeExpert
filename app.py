from flask import Flask, render_template, request, jsonify, Response, session
from flask_session import Session
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
import unicodedata
import uuid
import hashlib
from datetime import datetime
import logging
import shutil
import tempfile
from docx import Document  # New dependency for DOCX support

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)

# Configure session
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "your-secret-key-here")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# In-memory cache for resume data and uploaded file paths
resume_cache = {}
uploaded_files = {}

# Directory for shortlisted resumes
SHORTLIST_DIR = "shortlisted_resumes"
if not os.path.exists(SHORTLIST_DIR):
    os.makedirs(SHORTLIST_DIR)

# Directory for temporary storage of uploaded files
TEMP_UPLOAD_DIR = "temp_uploads"
if not os.path.exists(TEMP_UPLOAD_DIR):
    os.makedirs(TEMP_UPLOAD_DIR)

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'}

def extract_text_from_pdf(uploaded_file):
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text.strip()

def extract_text_with_ocr(file_path, lang='eng'):
    return pytesseract.image_to_string(Image.open(file_path), lang=lang)

def extract_text_from_file(file_path):
    filename = os.path.basename(file_path).lower()
    ext = os.path.splitext(filename)[1]
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported types are: {', '.join(SUPPORTED_EXTENSIONS)}")
    
    try:
        if ext == '.pdf':
            with open(file_path, 'rb') as f:
                return extract_text_from_pdf(f)
        elif ext == '.docx':
            doc = Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif ext in ('.png', '.jpg', '.jpeg'):
            return extract_text_with_ocr(file_path, lang='hin+guj+eng')
    except Exception as e:
        logger.error(f"Error extracting text from {filename}: {e}")
        return ""

def detect_language(text):
    return detect(text)

def translate_to_english(text, source_lang):
    translator = Translator()
    return translator.translate(text, src=source_lang, dest='en').text

def clean_text(text):
    if text:
        text = re.sub(r'\*\*|\*|__|_', '', text).strip()
        text = re.sub(r'^[\[\]{},"\s:-]+|[\[\]{},"\s:-]+$', '', text)
        return text
    return ""

def standardize_phone(phone):
    if not phone or phone == "N/A":
        return ""
    digits = re.sub(r'[^\d+]', '', phone)
    if digits.startswith('+91') and len(digits) == 13:
        return f"{digits[:3]}-{digits[3:]}"
    elif len(digits) == 10:
        return f"+91-{digits}"
    elif digits.startswith('91') and len(digits) == 12:
        return f"+91-{digits[2:]}"
    return phone

def parse_date(date_str):
    if not date_str or date_str.lower() in ["present", "till date", "ongoing"]:
        return datetime(2025, 4, 1)
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    date_str = date_str.lower().strip()
    
    if re.match(r'(\d{2})[/-](\d{4})', date_str):
        month, year = map(int, re.match(r'(\d{2})[/-](\d{4})', date_str).groups())
        return datetime(year, month, 1)
    elif re.match(r'([a-z]+)[-\s]+(\d{4})', date_str):
        month_str, year = re.match(r'([a-z]+)[-\s]+(\d{4})', date_str).groups()
        month = month_map.get(month_str, 1)
        return datetime(int(year), month, 1)
    elif re.match(r'^\d{4}$', date_str):
        return datetime(int(date_str), 1, 1)
    return None

def calculate_experience_years(experience):
    if not experience or experience == "":
        return 0
    
    periods = experience.split(" | ")
    date_pairs = []
    
    for period in periods:
        match = re.search(r'(\w+\s*\d{4}|\d{2}/\d{4}|\d{4})\s*[-–—]\s*(\w+\s*\d{4}|\d{2}/\d{4}|\d{4}|present|till date)', period, re.IGNORECASE)
        if match:
            start_str, end_str = match.groups()
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
            if start_date and end_date and start_date <= end_date:
                date_pairs.append((start_date, end_date))
        else:
            year_match = re.search(r'(\d{4})', period)
            if year_match:
                year = int(year_match.group(1))
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31)
                date_pairs.append((start_date, end_date))
    
    if not date_pairs:
        return 0
    
    date_pairs.sort(key=lambda x: x[0])
    total_months = 0
    current_start = date_pairs[0][0]
    current_end = date_pairs[0][1]
    
    for start, end in date_pairs[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            months = (current_end.year - current_start.year) * 12 + (current_end.month - current_start.month)
            total_months += max(0, months)
            current_start = start
            current_end = end
    
    months = (current_end.year - current_start.year) * 12 + (current_end.month - current_start.month)
    total_months += max(0, months)
    
    return round(total_months / 12, 1)

def categorize_resume(primary_role, skills=""):
    mainstream_categories = {
        "AIML": ["machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "computer vision", "artificial intelligence", "data science", "ai"],
        "Testing": ["testing", "qa", "quality assurance", "selenium", "junit", "pytest", "cypress", "mocha", "automation"],
        "Frontend": ["frontend", "react", "angular", "vue", "javascript", "html", "css", "typescript", "jquery", "scss", "rxjs", "ionic", "material ui", "primeng"],
        "Backend": ["backend", "node", "python", "java", "ruby", "php", "django", "flask", "spring", "express", "sails.js", "mongodb", "laravel", "mysql", "sqlite", "rest api", "socket.io", "jwt", "cronjob", "exceljs", "cryptojs", "razorpay", "node mailer", "fastapi"],
        "Full Stack": ["full stack", "full-stack", "mern", "mean"],
        "Mobile": ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin", "androidsdk", "retrofit", "room", "exoplayer", "bluetooth", "mvvm", "mvp", "dagger2", "rxjava", "glide", "okhttp"],
        "Cloud Engineer": ["cloud", "aws", "azure", "gcp", "infrastructure"],
        "DevOps": ["devops", "docker", "kubernetes", "ci/cd", "jenkins", "ansible", "terraform", "bitbucket", "git", "gitlab", "github", "jira", "trello", "server deploy"],
        "HR": ["hr", "human resources", "recruitment", "talent acquisition"]
    }

    primary_role_lower = primary_role.lower()
    skills_lower = skills.lower()

    if "qa" in primary_role_lower or "quality assurance" in primary_role_lower or "test" in primary_role_lower or "automation" in primary_role_lower:
        return ["Testing"]
    elif "full stack" in primary_role_lower or "full-stack" in primary_role_lower:
        return ["Full Stack"]
    elif "ai/ml" in primary_role_lower or "machine learning" in primary_role_lower or "ai" in primary_role_lower:
        return ["AIML"]
    elif "frontend" in primary_role_lower or any(k in primary_role_lower for k in ["react", "angular", "vue"]):
        return ["Frontend"]
    elif "backend" in primary_role_lower or any(k in primary_role_lower for k in ["node", "python", "java", "php"]):
        return ["Backend"]
    elif "mobile" in primary_role_lower or any(k in primary_role_lower for k in ["android", "ios", "flutter"]):
        return ["Mobile"]
    elif "cloud" in primary_role_lower or any(k in primary_role_lower for k in ["aws", "azure", "gcp"]):
        return ["Cloud Engineer"]
    elif "devops" in primary_role_lower or "dev ops" in primary_role_lower:
        return ["DevOps"]
    elif "hr" in primary_role_lower or "human resources" in primary_role_lower:
        return ["HR"]

    category_scores = {cat: 0 for cat in mainstream_categories}
    for category, keywords in mainstream_categories.items():
        for keyword in keywords:
            if keyword in primary_role_lower:
                category_scores[category] += 2
            if keyword in skills_lower:
                category_scores[category] += 1

    top_category = max(category_scores.items(), key=lambda x: x[1])[0]
    if category_scores[top_category] > 0:
        return [top_category]
    return ["Uncategorized"]

def parse_gemini_response(response_text, action="summarize"):
    structured_data = {}
    response_text = response_text.replace('\u2022', '-')

    try:
        if action == "match":
            response_text = unicodedata.normalize('NFKC', response_text.encode('utf-8').decode('utf-8'))
            percentage_match = re.search(r'(?i)percentage match[:\s*-]*\s*(\d{1,3}%)', response_text)
            structured_data["percentage_match"] = clean_text(percentage_match.group(1)) if percentage_match else ""
            justification = re.search(r"(?i)Justification[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["justification"] = clean_text(justification.group(1)) if justification else ""
            lacking = re.search(r'(?i)(?:[\*\s-]*Lacking[\*\s-]*:?)\s*((?:[\*\s-]*.*(?:\n|$))+)',
                              response_text, re.DOTALL)
            lacking_text = lacking.group(1) if lacking else ""
            structured_data["lacking"] = lacking_text.strip()
        else:
            name_match = re.search(r"(?i)(?:Name|Full Name)[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["name"] = clean_text(name_match.group(1)) if name_match else ""
            email_match = re.search(r"(?i)Email[:\s*-]*\s*([\w\.\-]+@[\w\.\-]+)", response_text)
            structured_data["email"] = clean_text(email_match.group(1)) if email_match else ""
            mobile_match = re.search(
                r"(?i)(?:Mobile\s*Number|M\s*No|Phone|Contact|Cell|Mobile|Contact\s*NO)?[\s:\-]*"
                r"(\+?\d{1,3}[\s-]?\(?\d{1,4}\)?[\s-]?\d{2,4}[\s-]?\d{2,4}[\s-]?\d{2,4}|"
                r"\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4})", response_text)
            structured_data["phone"] = standardize_phone(clean_text(mobile_match.group(1)) if mobile_match else "")
            qualification_match = re.search(r"(?i)(?:Qualification|Education)[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["qualification"] = clean_text(qualification_match.group(1)) if qualification_match else ""
            experience_match = re.search(
                r"(?i)(?:Experience|Work Experience|Professional Experience)[:\s*-]*([\s\S]+?)(?=\n\s*\n|Skills|Professional Evaluation|Personal Evaluation|$)",
                response_text)
            structured_data["experience"] = experience_match.group(1).strip() if experience_match else ""
            skills_match = re.search(r"(?i)Skills[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["skills"] = clean_text(skills_match.group(1)) if skills_match else ""
            evaluation_match = re.search(r"(?i)Professional Evaluation[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["evaluation"] = clean_text(evaluation_match.group(1)) if evaluation_match else ""
            personal_evaluation = re.search(r"(?i)Personal Evaluation[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["personal_evaluation"] = clean_text(personal_evaluation.group(1)) if personal_evaluation else ""
            role_match = re.search(r"(?i)Primary Role[\s]*[:\-]?\s*(.*)", response_text)
            structured_data["primary_role"] = clean_text(role_match.group(1)) if role_match else ""

    except Exception as e:
        return {"error": f"Error parsing response: {e}"}

    return structured_data

def get_gemini_response(input_text, prompt):
    model = genai.GenerativeModel('gemini-2.0-flash')
    time.sleep(2)
    response = model.generate_content([input_text, prompt])
    return response.text

@app.route("/")
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template("index.html")

@app.route('/generate_jd', methods=['POST'])
def generate_jd():
    data = request.get_json()
    job_role = data.get("job_role", "").strip()

    if not job_role:
        return jsonify({"error": "Job role is required"}), 400

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(f"Generate a Professional job description for {job_role} do not include company name or location")
        if not response or not hasattr(response, "text"):
            return jsonify({"error": "Invalid AI response"}), 500  
        raw_jd = response.text
        cleaned_jd = clean_text(raw_jd)
        return jsonify({"job_description": cleaned_jd})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/process_resumes", methods=["POST"])
def process_resumes():
    if "resumes" not in request.files:
        return jsonify({"error": "Missing resumes."}), 400

    job_description = request.form.get("job_description", "").strip()
    resumes = request.files.getlist("resumes")
    action = request.form["action"]
    category_filter = request.form.get("category", "").strip()
    session_id = session.get('session_id')

    if action == "match" and not job_description:
        return jsonify({"alert": "Job description is required to process matching action."}), 200

    # Validate file extensions
    for resume in resumes:
        ext = os.path.splitext(resume.filename.lower())[1]
        if ext not in SUPPORTED_EXTENSIONS:
            return jsonify({"error": f"Unsupported file type: {resume.filename}. Supported types are: {', '.join(SUPPORTED_EXTENSIONS)}"}), 400

    prompts = {
        "summarize": """
        always extract text with labels like below.
        - Name: [Full Name]
        - Email: [Email Address]
        - Contact NO: [Contact Number / Mobile number]
        - Qualification: [Highest Qualification] with college
        - Experience: - [Company Name], [Job Title], [Duration].
                      - [Company Name], [Job Title], [Duration].
                      [Disclaimer: add all experience companies like this. If duration is not mentioned, just avoid it.]
        - Skills: [List of skills]
        - Professional Evaluation: [Professional Evaluation in 1 or 2 short sentences.]
        - Personal Evaluation: [Personal Evaluation in 1 or 2 short sentences - how is he/she, in what way he/she is good at, e.g., good team player, good communication skills, etc.
                               Disclaimer: if personality is not provided, judge from the resume itself but don't mention "resume" in it.]
        - Primary Role: [Identify the primary job role the candidate presents themselves as, e.g., "Frontend Developer", "AI/ML Engineer", "Full Stack Developer", "Python Developer", based on their experience, skills, and overall resume content. Ensure this field is always filled with a meaningful role, inferring from context if necessary.]
        Ensure that Experience is formatted as 'Company Name, Role, Duration' with no extra details extracted.  
        Disclaimer: I want to see the extracted information in the format of the above example. Do not skip any fields, especially Primary Role.
        """,
        "match": """
        Given the resume and the job description, evaluate the match and provide:
        - Percentage Match: [e.g., 80%. Assume you are an ATS specialist with HR role; judge how much this resume matches the job description, e.g., if the JD is for a Node.js Developer and the resume is about frontend, it should be less than 20%.]
        - Justification: - Explain and justify why the candidate is, e.g., an 80% match for the job in 1-2 lines. Disclaimer: only positive points.  
                           Focus only on matching skills, strengths, and alignment with the JD.  
                           Do NOT mention lacking details or missing skills in this section.
        - Lacking: List only the critical missing skills.  
                - If the match is above 80%, list only 1-2 key gaps (do not exceed 2).  
                - If the match is between 60-80%, list exactly 2-4 missing skills.  
                - If the match is below 60%, list 4-6 missing skills, focusing only on major gaps.  
                Do not list more than the specified limit. Ensure the output strictly follows this rule.
        """
    }

    results = []
    categorized_results = {
        "Frontend": [], "Backend": [], "Full Stack": [], "Mobile": [], "AIML": [], 
        "Testing": [], "Cloud Engineer": [], "DevOps": [], "HR": [], "Uncategorized": []
    }

    if session_id not in resume_cache:
        resume_cache[session_id] = {"summaries": {}, "matches": {}}
    if session_id not in uploaded_files:
        uploaded_files[session_id] = {}

    jd_hash = hashlib.md5(job_description.encode('utf-8')).hexdigest() if job_description else ""

    for resume in resumes:
        summary_key = resume.filename
        match_key = f"{resume.filename}_{jd_hash}" if action == "match" else None

        # Save the uploaded file to a temporary location
        temp_file_path = os.path.join(TEMP_UPLOAD_DIR, f"{session_id}_{resume.filename}")
        resume.save(temp_file_path)
        uploaded_files[session_id][resume.filename] = temp_file_path
        logger.debug(f"Saved uploaded file to {temp_file_path}")

        cached_summary = resume_cache[session_id]["summaries"].get(summary_key)
        cached_match = resume_cache[session_id]["matches"].get(match_key) if match_key else None

        try:
            if cached_summary and "specific_role" in cached_summary:
                result = cached_summary.copy()
            else:
                resume_text = extract_text_from_file(temp_file_path)
                if not resume_text.strip() and os.path.splitext(resume.filename.lower())[1] in ('.png', '.jpg', '.jpeg'):
                    resume_text = extract_text_with_ocr(temp_file_path, lang='hin+guj+eng')
                language = detect_language(resume_text)
                if language != 'en':
                    resume_text = translate_to_english(resume_text, source_lang=language)

                summarize_response = get_gemini_response(resume_text, prompts["summarize"])
                summary_data = parse_gemini_response(summarize_response, action="summarize")
                result = {
                    "filename": resume.filename,
                    "name": summary_data.get("name", ""),
                    "email": summary_data.get("email", ""),
                    "phone": summary_data.get("phone", ""),
                    "qualification": summary_data.get("qualification", ""),
                    "experience": summary_data.get("experience", ""),
                    "skills": summary_data.get("skills", ""),
                    "evaluation": summary_data.get("evaluation", ""),
                    "personal_evaluation": summary_data.get("personal_evaluation", ""),
                    "specific_role": summary_data.get("primary_role", ""),
                    "categories": categorize_resume(summary_data.get("primary_role", ""), summary_data.get("skills", ""))
                }
                resume_cache[session_id]["summaries"][summary_key] = result

            if action == "match":
                if cached_match and "percentage_match" in cached_match and cached_match["percentage_match"] != "":
                    result.update(cached_match)
                else:
                    resume_text = extract_text_from_file(temp_file_path)
                    if not resume_text.strip() and os.path.splitext(resume.filename.lower())[1] in ('.png', '.jpg', '.jpeg'):
                        resume_text = extract_text_with_ocr(temp_file_path, lang='hin+guj+eng')
                    language = detect_language(resume_text)
                    if language != 'en':
                        resume_text = translate_to_english(resume_text, source_lang=language)

                    match_response = get_gemini_response(
                        f"Job Description:\n{job_description}\n\nResume:\n{resume_text}",
                        prompts["match"]
                    )
                    match_data = parse_gemini_response(match_response, action="match")
                    match_result = {
                        "percentage_match": match_data["percentage_match"],
                        "justification": match_data["justification"],
                        "lacking": match_data["lacking"]
                    }

                    if result["specific_role"] == "" or result["categories"] == ["Uncategorized"]:
                        percentage = int(match_data["percentage_match"].replace('%', '')) if match_data["percentage_match"] else 0
                        justification_lower = match_data["justification"].lower()
                        if percentage >= 70:
                            if "qa" in justification_lower or "testing" in justification_lower or "automation" in justification_lower:
                                result["specific_role"] = "QA Engineer"
                                result["categories"] = ["Testing"]
                            elif "machine learning" in justification_lower or "ai" in justification_lower:
                                result["specific_role"] = "AI/ML Engineer"
                                result["categories"] = ["AIML"]
                            elif "full stack" in justification_lower:
                                result["specific_role"] = "Full Stack Developer"
                                result["categories"] = ["Full Stack"]
                            elif "python" in justification_lower or "flask" in justification_lower or "fastapi" in justification_lower:
                                result["specific_role"] = "Python Developer"
                                result["categories"] = ["Backend"]
                            elif "node" in justification_lower or "express" in justification_lower:
                                result["specific_role"] = "Node.js Developer"
                                result["categories"] = ["Backend"]
                            elif "react" in justification_lower or "angular" in justification_lower or "vue" in justification_lower:
                                result["specific_role"] = "Frontend Developer"
                                result["categories"] = ["Frontend"]
                            elif "android" in justification_lower or "kotlin" in justification_lower:
                                result["specific_role"] = "Android Developer"
                                result["categories"] = ["Mobile"]
                            else:
                                result["specific_role"] = "Software Developer"
                                result["categories"] = ["Uncategorized"]

                    result.update(match_result)
                    resume_cache[session_id]["matches"][match_key] = match_result

            results.append(result)
            for category in result["categories"]:
                categorized_results[category].append(result)

        except Exception as e:
            result = {
                "filename": resume.filename,
                "name": "Error processing resume",
                "email": "",
                "phone": "",
                "qualification": "",
                "experience": "",
                "skills": "",
                "evaluation": "",
                "personal_evaluation": str(e),
                "specific_role": "",
                "categories": ["Uncategorized"]
            }
            if action == "match":
                result.update({
                    "percentage_match": "",
                    "justification": "",
                    "lacking": ""
                })
            resume_cache[session_id]["summaries"][summary_key] = result
            if action == "match":
                resume_cache[session_id]["matches"][match_key] = {"percentage_match": "", "justification": "", "lacking": ""}
            results.append(result)
            categorized_results["Uncategorized"].append(result)

    if category_filter and category_filter in categorized_results:
        return jsonify({"results": categorized_results[category_filter], "category": category_filter})
    return jsonify({"results": results, "categorized_results": categorized_results})

@app.route("/get_cached_results", methods=["GET"])
def get_cached_results():
    session_id = session.get('session_id')
    if session_id not in resume_cache or not resume_cache[session_id]["summaries"]:
        return jsonify({"error": "No cached results available. Please process resumes first."}), 404
    
    percentage_threshold = float(request.args.get('percentage_threshold', 0))

    results = []
    categorized_results = {
        "Frontend": [], "Backend": [], "Full Stack": [], "Mobile": [], "AIML": [],
        "Testing": [], "Cloud Engineer": [], "DevOps": [], "HR": [], "Uncategorized": []
    }

    for filename, summary in resume_cache[session_id]["summaries"].items():
        result = summary.copy()
        for match_key, match_data in resume_cache[session_id]["matches"].items():
            if match_key.startswith(filename):
                result.update(match_data)
                break
        
        percentage_str = result.get("percentage_match", "0%")
        try:
            percentage = float(percentage_str.replace('%', ''))
        except ValueError:
            percentage = 0.0
        
        if percentage >= percentage_threshold:
            results.append(result)
            for category in result["categories"]:
                categorized_results[category].append(result)

    return jsonify({"results": results, "categorized_results": categorized_results})

@app.route("/download_csv", methods=["POST"])
def download_csv():
    try:
        logger.debug("Received request for /download_csv: %s", request.get_json())
        
        if not request.is_json:
            logger.error("Request does not contain JSON data")
            return jsonify({"error": "Request must contain JSON data"}), 400

        data = request.json.get("summarized_data")
        percentage_threshold = float(request.json.get("percentage_threshold", 0))

        if data is None:
            logger.error("No summarized_data provided in request")
            return jsonify({"error": "No summarized data provided."}), 400

        if not isinstance(data, list):
            logger.error("summarized_data is not a list: %s", type(data))
            return jsonify({"error": "summarized_data must be a list."}), 400

        filtered_data = []
        for item in data:
            percentage_str = item.get("percentage_match", "0%")
            try:
                percentage = float(percentage_str.replace('%', ''))
            except ValueError:
                percentage = 0.0
            if percentage >= percentage_threshold:
                filtered_data.append(item)

        if not filtered_data:
            logger.warning("No data found after applying percentage threshold: %s", percentage_threshold)
            return jsonify({"error": f"No data found with percentage match >= {percentage_threshold}%."}), 404

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Filename", "Categories", "Specific Role", "Name", "Email", "Phone", "Qualification", 
                         "Experience", "Total Experience (Years)", "Skills", "Percentage Match", "Lacking"])

        for result in filtered_data:
            experience = result.get("experience", "").replace("<br>", " | ").replace("\n", " | ").strip()
            skills = result.get("skills", "").replace(", ", " | ").replace(",", " | ").strip()
            lacking = result.get("lacking", "").replace("<br>", " | ").replace("\n", " | ").replace("- ", "").strip()

            writer.writerow([
                result.get("filename", ""),
                ", ".join(result.get("categories", [])),
                result.get("specific_role", ""),
                result.get("name", ""),
                result.get("email", ""),
                result.get("phone", ""),
                result.get("qualification", ""),
                experience,
                calculate_experience_years(experience),
                skills,
                result.get("percentage_match", ""),
                lacking
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=summary_all.csv"}
        )
    except Exception as e:
        logger.error("Error in /download_csv: %s", str(e))
        return jsonify({"error": f"Error creating CSV: {e}"}), 500

@app.route("/download_filtered_csv", methods=["POST"])
def download_filtered_csv():
    try:
        logger.debug("Received request for /download_filtered_csv: %s", request.get_json())
        
        if not request.is_json:
            logger.error("Request does not contain JSON data")
            return jsonify({"error": "Request must contain JSON data"}), 400

        data = request.json.get("summarized_data")
        categories = request.json.get("categories", [])
        percentage_threshold = float(request.json.get("percentage_threshold", 0))

        if data is None:
            logger.error("No summarized_data provided in request")
            return jsonify({"error": "No summarized data provided."}), 400

        if not isinstance(data, list):
            logger.error("summarized_data is not a list: %s", type(data))
            return jsonify({"error": "summarized_data must be a list."}), 400

        if not categories:
            logger.error("No categories provided in request")
            return jsonify({"error": "No categories selected."}), 400

        if not isinstance(categories, list):
            logger.error("categories is not a list: %s", type(categories))
            return jsonify({"error": "categories must be a list."}), 400

        filtered_data = [item for item in data if any(cat in item.get("categories", []) for cat in categories)]
        final_filtered_data = []
        for item in filtered_data:
            percentage_str = item.get("percentage_match", "0%")
            try:
                percentage = float(percentage_str.replace('%', ''))
            except ValueError:
                percentage = 0.0
            if percentage >= percentage_threshold:
                final_filtered_data.append(item)

        if not final_filtered_data:
            logger.warning("No data found for the selected categories and percentage threshold: %s, %s", categories, percentage_threshold)
            return jsonify({"error": f"No data found for the selected categories with percentage match >= {percentage_threshold}%."}), 404

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Filename", "Categories", "Specific Role", "Name", "Email", "Phone", "Qualification", 
                         "Experience", "Total Experience (Years)", "Skills", "Percentage Match", "Lacking"])

        for result in final_filtered_data:
            experience = result.get("experience", "").replace("<br>", " | ").replace("\n", " | ").strip()
            skills = result.get("skills", "").replace(", ", " | ").replace(",", " | ").strip()
            lacking = result.get("lacking", "").replace("<br>", " | ").replace("\n", " | ").replace("- ", "").strip()

            writer.writerow([
                result.get("filename", ""),
                ", ".join(result.get("categories", [])),
                result.get("specific_role", ""),
                result.get("name", ""),
                result.get("email", ""),
                result.get("phone", ""),
                result.get("qualification", ""),
                experience,
                calculate_experience_years(experience),
                skills,
                result.get("percentage_match", ""),
                lacking
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=summary_{'_'.join(categories)}.csv"}
        )
    except Exception as e:
        logger.error("Error in /download_filtered_csv: %s", str(e))
        return jsonify({"error": f"Error creating filtered CSV: {e}"}), 500

@app.route("/shortlist_resumes", methods=["POST"])
def shortlist_resumes():
    try:
        logger.debug("Received request for /shortlist_resumes: %s", request.get_json())
        
        if not request.is_json:
            logger.error("Request does not contain JSON data")
            return jsonify({"error": "Request must contain JSON data"}), 400

        data = request.json.get("summarized_data")
        percentage_threshold = float(request.json.get("percentage_threshold", 0))
        categories = request.json.get("categories", [])
        session_id = session.get('session_id')

        if data is None:
            logger.error("No summarized_data provided in request")
            return jsonify({"error": "No summarized data provided."}), 400

        if not isinstance(data, list):
            logger.error("summarized_data is not a list: %s", type(data))
            return jsonify({"error": "summarized_data must be a list."}), 400

        if session_id not in uploaded_files:
            logger.error("No uploaded files found for session: %s", session_id)
            return jsonify({"error": "No uploaded files found. Please process resumes first."}), 404

        shortlisted_data = []
        for item in data:
            percentage_str = item.get("percentage_match", "0%")
            try:
                percentage = float(percentage_str.replace('%', ''))
            except ValueError:
                percentage = 0.0

            matches_percentage = percentage >= percentage_threshold
            matches_categories = not categories or any(cat in item.get("categories", []) for cat in categories)

            if matches_percentage and matches_categories:
                shortlisted_data.append(item)

        if not shortlisted_data:
            logger.warning("No resumes found with percentage match >= %s and categories: %s", percentage_threshold, categories)
            return jsonify({"error": f"No resumes found with percentage match >= {percentage_threshold}% and categories {categories}."}), 404

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        category_suffix = "_".join(categories) if categories else "all_categories"
        shortlist_folder = os.path.join(SHORTLIST_DIR, f"shortlist_{category_suffix}_{timestamp}")
        try:
            os.makedirs(shortlist_folder, exist_ok=True)
            logger.debug(f"Created shortlist folder: {shortlist_folder}")
        except Exception as e:
            logger.error(f"Failed to create shortlist folder {shortlist_folder}: {e}")
            return jsonify({"error": f"Failed to create shortlist folder: {e}"}), 500

        shortlisted_count = 0
        for item in shortlisted_data:
            filename = item.get("filename")
            if filename in uploaded_files[session_id]:
                temp_file_path = uploaded_files[session_id][filename]
                destination_path = os.path.join(shortlist_folder, filename)
                try:
                    shutil.copy2(temp_file_path, destination_path)
                    logger.debug(f"Copied {temp_file_path} to {destination_path}")
                    shortlisted_count += 1
                except Exception as e:
                    logger.error(f"Failed to copy {temp_file_path} to {destination_path}: {e}")
                    continue

        if shortlisted_count == 0:
            logger.warning("No files were successfully shortlisted")
            return jsonify({"error": "No files were successfully shortlisted. Check server logs for details."}), 500

        logger.info("Shortlisted %d resumes to %s", shortlisted_count, shortlist_folder)
        return jsonify({"message": f"Successfully shortlisted {shortlisted_count} resumes to {shortlist_folder}."}), 200

    except Exception as e:
        logger.error("Error in /shortlist_resumes: %s", str(e))
        return jsonify({"error": f"Error shortlisting resumes: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)