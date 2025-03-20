import io
import os
import pytest
from fastapi.testclient import TestClient
from uuid import UUID
import asyncio

from app.main import app
from app.models.dataroom import (
    FileCategory, 
    Folder, 
    File,
    FolderCreate
)
from app.services import dataroom_service

client = TestClient(app)

# Fixtures pour les tests
@pytest.fixture(autouse=True)
def reset_db():
    """Réinitialise la 'base de données' en mémoire avant chaque test"""
    dataroom_service.folders_db = {}
    dataroom_service.files_db = {}
    
    # Assure que le répertoire d'upload existe
    if not os.path.exists(dataroom_service.BASE_UPLOAD_DIR):
        os.makedirs(dataroom_service.BASE_UPLOAD_DIR, exist_ok=True)
    
    yield
    
    # Nettoie le répertoire d'upload après les tests
    if os.path.exists(dataroom_service.BASE_UPLOAD_DIR):
        import shutil
        shutil.rmtree(dataroom_service.BASE_UPLOAD_DIR)


# Pour les tests synchrones où nous devons appeler des fonctions asynchrones
def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# Tests pour l'API des dossiers
def test_create_folder():
    """Test de création d'un dossier via l'API"""
    response = client.post(
        "/api/dataroom/folders",
        json={"name": "Test Folder API"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Folder API"
    assert data["parent_id"] is None
    assert UUID(data["id"]) in dataroom_service.folders_db


@pytest.mark.asyncio
async def test_list_folders():
    """Test de listage des dossiers via l'API"""
    # Crée des dossiers directement dans le service
    folder1 = await dataroom_service.create_folder(FolderCreate(name="Folder 1"))
    folder2 = await dataroom_service.create_folder(FolderCreate(name="Folder 2"))
    
    # Appelle l'API
    response = client.get("/api/dataroom/folders")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    folder_names = [f["name"] for f in data]
    assert "Folder 1" in folder_names
    assert "Folder 2" in folder_names


@pytest.mark.asyncio
async def test_get_folder():
    """Test de récupération d'un dossier par son ID via l'API"""
    # Crée un dossier
    folder = await dataroom_service.create_folder(FolderCreate(name="Get Folder Test"))
    
    # Appelle l'API
    response = client.get(f"/api/dataroom/folders/{folder.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get Folder Test"
    assert data["id"] == str(folder.id)


@pytest.mark.asyncio
async def test_update_folder():
    """Test de mise à jour d'un dossier via l'API"""
    # Crée un dossier
    folder = await dataroom_service.create_folder(FolderCreate(name="Old Folder Name"))
    
    # Appelle l'API pour mettre à jour
    response = client.put(
        f"/api/dataroom/folders/{folder.id}",
        json={"name": "New Folder Name"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Folder Name"
    assert data["id"] == str(folder.id)
    assert dataroom_service.folders_db[folder.id].name == "New Folder Name"


@pytest.mark.asyncio
async def test_delete_folder():
    """Test de suppression d'un dossier via l'API"""
    # Crée un dossier
    folder = await dataroom_service.create_folder(FolderCreate(name="Folder To Delete"))
    
    # Appelle l'API pour supprimer
    response = client.delete(f"/api/dataroom/folders/{folder.id}")
    
    assert response.status_code == 204
    assert folder.id not in dataroom_service.folders_db


# Tests pour l'API des fichiers
def test_upload_file():
    """Test d'upload d'un fichier via l'API"""
    # Crée un fichier de test
    test_content = b"Contenu de test pour l'upload de fichier"
    
    # Appelle l'API pour uploader
    response = client.post(
        "/api/dataroom/files",
        files={
            "file": ("test_file.txt", io.BytesIO(test_content), "text/plain")
        },
        data={
            "name": "Test Upload File",
            "categories": [FileCategory.LEGAL.value]
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Upload File"
    assert data["size"] > 0
    assert FileCategory.LEGAL.value in [c for c in data["categories"]]
    
    # Vérifie que le fichier existe sur le disque
    file_id = UUID(data["id"])
    assert file_id in dataroom_service.files_db
    assert os.path.exists(dataroom_service.files_db[file_id].path)


@pytest.mark.asyncio
async def test_list_files():
    """Test de listage des fichiers via l'API"""
    # Crée un dossier
    folder = await dataroom_service.create_folder(FolderCreate(name="Files Folder"))
    
    # Upload des fichiers directement via le service
    for i in range(3):
        # Crée un fichier de test
        test_file_path = os.path.join(os.path.dirname(__file__), f"test_file_{i}.txt")
        with open(test_file_path, "w") as f:
            f.write(f"Contenu du fichier de test {i}")
        
        # Crée un mock UploadFile
        with open(test_file_path, "rb") as f:
            from app.models.dataroom import FileCreate
            from fastapi import UploadFile
            
            upload_file = UploadFile(
                filename=f"test_file_{i}.txt",
                file=f
            )
            
            file_data = FileCreate(
                name=f"File {i}",
                folder_id=folder.id,
                categories=[FileCategory.LEGAL]
            )
            
            await dataroom_service.upload_file(upload_file, file_data)
        
        # Nettoie le fichier de test
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
    
    # Appelle l'API pour lister les fichiers
    response = client.get(f"/api/dataroom/files?folder_id={folder.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    file_names = [f["name"] for f in data]
    for i in range(3):
        assert f"File {i}" in file_names


@pytest.mark.asyncio
async def test_update_file():
    """Test de mise à jour d'un fichier via l'API"""
    # Crée un fichier de test
    test_file_path = os.path.join(os.path.dirname(__file__), "update_test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("Contenu du fichier de test pour mise à jour")
    
    # Upload le fichier directement via le service
    with open(test_file_path, "rb") as f:
        from app.models.dataroom import FileCreate
        from fastapi import UploadFile
        
        upload_file = UploadFile(
            filename="update_test_file.txt",
            file=f
        )
        
        file_data = FileCreate(
            name="Old File Name",
            categories=[FileCategory.LEGAL]
        )
        
        file = await dataroom_service.upload_file(upload_file, file_data)
    
    # Nettoie le fichier de test
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    
    # Appelle l'API pour mettre à jour le fichier
    response = client.put(
        f"/api/dataroom/files/{file.id}",
        json={
            "name": "New File Name",
            "categories": [FileCategory.FINANCIAL.value]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New File Name"
    assert data["categories"] == [FileCategory.FINANCIAL.value]
    assert dataroom_service.files_db[file.id].name == "New File Name"
    assert dataroom_service.files_db[file.id].categories == [FileCategory.FINANCIAL]


@pytest.mark.asyncio
async def test_delete_file():
    """Test de suppression d'un fichier via l'API"""
    # Crée un fichier de test
    test_file_path = os.path.join(os.path.dirname(__file__), "delete_test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("Contenu du fichier de test pour suppression")
    
    # Upload le fichier directement via le service
    with open(test_file_path, "rb") as f:
        from app.models.dataroom import FileCreate
        from fastapi import UploadFile
        
        upload_file = UploadFile(
            filename="delete_test_file.txt",
            file=f
        )
        
        file_data = FileCreate(
            name="File To Delete",
            categories=[FileCategory.LEGAL]
        )
        
        file = await dataroom_service.upload_file(upload_file, file_data)
    
    # Nettoie le fichier de test
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    
    # Vérifie que le fichier existe
    assert file.id in dataroom_service.files_db
    assert os.path.exists(file.path)
    
    # Appelle l'API pour supprimer le fichier
    response = client.delete(f"/api/dataroom/files/{file.id}")
    
    assert response.status_code == 204
    assert file.id not in dataroom_service.files_db
    assert not os.path.exists(file.path) 