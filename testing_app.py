import os
import random
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException

# Initialize WebDriver
driver = webdriver.Chrome()
driver.get("http://127.0.0.1:5000")  # Change to your local server URL

# Explicit wait
wait = WebDriverWait(driver, 60)

# Resume folder path
resume_folder = r"C:\Users\Shruti Darji\OneDrive\Desktop\Logictrix\poc_resume\logictrix_resume"

# Get all PDF resumes
all_resumes = [os.path.join(resume_folder, f) for f in os.listdir(resume_folder) if f.endswith(".pdf")]

# Job roles to test
job_roles = [
    "Python Developer", "Django Developer", "Flask Developer", "Full Stack Python Developer",
    "Machine Learning Engineer", "Data Scientist", "React Developer", "Angular Developer",
    "Vue.js Developer", "Frontend Engineer", "Node.js Developer", "Java Developer",
    "Spring Boot Developer", "PHP Developer", "Ruby on Rails Developer", "MERN Stack Developer",
    "MEAN Stack Developer", "LAMP Stack Developer", "Full Stack Engineer",
    "Android Developer", "iOS Developer", "Flutter Developer", "React Native Developer",
    "DevOps Engineer", "AWS Cloud Engineer", "Azure Cloud Developer", "Kubernetes Engineer",
    "Cybersecurity Analyst", "Data Engineer", "Software Tester", "Scrum Master", "Project Manager"
]

def handle_alert():
    """Handles unexpected alerts and closes them."""
    try:
        alert = driver.switch_to.alert
        print(f"⚠️ Alert detected: {alert.text}")
        alert.accept()
        time.sleep(2)  # Allow alert to close
    except NoAlertPresentException:
        pass  # No alert detected

def test_resume_expert(job_role):
    try:
        print(f"\n🔄 Starting test for job role: '{job_role}'")

        # Refresh page to clear previous data
        driver.refresh()
        time.sleep(2)  # Allow time for refresh
        handle_alert()

        # Select 5 random resumes
        selected_resumes = random.sample(all_resumes, min(5, len(all_resumes)))
        print(f"📂 Selected resumes: {[os.path.basename(r) for r in selected_resumes]}")

        # Enter job role
        job_role_input = wait.until(EC.element_to_be_clickable((By.ID, "jobRole")))
        job_role_input.clear()
        job_role_input.send_keys(job_role)

        # Click Generate JD button
        generate_jd_button = driver.find_element(By.ID, "generateJD")
        generate_jd_button.click()

        # Wait for AI-generated Job Description
        jd_textarea = wait.until(EC.presence_of_element_located((By.ID, "jobDescription")))
        wait.until(lambda driver: jd_textarea.get_attribute("value").strip() != "")
        print("✅ Job description generated.")

        # Upload all 5 resumes at once
        file_input = driver.find_element(By.ID, "resumes")
        file_input.send_keys("\n".join(selected_resumes))
        print("✅ 5 resumes uploaded.")

        # Click Summarize and wait for completion
        summarize_button = driver.find_element(By.ID, "summarizeButton")
        summarize_button.click()
        wait.until(EC.invisibility_of_element((By.ID, "loader")))
        print("✅ Summarization completed.")

        # Click Percentage Match and wait for completion
        match_button = driver.find_element(By.ID, "matchButton")
        match_button.click()
        wait.until(EC.invisibility_of_element((By.ID, "loader")))
        print("✅ Percentage Match completed.")

        # Click Download CSV
        download_csv_button = wait.until(EC.element_to_be_clickable((By.ID, "downloadCsvButton")))
        download_csv_button.click()
        print("✅ CSV Download initiated.")

    except Exception as e:
        print(f"❌ Test failed for job role '{job_role}': {e}")

# Run tests for each job role (one by one)
for role in job_roles:
    test_resume_expert(role)
    time.sleep(5)  # Short delay before switching roles

driver.quit()
