from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil

from shell import create_filesystem, open_filesystem, execute_command

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()

# Store active filesystem sessions
filesystems = {}


@app.get("/", response_class=HTMLResponse)
async def menu(request: Request):
    """List all available filesystem images"""
    files = list(UPLOAD_DIR.glob("*.img"))
    filenames = [f.name for f in files]
    return JSONResponse({
        "filesystems": filenames,
        "upload_dir": str(UPLOAD_DIR)
    })


@app.post("/create")
async def create_fs(filename: str = Form(...), size_mb: int = Form(...)):
    """Create a new filesystem"""
    file_path = UPLOAD_DIR / filename
    if not filename.endswith(".img"):
        filename = filename + ".img"
        file_path = UPLOAD_DIR / filename
    
    result = create_filesystem(str(file_path), size_mb)
    return result


@app.post("/mount/{filename}")
async def mount_fs(filename: str):
    """Mount an existing filesystem"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return {"error": "Filesystem not found"}
    
    fs = open_filesystem(str(file_path))
    filesystems[filename] = fs
    return {"status": "success", "message": f"Mounted {filename}"}


@app.post("/unmount/{filename}")
async def unmount_fs(filename: str):
    """Unmount a filesystem"""
    if filename in filesystems:
        filesystems[filename].close()
        del filesystems[filename]
        return {"status": "success", "message": f"Unmounted {filename}"}
    return {"error": "Filesystem not mounted"}


@app.get("/{filename}/ls")
async def ls(filename: str, path: str = "/"):
    """List directory contents"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "ls", [path])
    return result


@app.get("/{filename}/tree")
async def tree(filename: str, path: str = "/"):
    """Show directory tree"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "tree", [path])
    return result


@app.post("/{filename}/mkdir")
async def mkdir(filename: str, path: str = Form(...)):
    """Create a directory"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "mkdir", [path])
    return result


@app.post("/{filename}/touch")
async def touch(filename: str, path: str = Form(...)):
    """Create an empty file"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "touch", [path])
    return result


@app.post("/{filename}/write")
async def write(filename: str, path: str = Form(...), content: str = Form(...)):
    """Write content to a file"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "write", [path, content])
    return result


@app.get("/{filename}/read")
async def read(filename: str, path: str):
    """Read file content"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "read", [path])
    return result


@app.delete("/{filename}/rm")
async def rm(filename: str, path: str):
    """Delete a file"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "rm", [path])
    return result


@app.get("/{filename}/info")
async def info(filename: str, path: str):
    """Get file information"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "info", [path])
    return result


@app.get("/{filename}/stats")
async def stats(filename: str):
    """Get filesystem statistics"""
    if filename not in filesystems:
        return {"error": "Filesystem not mounted"}
    
    fs = filesystems[filename]
    result = execute_command(fs, "stats")
    return result


@app.get("/{filename}/download")
async def download_file(filename: str):
    """Download the filesystem image"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a filesystem image"""
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "filename": file.filename,
        "status": "saved successfully"
    }


@app.delete("/{filename}/delete")
async def delete_filesystem(filename: str):
    """Delete a filesystem image from disk"""
    if filename in filesystems:
        filesystems[filename].close()
        del filesystems[filename]
    
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return {"status": "success", "message": f"Deleted {filename}"}
    
    return {"error": "File not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)