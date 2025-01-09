from dotenv import load_dotenv
import base64
import streamlit as st
import os
import io
from PIL import Image
import pdf2image
import google.generativeai as genai
from PyPDF2 import PdfReader
import re
import fitz

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def input_pdf_setup(uploaded_file):
    pdf_parts = []
    uploaded_file_bytes = uploaded_file.read()  # Read the file as bytes
    doc = fitz.open(io.BytesIO(uploaded_file_bytes))  # Open PDF from bytes

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)  # Load a specific page
        img = page.get_pixmap()  # Get an image representation of the page
        img_byte_arr = io.BytesIO(img.tobytes())  # Convert to bytes
        pdf_parts.append({
            "mime_type": "image/jpeg",
            "data": base64.b64encode(img_byte_arr.getvalue()).decode()
        })
    return pdf_parts

# Get Gemini API response
def get_gemini_response(input, pdf_content, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input, pdf_content[0], prompt])
    return response.text

# Streamlit App
st.set_page_config(page_title="ATS Resume Expert")
st.header("ATS Tracking System")
input_text = st.text_area("Job Description: ", key="input")
uploaded_files = st.file_uploader("Upload resumes (PDF)...", type=["pdf"], accept_multiple_files=True)

submit1 = st.button("Summarize Resumes")
submit3 = st.button("Percentage Match")

input_prompt1 = """
first of give information like NAME; email; qulification; experince ; from the resumes .and then asum
You are an experienced Technical Human Resource Manager And Review each provided resume against the job description.
Please provide a professional evaluation, including strengths, weaknesses, and alignment with the role. and all evalution should be in one or two line .
"""

input_prompt3 = """
You are a skilled ATS (Applicant Tracking System) scanner. Evaluate each resume against the job description.
Provide a percentage match, list missing keywords, and offer final thoughts. and all evalution should be in one or two line.
"""

if submit1 and uploaded_files:
    st.subheader("Resume Summaries")
    for uploaded_file in uploaded_files:
        pdf_content = uploaded_file.read()
        # structured_info = extract_pdf_info(pdf_content)
        pdf_parts = input_pdf_setup(pdf_content)
        response = get_gemini_response(input_prompt1, pdf_parts, input_text)
        
        st.markdown(f"### {uploaded_file.name}")
        # st.json(structured_info)
        # st.write("**Gemini Response:**")
        st.write(response)

elif submit3 and uploaded_files:
    st.subheader("Percentage Match Results")
    for uploaded_file in uploaded_files:
        pdf_content = uploaded_file.read()
        pdf_parts = input_pdf_setup(pdf_content)
        response = get_gemini_response(input_prompt3, pdf_parts, input_text)
        
        st.markdown(f"### {uploaded_file.name}")
        st.write(response)
else:
    if submit1 or submit3:
        st.write("Please upload at least one resume.")
