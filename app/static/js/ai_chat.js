// ============================================================================
// AI CHAT INTERACTIVITY
// ============================================================================
window.sendChatMessage = function() {
    const input = document.getElementById('ai-chat-input-box');
    const msg = input.value.trim();
    if (!msg) return;

    const chatBody = document.getElementById('ai-chat-body');
    
    // Add User Message
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg user-msg animate-slide-up';
    userDiv.textContent = msg;
    chatBody.appendChild(userDiv);
    
    input.value = '';
    chatBody.scrollTop = chatBody.scrollHeight;

    // Simulate AI Response (In a real app, this would be an API call)
    setTimeout(() => {
        const aiDiv = document.createElement('div');
        aiDiv.className = 'chat-msg ai-msg animate-slide-up';
        aiDiv.innerHTML = "I am currently analyzing your request for <strong>" + (window.currentTicker || 'the stock') + "</strong>. Please hold while I compile the latest intelligence.";
        chatBody.appendChild(aiDiv);
        chatBody.scrollTop = chatBody.scrollHeight;
    }, 800);
};
