from flask import Blueprint, request, session, jsonify

chatbot_bp = Blueprint('chatbot_bp', __name__)

@chatbot_bp.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        user_input = request.json.get('message', '').strip()
        session.setdefault('loan_data', {})
        data = session['loan_data']

        def is_valid_number(value):
            return value.isdigit()

        def is_valid_credit_score(value):
            return value.isdigit() and 300 <= int(value) <= 900

        def is_valid_employment(value):
            return value.lower() in ['salaried', 'self-employed', 'freelancer']

        # Conversational flow
        if 'name' not in data:
            data['name'] = user_input
            reply = f"Hi {user_input}! How old are you?"
        elif 'age' not in data:
            if is_valid_number(user_input):
                data['age'] = user_input
                reply = "What’s your employment type? (Salaried / Self-employed / Freelancer)"
            else:
                reply = "Please enter a valid age (numbers only)."
        elif 'employment_type' not in data:
            if is_valid_employment(user_input):
                data['employment_type'] = user_input.lower()
                reply = "What is your monthly income?"
            else:
                reply = "Please enter a valid employment type: Salaried, Self-employed, or Freelancer."
        elif 'income' not in data:
            if is_valid_number(user_input):
                data['income'] = user_input
                reply = "Do you have any existing EMIs or loans? (Yes / No)"
            else:
                reply = "Please enter your monthly income in numbers."
        elif 'existing_emis' not in data:
            data['existing_emis'] = user_input
            reply = "What is your credit score?"
        elif 'credit_score' not in data:
            if is_valid_credit_score(user_input):
                data['credit_score'] = user_input
                reply = "Which bank do you hold your salary account with?"
            else:
                reply = "Please enter a valid credit score between 300 and 900."
        elif 'bank_name' not in data:
            data['bank_name'] = user_input
            reply = "Do you have a co-applicant? (Yes / No)"
        elif 'co_applicant' not in data:
            data['co_applicant'] = user_input
            if user_input.lower() == 'yes':
                reply = "Please enter co-applicant’s monthly income."
            else:
                data['co_income'] = "N/A"
                data['co_credit_score'] = "N/A"
                reply = "What is your PAN number?"
        elif 'co_income' not in data and data['co_applicant'].lower() == 'yes':
            if is_valid_number(user_input):
                data['co_income'] = user_input
                reply = "What is co-applicant’s credit score?"
            else:
                reply = "Please enter co-applicant’s income in numbers."
        elif 'co_credit_score' not in data and data['co_applicant'].lower() == 'yes':
            if is_valid_credit_score(user_input):
                data['co_credit_score'] = user_input
                reply = "What is your PAN number?"
            else:
                reply = "Please enter a valid credit score between 300 and 900."
        elif 'pan_number' not in data:
            data['pan_number'] = user_input
            reply = "What type of loan are you applying for? (Home / Personal / Business / Education)"
        elif 'loan_type' not in data:
            data['loan_type'] = user_input
            reply = "What is the desired loan amount?"
        elif 'loan_amnt' not in data:
            if is_valid_number(user_input):
                data['loan_amnt'] = user_input
                reply = "What is the preferred tenure in months?"
            else:
                reply = "Please enter the loan amount in numbers."
        elif 'loan_tenure' not in data:
            if is_valid_number(user_input):
                data['loan_tenure'] = user_input
                reply = "Do you have collateral or property to pledge? (Yes / No)"
            else:
                reply = "Please enter the tenure in months (numbers only)."
        elif 'collateral' not in data:
            data['collateral'] = user_input
            reply = "Thanks! You can now upload your documents on the dashboard."
        else:
            reply = "You're all set! Head to the dashboard to upload documents and view your eligibility report."

        return jsonify({"reply": reply})