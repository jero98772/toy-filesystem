        const { useState, useEffect } = React;

function Menu() {
    const [filesystems, setFilesystems] = useState([]);
    const [selectedFS, setSelectedFS] = useState('');
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newFSName, setNewFSName] = useState('');
    const [newFSSize, setNewFSSize] = useState();

    useEffect(() => {
        loadFilesystems();
    }, []);

    const loadFilesystems = async () => {
        try {
            const response = await fetch('/list_files');
            const data = await response.json();
            setFilesystems(data.filesystems || []);
        } catch (error) {
            console.error('Error loading filesystems:', error);
        }
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        try {
            const formData = new FormData();
            formData.append('filename', newFSName);
            formData.append('size_mb', newFSSize);

            const response = await fetch('/create', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.error) {
                alert('Error: ' + result.error);
            } else {
                alert('Filesystem created successfully!');
                setShowCreateModal(false);
                setNewFSName('');
                setNewFSSize(100);
                loadFilesystems();
            }
        } catch (error) {
            alert('Error creating filesystem: ' + error.message);
        }
    };

    const handleOpen = async () => {
        if (!selectedFS) {
            alert('Please select a filesystem first');
            return;
        }

        try {
            const response = await fetch(`/mount/${selectedFS}`, {
                method: 'POST'
            });

            const result = await response.json();
            
            if (result.error) {
                alert('Error: ' + result.error);
            } else {
                window.location.href = `filesystem/${selectedFS}/info`;
            }
        } catch (error) {
            alert('Error opening filesystem: ' + error.message);
        }
    };

    const handleDelete = async (filename) => {
        if (!confirm(`Are you sure you want to delete ${filename}?`)) {
            return;
        }

        try {
            const response = await fetch(`/${filename}/delete`, {
                method: 'DELETE'
            });

            const result = await response.json();
            
            if (result.error) {
                alert('Error: ' + result.error);
            } else {
                alert('Filesystem deleted successfully!');
                loadFilesystems();
                if (selectedFS === filename) {
                    setSelectedFS('');
                }
            }
        } catch (error) {
            alert('Error deleting filesystem: ' + error.message);
        }
    };

    return (
        <div className="menu-container">
            <div className="menu-header">
                <h1>File System Manager</h1>
            </div>

            <div className="menu-content">
                <div className="filesystem-list">
                    <h2>Available File Systems</h2>
                    {filesystems.length === 0 ? (
                        <p className="empty-message">No filesystems available. Create one to get started.</p>
                    ) : (
                        <div className="fs-grid">
                            {filesystems.map(fs => (
                                <div 
                                    key={fs}
                                    className={`fs-item ${selectedFS === fs ? 'selected' : ''}`}
                                    onClick={() => setSelectedFS(fs)}
                                >
                                    <div className="fs-icon">📁</div>
                                    <div className="fs-name">{fs}</div>
                                    <button 
                                        className="delete-btn"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDelete(fs);
                                        }}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="menu-actions">
                    <button 
                        className="primary-btn create-btn"
                        onClick={() => setShowCreateModal(true)}
                    >
                        Create New Filesystem
                    </button>
                    <button 
                        className="primary-btn open-btn"
                        onClick={handleOpen}
                        disabled={!selectedFS}
                    >
                        Open Selected Filesystem
                    </button>
                </div>
            </div>

            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h2>Create New Filesystem</h2>
                        <form onSubmit={handleCreate}>
                            <div className="form-group">
                                <label htmlFor="fs-name">Filesystem Name:</label>
                                <input
                                    id="fs-name"
                                    type="text"
                                    value={newFSName}
                                    onChange={(e) => setNewFSName(e.target.value)}
                                    placeholder="myfilesystem.img"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="fs-size">Size (MB):</label>
                                <input
                                    id="fs-size"
                                    type="number"
                                    value={newFSSize}
                                    onChange={(e) => setNewFSSize(parseInt(e.target.value))}
                                    min="1"
                                    max="10000"
                                    required
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="submit" className="primary-btn">Create</button>
                                <button 
                                    type="button" 
                                    className="secondary-btn"
                                    onClick={() => setShowCreateModal(false)}
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

ReactDOM.render(<Menu />, document.getElementById('root'));
