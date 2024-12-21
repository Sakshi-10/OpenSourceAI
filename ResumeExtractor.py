import fitz  # PyMuPDF
from flask import Flask, render_template, request, redirect, url_for,session
from werkzeug.utils import secure_filename
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer
from huggingface_hub import login
from dotenv import load_dotenv
import os
import re
import requests

app = Flask(__name__)
# Set Flask's secret key using the environment variable
app.secret_key = os.getenv('SECRET_KEY')


# Directory to save uploaded PDFs
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf"}


# Function to check if file extension is allowed
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Step 2: Extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)  # Open the PDF file
    text = ""
    for page in doc:  # Loop through each page and extract text
        text += page.get_text("text")  # Extract text as plain text
    return text


# Step 3: Use Mistral AI to generate a response (or keyword extraction)
# Load Mistral model for text generation (use authentication if needed)
# Authenticate HuggingFace with a token
# If you need to use a token, uncomment the line below.

# Load .env file
load_dotenv()

# Access token from environment variable
token = os.getenv("HUGGINGFACE_TOKEN")

# Login to Hugging Face
login(token=token)

# Step 3: Use the DistilGPT-2 model to generate text or keywords
# Load model and tokenizer separately and pass the token explicitly
model = AutoModelForCausalLM.from_pretrained("distilgpt2", use_auth_token=token)
tokenizer = AutoTokenizer.from_pretrained("distilgpt2", use_auth_token=token)
# Initialize the pipeline using the loaded model and tokenizer
mistral = pipeline("text-generation", model=model, tokenizer=tokenizer)

def extract_keywords_from_text(text):
   
    # Define a dictionary to hold the extracted data
    keywords = {
        'name': None,
        'location': None,
        'skills': None,
        'experience': None,
        'education': None,
        'projects': None
    }

    # Clean the text by removing extra spaces and newlines
    cleaned_text = " ".join(text.splitlines())

    # Step 1: Extract name from the first line (title)
    # We'll focus on the first line or a few initial lines that are most likely to contain the name
    first_line = cleaned_text.split(' ')[0]  # Take the first word as the first line

    # Regex pattern to capture capitalized names (first and last names)
    name_pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"  # Matches First Last name

    # Try to extract name from the first line
    name_match = re.match(name_pattern, first_line)
    if name_match:
        keywords['name'] = name_match.group(1).strip()

    # Step 2: Use Mistral AI to generate keywords from the resume text
    response = mistral(text, max_length=500)  # You can adjust the max_length
    extracted_text = response[0]["generated_text"]
     # Regex patterns for extracting sections (basic examples)
    
    location_pattern = r"(?i)Location:?\s*(.*)"
    skills_pattern = r"(?i)Skills?:?\s*(.*)"
    experience_pattern = r"(?i)Experience?:?\s*(.*)"
    education_pattern = r"(?i)Education?:?\s*(.*)"
    projects_pattern = r"(?i)Projects?:?\s*(.*)"
   
    # Extract the name
    location_match = re.search(location_pattern, extracted_text)
    if location_match:
        keywords['location'] = location_match.group(1).strip()

    # Extract the skills
    skills_match = re.search(skills_pattern, extracted_text)
    if skills_match:
        keywords['skills'] = skills_match.group(1).strip()

    # Extract the experience
    experience_match = re.search(experience_pattern, extracted_text)
    if experience_match:
        keywords['experience'] = experience_match.group(1).strip()

    # Extract the education
    education_match = re.search(education_pattern, extracted_text)
    if education_match:
        keywords['education'] = education_match.group(1).strip()

    # Extract the projects
    projects_match = re.search(projects_pattern, extracted_text)
    if projects_match:
        keywords['projects'] = projects_match.group(1).strip()

    return keywords


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(request.url)

    file = request.files["file"]

    if file.filename == "":
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Step 1: Extract text from the uploaded PDF
        resume_text = extract_text_from_pdf(file_path)

        # Step 2: Use Mistral AI to extract keywords and insights from the resume text
        extracted_keywords = extract_keywords_from_text(resume_text)

        # Step 3: Display extracted details in a form or response
        return render_template("form.html", keywords=extracted_keywords)

    return redirect(request.url)

@app.route("/submit",methods=["POST"])
def submit_form():
    # Get form data from the POST request
    name = request.form.get('name')
    location = request.form.get('location')
    skills = request.form.get('skills')
    experience = request.form.get('experience')
    education = request.form.get('education')
    projects = request.form.get('projects')

    # Store the submitted form data in session to use later
    session['submitted_data'] = {
        'name': name,
        'location': location,
        'skills': skills,
        'experience': experience,
        'education': education,
        'projects': projects
    }
      
    # For now, we will just print the data and redirect back to the home page
    print(f"Name: {name}, Skills: {skills}, Experience: {experience}, Education: {education}, Projects: {projects}")
    
    return redirect(url_for('linkdin'))
  
@app.route('/linkdin')
def linkdin():
    # Retrieve the submitted data from session
    submitted_data = session.get('submitted_data', {})

    # Extract skill and location data from the session
    skills = submitted_data.get('skills', '')
    location = submitted_data.get('location', '')

    # Get the first skill from the comma-separated list of skills
    skills_list = [skill.strip() for skill in skills.split(',')]
    first_skill = skills_list[0] if skills_list else None
    print(first_skill)
    if not first_skill:
        return "No Skill provided to search jobs"

   # Prepare the LinkedIn API request based on skills and location
    career_keyword = first_skill  # We use the "skills" field as the job keyword
    location = location if location else "anywhere"  # Default to "anywhere" if no location is provided
    url = "https://linkedin-api8.p.rapidapi.com/search-jobs"
    #querystring = {"keywords":"golang","locationId":"92000000","datePosted":"anyTime","sort":"mostRelevant"}
    querystring = {"keywords":career_keyword,"locationId":"92000000","datePosted":"anyTime","sort":"mostRelevant"}
    headers = {
	#"x-rapidapi-key": "Paste your Rapid API Key",
	"x-rapidapi-host": "linkedin-api8.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    
    print(f"Response code is :{response.status_code} ");
   
    data = response.json()
    print(data)

     # Pass data to the template
    return render_template('linkdin.html', jobs=data,user=session.get('user'))



if __name__ == "__main__":
    app.run(debug=True)
