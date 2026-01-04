const { useState, useEffect, useRef } = React;
function FileSystem() {
    const [currentPath, setCurrentPath] = useState('/');
    const [terminalOutput, setTerminalOutput] = useState([]);
    const [commandInput, setCommandInput] = useState('');
    const [treeData, setTreeData] = useState('');
    const [rawBytes, setRawBytes] = useState('');
    const [selectedFile, setSelectedFile] = useState(null);
    const terminalEndRef = useRef(null);
    const filesystemName = window.location.pathname.split('/').filter(Boolean)[1];

    
    useEffect(() => {
        mountFilesystem();
        loadTree();
        loadRawBytes();
        addOutput('Filesystem mounted successfully. Type "help" for available commands.', 'success');
    }, []);
    
    useEffect(() => {
        terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [terminalOutput]);
    
    const addOutput = (text, type = 'info') => {
        setTerminalOutput(prev => [...prev, { text, type, timestamp: Date.now() }]);
    };
    const mountFilesystem = async () => {
        await fetch(`/mount/${filesystemName}`, {
            method: 'POST'
        });
    };
    const loadTree = async (path = '/') => {
        const response = await fetch(`/filesystem/${filesystemName}/tree?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        const tree = data.output || data.tree;
        const formatted = Array.isArray(tree) ? tree.join('\n') : tree;
        
        setTreeData(formatted || 'Empty');
    };
    
    const loadRawBytes = async () => {
        const response = await fetch(`/filesystem/${filesystemName}/raw_content`);
        const data = await response.text();
        setRawBytes(data);
    };
    
    const executeCommand = async (cmd) => {
        const parts = cmd.trim().split(/\s+/);
        const command = parts[0].toLowerCase();
        const args = parts.slice(1);
        
        addOutput(`$ ${cmd}`, 'command');
        
        if (command === 'help') {
            addOutput('Available commands:', 'info');
            addOutput('  ls [path]       - List directory contents', 'info');
            addOutput('  cat <file>      - Read file content', 'info');
            addOutput('  mkdir <path>    - Create directory', 'info');
            addOutput('  touch <file>    - Create empty file', 'info');
            addOutput('  rm <path>       - Delete file', 'info');
            addOutput('  write <file> <content> - Write to file', 'info');
            addOutput('  tree [path]     - Show directory tree', 'info');
            addOutput('  stats           - Show filesystem statistics', 'info');
            addOutput('  pwd             - Print working directory', 'info');
            addOutput('  clear           - Clear terminal', 'info');
            addOutput('  exit            - Return to menu', 'info');
            return;
        }
        
        if (command === 'clear') {
            setTerminalOutput([]);
            return;
        }
        
        if (command === 'pwd') {
            addOutput(currentPath, 'success');
            return;
        }
        
        if (command === 'exit') {
            window.location.href = '/';
            return;
        }
        
        
        let response, data;
        const targetPath = args[0]?.startsWith('/') ? args[0] : `${currentPath}/${args[0]}`.replace(/\/+/g, '/');
        
        switch (command) {
            case 'ls':
                response = await fetch(`/filesystem/${filesystemName}/ls?path=${encodeURIComponent(args[0] || currentPath)}`);
                data = await response.json();
                break;
            case 'cat':
                response = await fetch(`/filesystem/${filesystemName}/read?path=${encodeURIComponent(targetPath)}`);
                data = await response.json();
                setSelectedFile(targetPath);
                loadRawBytes(targetPath);
                break;
            case 'mkdir':
                const mkdirForm = new FormData();
                mkdirForm.append('path', targetPath);
                response = await fetch(`/filesystem/${filesystemName}/mkdir`, {
                    method: 'POST',
                    body: mkdirForm
                });
                data = await response.json();
                loadTree();
                break;
            case 'touch':
                const touchForm = new FormData();
                touchForm.append('path', targetPath);
                response = await fetch(`/filesystem/${filesystemName}/touch`, {
                    method: 'POST',
                    body: touchForm
                });
                data = await response.json();
                loadTree();
                break;
            case 'rm':
                response = await fetch(`/filesystem/${filesystemName}/rm?path=${encodeURIComponent(targetPath)}`, {
                    method: 'DELETE'
                });
                data = await response.json();
                loadTree();
                break;
            case 'write':
                const writeForm = new FormData();
                writeForm.append('path', targetPath);
                writeForm.append('content', args.slice(1).join(' '));
                response = await fetch(`/filesystem/${filesystemName}/write`, {
                    method: 'POST',
                    body: writeForm
                });
                data = await response.json();
                loadTree();
                break;
            case 'tree':
                response = await fetch(`/filesystem/${filesystemName}/tree?path=${encodeURIComponent(args[0] || currentPath)}`);
                data = await response.json();
                loadTree(args[0] || currentPath);
                break;
            case 'stats':
                response = await fetch(`/filesystem/${filesystemName}/stats`);
                data = await response.json();
                break;
            default:
                addOutput(`Unknown command: ${command}. Type "help" for available commands.`, 'error');
                return;
        }
        
        let output;
        if (data.tree !== undefined) {
            // tree command
            output = Array.isArray(data.tree) ? data.tree.join('\n') : JSON.stringify(data.tree, null, 2);
        } else if (data.entries !== undefined) {
            // ls command
            output = data.entries.length > 0 ? data.entries.join('\n') : 'Empty directory';
        } else if (data.message) {
            // Success messages
            output = data.message;
        } else {
            // Everything else
            output = data.output || data.content || JSON.stringify(data, null, 2);
        }
        addOutput(output, 'success');
        };
    
    const handleSubmit = (e) => {
        e.preventDefault();
        if (commandInput.trim()) {
            executeCommand(commandInput);
            setCommandInput('');
        }
    };
    
    return (
        <div className="filesystem-container">
            <div className="header">
                <h1>📁 {filesystemName}</h1>
                <button className="back-btn" onClick={() => window.location.href = '/'}>
                    ← Back to Menu
                </button>
            </div>
            <div className="main-layout">
                <div className="terminal-panel">
                    <div className="panel-header">Terminal</div>
                    <div className="terminal-output">
                        {terminalOutput.map((item, idx) => (
                            <div key={idx} className={`terminal-line ${item.type}`}>
                                {item.text}
                            </div>
                        ))}
                        <div ref={terminalEndRef} />
                    </div>
                    <form onSubmit={handleSubmit} className="terminal-input-form">
                        <span className="prompt">{currentPath} $</span>
                        <input
                            type="text"
                            value={commandInput}
                            onChange={(e) => setCommandInput(e.target.value)}
                            className="terminal-input"
                            placeholder="Type a command..."
                            autoFocus
                        />
                    </form>
                </div>
                <div className="right-panel">
                    <div className="raw-bytes-panel">
                        <div className="panel-header">
                            Raw Bytes {selectedFile && <span className="file-info">- {selectedFile}</span>}
                        </div>
                        <pre className="raw-bytes-content">{rawBytes}</pre>
                    </div>
                    <div className="tree-panel">
                        <div className="panel-header">Directory Tree</div>
                        <pre className="tree-content">{treeData}</pre>
                    </div>
                </div>
            </div>
        </div>
    );
}
ReactDOM.render(<FileSystem />, document.getElementById('root'));