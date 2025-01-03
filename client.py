import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to the server!")
    sio.emit("join-quiz", {"username": "Participant1"})

@sio.event
def disconnect():
    print("Disconnected from the server.")

@sio.on("new-question")
def on_new_question(data):
    print(f"New Question: {data['question']}")
    for idx, option in enumerate(data["options"], 1):
        print(f"{idx}. {option}")
    answer = input("Enter your answer: ")
    sio.emit("submit-answer", {"answer": answer})

@sio.on("update-scores")
def on_update_scores(data):
    print("Updated Scores:", data)

@sio.on("quiz-ended")
def on_quiz_ended(data):
    print("Quiz ended! Final Scores:")
    for participant, info in data.items():
        print(f"{info['username']}: {info['score']}")

sio.connect("http://127.0.0.1:5000")
sio.wait()
