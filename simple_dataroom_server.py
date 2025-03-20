from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uuid
import os
import shutil
from enum import Enum
from pydantic import BaseModel
import uvicorn

# Création de l'application FastAPI
app = FastAPI(title="DataRoom API")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Définition des modèles
class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    OTHER = "other"

class FileCategory(str, Enum):
    LEGAL = "legal"
    FINANCIAL = "financial"
    HR = "hr"
    COMMERCIAL = "commercial"
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    OTHER = "other"

class Folder(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    created_at: str
    updated_at: str

class File(BaseModel):
    id: str
    name: str
    size: int
    file_type: str
    folder_id: Optional[str] = None
    categories: List[str] = []
    path: str
    created_at: str
    updated_at: str
    description: Optional[str] = None

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None

class FileUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[str] = None
    categories: Optional[List[str]] = None
    description: Optional[str] = None

# Simulation de base de données
folders_db = {}
files_db = {}

# Répertoire pour les fichiers
UPLOAD_DIR = "uploads/dataroom"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_file_type(filename: str) -> str:
    """Détermine le type de fichier à partir de son extension"""
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    
    if ext == 'pdf':
        return FileType.PDF
    elif ext == 'docx':
        return FileType.DOCX
    elif ext == 'xlsx':
        return FileType.XLSX
    elif ext == 'pptx':
        return FileType.PPTX
    elif ext == 'txt':
        return FileType.TXT
    else:
        return FileType.OTHER

# Routes pour les dossiers
@app.post("/folders", response_model=Folder, status_code=201)
def create_folder(folder: FolderCreate):
    """Crée un nouveau dossier"""
    folder_id = str(uuid.uuid4())
    now = str(uuid.uuid4())  # Simulé pour éviter d'importer datetime
    
    # Vérifie si le parent existe
    if folder.parent_id and folder.parent_id not in folders_db:
        raise HTTPException(status_code=404, detail="Le dossier parent n'existe pas")
    
    new_folder = {
        "id": folder_id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": now,
        "updated_at": now
    }
    
    folders_db[folder_id] = new_folder
    return new_folder

@app.get("/folders", response_model=List[Folder])
def list_folders(parent_id: Optional[str] = None):
    """Liste les dossiers, optionnellement filtrés par dossier parent"""
    if parent_id:
        return [f for f in folders_db.values() if f["parent_id"] == parent_id]
    else:
        return [f for f in folders_db.values() if f["parent_id"] is None]

@app.get("/folders/{folder_id}", response_model=Folder)
def get_folder(folder_id: str):
    """Récupère un dossier par son ID"""
    if folder_id not in folders_db:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    return folders_db[folder_id]

@app.put("/folders/{folder_id}", response_model=Folder)
def update_folder(folder_id: str, folder: FolderUpdate):
    """Met à jour un dossier existant"""
    if folder_id not in folders_db:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    existing_folder = folders_db[folder_id]
    
    if folder.name is not None:
        existing_folder["name"] = folder.name
    
    if folder.parent_id is not None:
        if folder.parent_id and folder.parent_id not in folders_db:
            raise HTTPException(status_code=404, detail="Le dossier parent n'existe pas")
        existing_folder["parent_id"] = folder.parent_id
    
    existing_folder["updated_at"] = str(uuid.uuid4())  # Simulé
    return existing_folder

@app.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str):
    """Supprime un dossier et son contenu"""
    if folder_id not in folders_db:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    # Vérifie si le dossier contient des sous-dossiers
    if any(f["parent_id"] == folder_id for f in folders_db.values()):
        raise HTTPException(
            status_code=400, 
            detail="Le dossier contient des sous-dossiers et ne peut pas être supprimé"
        )
    
    # Supprime tous les fichiers du dossier
    files_to_delete = [f_id for f_id, f in files_db.items() if f["folder_id"] == folder_id]
    for file_id in files_to_delete:
        delete_file(file_id)
    
    # Supprime le dossier
    del folders_db[folder_id]
    return None

# Routes pour les fichiers
@app.post("/files", response_model=File, status_code=201)
def upload_file(
    file: UploadFile = None,
    name: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    categories: List[str] = Form([]),
    description: Optional[str] = Form(None)
):
    """Télécharge un fichier"""
    if file is None:
        raise HTTPException(status_code=400, detail="Le fichier est requis")
        
    # Vérifie si le dossier existe
    if folder_id and folder_id not in folders_db:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")
    
    file_id = str(uuid.uuid4())
    file_name = name or file.filename
    file_type = get_file_type(file.filename)
    now = str(uuid.uuid4())  # Simulé
    
    # Crée le chemin de fichier
    file_path = os.path.join(UPLOAD_DIR, file_id)
    
    # Enregistre le fichier
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Récupère la taille du fichier
    file_size = os.path.getsize(file_path)
    
    # Crée l'enregistrement du fichier
    new_file = {
        "id": file_id,
        "name": file_name,
        "size": file_size,
        "file_type": file_type,
        "folder_id": folder_id,
        "categories": categories,
        "path": file_path,
        "created_at": now,
        "updated_at": now,
        "description": description
    }
    
    files_db[file_id] = new_file
    return new_file

@app.get("/files", response_model=List[File])
def list_files(folder_id: Optional[str] = None):
    """Liste les fichiers, optionnellement filtrés par dossier"""
    if folder_id:
        if folder_id not in folders_db:
            raise HTTPException(status_code=404, detail="Dossier non trouvé")
        return [f for f in files_db.values() if f["folder_id"] == folder_id]
    else:
        return list(files_db.values())

@app.get("/files/{file_id}", response_model=File)
def get_file(file_id: str):
    """Récupère les métadonnées d'un fichier"""
    if file_id not in files_db:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    return files_db[file_id]

@app.get("/files/{file_id}/download")
def download_file(file_id: str):
    """Télécharge un fichier"""
    if file_id not in files_db:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    file = files_db[file_id]
    return FileResponse(
        path=file["path"],
        filename=file["name"],
        media_type="application/octet-stream"
    )

@app.put("/files/{file_id}", response_model=File)
def update_file(file_id: str, file_data: FileUpdate):
    """Met à jour les métadonnées d'un fichier"""
    if file_id not in files_db:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    existing_file = files_db[file_id]
    
    if file_data.name is not None:
        existing_file["name"] = file_data.name
    
    if file_data.folder_id is not None:
        if file_data.folder_id and file_data.folder_id not in folders_db:
            raise HTTPException(status_code=404, detail="Le dossier n'existe pas")
        existing_file["folder_id"] = file_data.folder_id
    
    if file_data.categories is not None:
        existing_file["categories"] = file_data.categories
    
    if file_data.description is not None:
        existing_file["description"] = file_data.description
    
    existing_file["updated_at"] = str(uuid.uuid4())  # Simulé
    return existing_file

@app.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: str):
    """Supprime un fichier"""
    if file_id not in files_db:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    
    file = files_db[file_id]
    
    # Supprime le fichier du disque
    if os.path.exists(file["path"]):
        os.remove(file["path"])
    
    # Supprime le fichier de la base de données
    del files_db[file_id]
    return None

# Endpoint racine
@app.get("/")
def read_root():
    return {"message": "API de Dataroom virtuelle pour LegalAI M&A"}

# Point d'entrée pour le démarrage de l'application
if __name__ == "__main__":
    uvicorn.run("simple_dataroom_server:app", host="127.0.0.1", port=8081, reload=True) 