class Sync {
  constructor(player) {
    this.listeners = {};

    this.player = player;
    this.room = '';

    this.socket = io();
    this.socket.on('connected', this.on_connected.bind(this));
    this.socket.on('connect', this.on_connect.bind(this));
    this.socket.on('message', this.on_message.bind(this));
    this.socket.on('joined', this.on_joined.bind(this));
    this.socket.on('left', this.on_left.bind(this));

    if (this.player) {
      this.socket.on('time_start', this.on_time_start.bind(this));
      this.socket.on('time_pause', this.on_time_pause.bind(this));
      this.socket.on('time_reset', this.on_time_reset.bind(this));
      this.socket.on('time_get', this.on_time_get.bind(this));

      this.player.addEventListener('play-clicked', this.on_play_clicked.bind(this));
      this.player.addEventListener('pause-clicked', this.on_pause_clicked.bind(this));
      this.player.addEventListener('seek-clicked', this.on_seek_clicked.bind(this));
      //this.player.addEventListener('video-canplay', this.on_canplay.bind(this));
      //this.player.addEventListener('video-canplaythrough', this.on_video_canplaythrough.bind(this));
      //this.player.addEventListener('video-seeking', this.on_seeking.bind(this));
      //this.player.addEventListener('video-seeked', this.on_video_seeked.bind(this));
    }

    this.timer_seconds = 10;
    this.timer = null;
    this.latency = 0;
  }

  time_get() {
    var now = (new Date()).getTime();
    this.socket.emit('time_get', { 'stamp': now, 'room': this.room });
  }

  start_timer() {
    if (! this.timer) {
      this.timer = setInterval(this.time_get.bind(this), this.timer_seconds * 1000);
    }
  }

  join(username, room) {
    console.log("sync: joining room: " + room + " as: " + username);

    this.username = username;
    this.room = room;

    this.socket.emit('join', { 'username': this.username, 'room': this.room });
  }

  message(text) {
    this.socket.emit('message', { 'username': this.username, 'room': this.room, 'text': text });
  }

  stop_timer() {
    clearInterval(this.timer);
    this.timer = null;
  }

  on_play_clicked() {
    console.log('sync: on_play_clicked');

    this.start_timer();
    this.socket.emit('time_start', { 'room': this.room });
  }

  on_pause_clicked() {
    console.log('sync: on_paused_clicked');

    this.stop_timer();
    this.socket.emit('time_pause', { 'room': this.room });
  }

  on_seek_clicked(e) {
    var time = e.detail['time'];
    console.log('sync: on_seek_clicked. Seeking to: ' + time);
    this.socket.emit('time_set', { 'time': time, 'room': this.room});
  }

  on_video_canplaythrough() {
    this.start_timer();
  }

  on_video_seeked() {
  }

  on_connect() {
    console.log('sync: on_connect');

    if (this.username && this.room) {
      console.log('sync: reconnecting');
      this.join(this.username, this.room);
    }

    this.dispatchEvent(new Event('connect'));
  }

  on_connected(data) {
    console.log('sync: on_connected.');

    if (this.player) {
      if (data.state) {
        this.player.show_message("Video started by " + data['username'], 3000);
      } else {
        this.player.show_message("Video paused by " + data['username']);
      }

      this.start_timer();
      this.time_get();
    }

    this.dispatchEvent(new Event('connected'));
  }

  on_time_start(data) {
    console.log('sync: time_start');

    this.start_timer();
    this.time_get();

    this.player.show_message("Video started by " + data['username'], 3000);
    this.dispatchEvent(new CustomEvent('started', {detail:data.username}));
  }

  on_time_pause(data) {
    console.log('sync: time_pause');

    this.player.pause();
    this.stop_timer();
    this.time_get();
    this.player.show_message("Video paused by " + data['username']);
    this.dispatchEvent(new CustomEvent('paused', {detail:data.username}));
  }

  on_time_reset(data) {
    console.log('sync: time_reset');

    this.player.seek(data['time'] + this.latency);
    this.time_get();
    this.player.show_message("Video seek by " + data['username'], 3000);
    this.dispatchEvent(new CustomEvent('seeked', {detail:data.username}));
  }

  on_time_get(data) {
    var now = (new Date()).getTime();
    var delta = ((now - data.stamp) / 1000);
    var time = data.time + delta;

    this.latency = ((this.latency * 9) + delta) / 10;

    if (data.state) {
      this.start_timer();
      this.player.seek(time, this.timer_seconds);
      this.player.play();
    } else {
      this.stop_timer();
      this.player.pause();
      this.player.seek(time);
    }
  }

  on_message(data) {
    console.log("sync: message received");

    if (data.message) {
      this.dispatchEvent(new CustomEvent('message', {detail:data.message}));
    }
  }

  on_joined(data) {
    console.log("sync: joined");

    this.dispatchEvent(new CustomEvent('joined', {detail:data.username}));
  }

  on_left(data) {
    console.log("sync: left");

    this.dispatchEvent(new CustomEvent('left', {detail:data.username}));
  }

  /* Event interface */

  addEventListener(type, callback) {
    if (!(type in this.listeners)) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(callback);
  }

  dispatchEvent(event) {
    if (!(event.type in this.listeners)) {
      return true;
    }
    var stack = this.listeners[event.type].slice();

    for (var i = 0, l = stack.length; i < l; i++) {
      stack[i].call(this, event);
    }
    return !event.defaultPrevented;
  };
}
