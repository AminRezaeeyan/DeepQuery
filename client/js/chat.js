// chat.js

const API_BASE = 'http://localhost:8000/api'; // Update with your backend URL

class ChatApp {
    constructor() {
        this.currentChatId = null;
        this.currentChatTitle = 'New Chat';
        this.selectedImage = null;
        this.chats = [];
        this.isLoadingMessages = false;
        this.messageCount = 0;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadUserSubscription();
        this.loadChatHistory();
        this.autoResizeTextarea();
    }

    setupEventListeners() {
        // Search
        document.getElementById('searchBtn').addEventListener('click', () => {
            document.getElementById('searchBox').classList.add('active');
            document.getElementById('searchInput').focus();
        });

        document.getElementById('closeSearch').addEventListener('click', () => {
            document.getElementById('searchBox').classList.remove('active');
            document.getElementById('searchInput').value = '';
            this.loadChatHistory();
        });

        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.searchChats(e.target.value);
        });

        // New chat
        document.getElementById('newChatBtn').addEventListener('click', () => {
            this.createNewChat();
        });

        // Message input
        const messageInput = document.getElementById('messageInput');
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        document.getElementById('sendBtn').addEventListener('click', () => {
            this.sendMessage();
        });

        // Image attachment
        document.getElementById('attachBtn').addEventListener('click', () => {
            document.getElementById('imageInput').click();
        });

        document.getElementById('imageInput').addEventListener('change', (e) => {
            this.handleImageSelect(e);
        });

        document.getElementById('removeImage').addEventListener('click', () => {
            this.removeImage();
        });
    }

    autoResizeTextarea() {
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        });
    }

    async loadUserSubscription() {
        try {
            const response = await this.apiCall('/subscriptions/my-subscription/');
            const data = await response.json();
            
            const firstName = localStorage.getItem('user_name') || '';
            const lastName = localStorage.getItem('user_last_name') || '';
            document.getElementById('userName').textContent = `${firstName} ${lastName}`.trim() || 'User';
            
            if (data.plan) {
                document.getElementById('planName').textContent = data.plan.name;
            }
        } catch (error) {
            console.error('Failed to load subscription:', error);
        }
    }

    async loadChatHistory() {
        try {
            const response = await this.apiCall('/chats/');
            const data = await response.json();
            this.chats = data.results || data;
            this.renderChatHistory(this.chats);
        } catch (error) {
            console.error('Failed to load chat history:', error);
            document.getElementById('chatHistory').innerHTML = '<div class="loading">Failed to load chats</div>';
        }
    }

    renderChatHistory(chats) {
        const container = document.getElementById('chatHistory');
        
        if (chats.length === 0) {
            container.innerHTML = '<div class="loading">No chats yet</div>';
            return;
        }

        const grouped = this.groupChatsByTime(chats);
        let html = '';

        for (const [group, items] of Object.entries(grouped)) {
            html += `<div class="chat-group">`;
            html += `<div class="chat-group-title">${group}</div>`;
            
            items.forEach(chat => {
                const isActive = chat.uuid === this.currentChatId ? 'active' : '';
                html += `
                    <div class="chat-item ${isActive}" data-chat-id="${chat.uuid}">
                        <div class="chat-item-title" data-title="${chat.title}">
                            ${this.escapeHtml(chat.title)}
                        </div>
                        <button class="edit-chat-btn" title="Edit Title">✎</button>
                    </div>
                `;
            });
            
            html += `</div>`;
        }

        container.innerHTML = html;

        // Add click listeners
        container.querySelectorAll('.chat-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Ignore clicks on input fields or the edit button
                if (!e.target.closest('input') && !e.target.closest('.edit-chat-btn')) {
                    this.loadChat(item.dataset.chatId);
                }
            });

            const titleDiv = item.querySelector('.chat-item-title');
            const editBtn = item.querySelector('.edit-chat-btn');
            
            // Allow explicit edit button click
            if (editBtn) {
                editBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.editChatTitle(item.dataset.chatId, titleDiv);
                });
            }

            // Keep double-click functionality for convenience
            titleDiv.addEventListener('dblclick', () => {
                this.editChatTitle(item.dataset.chatId, titleDiv);
            });
        });
    }

    groupChatsByTime(chats) {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const lastWeek = new Date(today);
        lastWeek.setDate(lastWeek.getDate() - 7);
        const lastMonth = new Date(today);
        lastMonth.setMonth(lastMonth.getMonth() - 1);

        const groups = {
            'Today': [],
            'Yesterday': [],
            'Last Week': [],
            'Last Month': [],
            'Older': []
        };

        chats.forEach(chat => {
            const chatDate = new Date(chat.updated_at || chat.created_at);
            
            if (chatDate >= today) {
                groups['Today'].push(chat);
            } else if (chatDate >= yesterday) {
                groups['Yesterday'].push(chat);
            } else if (chatDate >= lastWeek) {
                groups['Last Week'].push(chat);
            } else if (chatDate >= lastMonth) {
                groups['Last Month'].push(chat);
            } else {
                groups['Older'].push(chat);
            }
        });

        Object.keys(groups).forEach(key => {
            if (groups[key].length === 0) {
                delete groups[key];
            }
        });

        return groups;
    }

    async searchChats(query) {
        if (!query.trim()) {
            this.loadChatHistory();
            return;
        }

        try {
            const response = await this.apiCall(`/chats/search/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            this.renderChatHistory(data);
        } catch (error) {
            console.error('Search failed:', error);
        }
    }

    async createNewChat() {
        const emptyChat = this.chats.find(chat => chat.title === 'New Chat');
        if (emptyChat) {
            this.loadChat(emptyChat.uuid);
            return;
        }

        try {
            const response = await this.apiCall('/chats/', 'POST', {});
            const data = await response.json();
            this.currentChatId = data.uuid;
            this.currentChatTitle = data.title;
            this.messageCount = 0;
            await this.loadChatHistory();
            this.clearMessages();
            document.getElementById('chatTitle').textContent = this.currentChatTitle;
        } catch (error) {
            console.error('Failed to create chat:', error);
        }
    }

    async loadChat(uuid) {
        if (this.isLoadingMessages) return;
        
        this.currentChatId = uuid;
        this.isLoadingMessages = true;
        
        this.renderChatHistory(this.chats);
        
        try {
            const chatResponse = await this.apiCall(`/chats/${uuid}/`);
            const chatData = await chatResponse.json();
            this.currentChatTitle = chatData.title;
            document.getElementById('chatTitle').textContent = this.currentChatTitle;
            
            const messagesResponse = await this.apiCall(`/chats/${uuid}/messages/`);
            const messagesData = await messagesResponse.json();
            const messages = messagesData.results || messagesData;
            
            this.messageCount = messages.length;
            this.renderMessages(messages);
        } catch (error) {
            console.error('Failed to load chat:', error);
        } finally {
            this.isLoadingMessages = false;
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';
        
        if (messages.length === 0) {
            container.innerHTML = `
                <div class="messages-container" id="messagesContainer">
                <div class="welcome-screen">
                    <img src="assets/images/logo.svg" alt="">
                    <p>How can I help you today?</p>
                </div>
            </div>
            `;
            return;
        }
        
        messages.forEach(message => {
            this.appendMessage(message.role, message.content, message.image_url);
        });
        
        this.scrollToBottom();
    }

    appendMessage(role, content, imageUrl = null) {
        const container = document.getElementById('messagesContainer');
        const welcomeScreen = container.querySelector('.welcome-screen');
        if (welcomeScreen) {
            welcomeScreen.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (imageUrl) {
            const img = document.createElement('img');
            img.src = imageUrl;
            img.className = 'message-image';
            contentDiv.appendChild(img);
        }
        
        const textDiv = document.createElement('div');
        textDiv.textContent = content;
        contentDiv.appendChild(textDiv);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        container.appendChild(messageDiv);
        
        this.scrollToBottom();
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();
        
        if (!content && !this.selectedImage) return;
        
        if (!this.currentChatId) {
            await this.createNewChat();
        }
        
        try {
            const formData = new FormData();
            formData.append('content', content);
            formData.append('role', 'user');
            
            if (this.selectedImage) {
                formData.append('image', this.selectedImage);
            }
            
            const response = await fetch(`${API_BASE}/chats/${this.currentChatId}/messages/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access')}`
                },
                body: formData
            });
            
            if (!response.ok) throw new Error('Failed to send message');
            
            const data = await response.json();
            
            this.appendMessage('user', content, data.image_url);
            
            input.value = '';
            input.style.height = 'auto';
            this.removeImage();
            
            this.messageCount++;
            
            if (this.messageCount === 1) {
                this.requestChatTitle();
            }
            
            if (data.assistant_response) {
                this.appendMessage('assistant', data.assistant_response);
            }
            
            this.loadChatHistory();
            
        } catch (error) {
            console.error('Failed to send message:', error);
            alert('Failed to send message. Please try again.');
        }
    }

    async requestChatTitle() {
        try {
            setTimeout(async () => {
                const response = await this.apiCall(`/chats/${this.currentChatId}/`);
                const data = await response.json();
                if (data.title && data.title !== 'New Chat') {
                    this.currentChatTitle = data.title;
                    document.getElementById('chatTitle').textContent = this.currentChatTitle;
                    this.loadChatHistory();
                }
            }, 2000);
        } catch (error) {
            console.error('Failed to update chat title:', error);
        }
    }

    async editChatTitle(uuid, element) {
        const currentTitle = element.textContent.trim();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'edit-title-input';
        
        element.innerHTML = '';
        element.appendChild(input);
        input.focus();
        input.select();

        const saveTitle = async () => {
            const newTitle = input.value.trim();
            if (newTitle && newTitle !== currentTitle) {
                try {
                    await this.apiCall(`/chats/${uuid}/`, 'PATCH', { title: newTitle });
                    element.textContent = newTitle;
                    if (uuid === this.currentChatId) {
                        document.getElementById('chatTitle').textContent = newTitle;
                    }
                    this.loadChatHistory();
                } catch (error) {
                    console.error('Failed to update title:', error);
                    element.textContent = currentTitle;
                }
            } else {
                element.textContent = currentTitle;
            }
        };

        input.addEventListener('blur', saveTitle);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                input.blur();
            } else if (e.key === 'Escape') {
                element.textContent = currentTitle;
            }
        });
    }

    scrollToBottom() {
        const container = document.getElementById('messagesContainer');
        container.scrollTop = container.scrollHeight;
    }

    clearMessages() {
        const container = document.getElementById('messagesContainer');
        const firstName = localStorage.getItem('user_name') || '';
        const lastName = localStorage.getItem('user_last_name') || '';
        const welcomeText = `Hello ${firstName} ${lastName}`.trim();
        
        container.innerHTML = `
             <div class="messages-container" id="messagesContainer">
                <div class="welcome-screen">
                    <img src="assets/images/logo.svg" alt="">
                    <p>How can I help you today?</p>
                </div>
            </div>
        `;
        document.getElementById('chatTitle').textContent = 'New Chat';
    }

    handleImageSelect(e) {
        const file = e.target.files[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                alert('Please select an image file');
                return;
            }
            
            if (file.size > 10 * 1024 * 1024) {
                alert('Image size should be less than 10MB');
                return;
            }
            
            this.selectedImage = file;
            const reader = new FileReader();
            reader.onload = (event) => {
                document.getElementById('previewImg').src = event.target.result;
                document.getElementById('imagePreview').style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    }

    removeImage() {
        this.selectedImage = null;
        document.getElementById('imagePreview').style.display = 'none';
        document.getElementById('imageInput').value = '';
    }

    async apiCall(url, method = 'GET', body = null) {
        const headers = {
            'Authorization': `Bearer ${localStorage.getItem('access')}`,
            'Content-Type': 'application/json'
        };

        const options = { method, headers };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(`${API_BASE}${url}`, options);
        
        if (response.status === 401) {
            localStorage.clear();
            window.location.href = 'login.html';
        }
        
        if (!response.ok && method !== 'GET') {
            throw new Error(`API call failed: ${response.statusText}`);
        }
        
        return response;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});
