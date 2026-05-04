const vscode = require('vscode');
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    const disposable = vscode.commands.registerCommand('genlayer.generateAbi', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor found.');
            return;
        }

        const doc = editor.document;
        if (doc.languageId !== 'python') {
            vscode.window.showErrorMessage('This command only works on Python files.');
            return;
        }

        const sourcePath = doc.fileName;
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        
        // Detect venv or fallback to global python
        const venvPython = path.join(workspaceFolder, 'venv', 'Scripts', 'python.exe');
        const python = fs.existsSync(venvPython) ? venvPython : 'python';

        // Determine output directory
        const outputDir = path.join(workspaceFolder, 'generated');

        try {
            const result = execFileSync(
                python,
                ['-m', 'genlayer_abi.cli', 'generate', sourcePath, '--output-dir', outputDir, '--format', 'all'],
                { cwd: workspaceFolder, encoding: 'utf-8', timeout: 30000 }
            );

            // Show output panel with generated TS preview
            // The CLI names files by contract class name, not source filename
            const files = fs.readdirSync(outputDir);
            const byMtime = (a, b) => fs.statSync(b).mtime - fs.statSync(a).mtime;

            const abiFile = files.filter(f => f.endsWith('Abi.ts')).map(f => path.join(outputDir, f)).sort(byMtime)[0];
            const hooksFile = files.filter(f => f.includes('Hooks')).map(f => path.join(outputDir, f)).sort(byMtime)[0];
            const wrapperFile = files.filter(f => f.includes('Wrapper')).map(f => path.join(outputDir, f)).sort(byMtime)[0];

            const artifacts = {
                abi: abiFile && fs.existsSync(abiFile) ? fs.readFileSync(abiFile, 'utf-8') : '',
                hooks: hooksFile && fs.existsSync(hooksFile) ? fs.readFileSync(hooksFile, 'utf-8') : '',
                wrapper: wrapperFile && fs.existsSync(wrapperFile) ? fs.readFileSync(wrapperFile, 'utf-8') : ''
            };

            const panel = vscode.window.createWebviewPanel(
                'genlayerAbiPreview',
                'GenLayer ABI Preview',
                vscode.ViewColumn.Two,
                { enableScripts: true }
            );

            panel.webview.html = getWebviewContent(artifacts);
            
            vscode.window.showInformationMessage('GenLayer ABI generated successfully!');
        } catch (err) {
            vscode.window.showErrorMessage(`GenLayer ABI generation failed: ${err.message}`);
        }
    });

    context.subscriptions.push(disposable);
}

function getWebviewContent(artifacts) {
    function highlight(code) {
        const escaped = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return escaped
            .replace(/\b(const|export|function|class|interface|type|return|async|await|import|from|as)\b/g, '<span style="color:#569cd6">$1</span>')
            .replace(/\b(string|number|boolean|bigint|any|void|null|Record|Promise)\b/g, '<span style="color:#4ec9b0">$1</span>')
            .replace(/("(?:[^"\\]|\\.)*")/g, '<span style="color:#ce9178">$1</span>')
            .replace(/(\/\/.*$)/gm, '<span style="color:#6a9955">$1</span>')
            .replace(/\b(true|false)\b/g, '<span style="color:#569cd6">$1</span>')
            .replace(/\b([0-9]+)\b/g, '<span style="color:#b5cea8">$1</span>')
            .replace(/(\b[A-Z][a-zA-Z0-9_]*\b)/g, '<span style="color:#4ec9b0">$1</span>');
    }

    const data = JSON.stringify({
        abi: highlight(artifacts.abi),
        hooks: highlight(artifacts.hooks),
        wrapper: highlight(artifacts.wrapper)
    });

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --surface-hover: #1f242c;
            --border: #30363d;
            --accent: #58a6ff;
            --text: #c9d1d9;
            --text-secondary: #8b949e;
            --text-muted: #484f58;
            --font-mono: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body {
            height: 100%;
            background: var(--bg);
            color: var(--text);
            font-family: var(--font-mono);
            font-size: 14px;
            line-height: 1.6;
            overflow: hidden;
        }
        .tab-bar {
            display: flex;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 0 8px;
            flex-shrink: 0;
        }
        .tab {
            padding: 8px 14px;
            font-size: 11px;
            font-weight: 500;
            color: var(--text-secondary);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -1px;
            transition: all 0.1s;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tab:hover { color: var(--text); }
        .tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        .tab .tab-badge {
            font-size: 11px;
            background: var(--border);
            padding: 1px 5px;
            border-radius: 10px;
            color: var(--text-secondary);
        }
        .tab.active .tab-badge { background: rgba(88,166,255,0.15); color: var(--accent); }
        .pane-header {
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: var(--text-secondary);
            user-select: none;
        }
        .actions {
            display: flex;
            gap: 4px;
        }
        .btn {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 3px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-mono);
            font-size: 11px;
            transition: all 0.1s;
        }
        .btn:hover {
            background: var(--border);
            color: var(--text);
        }
        .btn:active { transform: translateY(1px); }
        .btn.copied {
            background: var(--accent);
            color: #0d1117;
            border-color: var(--accent);
        }
        .editor {
            height: calc(100vh - 82px);
            overflow: auto;
            padding: 12px 16px;
        }
        pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: var(--font-mono);
            font-size: 14px;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="tab-bar" role="tablist">
        <div class="tab active" data-file="abi" role="tab" tabindex="0" title="Type-safe ABI object for genlayer-js" aria-selected="true">ABI<span class="tab-badge">TS</span></div>
        <div class="tab" data-file="hooks" role="tab" tabindex="0" title="React useContractRead / useContractWrite hooks" aria-selected="false">Hooks<span class="tab-badge">TS</span></div>
        <div class="tab" data-file="wrapper" role="tab" tabindex="0" title="Pre-built genlayer-js client with typed methods" aria-selected="false">Wrapper<span class="tab-badge">TS</span></div>
    </div>
    <div class="pane-header">
        <span id="filename">Generated TypeScript</span>
        <div class="actions">
            <button class="btn" id="copyBtn" aria-label="Copy to clipboard">Copy</button>
        </div>
    </div>
    <div class="editor">
        <pre id="code"></pre>
    </div>
    <script>
        const data = ${data};
        let activeFile = 'abi';

        function render() {
            const content = data[activeFile] || '';
            const map = { abi: 'ABI', hooks: 'Hooks', wrapper: 'Wrapper' };
            document.getElementById('filename').textContent = map[activeFile];
            document.getElementById('code').innerHTML = content || '<div style="color:var(--text-muted);padding:40px 0;text-align:center;font-style:italic">Select a tab above to view generated artifacts</div>';
        }

        function activateTab(tab) {
            document.querySelectorAll('.tab').forEach(x => {
                x.classList.remove('active');
                x.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('active');
            tab.setAttribute('aria-selected', 'true');
            activeFile = tab.dataset.file;
            render();
        }
        document.querySelectorAll('.tab').forEach(t => {
            t.addEventListener('click', () => activateTab(t));
            t.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    activateTab(t);
                }
            });
        });

        function copyCode() {
            const btn = document.getElementById('copyBtn');
            const text = document.getElementById('code').innerText;
            navigator.clipboard.writeText(text).then(() => {
                const original = btn.textContent;
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.textContent = original;
                    btn.classList.remove('copied');
                }, 1500);
            });
        }
        document.getElementById('copyBtn').addEventListener('click', copyCode);

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'c' && !window.getSelection().toString()) {
                e.preventDefault();
                copyCode();
            }
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                const order = ['abi', 'hooks', 'wrapper'];
                const idx = order.indexOf(activeFile);
                if (e.key === 'ArrowLeft' && idx > 0) activeFile = order[idx - 1];
                if (e.key === 'ArrowRight' && idx < order.length - 1) activeFile = order[idx + 1];
                document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.file === activeFile));
                render();
            }
        });

        render();
    </script>
</body>
</html>`;
}

function deactivate() {}

module.exports = { activate, deactivate };
