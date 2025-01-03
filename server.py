import heapq
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import os
import pyrebase

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

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
db = firebase.database()

quiz_state = {
    "current_question": None,
    "questions": [],
    "participants": {},
}

class Leaderboard:
    def __init__(self):
        self.heap = []
        self.candidate_map = {}

    def add_candidate(self, username, score):
        if username in self.candidate_map:
            self.update_score(username, score)
        else:
            heapq.heappush(self.heap, (-score, username))
            self.candidate_map[username] = score

    def update_score(self, username, new_score):
        old_score = self.candidate_map[username]
        self.candidate_map[username] = new_score
        self.heap = [(-score, name) if name != username else (-new_score, name)
                     for score, name in self.heap]
        heapq.heapify(self.heap)

    def get_top_candidates(self, n):
        return [(username, -score) for score, username in heapq.nlargest(n, self.heap)]

    def get_all_scores(self):
        return [(username, -score) for score, username in self.heap]

    def print_leaderboard(self):
        print("Leaderboard:")
        top_candidates = self.get_top_candidates(len(self.heap))
        for rank, (username, score) in enumerate(top_candidates, start=1):
            print(f"Rank {rank}: {username} with score {score}")

leaderboard = Leaderboard()

@app.route('/')
def home():
    return jsonify({"message": "Backend for quiz app with Firebase and SocketIO"})

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

    user_data = {
        'Quiz': mcq,
        'time': time,
        'status': status,
        'visible user emails': users
    }

    db.child('Users').child(username).push(user_data)

    return jsonify({'message': 'Data pushed successfully!'})

@app.route('/read_data', methods=['POST'])
def read_data():
    data = request.json
    username = data.get('username')

    if not username:
        return jsonify({'error': 'Missing Username'}), 400

    users = db.child('Users').child(username).get()
    data = users.val()

    return jsonify({'message': 'Data fetched successfully!', 'data': data})

@app.route('/start-quiz', methods=['POST'])
def start_quiz():
    data = request.json
    quiz_state["questions"] = data.get("questions", [])
    quiz_state["current_question"] = 0
    quiz_state["participants"] = {}
    socketio.emit('quiz-started', {"total_questions": len(quiz_state["questions"])})
    broadcast_current_question()
    return jsonify({"message": "Quiz started successfully!"})

@socketio.on('join-quiz')
def handle_join(data):
    username = data.get("username")
    if username:
        quiz_state["participants"][request.sid] = {"username": username, "score": 0}
        leaderboard.add_candidate(username, 0)  # Add user with initial score of 0
        emit("joined-quiz", {"message": f"Welcome {username}!"})

@socketio.on('submit-answer')
def handle_submit_answer(data):
    answer = data.get("answer")
    user = quiz_state["participants"].get(request.sid)
    if not user:
        return
    correct_answer = quiz_state["questions"][quiz_state["current_question"]]["correct_answer"]
    if answer == correct_answer:
        user["score"] += 1
        leaderboard.update_score(user["username"], user["score"])
    emit("update-scores", quiz_state["participants"], broadcast=True)

@socketio.on('next-question')
def handle_next_question():
    if quiz_state["current_question"] < len(quiz_state["questions"]) - 1:
        quiz_state["current_question"] += 1
        broadcast_current_question()
    else:
        emit("quiz-ended", quiz_state["participants"], broadcast=True)
        end_quiz()

@socketio.on('get-leaderboard')
def handle_get_leaderboard():
    top_candidates = leaderboard.get_top_candidates(5)  # Fetch top 5 candidates
    emit("leaderboard", {"top_candidates": top_candidates}, broadcast=True)

def broadcast_current_question():
    question_data = quiz_state["questions"][quiz_state["current_question"]]
    socketio.emit("new-question", {
        "question": question_data["question"],
        "options": question_data["options"]
    })

def end_quiz():
    all_scores = leaderboard.get_all_scores()
    winner = all_scores[0] if all_scores else None
    if winner:
        winner_username, winner_score = winner
        print(f"Winner: {winner_username} with {winner_score} points")
    socketio.emit("quiz-over", {"final_scores": all_scores, "winner": winner}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)
