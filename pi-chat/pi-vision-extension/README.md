# PI Vision Chat Extension

Custom PI Vision symbol that embeds the chat interface directly into PI Vision displays.

## Installation

1. Copy all files from this directory to your PI Vision extensibility folder:
   ```
   C:\Program Files\AVEVA\PI Vision\Scripts\app\editor\symbols\ext\
   ```

2. Create a subdirectory called `pichat`:
   ```
   C:\Program Files\AVEVA\PI Vision\Scripts\app\editor\symbols\ext\pichat\
   ```

3. Copy the following files to the `pichat` directory:
   - `sym-pichat.js`
   - `sym-pichat-template.html`
   - `sym-pichat-config.js`

4. Restart IIS or recycle the PI Vision application pool:
   ```powershell
   iisreset
   # OR
   Restart-WebAppPool -Name "PI Vision"
   ```

5. Clear your browser cache and refresh PI Vision

## Usage

1. Open PI Vision in edit mode
2. Find "PI Chat" in the symbol palette
3. Drag and drop onto your display
4. Configure the symbol to point to your FastAPI backend
5. Optionally associate PI elements for context-aware chat

## Configuration

The symbol can be configured with:
- **Backend URL**: URL of the FastAPI backend (default: `http://localhost:8000`)
- **Context Elements**: PI elements to provide as context to the chat
- **Model**: LLM model to use for chat
- **Height**: Chat window height
- **Theme**: Light or dark theme

## Features

- Real-time chat interface
- Context-aware responses based on selected PI elements
- Streaming responses
- Conversation history
- PI element and attribute queries
- Responsive design

## Troubleshooting

If the symbol doesn't appear:
1. Check that files are in the correct directory
2. Verify file permissions (IIS user needs read access)
3. Check browser console for JavaScript errors
4. Verify backend is running and accessible
5. Check CORS settings in backend configuration
