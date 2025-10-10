from flask import Flask, render_template, request, redirect, session, jsonify, send_file
from reportlab.pdfgen import canvas
from io import BytesIO
import os
from utils.ocr_utils import extract_aadhaar_number

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def generate_assessment(data, aadhaar_verified=True, extracted_aadhaar=None):
    income = int(data.get('income', 0))
    loan_amnt = data.get('loan_amnt', 'N/A')
    loan_type = data.get('loan_type', 'N/A')
    bank = data.get('bank_name', 'N/A')
    tenure = data.get('loan_tenure', 'N/A')
    user_name = data.get('name', 'N/A')

    # Check for document mismatches first (Aadhaar number only)
    if not aadhaar_verified:
        reason = "Aadhaar Number Mismatch - Document verification failed"
        status = "Not Eligible"
        recommendations = [
            "Please ensure the Aadhaar number you entered matches the document",
            "Upload a clear, high-quality image of your Aadhar card",
            "Contact support if you believe this is an error"
        ]
    else:
        # Eligibility logic without credit score
        min_income_threshold = 25000
        is_income_sufficient = income >= min_income_threshold
        status = "Eligible" if is_income_sufficient else "Not Eligible"
        reason = "Sufficient income for requested loan" if is_income_sufficient else "Income below minimum threshold"
        recommendations = (
            [
                "Maintain consistent income inflow",
                "Keep existing EMIs low to improve affordability",
                "Consider adding a co-applicant to strengthen the application",
                "Choose a longer tenure to reduce monthly EMI",
            ]
            if not is_income_sufficient
            else [
                "You're on track! Maintain your financial discipline.",
                "Upload clear documents to speed up approval.",
            ]
        )

    summary = f"""
📋 Loan Eligibility Assessment

🔍 Status: {status}
🔍 Reason: {reason}  
👤 Applicant Name: {user_name}
🆔 Entered Aadhaar: {data.get('aadhaar_number', 'N/A')}
🆔 Document Aadhaar: {extracted_aadhaar if extracted_aadhaar else 'N/A'}
💰 Monthly Income: ₹{income}  
🏦 Bank: {bank}  
📄 Loan Type: {loan_type}  
💸 Requested Amount: ₹{loan_amnt}  
📆 Tenure: {tenure} months  

✅ Recommendations:
{chr(10).join([f"{i+1}. {r}" for i, r in enumerate(recommendations)])}
"""
    return summary, status


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # You can add authentication logic here
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        return redirect('/dashboard')
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        user_input = request.json.get('message', '').strip()
        session.setdefault('loan_data', {})
        data = session['loan_data']

        def is_valid_number(value): return value.isdigit()
        def is_valid_employment(value): return value.lower() in ['salaried', 'self-employed', 'freelancer']
        def is_valid_aadhaar(value):
            digits = ''.join(ch for ch in value if ch.isdigit())
            return len(digits) == 12

        if 'name' not in data:
            data['name'] = user_input
            reply = f"Hi {user_input}! How old are you?"
        elif 'age' not in data:
            reply = "What’s your employment type?(Salaried, Self-employed, or Freelancer)" if is_valid_number(user_input) else "Please enter a valid age."
            if is_valid_number(user_input): data['age'] = user_input
        elif 'employment_type' not in data:
            reply = "What is your monthly income?" if is_valid_employment(user_input) else "Please enter a valid employment type."
            if is_valid_employment(user_input): data['employment_type'] = user_input.lower()
        elif 'income' not in data:
            reply = "Do you have any existing EMIs or loans?(if No enter 0)" if is_valid_number(user_input) else "Please enter your income in numbers."
            if is_valid_number(user_input): data['income'] = user_input
        elif 'existing_emis' not in data:
            data['existing_emis'] = user_input
            reply = "Which bank do you hold your salary account with?"
        elif 'bank_name' not in data:
            data['bank_name'] = user_input
            reply = "Do you have a co-applicant? (Yes / No)"
        elif 'co_applicant' not in data:
            data['co_applicant'] = user_input
            reply = "Please enter co-applicant’s monthly income." if user_input.lower() == 'yes' else "Please enter your 12-digit Aadhaar number."
            if user_input.lower() != 'yes':
                data['co_income'] = "N/A"
                data['co_credit_score'] = "N/A"
        elif data.get('co_applicant', '').lower() == 'yes' and 'co_income' not in data:
            reply = "Please enter your 12-digit Aadhaar number." if is_valid_number(user_input) else "Enter co-applicant’s income in numbers."
            if is_valid_number(user_input): data['co_income'] = user_input
        elif 'aadhaar_number' not in data:
            # Ask Aadhaar number before PAN
            if is_valid_aadhaar(user_input):
                # Normalize to XXXX XXXX XXXX
                d = ''.join(ch for ch in user_input if ch.isdigit())
                data['aadhaar_number'] = f"{d[0:4]} {d[4:8]} {d[8:12]}"
                reply = "What is your PAN number?"
            else:
                reply = "Please enter your 12-digit Aadhaar number (digits only)."
        elif 'pan_number' not in data:
            data['pan_number'] = user_input
            reply = "What type of loan are you applying for?"
        elif 'loan_type' not in data:
            data['loan_type'] = user_input
            reply = "What is the desired loan amount?"
        elif 'loan_amnt' not in data:
            reply = "What is the preferred tenure in months?(Personal/Home/Vehicle/Business/Education/Gold/Other)" if is_valid_number(user_input) else "Enter loan amount in numbers."
            if is_valid_number(user_input): data['loan_amnt'] = user_input
        elif 'loan_tenure' not in data:
            reply = "Do you have collateral or property to pledge?" if is_valid_number(user_input) else "Enter tenure in months (numbers only)."
            if is_valid_number(user_input): data['loan_tenure'] = user_input
        elif 'collateral' not in data:
            data['collateral'] = user_input
            reply = "Thanks! You can now upload your documents on the dashboard."
        else:
            reply = "You're all set! Head to the dashboard to upload documents and view your eligibility report."

        session.modified = True
        return jsonify({"reply": reply})

    # Reset conversation on fresh load to avoid stale session data
    session['loan_data'] = {}
    session.modified = True
    return render_template('chatbot.html')

@app.route('/upload', methods=['POST'])
def upload_docs():
    uploaded_files = {}
    
    # Save uploaded files
    for field in ['aadhar', 'salary', 'bank']:
        file = request.files.get(field)
        if file:
            folder = os.path.join(app.config['UPLOAD_FOLDER'], field + '_slips' if field == 'salary' else field)
            os.makedirs(folder, exist_ok=True)
            file_path = os.path.join(folder, file.filename)
            file.save(file_path)
            uploaded_files[field] = file_path

    loan_data = session.get('loan_data', {})
    user_name = loan_data.get('name', '')
    
    # Perform document verifications if Aadhar card is uploaded
    aadhaar_verified = True
    extracted_aadhaar = None
    
    if 'aadhar' in uploaded_files:
        try:
            # Aadhaar number verification
            extracted_aadhaar = extract_aadhaar_number(uploaded_files['aadhar'])
            entered_aadhaar = session.get('loan_data', {}).get('aadhaar_number')
            if entered_aadhaar and extracted_aadhaar:
                entered_digits = ''.join(ch for ch in entered_aadhaar if ch.isdigit())
                extracted_digits = ''.join(ch for ch in extracted_aadhaar if ch.isdigit())
                aadhaar_verified = (entered_digits == extracted_digits)
            elif entered_aadhaar and not extracted_aadhaar:
                aadhaar_verified = False
        except Exception as e:
            print(f"Error during name verification: {e}")
            aadhaar_verified = False
    
    # Generate assessment with verification results
    assessment, result = generate_assessment(
        loan_data,
        aadhaar_verified=aadhaar_verified,
        extracted_aadhaar=extracted_aadhaar,
    )

    session['loan_result'] = result
    session['loan_assessment'] = assessment
    session['aadhaar_verified'] = aadhaar_verified
    session['extracted_aadhaar'] = extracted_aadhaar
    return redirect('/result')

@app.route('/result')
def result_page():
    result = session.get('loan_result', 'N/A')
    assessment = session.get('loan_assessment', 'No assessment available.')
    name_verified = session.get('name_verified', True)
    extracted_name = session.get('extracted_name', None)
    return render_template('result.html', result=result, assessment=assessment, 
                         name_verified=name_verified, extracted_name=extracted_name)

@app.route('/generate_pdf')
def generate_pdf():
    data = session.get('loan_data', {})
    result= session.ge('loan_result','N/A')
    uploaded_files = []

    for field in ['aadhar', 'salary', 'bank']:
        folder = os.path.join(app.config['UPLOAD_FOLDER'], field + '_slips' if field == 'salary' else field)
        if os.path.exists(folder):
            files = os.listdir(folder)
            uploaded_files.extend([f"{field.capitalize()}: {file}" for file in files])

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 12)
    y = 800

    p.drawString(100, y, "LoanAdvisor Summary Report")
    y -= 30

    for key, value in data.items():
        p.drawString(100, y, f"{key.replace('_', ' ').title()}: {value}")
        y -= 20

    y -= 10
    p.drawString(100, y, "Uploaded Documents:")
    for doc in uploaded_files:
        y -= 20
        p.drawString(120, y, doc)

    y -= 30
    p.drawString(100, y, "Loan Eligibility: status")
    p.drawString(100,f"Loan Eligibility:{result}")
    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(buffer, download_name="LoanAdvisor_Report.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)