from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import pyrebase
import google.generativeai as genai
from flask_socketio import SocketIO, emit
from collections import defaultdict
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# Firebase configuration
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

print(firebaseConfig)

# Initialize Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# Initialize quiz map
quiz_map = defaultdict(dict)


# Routes

@app.route('/')
def home():
    return jsonify({"message": "This is backend created for fixit"})


@app.route('/signup', methods=['POST'])
def signup_form():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    print(email) 
    print(password)
    # Firebase configuration
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


    print(firebaseConfig)

    # Initialize Firebase
    firebase = pyrebase.initialize_app(firebaseConfig)
    auth = firebase.auth()
    
    


    if not email or not password:
        return jsonify({"error": "No Data provided !!"}), 400

    try:
        user = auth.create_user_with_email_and_password(email=email, password=password)
        return jsonify({"message": "User created successfully!", "uid": user['localId']}), 201
    except:
        return jsonify({"message": "Weak Password."}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"error": "No Data provided !!"}), 400

    try:
        user = auth.sign_in_with_email_and_password(email,password)
        return jsonify({"message": "Login successfully!", "uid": user['localId']}), 200
    except:
        return jsonify({"message": "unable to login"}), 400


@app.route('/add_data', methods=['POST'])
def start_quiz():
    data = request.json
    username = data.get('username')
    time = data.get('time')
    mcq = data.get('mcq')
    users = data.get('users')
    
    if not username or not time or not mcq or not users:
        return jsonify({'error': 'Missing data'}), 400

    db = firebase.database()
    
    # Start quiz logic
    number_of_quizzes_conducted = len(quiz_map.get(username, []))
    quiz_id = f"{username}quiz{number_of_quizzes_conducted}"    
    user_data = {
        'QuizId': quiz_id,
        'Quiz': mcq,
        'time': time,
        'status': 'ongoing',
        'visible user emails': users, 
        'winner': ''
    }

    db.child('Users').child(username).child('Quizes Attended').push(user_data)
    
    correct_answer = mcq[0]['answer']
    
    quiz_map[username][quiz_id] = {
        'users': {}, 
        'correct_answer': correct_answer, 
        'time': time, 
        'time_remaining': time
    }

    number_of_questions = len(mcq)  
    
    for user in users:
        quiz_map[username][quiz_id]['users'][user] = [0] * number_of_questions
        
    return jsonify({'message': 'Quiz Started Successfully!', 'quiz': mcq})


@app.route('/end_game', methods=['POST'])
def end_game():
    data = request.json
    quiz_id = data.get('quiz_id')
    hostname = data.get('hostname')

    if not quiz_id or not hostname:
        return jsonify({'error': 'Missing hostname or quiz_id'}), 400

    # Check if the quiz exists
    if hostname not in quiz_map or quiz_id not in quiz_map[hostname]:
        return jsonify({'error': 'Quiz not found'}), 404

    quiz_data = quiz_map[hostname][quiz_id]
    user_scores = quiz_data['users']

    # Calculate scores
    final_scores = {user: sum(scores) for user, scores in user_scores.items()}

    # Determine winners
    max_score = max(final_scores.values())
    winners = [user for user, score in final_scores.items() if score == max_score]

    # Update Firebase
    db = firebase.database()
    db.child('Users').child(hostname).child('Quizes Attended').child(quiz_id).update({
        'status': 'finished',
        'winner': ', '.join(winners),  
        'final_scores': final_scores  
    })

    # Remove quiz from quiz_map
    del quiz_map[hostname][quiz_id]

    return jsonify({
        'message': 'Game ended successfully!',
        'winners': winners,
        'final_scores': final_scores
    }), 200


@app.route('/read_data', methods=['POST'])
def read_data():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'error': 'Missing Username'}), 400

    db = firebase.database()
    users = db.child('Users').child(username).get()  # Use dynamic username

    result_data = users.val()

    if result_data:
        return jsonify({'message': 'Data fetched successfully!', 'data': result_data})
    else:
        return jsonify({'error': 'User data not found'}), 404


@app.route('/generate_data_ai', methods=['POST'])
def generate_by_ai_data():
    data = request.json
    questionno = data.get('questionno')
    quiz = data.get('type')
    
    if not questionno or not quiz:
        return jsonify({'error': 'Missing questionno or quiz type'}), 400

    # Configure Gemini API
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config={"response_mime_type": "application/json"})
    
    # Generate questions using Gemini AI
    prompt = (
        f"Generate {questionno} {quiz} multiple-choice questions in the following format: "
        f"[{{'title': 'question text', 'options': ['option 1', 'option 2', 'option 3'], 'answer': 'correct_option_number'}}]. "
        "The correct_option_number should be the index (1-based) of the correct answer in the options list."
    )
    
    response = model.generate_content(prompt)

    result_data = response.text
    try:
        questions = json.loads(result_data)
    except json.JSONDecodeError:
        print("Error: The response is not valid JSON.")

    return jsonify({'message': 'Questions generated successfully!', 'data': questions})

# Socket logic
@socketio.on('user_joined') 
def handle_user_join(data): 
    username = data.get('username') 
    
    if not username:
        emit('error', {'message': 'Username is required to join.'}, broadcast=True)
        return
    
    emit('user_joined', {'message': f"{username} has joined the game!"}, broadcast=True)


@socketio.on('user_leaved') 
def handle_user_leave(data): 
    username = data.get('username') 
    
    if not username:
        emit('error', {'message': 'Username is required to leave.'}, broadcast=True)
        return
    
    emit('user_left', {'message': f"{username} has left the game!"}, broadcast=True)


@socketio.on('submit_answer')
def submit_answer(data): 
    current_question_index = data.get('current_index')
    username = data.get('username') 
    answer = data.get('answer_submitted') 
    hostname = data.get('hostname') 
    correct = data.get('correct_answer') 
    quiz_id = data.get('quiz_id')
    
    if answer == correct: 
        quiz_map[hostname][quiz_id]['users'][username][current_question_index] += 1
    
    emit('user_submit', {'message': f"Submitted answer!"}, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, debug=True)


# from flask import Flask, jsonify, request
# from flask_cors import CORS
# from dotenv import load_dotenv
# import os
# import pyrebase
# import google.generativeai as genai
# import heapq
# from flask_socketio import SocketIO, emit
# from collections import defaultdict



# # Codes

# # backend url: https://backend-code-ngs0.onrender.com/
# load_dotenv()
# quiz_map = {}


# app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})
# socketio = SocketIO(app, cors_allowed_origins="*")


# firebaseConfig = {
#     'apiKey': os.getenv('API_KEY'),
#     'authDomain': os.getenv('AUTH_DOMAIN'),
#     'projectId': os.getenv('PROJECT_ID'),
#     'storageBucket': os.getenv('STORAGE_BUCKET'),
#     'messagingSenderId': os.getenv('MESSAGING_SENDER_ID'),
#     'appId': os.getenv('APP_ID'),
#     'measurementId': os.getenv('MEASUREMENT_ID'),
#     'databaseURL': os.getenv('DATABASE_URL')
# }

# firebase = pyrebase.initialize_app(firebaseConfig)
# auth = firebase.auth()



# quiz_map = defaultdict(list)




# # Routes

# @app.route('/')
# def home():
#     return jsonify({"message": "This is backend created for fixit"})


# @app.route('/signup', methods=['POST'])
# def signup():
#     data = request.json
#     email = data.get('email')
#     password = data.get('password')

#     if not email or not password:
#         return jsonify({"error": "No Data provided !!"}), 400

#     try:
#         user = auth.create_user_with_email_and_password(email=email, password=password)
#         return jsonify({"message": "User created successfully!", "uid": user['localId']}), 201
#     except pyrebase.pyrebase.FirebaseException as e:
#         return jsonify({"message": str(e)}), 400


# @app.route('/login', methods=['POST'])
# def login():
#     data = request.json
#     email = data.get('email')
#     password = data.get('password')

#     if not email or not password:
#         return jsonify({"error": "No Data provided !!"}), 400

#     try:
#         user = auth.sign_in_with_email_and_password(email=email, password=password)
#         return jsonify({"message": "Login successfully!", "uid": user['localId']}), 200
#     except pyrebase.pyrebase.FirebaseException as e:
#         return jsonify({"error": str(e)}), 400


# @app.route('/add_data', methods=['POST'])
# def start_quiz():
#     data = request.json
#     username = data.get('username')
#     time = data.get('time')
#     mcq = data.get('mcq')
#     users = data.get('users')
#     print(mcq)
    
    
#     if not username or not time or not mcq or not users:
#         return jsonify({'error': 'Missing data'}), 400

#     db = firebase.database()
    
#     "Code to Start the quiz" 
#     number_of_quizzes_conducted = len(quiz_map.get(username, []))
#     quiz_id = f"{username}quiz{number_of_quizzes_conducted}"    
#     user_data = {
#         'QuizId':quiz_id,
#         'Quiz': mcq,
#         'time': time,
#         'status': 'ongoing',
#         'visible user emails':users, 
#         'winner':''
#     }

#     db.child('Users').child(username).child('Quizes Attended').push(user_data)
    
    
    
#     correct_answer = mcq[0]['answer']
#     quiz_map[username] = quiz_map.get(username, {})
    
#     quiz_map[username][quiz_id] = {
#         'users': {}, 
#         'correct_answer': correct_answer, 
#         'time': time, 
#         'time_remaining': time
#     }

    
#     number_of_questions = len(mcq)  
    
#     for user in users:
#         quiz_map[username][quiz_id]['users'][user] = [0] * number_of_questions
        
#     return jsonify({'message': 'Quiz Started Successfully!','quiz':mcq})

# @app.route('/end_game', methods=['POST'])
# def end_game():
#     data = request.json
#     quiz_id = data.get('quiz_id')
#     hostname = data.get('hostname')

#     if not quiz_id or not hostname:
#         return jsonify({'error': 'Missing hostname or quiz_id'}), 400

#     # Check if the quiz exists in the quiz_map
#     if hostname not in quiz_map or quiz_id not in quiz_map[hostname]:
#         return jsonify({'error': 'Quiz not found'}), 404

#     quiz_data = quiz_map[hostname][quiz_id]
#     user_scores = quiz_data['users']

#     # Calculate the total score for each user
#     final_scores = {user: sum(scores) for user, scores in user_scores.items()}

#     # Determine the winner(s)
#     max_score = max(final_scores.values())
#     winners = [user for user, score in final_scores.items() if score == max_score]

#     # Update Firebase with the results
#     db = firebase.database()
#     db.child('Users').child(hostname).child('Quizes Attended').child(quiz_id).update({
#         'status': 'finished',
#         'winner': ', '.join(winners),  
#         'final_scores': final_scores  
#     })

#     # Remove the quiz from quiz_map
#     del quiz_map[hostname][quiz_id]

#     return jsonify({
#         'message': 'Game ended successfully!',
#         'winners': winners,
#         'final_scores': final_scores
#     }),200

    
    
    


# @app.route('/read_data', methods=['POST'])
# def read_data():
#     data = request.json
#     username = data.get('username')
    
#     if not username:
#         return jsonify({'error': 'Missing Username'}), 400

#     db = firebase.database()
#     users = db.child('Users').child(username).get()  # Use dynamic username

#     result_data = users.val()

#     if result_data:
#         return jsonify({'message': 'Data fetched successfully!', 'data': result_data})
#     else:
#         return jsonify({'error': 'User data not found'}), 404


# # code to generate questions using gemini api
# @app.route('/generate_data_ai', methods=['POST'])
# def generate_by_ai_data():
#     data = request.json
#     questionno = data.get('questionno')
#     quiz = data.get('type')
    
#     if not questionno or not quiz:
#         return jsonify({'error': 'Missing questionno or quiz type'}), 400

#     # Configure Gemini API
#     genai.configure(api_key=os.environ["GEMINI_API_KEY"])
#     model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
#     # Generate questions using Gemini AI
#     response = model.generate_content(f"Generate {questionno} {quiz} mcq based questions in json format")

#     result_data = response.text

#     return jsonify({'message': 'Questions generated successfully!', 'data': result_data})

# # code socket logic
# # Handle user joining the game
# @socketio.on('user_joined') 
# def handle_user_join(data): 
#     username = data.get('username') 
    
#     if not username:
#         emit('error', {'message': 'Username is required to join.'}, broadcast=True)
#         return
    
#     # Assuming users joining late have scores initialized to zero
#     emit('user_joined', {'message': f"{username} has joined the game!"}, broadcast=True)

# # Handle user leaving the game
# @socketio.on('user_leaved') 
# def handle_user_leave(data): 
#     username = data.get('username') 
    
#     if not username:
#         emit('error', {'message': 'Username is required to leave.'}, broadcast=True)
#         return
    
#     emit('user_left', {'message': f"{username} has left the game!"}, broadcast=True)


# # Code to broadcast new question 
# @socketio.on('submit_answer')
# def submit_answer(data): 
#     current_question_index = data.get('current_index')
#     username = data.get('username') 
#     answer = data.get('answer_submitted') 
#     hostname = data.get('hostname') 
#     correct = data.get('correct_answer') 
#     quiz_id = data.get('quiz_id')
    
#     if answer == correct: 
#         quiz_map[hostname][quiz_id]['users'][username][current_question_index] += 1
    
#     emit('user_submit', {'message': f"Submited answer!"}, broadcast=True)








# if __name__ == "__main__":
#     socketio.run(app, debug=True)
