/**
 * PI Vision Chat Symbol
 *
 * Custom PI Vision symbol that embeds a chat interface
 * for interacting with PI System using LLMs
 */

(function (PV) {
    'use strict';

    // Symbol definition
    function symbolVis() { }
    PV.deriveVisualizationFromBase(symbolVis);

    // Symbol metadata
    var definition = {
        typeName: 'pichat',
        displayName: 'PI Chat',
        description: 'Interactive chat interface for PI System queries',
        iconUrl: '/Scripts/app/editor/symbols/ext/pichat/icon.png',

        // Data sources (optional PI elements for context)
        datasourceBehavior: PV.Extensibility.Enums.DatasourceBehaviors.Multiple,

        // Support multi-state configuration
        getDefaultConfig: function () {
            return {
                BackgroundColor: 'transparent',
                Height: 500,
                Width: 400,
                BackendUrl: 'http://localhost:8000',
                Model: 'llama3',
                Theme: 'light',
                ShowTimestamps: true,
                MaxMessages: 100,
                EnableContext: true
            };
        },

        // Configuration pane
        configOptions: function () {
            return [
                {
                    title: 'Chat Configuration',
                    mode: 'format'
                },
                {
                    title: 'Backend Settings',
                    mode: 'backend'
                }
            ];
        }
    };

    // Symbol visualization implementation
    symbolVis.prototype.init = function (scope, elem) {
        var self = this;

        // Initialize state
        this.scope = scope;
        this.elem = elem;
        this.conversationId = null;
        this.messages = [];

        // Get configuration
        this.config = scope.config || definition.getDefaultConfig();

        // Setup UI
        this.setupUI();

        // Setup event listeners
        this.setupEventListeners();

        // Connect to backend
        this.connectBackend();

        console.log('PI Chat symbol initialized');
    };

    symbolVis.prototype.setupUI = function () {
        var container = this.elem.find('#chat-container');

        if (container.length === 0) {
            return;
        }

        // Apply theme
        container.addClass('theme-' + this.config.Theme);

        // Set dimensions
        container.css({
            height: this.config.Height + 'px',
            width: this.config.Width + 'px'
        });
    };

    symbolVis.prototype.setupEventListeners = function () {
        var self = this;
        var sendButton = this.elem.find('#send-button');
        var inputField = this.elem.find('#message-input');
        var clearButton = this.elem.find('#clear-button');

        // Send message on button click
        sendButton.on('click', function () {
            self.sendMessage();
        });

        // Send message on Enter key
        inputField.on('keypress', function (e) {
            if (e.which === 13 && !e.shiftKey) {
                e.preventDefault();
                self.sendMessage();
            }
        });

        // Clear conversation
        clearButton.on('click', function () {
            self.clearConversation();
        });
    };

    symbolVis.prototype.connectBackend = function () {
        this.backendUrl = this.config.BackendUrl.replace(/\/$/, '');
        console.log('Connected to backend:', this.backendUrl);
    };

    symbolVis.prototype.sendMessage = async function () {
        var inputField = this.elem.find('#message-input');
        var message = inputField.val().trim();

        if (!message) {
            return;
        }

        // Clear input
        inputField.val('');

        // Add user message to chat
        this.addMessage('user', message);

        // Get context from PI elements
        var context = this.getContext();

        // Send to backend
        try {
            var response = await this.callBackendAPI('/api/chat/message', {
                message: message,
                context: context,
                conversation_id: this.conversationId,
                model: this.config.Model,
                stream: false
            });

            // Update conversation ID
            if (response.conversation_id) {
                this.conversationId = response.conversation_id;
            }

            // Add assistant response
            this.addMessage('assistant', response.response);

            // Add sources if available
            if (response.sources && response.sources.length > 0) {
                this.showSources(response.sources);
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('system', 'Error: Failed to get response from backend');
        }
    };

    symbolVis.prototype.addMessage = function (role, content) {
        var messagesContainer = this.elem.find('#messages');
        var timestamp = this.config.ShowTimestamps ? this.formatTimestamp(new Date()) : '';

        // Create message element
        var messageDiv = $('<div>')
            .addClass('message')
            .addClass('message-' + role);

        if (this.config.ShowTimestamps) {
            var timestampSpan = $('<span>')
                .addClass('timestamp')
                .text(timestamp);
            messageDiv.append(timestampSpan);
        }

        var contentDiv = $('<div>')
            .addClass('message-content')
            .text(content);

        messageDiv.append(contentDiv);
        messagesContainer.append(messageDiv);

        // Scroll to bottom
        messagesContainer.scrollTop(messagesContainer[0].scrollHeight);

        // Store message
        this.messages.push({
            role: role,
            content: content,
            timestamp: new Date()
        });

        // Limit message history
        if (this.messages.length > this.config.MaxMessages) {
            this.messages.shift();
        }
    };

    symbolVis.prototype.showSources = function (sources) {
        var sourcesText = 'Sources: ' + sources.map(function (s) {
            return s.name || s.path;
        }).join(', ');

        this.addMessage('system', sourcesText);
    };

    symbolVis.prototype.clearConversation = function () {
        var messagesContainer = this.elem.find('#messages');
        messagesContainer.empty();
        this.messages = [];
        this.conversationId = null;

        this.addMessage('system', 'Conversation cleared');
    };

    symbolVis.prototype.getContext = function () {
        if (!this.config.EnableContext) {
            return {};
        }

        var context = {
            elements: []
        };

        // Get data items (PI elements) associated with the symbol
        if (this.scope.symbol && this.scope.symbol.DataSources) {
            this.scope.symbol.DataSources.forEach(function (ds) {
                if (ds.Path) {
                    context.elements.push({
                        path: ds.Path,
                        label: ds.Label
                    });
                }
            });
        }

        return context;
    };

    symbolVis.prototype.callBackendAPI = async function (endpoint, data) {
        var url = this.backendUrl + endpoint;

        var response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error('Backend API error: ' + response.statusText);
        }

        return await response.json();
    };

    symbolVis.prototype.formatTimestamp = function (date) {
        var hours = date.getHours().toString().padStart(2, '0');
        var minutes = date.getMinutes().toString().padStart(2, '0');
        return hours + ':' + minutes;
    };

    // Update method (called when data changes)
    symbolVis.prototype.onDataUpdate = function (newData) {
        // Handle data updates if needed
        console.log('Data updated:', newData);
    };

    // Resize method
    symbolVis.prototype.onResize = function (width, height) {
        var container = this.elem.find('#chat-container');
        container.css({
            width: width + 'px',
            height: height + 'px'
        });
    };

    // Register the symbol
    PV.symbolCatalog.register(definition, symbolVis);

})(window.PIVisualization);
