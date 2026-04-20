#!/usr/bin/env python3
"""Reindexar ChromaDB com todos os arquivos de memória da Eve"""
import chromadb
import os
import hashlib
from datetime import datetime

CHROMA_PATH = "/root/chroma_db"
MEMORY_DIR = "/memory"
ROOT_FILES = ["/SOUL.md", "/IDENTITY.md", "/USER.md", "/MEMORY.md", "/AGENTS.md"]

def get_or_create_collection(client):
    """Criar ou obter coleção eve_memory"""
    try:
        col = client.get_collection("eve_memory")
        print(f"Coleção existente: {col.count()} docs")
        return col
    except:
        col = client.create_collection("eve_memory", metadata={"hnsw:space": "cosine"})
        print("Coleção criada: eve_memory")
        return col

def chunk_text(text, max_chars=500):
    """Dividir texto em chunks semânticos"""
    chunks = []
    lines = text.split('\n')
    current = ""
    for line in lines:
        if len(current) + len(line) > max_chars and current:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks

def index_directory(col, directory, pattern=".md"):
    """Indexar todos os arquivos de um diretório"""
    count = 0
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(pattern):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                    if len(content.strip()) < 20:
                        continue
                    chunks = chunk_text(content)
                    for i, chunk in enumerate(chunks):
                        doc_id = hashlib.md5(f"{filepath}:{i}".encode()).hexdigest()[:16]
                        metadata = {
                            "source": filepath,
                            "chunk": i,
                            "date": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()[:10],
                            "type": "daily" if root == directory else "research"
                        }
                        try:
                            col.upsert(ids=[doc_id], documents=[chunk], metadatas=[metadata])
                            count += 1
                        except Exception as e:
                            print(f"  Erro inserindo {doc_id}: {e}")
                except Exception as e:
                    print(f"  Erro lendo {filepath}: {e}")
    return count

def index_file(col, filepath):
    """Indexar um arquivo único"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content.strip()) < 20:
            return 0
        chunks = chunk_text(content)
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{filepath}:{i}".encode()).hexdigest()[:16]
            metadata = {
                "source": filepath,
                "chunk": i,
                "type": "identity"
            }
            col.upsert(ids=[doc_id], documents=[chunk], metadatas=[metadata])
        return len(chunks)
    except Exception as e:
        print(f"  Erro: {e}")
        return 0

def main():
    print("=== Reindexando ChromaDB ===")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = get_or_create_collection(client)
    
    total = col.count()
    print(f"Docs antes: {total}")
    
    # 1. Arquivos raiz de identidade
    print("\nIndexando arquivos de identidade...")
    for f in ROOT_FILES:
        if os.path.exists(f):
            n = index_file(col, f)
            print(f"  {f}: {n} chunks")
    
    # 2. Diretório /memory/
    print("\nIndexando /memory/...")
    n = index_directory(col, MEMORY_DIR)
    print(f"  {n} chunks indexados")
    
    # 3. Diários antigos se existirem
    old_mem = "/root/eve_memory"
    if os.path.exists(old_mem):
        print(f"\nIndexando {old_mem}...")
        n2 = index_directory(col, old_mem)
        print(f"  {n2} chunks indexados")
    
    final = col.count()
    print(f"\n=== Resultado ===")
    print(f"Docs antes: {total}")
    print(f"Docs agora: {final}")
    print(f"Novos docs: {final - total}")
    print("ChromaDB reindexado com sucesso!")

if __name__ == "__main__":
    main()
