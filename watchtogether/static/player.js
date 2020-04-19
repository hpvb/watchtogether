class VideoPlayer {
  constructor(video) {

    this.listeners = {};

    this.video = video;
    this.playing = false;
    this.interacted = false;
    this.tickled = false;
    this.max_ease = 0.2;
    this.max_ease_time = 7;
    this.ready = false;
    this.want_seek = false;
    this.want_seek_time = 0;
    this.last_seek_time_delay = 0;

    this.hls = null;
    this.dash = null;

    this.setup_dom();

    this.mouse_timer = null;
    this.playback_speed_timer = null;

    this.status = {};
    this.status_timers = {};

    this.video.addEventListener("timeupdate", this.on_timeupdate.bind(this));
    this.video.addEventListener("loadedmetadata", this.on_loadedmetadata.bind(this));
    this.video.addEventListener("play", this.on_play.bind(this));
    this.video.addEventListener("pause", this.on_pause.bind(this));
    this.video.addEventListener("playing", this.on_playing.bind(this));
    this.video.addEventListener("canplay", this.on_canplay.bind(this));
    this.video.addEventListener("canplaythrough", this.on_canplaythrough.bind(this));
    this.video.addEventListener("waiting", this.on_waiting.bind(this));
    this.video.addEventListener("stalled", this.on_stalled.bind(this));
    this.video.addEventListener("seeking", this.on_seeking.bind(this));
    this.video.addEventListener("seeked", this.on_seeked.bind(this));

    this.rootelement.addEventListener("mousemove", this.on_mouse.bind(this));
    this.rootelement.addEventListener("onmousedown", this.on_mouse.bind(this));

    this.play_button_lg.addEventListener("click", this.on_play_click.bind(this));
    this.play_button_lg.disabled = true;

    this.play_button = this.create_toolbar_button(['play-button'], 'play');
    this.play_button.addEventListener("click", this.on_play_click.bind(this));
    this.play_button.disabled = true;

    this.mute_button = this.create_toolbar_button(['mute-button'], 'mute');
    this.mute_button.addEventListener("click", this.on_mute_click.bind(this));
    this.fullscreen_button = this.create_toolbar_button(['fullscreen-button'], 'fullscreen');
    this.fullscreen_button.addEventListener("click", this.on_fullscreen_click.bind(this));
    this.settings_button = this.create_toolbar_button(['settings-button'], 'settings');
    this.settings_button.addEventListener("click", this.on_settings_click.bind(this));

    this.timeline.addEventListener("change", this.on_seek.bind(this));
    this.timeline.disabled = true;

    this.videotime_label.innerHTML = this.seconds_to_timestring(0);
    this.videoduration_label.innerHTML = this.seconds_to_timestring(0);

    this.settings_debug.addEventListener('click', this.on_settings_debug_click.bind(this));

    document.addEventListener('fullscreenchange', this.exit_fullscreen.bind(this), false);
    this.show_loader();
  }

  create_element(type, classes) {
    var element = document.createElement(type);

    for (var i = 0; i < classes.length; i++) {
      element.classList.add(classes[i]);
    }

    return element;
  }

  create_toolbar_button(classes, title = "") {
    var element = this.create_element('button', classes);
    element.title = title;
    this.toolbar.appendChild(element);
    return element;
  }

  setup_dom() {
    var video_parent = this.video.parentElement;

    this.rootelement = this.create_element('div', ['player']);
    this.rootelement.appendChild(this.video);

    this.ttml = this.create_element('div', ['ttml']);
    this.rootelement.appendChild(this.ttml);

    this.poster = this.create_element('div', ['poster']);
    this.rootelement.appendChild(this.poster);

    this.loader = this.create_element('div', ['loader']);
    this.rootelement.appendChild(this.loader);

    this.debug_panel = this.create_element('div', ['debug-panel']);
    this.debug_panel.style.visibility = 'hidden';
    this.rootelement.appendChild(this.debug_panel);

    this.message_panel = this.create_element('div', ['message-panel']);
    this.rootelement.appendChild(this.message_panel);
    this.message_text = this.create_element('div', ['message-text']);
    this.message_panel.appendChild(this.message_text);

    this.controls = this.create_element('div', ['controls']);
    this.rootelement.appendChild(this.controls);

    this.play_button_lg = this.create_element('button', ['play-button-lg']);
    this.play_button_lg.disabled = true;
    this.controls.appendChild(this.play_button_lg);

    this.settings = this.create_element('div', ['settings']);
    this.controls.appendChild(this.settings);

    this.settings_debug = this.create_element('button', ['debug', 'inactive']);
    this.settings_debug.innerHTML = "Debug";
    this.settings.appendChild(this.settings_debug);

    this.toolbar = this.create_element('div', ['toolbar']);
    this.controls.appendChild(this.toolbar);

    this.timeline_bar = this.create_element('div', ['timeline-bar']);
    this.controls.appendChild(this.timeline_bar);

    this.videotime_label = this.create_element('span', ['time-label', 'video-time']);
    this.timeline_bar.appendChild(this.videotime_label);

    this.timeline = this.create_element('input', ['timeline']);
    this.timeline.type = 'range';
    this.timeline.value = 0;
    this.timeline.disabled = true;
    this.timeline_bar.appendChild(this.timeline);

    this.videoduration_label = this.create_element('span', ['time-label', 'video-duration']);
    this.timeline_bar.appendChild(this.videoduration_label);

    video_parent.appendChild(this.rootelement);
  }

  set_stream(url) {
    if (url.endsWith(".mpd")) {
      this.set_dash_stream(url);
    } else if (url.endsWith(".m3u8")) {
      this.set_hls_stream(url);
    } else {
      console.log("Uknown URL type, player not initializing");
    }
  }

  set_dash_stream(url) {
    console.log("player: initializing DASH stream");

    this.dash = dashjs.MediaPlayer().create();
    this.dash.initialize(this.video, url, false);

    this.dash.updateSettings({
        'debug': {
          'logLevel': 1
        },
        'streaming': {
          //'abr': {
          //  'movingAverageMethod': 'slidingWindow',
          //  'bandwidthSafetyFactor': 0.85
          //},
          //'metricsMaxListDepth': 50,
          'fastSwitchEnabled': true,
          //'bufferAheadToKeep': 60,
          //'bufferToKeep': 60,
          //'bufferTimeAtTopQualityLongForm': 120,
          'lastBitrateCachingInfo': {
            'enabled': false
          }
        }
    });

    this.dash.attachTTMLRenderingDiv(this.ttml);
  }

  set_hls_stream(url) {
    console.log("player: initializing HLS stream");

    if (Hls.isSupported()) {
      if (this.hls) {
        hls.destroy();
      }
      this.hls = new Hls(
        {
          abrBandWidthUpFactor: 0.7,
          maxBufferLength: 15,
          maxMaxBufferLength: 30,
          capLevelOnFPSDrop: true,
          debug: false,
          autoStartLoad: true
        }
      );

      this.hls.on(Hls.Events.ERROR, function (event, data) {
        if (data.fatal) {
          switch(data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            console.log("player: hls: fatal network error encountered, try to recover");
            this.hls.startLoad();
            this.show_loader();
            break;
          case Hls.ErrorTypes.MEDIA_ERROR:
            console.log("player: hls: fatal media error encountered, try to recover");
            this.hls.recoverMediaError();
            this.show_loader();
            break;
          default:
            this.hls.destroy();
            console.log("player: hls: fatal error, can't recover");
            this.show_message("Video playing failed for some reason. Please reload the page");
            this.show_poster();
            break;
          }
        }
      }.bind(this));

      this.hls.attachMedia(this.video);
      this.hls.on(Hls.Events.MEDIA_ATTACHED, function () {
          this.hls.loadSource(url);
      }.bind(this));
    }
  }

  seconds_to_timestring(sec) {
    var hours = new String(Math.floor(sec / 3600).toFixed());
    sec %= 3600;
    var minutes = new String(Math.floor(sec / 60)).padStart(2, '0');
    var seconds = new String((sec % 60).toFixed()).padStart(2, '0');

    return "" + hours + ":" + minutes + ":" + seconds;
  }

  hide_message() {
    this.message_panel.style.visibility = "hidden"
  }

  show_message(text, timeout) {
    this.message_text.innerHTML = text;
    this.message_panel.style.visibility = "visible";

    if (timeout) {
      setTimeout(function() {
        this.hide_message();
      }.bind(this), timeout);
    }
  }

  tickle() {
    var current_time = this.video.currentTime;
    var play_promise = this.video.play();

    if (play_promise !== undefined) {
      play_promise.then(function() {
        this.video.pause();
        this.video.currentTime = current_time;
        this.tickled = true;
      }.bind(this)).catch(function(error) {
      });
    } else {
      this.tickled = true;
      this.video.pause();
      this.video.currentTime = current_time;
    }
  }

  play() {
    this.playing = true;

    if (! this.ready) {
      return;
    }

    var play_promise = this.video.play();

    if (play_promise !== undefined) {
      play_promise.then(function() {
        this.play_button.classList.add("pause");
        this.play_button_lg.classList.add("pause");
        this.hide_controls();
        this.dispatchEvent(new Event('play'));
      }.bind(this)).catch(function(error) {
        console.log("Player promise fail");
        this.play_button.classList.add('pulse');
        this.play_button_lg.classList.add('pulse');
      }.bind(this));
    } else {
      this.play_button.classList.add("pause");
      this.play_button_lg.classList.add("pause");
      this.hide_controls();
    }
  }

  pause() {
    this.playing = false;
    this.show_controls();
    this.video.pause();

    this.play_button.classList.remove("pause");
    this.play_button_lg.classList.remove("pause");
    this.dispatchEvent(new Event('pause'));
  }

  _set_time(time) {
    this.video.playbackRate = 1.0;
    this.video.currentTime = time;
  }

  _seek(time, time_scale) {
    var time_diff = this.video.currentTime - time;
    var time_delta = Math.abs(time_diff);

    if (this.video.currentTime == time) {
      return;
    }

    if (! this.ready) {
      this.want_seek = true;
      this.want_seek_time = time;
      return;
    }

    if ((this.video.paused && time_delta) || time_scale == 0 || isNaN(time_delta) || time_delta > this.max_ease_time) {
      this._set_time(time);
      return;
    }

    if (time_delta >= this.max_ease) {
      var time_easing_factor = time_delta / time_scale;
      if (time_easing_factor > this.max_ease) time_easing_factor = this.max_ease;

      if (time_diff < 0) {
        console.log("player: seek: speeding up playback by " + time_easing_factor * 100 +"%");
        this.video.playbackRate = 1.0 + time_easing_factor;
      } else {
        console.log("player: seek: slowing down playback by " + time_easing_factor * 100 +"%");
        this.video.playbackRate = 1.0 - time_easing_factor;
      }

      clearTimeout(this.playback_speed_timer);
      this.playback_speed_timer = setTimeout(function() {
        console.log("player: seek: resetting playback speed");
        this.video.playbackRate = 1.0;
      }.bind(this), time_scale * 1000);
    }
  }

  seek(time, time_scale = 0) {
    this._seek(time, time_scale);
    this.dispatchEvent(new CustomEvent('seek', {detail:{'time': time}}));
  }

  start_status_timers() {
    this.status_timers['debug'] = setInterval(this.update_debug.bind(this), 500);
  }

  stop_status_timers() {
    for (var key in this.status_timers) {
      clearInterval(this.status_timers[key]);
    }
  }

  update_debug() {

    var debugtext = "";

    var quality = "unknown";
    var bandwidth = "unknown";
    var bufferlength = "unknown";

    if (this.hls) {
      bandwidth = "" + this.hls.bandwidthEstimate / 1024 + "kbit/s";
      if (this.hls.currentLevel >= 0) {
        var level = this.hls.levels[this.hls.currentLevel];
        quality = "" + level.width + "x" + level.height + "@" + level.bitrate;
      } 
    }

    if (this.dash) {
      var vidinfo = this.dash.getBitrateInfoListFor("video")[this.dash.getQualityFor("video")]
      var audinfo = this.dash.getBitrateInfoListFor("audio")[this.dash.getQualityFor("audio")]

      quality = "Video: " + vidinfo.width + "x" + vidinfo.height + "@" + vidinfo.bitrate;
      quality += " Audio: " + audinfo.bitrate;
      bufferlength = "" + player.dash.getBufferLength() + "seconds";
    }
    
    debugtext += "Stream quality: " + quality + "<br>";
    debugtext += "Bandwidth: " + bandwidth + "<br>";
    debugtext += "Buffer: " + bufferlength + "<br>";
    debugtext += "Player playing: " + this.playing + "<br>";
    debugtext += "Video playing: " + ! this.video.paused + "<br>";
    debugtext += "Video playback speed: " + this.video.playbackRate * 100 + "%<br>";
    this.debug_panel.innerHTML = debugtext;
  }

  show_controls() {
    clearInterval(this.mouse_timer);
    this.controls.classList.remove("hidden");
  }

  hide_controls() {
    clearInterval(this.mouse_timer);
    this.mouse_timer = null;

    this.controls.classList.add("hidden");
    this.settings.classList.remove("active");
  }

  toggle_debug_panel() {
    if (this.debug_panel.style.visibility == "hidden") {
      this.debug_panel.style.visibility = "visible";
    } else {
      this.debug_panel.style.visibility = "hidden";
    }
  }

  show_loader() {
    this.loader.classList.add('loading');
  }

  hide_loader() {
    this.loader.classList.remove('loading');
  }

  show_poster() {
    this.poster.classList.remove('hidden');
  }

  hide_poster() {
    this.poster.classList.add('hidden');
  }

  exit_fullscreen(event) {
    this.fullscreen_button.classList.toggle("fullscreen");
  }

  get_interacted() {
    return this.interacted;
  }

  get_streams() {
    var streams = this.video.getElementsByTagName('source');

    return streams;
  }

  on_play() {
    console.log("video: play");
  }

  on_pause() {
    console.log("video: pause");
  }

  on_playing() {
    console.log("video: playing");

    if (this.interacted) {
      this.play_button.classList.remove('pulse');
      this.play_button_lg.classList.remove('pulse');
      this.hide_loader();
      this.hide_poster();
      this.hide_message();
    }
    this.interacted = true;
    this.dispatchEvent(new Event('video-playing'));
  }

  on_canplay() {
    console.log("video: canplay");
    this.hide_loader();
    this.dispatchEvent(new Event('video-canplay'));
  }

  on_canplaythrough() {
    console.log("video: canplaythrough");
    this.hide_loader();

    if (this.want_seek) {
      this.want_seek = false;
      this._seek(this.want_seek_time);
    } else if (this.playing && this.video.paused) {
      this.play();
    }
    this.dispatchEvent(new Event('video-canplaythrough'));
  }

  on_waiting() {
    console.log("video: waiting");
    this.show_loader();
  }

  on_stalled() {
    console.log("video: stalled");
  }

  on_seeking() {
    console.log("video: seeking");
    this.seek_start = (new Date()).getTime();
    this.show_loader();
  }

  on_seeked() {
    var now = (new Date()).getTime();
    this.last_seek_time_delay = Math.round((now - this.seek_start) / 1000);

    console.log("video: seeked (delay: " + this.last_seek_time_delay + ")");
    if (this.playing) {
      if (this.last_seek_time_delay > this.max_ease_time) {
        console.log("reseeking ahead");
        this.seek(this.video.currentTime + (this.last_seek_time_delay * 2));
        return;
      }
    } 
    
    this.hide_loader();
    this.dispatchEvent(new Event('video-seeked'));
  }

  on_seek() {
    var time = parseFloat(this.timeline.value);
    console.log("timeline: seek to: " + time);

    this.seek(time);
    this.dispatchEvent(new CustomEvent('seek-clicked', {detail:{'time': time}}));
  }

  on_timeupdate() {
    this.timeline.value = this.video.currentTime;
    this.videotime_label.innerHTML = this.seconds_to_timestring(this.video.currentTime);
  }

  on_loadedmetadata() {
    console.log("video: loadedmetadata");

    this.timeline.setAttribute('min', 0);
    this.timeline.setAttribute('max', this.video.duration);
    this.timeline.value = this.video.currentTime;

    this.timeline.disabled = false;
    this.play_button.disabled = false;
    this.play_button_lg.disabled = false;

    this.videoduration_label.innerHTML = this.seconds_to_timestring(this.video.duration);
    // this.hide_loader();

    this.start_status_timers();
    this.timeline.disabled = false;
    this.ready = true;
  }

  on_mouse() {
    if (this.video.paused) {
      return;
    }

    if (this.mouse_timer) {
      clearInterval(this.mouse_timer);
    } 

    this.show_controls();

    this.mouse_timer = setInterval(function() {
      if (this.playing) {
        this.hide_controls();
      }
    }.bind(this), 2000);
  }

  /* Button events */

  on_play_click() {
    this.play_button.blur();
    this.play_button_lg.blur();
    this.play_button.classList.toggle("pause");
    this.play_button_lg.classList.toggle("pause");
    this.interacted = true;

    if (this.video.paused) {
      console.log("Player is paused, playing");
      this.dispatchEvent(new Event('play-clicked'));
      this.play();
    } else {
      this.pause();
      this.dispatchEvent(new Event('pause-clicked'));
    }
  }

  on_fullscreen_click() {
    this.fullscreen_button.blur();

    if (! document.fullscreenElement) {
      var fullscreen_promise = this.rootelement.requestFullscreen();

      if (fullscreen_promise !== undefined) {
        fullscreen_promise.then(function() {
        }.bind(this)).catch(function(error) {
          this.exit_fullscreen();
        }.bind(this));
      }
    } else {
      document.exitFullscreen();
    }
  }

  on_mute_click() {
    this.mute_button.blur();
    if (this.video.muted == false) {
      this.video.muted = true;
      this.mute_button.classList.add("muted");
    } else {
      this.video.muted = false;
      this.mute_button.classList.remove("muted");
    }
  }

  on_settings_click() {
    this.settings_button.blur();
    this.settings.classList.toggle("active");
  }

  on_settings_debug_click() {
    this.settings_debug.classList.toggle("inactive");
    this.toggle_debug_panel();
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

