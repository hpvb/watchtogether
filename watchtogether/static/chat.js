class Chat {
  constructor(sync, player, rootelement, room, username) {
    this.room = room;
    this.username = username;
    this.users = [];

    this.listeners = {};

    this.sync = sync;
    this.player = player;

    if (this.player) {
      this.rootelement = this.player.rootelement;
    } else {
      this.rootelement = rootelement;
    }

    this.setup_dom();

    this.sync.join(this.username, this.room);
    this.chat_form.addEventListener("submit", this.on_submit.bind(this));
    this.sync.addEventListener("connected", this.on_connected.bind(this));
    this.sync.addEventListener("message", this.on_message.bind(this));
    this.sync.addEventListener("joined", this.on_joined.bind(this));
    this.sync.addEventListener("left", this.on_left.bind(this));
    this.sync.addEventListener("started", this.on_started.bind(this));
    this.sync.addEventListener("paused", this.on_paused.bind(this));
    this.sync.addEventListener("seeked", this.on_seeked.bind(this));

    this.people_button.addEventListener("click", this.toggle_people_panel.bind(this));

    if (this.player) {
      this.hide_button = this.player.create_toolbar_button(['chat-button'], 'hide/show chat');
      this.hide_button.addEventListener("click", this.on_hide_chat.bind(this));

      this.popout_button = this.player.create_toolbar_button(['popout-button'], 'open chat in new window');
      this.popout_button.addEventListener("click", this.on_popout.bind(this));
    }
  }

  create_element(type, classes = []) {
    var element = document.createElement(type);

    for (var i = 0; i < classes.length; i++) {
      element.classList.add(classes[i]);
    }

    return element;
  }

  setup_dom() {
    this.chat_window = this.create_element('div', ['chat-window']);
    this.rootelement.appendChild(this.chat_window);

    this.chat_form = this.create_element('form');
    this.chat_window.appendChild(this.chat_form);

    this.chat_input = this.create_element('input', ['chat-input']);
    this.chat_input.type = 'text';
    this.chat_input.spellcheck = 'true';
    this.chat_form.appendChild(this.chat_input);

    this.chat_text = this.create_element('div', ['chat-text']);
    this.chat_window.appendChild(this.chat_text);

    this.chat_text_ul = this.create_element('ul');
    this.chat_text.appendChild(this.chat_text_ul);

    this.people_button = this.create_element('button', ['people-button']);
    this.people_button.innerHTML = "People (0)";
    this.chat_window.appendChild(this.people_button);

    this.people_panel = this.create_element('div', ['people-panel']);
    this.people_panel.style.visibility = 'hidden';
    this.chat_window.appendChild(this.people_panel);
  }

  insert_message(text, notice = false) {
    if (notice) {
      var message = '<li><i>' + text + '</i></li>';
    } else {
      var message = text;
    }

    this.chat_text_ul.innerHTML += message;
    this.chat_text.scrollTop = this.chat_text.scrollHeight;
  }

  get_messages() {
    var httpRequest = new XMLHttpRequest();

    httpRequest.onreadystatechange = function() {
      if (httpRequest.readyState === XMLHttpRequest.DONE) {
        if (httpRequest.status === 200) {
          var text = httpRequest.responseText;
          if (text.length) {
            this.chat_text_ul.innerHTML = text;
            this.chat_text.scrollTop = this.chat_text.scrollHeight;
          }
        }
      }
    }.bind(this);

    httpRequest.open('GET', '/messages/' + this.room);
    httpRequest.send();
  }

  update_users() {
    var httpRequest = new XMLHttpRequest();

    httpRequest.onreadystatechange = function() {
      if (httpRequest.readyState === XMLHttpRequest.DONE) {
        if (httpRequest.status === 200) {
          this.users = JSON.parse(httpRequest.responseText);
          this.people_button.innerHTML = "People (" + this.users.length + ")";
          var people_text = "<b> People here </b><br>";
          for (var i = 0; i < this.users.length; i++) {
            people_text += this.users[i] + '<br>';
          }
          this.people_panel.innerHTML = people_text;
        }
      }
    }.bind(this);

    httpRequest.open('GET', '/users/' + this.room);
    httpRequest.send();
  }

  toggle_people_panel() {
    if (this.people_panel.style.visibility == 'hidden') {
      this.people_panel.style.visibility = 'visible';
    } else {
      this.people_panel.style.visibility = 'hidden';
    }
  }

  on_submit(event) {
    event.preventDefault();
    var text = this.chat_input.value;

    if (text != "") {
      this.sync.message(text);
      this.chat_input.value = "";
    }
  }

  on_connected(event) {
    this.get_messages();
    this.update_users();
  }

  on_message(event) {
    this.insert_message(event.detail);
  }

  on_joined(event) {
    this.insert_message("" + event.detail + " joined", true);
    this.update_users();
  }

  on_left(event) {
    this.insert_message("" + event.detail + " left", true);
    this.update_users();
  }

  on_started(event) {
    this.insert_message("" + event.detail + " started video", true);
  }

  on_paused(event) {
    this.insert_message("" + event.detail + " paused video", true);
  }

  on_seeked(event) {
    this.insert_message("" + event.detail + " seeked video", true);
  }

  show_chat() {
    this.chat_window.style.visibility = "visible";
    this.hide_button.classList.remove("hidden");
  }

  hide_chat() {
    this.chat_window.style.visibility = "hidden";
    this.hide_button.classList.add("hidden");
  }

  on_hide_chat() {
    this.hide_button.blur();
    if (this.chat_window.style.visibility == "hidden") {
      this.show_chat();
    } else {
      this.hide_chat();
    }
  }

  on_popout() {
    this.hide_chat();
    window.open("/chat/" + this.room + "?username=" + this.username, "ChatWindowFor" + this.room, "menubar=off,toolbar=off,location=off,status=off,resizable=on,scrollbars=on,width=400,height=800"); 
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
