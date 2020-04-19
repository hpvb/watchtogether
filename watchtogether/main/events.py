#!/usr/bin/env python3

import html

from flask import request
from flask_socketio import SocketIO, join_room, leave_room, emit

from watchtogether import rooms, socketio, Room
from watchtogether.database import models, db_session

@socketio.on('connect')
def on_connect():
    print(rooms)
    print("Client connected")

@socketio.on('join')
def on_join(data):
    print(f"Client logged on, username:{data['username']}, room:{data['room']}")
    if data['room'] not in rooms.keys():
        video = db_session.query(models.Video).filter_by(id=data['room']).one_or_none()
        rooms[data['room']] = Room(data['room'], video)

    roomname = data['room']
    room = rooms[roomname]

    username = html.escape(data['username'])

    new_user = room.join(request.sid, username)
    join_room(roomname)
    timer = rooms[roomname].timer

    emit('connected', {'time': timer.get(), 'state': timer.running, 'username': room.last })
    if new_user:
      emit('joined', {'username': username}, room=roomname, include_self=False)

@socketio.on('disconnect')
def on_disconnect():
    print("Client disconnected")

    for name, room in rooms.items():
        if room.has_sid(request.sid):
            username = room.get_user_by_sid(request.sid)
            if room.leave(request.sid):
                emit('left', {'username': username}, room=room.name)
        
@socketio.on('time_get')
def on_time_get(data):
    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer

    print(f"Time_get: {timer.get()}, {timer.running}, {data['stamp']}")
    emit('time_get', {'time': timer.get(), 'state': timer.running, 'stamp': data['stamp']});

@socketio.on('time_start')
def on_time_start(data):
    print("Start")
    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer
    username = room.get_user_by_sid(request.sid)

    timer.start()

    room.last = username
    emit("time_start", {'time': timer.get(), 'username': username}, room=roomname, include_self=False);

@socketio.on('time_pause')
def on_time_pause(data):
    print("Pause")
    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer
    username = room.get_user_by_sid(request.sid)

    timer.pause()

    room.last = username
    emit("time_pause", {'time': timer.get(), 'username': username}, room=roomname);

@socketio.on('time_reset')
def on_time_reset(data):
    print("Reset")
    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer
    username = room.get_user_by_sid(request.sid)

    timer.reset()

    room.last = username
    emit("time_reset", {'time': timer.get(), 'username': username}, room=roomname);

@socketio.on('time_set')
def on_time_set(data):
    time = 0

    try:
        time = int(data['time'])
    except ValueError:
        print("Time_set: '{data['time']}' is not a valid number")
        return

    print(f"Time_set: {time}")

    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer
    username = room.get_user_by_sid(request.sid)

    timer.set(time)

    room.last = username
    emit("time_reset", {'time': timer.get(), 'username': username}, room=roomname, include_self=False);

@socketio.on('message')
def on_message(data):
    roomname = data['room']
    room = rooms[roomname]
    timer = rooms[roomname].timer
    username = room.get_user_by_sid(request.sid)

    print(f"message: {username}: {data['text']}");

    text = html.escape(data['text'])
    message = room.message(username, text)
    print(message)
    emit("message", {'message': message}, room=roomname);

