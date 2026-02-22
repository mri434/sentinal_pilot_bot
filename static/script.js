
  const chatWindow = document.getElementById('chatWindow');
  const userInput  = document.getElementById('userInput');
  const sendBtn    = document.getElementById('sendBtn');

  function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  function handleKey(e) {
    // Send on Enter, new line on Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function sendChip(el) {
    userInput.value = el.textContent;
    sendMessage();
  }

  function appendMessage(role, text) {
    // Hide welcome screen on first message
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.remove();

    const msg = document.createElement('div');
    msg.classList.add('message', role);

    const avatar = document.createElement('div');
    avatar.classList.add('avatar');
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');
    bubble.textContent = text;

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return msg;
  }

  function showTyping() {
    const msg = document.createElement('div');
    msg.classList.add('message', 'bot', 'typing');
    msg.id = 'typing';

    const avatar = document.createElement('div');
    avatar.classList.add('avatar');
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');
    bubble.innerHTML = `
      <div class="dot"></div>
      <div class="dot"></div>
      <div class="dot"></div>`;

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function removeTyping() {
    const t = document.getElementById('typing');
    if (t) t.remove();
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Show user message
    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Show typing dots
    showTyping();

    try {
      const res = await fetch('/chat', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({ message: text })
      });
      const data = await res.json();
      removeTyping();
      appendMessage('bot', data.reply);
    } catch (err) {
      removeTyping();
      appendMessage('bot', '⚠️ Something went wrong. Please try again.');
    }

    sendBtn.disabled = false;
    userInput.focus();
  }