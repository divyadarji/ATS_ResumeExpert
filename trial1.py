from dotenv import load_dotenv
import base64
import streamlit as st
import os
import io
import pdf2image
import google.generativeai as genai
import fitz  # PyMuPDF
import re

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Function to process uploaded PDF and convert pages to images
def input_pdf_setup(uploaded_file):
    pdf_parts = []
    try:
        doc = fitz.open(io.BytesIO(uploaded_file))  # Open PDF from bytes
        for page in doc:
            pix = page.get_pixmap()  # Convert page to image
            img_byte_arr = io.BytesIO()
            pix.save(img_byte_arr)
            pdf_parts.append({
                "mime_type": "image/png",  # Using PNG format
                "data": base64.b64encode(img_byte_arr.getvalue()).decode()
            })
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
    if not pdf_parts:
        st.error("No pages found in the PDF.")
    return pdf_parts

# Function to get Gemini API response
def get_gemini_response(input, pdf_content, prompt):
    if not pdf_content:
        raise ValueError("PDF content is empty, no pages to process.")
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
Please provide a professional evaluation, including strengths, weaknesses, and alignment with the role. and all evalution should be in one or two line ."""

input_prompt3 = """
You are a skilled ATS (Applicant Tracking System) scanner. Evaluate each resume against the job description.
Provide a percentage match, list missing keywords, and offer final thoughts. and all evalution should be in one or two line."""

if submit1 and uploaded_files:
    st.subheader("Resume Summaries")
    for uploaded_file in uploaded_files:
        pdf_content = uploaded_file.read()
        pdf_parts = input_pdf_setup(pdf_content)
        
        if pdf_parts:  # Check if pdf_parts is non-empty
            response = get_gemini_response(input_prompt1, pdf_parts, input_text)
            st.markdown(f"### {uploaded_file.name}")
            st.write("**Gemini Response:**")
            st.write(response)
        else:
            st.warning("No content extracted from the PDF.")

elif submit3 and uploaded_files:
    st.subheader("Percentage Match Results")
    for uploaded_file in uploaded_files:
        pdf_content = uploaded_file.read()
        pdf_parts = input_pdf_setup(pdf_content)
        
        if pdf_parts:  # Check if pdf_parts is non-empty
            response = get_gemini_response(input_prompt3, pdf_parts, input_text)
            st.markdown(f"### {uploaded_file.name}")
            st.write(response)
        else:
            st.warning("No content extracted from the PDF.")
else:
    if submit1 or submit3:
        st.write("Please upload at least one resume.")
