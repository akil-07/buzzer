import string
import random
import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'buzzer_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for rooms
rooms = {}

BACKEND_URL = os.environ.get('BACKEND_URL', '')

def generate_room_code(length=6):
    letters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(letters) for _ in range(length))
        if code not in rooms:
            return code

@app.route('/')
def index():
    return render_template('index.html', backend_url=BACKEND_URL)

@app.route('/host/<code>')
def host(code):
    if code not in rooms:
        return "Room not found", 404
    return render_template('host.html', code=code, backend_url=BACKEND_URL)

@app.route('/team/<code>/<team_id>')
def team(code, team_id):
    if code not in rooms:
        return "Room not found", 404
    if team_id not in rooms[code]['teams']:
        return "Team not found", 404
    return render_template('team.html', code=code, team_id=team_id, team_name=rooms[code]['teams'][team_id]['name'], backend_url=BACKEND_URL)


# Socket.IO Event Handlers

@socketio.on('create_room')
def on_create_room():
    code = generate_room_code()
    rooms[code] = {
        'host_sid': request.sid,
        'teams': {},
        'buzzer_active': False,
        'buzzes': []  # List of dicts: {'team_id': id, 'team_name': name, 'time': timestamp}
    }
    join_room(code)
    emit('room_created', {'code': code})

@socketio.on('join_host')
def on_join_host(data):
    code = data.get('code')
    if code in rooms:
        rooms[code]['host_sid'] = request.sid
        join_room(code)
        emit('update_teams', {'teams': list(rooms[code]['teams'].values())}, room=request.sid)
        emit('buzzer_state', {'active': rooms[code]['buzzer_active'], 'buzzes': rooms[code]['buzzes']}, room=request.sid)

@socketio.on('add_team')
def on_add_team(data):
    code = data.get('code')
    team_name = data.get('team_name')
    if code in rooms and rooms[code]['host_sid'] == request.sid:
        team_id = str(len(rooms[code]['teams']) + 1)
        rooms[code]['teams'][team_id] = {'id': team_id, 'name': team_name, 'joined': False}
        emit('update_teams', {'teams': list(rooms[code]['teams'].values())}, room=code)

@socketio.on('join_team')
def on_join_team(data):
    code = data.get('code')
    team_id = data.get('team_id')
    if code in rooms and team_id in rooms[code]['teams']:
        join_room(code)
        rooms[code]['teams'][team_id]['joined'] = True
        emit('update_teams', {'teams': list(rooms[code]['teams'].values())}, room=code)
        emit('buzzer_state', {'active': rooms[code]['buzzer_active'], 'buzzes': rooms[code]['buzzes']}, room=request.sid)

@socketio.on('activate_buzzer')
def on_activate_buzzer(data):
    code = data.get('code')
    if code in rooms and rooms[code]['host_sid'] == request.sid:
        rooms[code]['buzzer_active'] = True
        rooms[code]['buzzes'] = []
        emit('buzzer_state', {'active': True, 'buzzes': []}, room=code)

@socketio.on('buzz')
def on_buzz(data):
    code = data.get('code')
    team_id = data.get('team_id')
    
    if code in rooms and rooms[code]['buzzer_active']:
        import time
        # Record the buzz
        team_name = rooms[code]['teams'][team_id]['name']
        rooms[code]['buzzes'].append({
            'team_id': team_id,
            'team_name': team_name,
            'timestamp': time.time()
        })
        # Emit updated buzzes to everyone without deactivating the buzzer
        emit('buzzer_state', {'active': True, 'buzzes': rooms[code]['buzzes']}, room=code)

@socketio.on('reset_buzzer')
def on_reset_buzzer(data):
    code = data.get('code')
    if code in rooms and rooms[code]['host_sid'] == request.sid:
        rooms[code]['buzzer_active'] = False
        rooms[code]['buzzes'] = []
        emit('buzzer_state', {'active': False, 'buzzes': []}, room=code)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
