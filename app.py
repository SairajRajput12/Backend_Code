from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import pyrebase
import google.generativeai as genai


# backend url: https://backend-code-ngs0.onrender.com/
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


firebaseConfig = {
    'apiKey': os.getenv('API_KEY'),
    'authDomain': os.getenv('AUTH_DOMAIN'),
    'projectId': os.getenv('PROJECT_ID'),
    'storageBucket': os.getenv('STORAGE_BUCKET'),
    'messagingSenderId': os.getenv('MESSAGING_SENDER_ID'),
    'appId': os.getenv('APP_ID'),
    'measurementId': os.getenv('MEASUREMENT_ID'),
    'databaseURL': os.getenv('DATABASE_URL')
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()


@app.route('/')
def home():
    return jsonify({"message": "This is backend created for fixit"})


@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "No Data provided !!"}), 400

    try:
        user = auth.create_user_with_email_and_password(email=email, password=password)
        return jsonify({"message": "User created successfully!", "uid": user['localId']}), 201
    except pyrebase.pyrebase.FirebaseException as e:
        return jsonify({"message": str(e)}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "No Data provided !!"}), 400

    try:
        user = auth.sign_in_with_email_and_password(email=email, password=password)
        return jsonify({"message": "Login successfully!", "uid": user['localId']}), 200
    except pyrebase.pyrebase.FirebaseException as e:
        return jsonify({"error": str(e)}), 400


@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    username = data.get('username')
    time = data.get('time')
    mcq = data.get('mcq')
    status = data.get('status')
    users = data.get('users')
    
    
    if not username or not time or not mcq or not status or not users:
        return jsonify({'error': 'Missing data'}), 400

    db = firebase.database()
    user_data = {
        'Quiz': mcq,
        'time': time,
        'status': status,
        'visible user emails':users
    }

    db.child('Users').child(username).push(user_data)

    return jsonify({'message': 'Data pushed successfully!'})


@app.route('/read_data', methods=['POST'])
def read_data():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Missing Username'}), 400

    db = firebase.database()
    users = db.child('Users').child('sairajrajput').get()

    result_data = users.val()

    return jsonify({'message': 'Data pushed successfully!','data':result_data})


@app.route('/generate_data_ai', methods=['POST'])
def read_data():
    data = request.json
    questionno = data.get('questionno')
    quiz = data.get('type')
    
    
    if not questionno or not quiz:
        return jsonify({'error': 'Missing questionno'}), 400

    # code to generate the ai based question
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(f"Generate {questionno} {quiz} mcq based questions in json formate")

    result_data = response.text

    return jsonify({'message': 'Data pushed successfully!','data':result_data})



    
    

if __name__ == "__main__":
    app.run(debug=True)
