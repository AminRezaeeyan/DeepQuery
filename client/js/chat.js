// chat.js

const API_BASE = 'http://localhost:8000/api';

class ChatApp {
    constructor() {
        this.currentChatId = null;
        this.currentChatTitle = 'New Chat';
        this.chats = [];
        this.documents = [];
        this.models = [];
        this.currentProviderId = null;
        this.isTemporary = false;
        this.isLoadingMessages = false;
        this.messageCount = 0;
        
        this.allowedExtensions = ['.txt', '.pdf', '.csv', '.xlsx', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.json', '.md'];
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadUserSubscription();
        this.loadModels();
        this.loadChatHistory();
        this.autoResizeTextarea();
    }

    getProviderSvg(providerType) {
        const type = (providerType || '').toLowerCase();
        if (type === 'openai') {
            return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2057 5.9847 5.9847 0 0 0 3.989-2.9001 6.0557 6.0557 0 0 0-.7388-7.0731zM13.2599 22.5002c-1.229 0-2.3949-.3846-3.366-1.0776l.1691-.0976 4.7928-2.7663a1.4938 1.4938 0 0 0 .7536-1.2982v-6.7214l2.5843 1.4908a.0903.0903 0 0 1 .0465.0784v5.6264a4.5501 4.5501 0 0 1-4.9803 4.7651z"/></svg>`;
        } else if (type === 'anthropic' || type === 'claude') {
            return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm3.5 14h-7v-2h7v2zm1.5-4h-10v-2h10v2z"/></svg>`;
        } else if (type === 'google' || type === 'gemini') {
            return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7.6H22l-6.2 4.6 2.4 7.6-6.2-4.6-6.2 4.6 2.4-7.6L2 9.6h7.6L12 2z"/></svg>`;
        } else if (type === 'ollama') {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/></svg>`;
        }
        // Fallback
        return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`;
    }

    setupEventListeners() {
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

        document.getElementById('newChatBtn').addEventListener('click', () => {
            this.prepareNewChatUI();
        });

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

        document.getElementById('attachBtn').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.handleFileSelect(e);
        });

        // Custom Dropdown Event Listeners
        const trigger = document.getElementById('modelSelectTrigger');
        trigger.addEventListener('click', () => {
            if (!trigger.classList.contains('disabled')) {
                document.getElementById('modelSelectContainer').classList.toggle('open');
            }
        });

        document.addEventListener('click', (e) => {
            if (!document.getElementById('modelSelectContainer').contains(e.target)) {
                document.getElementById('modelSelectContainer').classList.remove('open');
            }
        });

        // Temp Chat Toggle
        document.getElementById('tempChatToggle').addEventListener('change', async (e) => {
            this.isTemporary = e.target.checked;
            if (this.currentChatId) {
                try {
                    await this.apiCall(`/chats/${this.currentChatId}/`, 'PATCH', { is_temporary: this.isTemporary });
                } catch (err) {
                    console.error("Failed to update temporary status", err);
                }
            }
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

    async loadModels() {
        try {
            const response = await this.apiCall('/models/');
            this.models = await response.json();
            this.renderModelSelect();
        } catch (error) {
            console.error('Failed to load models:', error);
        }
    }

    renderModelSelect() {
        const dropdown = document.getElementById('modelSelectDropdown');
        dropdown.innerHTML = '';
        
        let defaultId = null;
        
        this.models.forEach(model => {
            const option = document.createElement('div');
            option.className = 'model-option';
            
            const svg = this.getProviderSvg(model.provider_type);
            
            option.innerHTML = `
                <div class="model-icon">${svg}</div>
                <div class="model-details">
                    <div class="model-name">${model.name}</div>
                    <div class="model-desc">${model.description || model.model_name}</div>
                </div>
            `;
            
            option.addEventListener('click', () => {
                this.selectModel(model);
                document.getElementById('modelSelectContainer').classList.remove('open');
            });
            
            dropdown.appendChild(option);
            
            if (model.is_default_for_chat) {
                defaultId = model.id;
            }
        });

        const targetId = defaultId || (this.models.length > 0 ? this.models[0].id : null);
        if (targetId) {
            const targetModel = this.models.find(m => m.id === targetId);
            this.selectModel(targetModel);
        }
        
        this.updateHeaderLocks();
    }

    selectModel(model) {
        if (!model) return;
        this.currentProviderId = model.id;
        
        const triggerInfo = document.getElementById('selectedModelInfo');
        const svg = this.getProviderSvg(model.provider_type);
        triggerInfo.innerHTML = `
            <div class="model-icon" style="width:16px;height:16px;">${svg}</div>
            <span>${model.name}</span>
        `;
    }

    updateHeaderLocks() {
        const hasMessages = this.messageCount > 0;
        
        // Lock model select
        const trigger = document.getElementById('modelSelectTrigger');
        if (hasMessages) {
            trigger.classList.add('disabled');
        } else {
            trigger.classList.remove('disabled');
        }

        // Lock temp toggle
        const tempToggle = document.getElementById('tempChatToggle');
        tempToggle.disabled = hasMessages;
    }

    async loadChatHistory() {
        try {
            const response = await this.apiCall('/chats/');
            const data = await response.json();
            this.chats = data.results || data;
            this.renderChatHistory(this.chats);
        } catch (error) {
            console.error('Failed to load chat history:', error);
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
            html += `<div class="chat-group"><div class="chat-group-title">${group}</div>`;
            items.forEach(chat => {
                const isActive = chat.uuid === this.currentChatId ? 'active' : '';
                html += `
                    <div class="chat-item ${isActive}" data-chat-id="${chat.uuid}">
                        <div class="chat-item-title" data-title="${chat.title}">
                            ${this.escapeHtml(chat.title)}
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
        }
        container.innerHTML = html;

        container.querySelectorAll('.chat-item').forEach(item => {
            item.addEventListener('click', () => {
                this.loadChat(item.dataset.chatId);
            });
        });
    }

    groupChatsByTime(chats) {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
        const lastWeek = new Date(today); lastWeek.setDate(lastWeek.getDate() - 7);
        const groups = { 'Today': [], 'Yesterday': [], 'Last Week': [], 'Older': [] };

        chats.forEach(chat => {
            const chatDate = new Date(chat.updated_at || chat.created_at);
            if (chatDate >= today) groups['Today'].push(chat);
            else if (chatDate >= yesterday) groups['Yesterday'].push(chat);
            else if (chatDate >= lastWeek) groups['Last Week'].push(chat);
            else groups['Older'].push(chat);
        });

        Object.keys(groups).forEach(key => { if (groups[key].length === 0) delete groups[key]; });
        return groups;
    }

    prepareNewChatUI() {
        this.currentChatId = null;
        this.currentChatTitle = 'New Chat';
        this.messageCount = 0;
        this.documents = [];
        this.isTemporary = false;
        
        document.getElementById('tempChatToggle').checked = false;
        document.getElementById('chatTitle').textContent = this.currentChatTitle;
        
        this.clearMessages();
        this.renderDocuments([]);
        this.renderChatHistory(this.chats);
        this.updateHeaderLocks();
    }

    async ensureChatExists() {
        if (this.currentChatId) return;
        try {
            const payload = { is_temporary: this.isTemporary };
            const response = await this.apiCall('/chats/', 'POST', payload);
            const data = await response.json();
            this.currentChatId = data.uuid;
            this.currentChatTitle = data.title;
            await this.loadChatHistory();
        } catch (error) {
            console.error('Failed to create chat:', error);
            throw error;
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
            this.isTemporary = chatData.is_temporary || false;
            
            document.getElementById('chatTitle').textContent = this.currentChatTitle;
            document.getElementById('tempChatToggle').checked = this.isTemporary;
            
            const messagesResponse = await this.apiCall(`/chats/${uuid}/messages/`);
            const messagesData = await messagesResponse.json();
            const messages = messagesData.results || messagesData;
            
            this.messageCount = messages.length;
            this.renderMessages(messages);
            this.updateHeaderLocks();
            
            this.loadDocuments();
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
            this.clearMessages();
            return;
        }
        messages.forEach(message => this.appendMessage(message.role, message.content));
        this.scrollToBottom();
    }

    appendMessage(role, content) {
        const container = document.getElementById('messagesContainer');
        const welcomeScreen = container.querySelector('.welcome-screen');
        if (welcomeScreen) welcomeScreen.remove();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
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
        if (!content) return;
        
        try {
            await this.ensureChatExists();
            
            const formData = new FormData();
            formData.append('content', content);
            formData.append('role', 'user');
            
            if (this.currentProviderId) {
                formData.append('provider_id', this.currentProviderId);
            }
            
            this.appendMessage('user', content);
            input.value = '';
            input.style.height = 'auto';
            
            this.messageCount++;
            this.updateHeaderLocks();
            
            const response = await fetch(`${API_BASE}/chats/${this.currentChatId}/messages/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access')}` },
                body: formData
            });
            
            if (!response.ok) throw new Error('Failed to send message');
            const data = await response.json();
            
            if (this.messageCount === 1) this.requestChatTitle();
            if (data.assistant_response) this.appendMessage('assistant', data.assistant_response);
            
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

    scrollToBottom() {
        const container = document.getElementById('messagesContainer');
        container.scrollTop = container.scrollHeight;
    }

    clearMessages() {
        const container = document.getElementById('messagesContainer');
        container.innerHTML = `<div class="welcome-screen"><p>How can I help you today?</p></div>`;
    }

    async loadDocuments() {
        if (!this.currentChatId) return;
        try {
            const response = await this.apiCall('/documents/');
            const data = await response.json();
            const docs = data.results || data;
            this.documents = docs.filter(d => d.chat === this.currentChatId);
            this.renderDocuments(this.documents);
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }

    renderDocuments(docs) {
        const container = document.getElementById('documentsList');
        container.innerHTML = '';

        if (docs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
                    </svg>
                    <p>No documents yet</p>
                </div>
            `;
            return;
        }

        docs.forEach(doc => {
            container.appendChild(this.createDocumentCard(doc));
        });
    }

    createDocumentCard(doc, isLoading = false) {
        const extMatch = (doc.original_filename || '').match(/\.([0-9a-z]+)(?:[\?#]|$)/i);
        const extension = extMatch ? extMatch[1].toLowerCase() : 'file';
        
        const card = document.createElement('div');
        card.className = `document-card ${isLoading ? 'loading' : ''}`;
        card.dataset.uuid = doc.uuid || 'temp';

        let colorClass = 'doc-color-default';
        if (['py', 'js', 'ts', 'java', 'c', 'cpp'].includes(extension)) colorClass = 'doc-color-code';
        else if (extension === 'pdf') colorClass = 'doc-color-pdf';
        else if (['csv', 'xlsx'].includes(extension)) colorClass = 'doc-color-csv';
        else if (['txt', 'md'].includes(extension)) colorClass = 'doc-color-txt';
        else if (extension === 'json') colorClass = 'doc-color-json';

        const statusDisplay = isLoading ? 'Uploading...' : (doc.status || 'Ready');
        
        card.innerHTML = `
            <div class="document-icon ${colorClass}">${extension}</div>
            <div class="document-details">
                <div class="document-name" title="${doc.original_filename}">${doc.original_filename}</div>
                <div class="document-meta">${statusDisplay}</div>
            </div>
            <div class="document-actions">
                ${isLoading ? 
                    '<div class="spinner"></div>' : 
                    `<button class="delete-doc-btn" onclick="app.deleteDocument('${doc.uuid}')" title="Remove Document">
                       <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 6h18" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                    </button>`
                }
            </div>
        `;
        return card;
    }

    async handleFileSelect(e) {
        const file = e.target.files[0];
        document.getElementById('fileInput').value = '';
        if (!file) return;

        const extMatch = file.name.match(/\.([0-9a-z]+)(?:[\?#]|$)/i);
        const extension = extMatch ? '.' + extMatch[1].toLowerCase() : '';
        
        if (!this.allowedExtensions.includes(extension)) {
            alert(`Unsupported file type. Supported: ${this.allowedExtensions.join(', ')}`);
            return;
        }

        try {
            await this.ensureChatExists();

            const tempDoc = { original_filename: file.name, uuid: 'temp-' + Date.now() };
            const container = document.getElementById('documentsList');
            const emptyState = container.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            const tempCard = this.createDocumentCard(tempDoc, true);
            container.appendChild(tempCard);

            const formData = new FormData();
            formData.append('file', file);
            formData.append('chat', this.currentChatId);

            const response = await fetch(`${API_BASE}/documents/`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access')}` },
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData[0] || 'Upload failed');
            }

            const newDoc = await response.json();
            this.documents.push(newDoc);
            tempCard.replaceWith(this.createDocumentCard(newDoc));

        } catch (error) {
            console.error('Failed to upload document:', error);
            alert(`Failed to upload: ${error.message}`);
            this.renderDocuments(this.documents);
        }
    }

    async deleteDocument(uuid) {
        if (!confirm('Are you sure you want to remove this document?')) return;
        
        const card = document.querySelector(`.document-card[data-uuid="${uuid}"]`);
        if (card) card.style.opacity = '0.5';

        try {
            const response = await fetch(`${API_BASE}/documents/${uuid}/`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access')}` }
            });

            if (!response.ok) throw new Error('Failed to delete');
            
            this.documents = this.documents.filter(d => d.uuid !== uuid);
            this.renderDocuments(this.documents);
        } catch (error) {
            console.error('Failed to delete document:', error);
            alert('Failed to delete document. Please try again.');
            if (card) card.style.opacity = '1';
        }
    }

    async apiCall(url, method = 'GET', body = null) {
        const headers = {
            'Authorization': `Bearer ${localStorage.getItem('access')}`,
            'Content-Type': 'application/json'
        };
        const options = { method, headers };
        if (body) options.body = JSON.stringify(body);
        const response = await fetch(`${API_BASE}${url}`, options);
        if (!response.ok && method !== 'GET') throw new Error(`API call failed: ${response.statusText}`);
        return response;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new ChatApp();
});
