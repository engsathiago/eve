#!/usr/bin/env python3
"""
eve_temporal_decay.py — Temporal Decay for ChromaDB Memory
Ciclo #111 — Based on SRMU (Sequential Relevance Memory Unit) paper arXiv:2604.15121

Relevance-Gated Updates for Streaming Hyperdimensional Memories:
- Combina temporal decay com relevance gating
- Filtra redundant, conflicting, stale information antes do storage
- Resultados: +12.6% memory similarity, -53.5% cumulative magnitude
"""

import chromadb
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import json
import hashlib


class TemporalDecayManager:
    """
    Gerencia decay temporal de documentos em ChromaDB.
    Baseado em SRMU: temporal decay + relevance gating.
    """
    
    def __init__(
        self,
        collection_name: str = "eve_memory",
        db_path: str = "/memory/.chroma_cacm",
        default_ttl_days: int = 30,
        relevance_threshold: float = 0.7
    ):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.default_ttl_days = default_ttl_days
        self.relevance_threshold = relevance_threshold
        
    def add_with_decay(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
        ttl_days: Optional[int] = None,
        relevance_check: bool = True
    ) -> Dict:
        """
        Adiciona documentos com TTL e relevance checking.
        
        Args:
            documents: Lista de documentos
            metadatas: Metadados opcionais
            ids: IDs opcionais (gerados se não fornecidos)
            ttl_days: Dias até expiração (usa default se None)
            relevance_check: Se True, verifica redundância antes de adicionar
        """
        if ids is None:
            ids = [self._generate_id(doc) for doc in documents]
            
        if metadatas is None:
            metadatas = [{} for _ in documents]
            
        ttl = ttl_days or self.default_ttl_days
        expiry = datetime.utcnow() + timedelta(days=ttl)
        
        # Enrich metadatas com decay info
        enriched_metadatas = []
        for i, metadata in enumerate(metadatas):
            enriched = {
                **metadata,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expiry.isoformat(),
                "ttl_days": ttl,
                "relevance_score": 1.0,  # Initial relevance
                "access_count": 0,
                "last_accessed": datetime.utcnow().isoformat()
            }
            enriched_metadatas.append(enriched)
            
        # Relevance gating: verificar se documento similar já existe
        if relevance_check:
            filtered_docs = []
            filtered_meta = []
            filtered_ids = []
            
            for doc, meta, doc_id in zip(documents, enriched_metadatas, ids):
                if not self._is_redundant(doc):
                    filtered_docs.append(doc)
                    filtered_meta.append(meta)
                    filtered_ids.append(doc_id)
                else:
                    print(f"[TemporalDecay] Redundant document skipped: {doc_id}")
                    
            documents = filtered_docs
            enriched_metadatas = filtered_meta
            ids = filtered_ids
            
        if not documents:
            return {"added": 0, "skipped": len(documents)}
            
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=enriched_metadatas,
            ids=ids
        )
        
        return {
            "added": len(documents),
            "skipped": len(metadatas) - len(documents),
            "expiry": expiry.isoformat()
        }
        
    def query_with_decay(
        self,
        query_text: str,
        n_results: int = 10,
        filter_expired: bool = True
    ) -> Dict:
        """
        Query com decay awareness — atualiza relevance scores.
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results * 2 if filter_expired else n_results
        )
        
        if not results['ids'][0]:
            return {"documents": [], "metadatas": [], "distances": []}
            
        # Filter expired e update access stats
        filtered = {"documents": [], "metadatas": [], "distances": []}
        now = datetime.utcnow()
        
        for i, (doc_id, doc, meta, dist) in enumerate(zip(
            results['ids'][0],
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            expires_at = datetime.fromisoformat(meta.get("expires_at", "2099-01-01"))
            
            if filter_expired and now > expires_at:
                # Soft delete ou marcar para cleanup
                continue
                
            # Update access stats
            meta["access_count"] = meta.get("access_count", 0) + 1
            meta["last_accessed"] = now.isoformat()
            
            # Boost relevance por acesso recente
            meta["relevance_score"] = min(
                1.0,
                meta.get("relevance_score", 0.5) + 0.1
            )
            
            filtered["documents"].append(doc)
            filtered["metadatas"].append(meta)
            filtered["distances"].append(dist)
            
            # Update in collection
            self.collection.update(
                ids=[doc_id],
                metadatas=[meta]
            )
            
            if len(filtered["documents"]) >= n_results:
                break
                
        return filtered
        
    def cleanup_expired(self, hard_delete: bool = False) -> Dict:
        """
        Remove documentos expirados.
        
        Args:
            hard_delete: Se True, deleta permanentemente. Se False, marca como expired.
        """
        all_docs = self.collection.get()
        now = datetime.utcnow()
        expired_ids = []
        expired_count = 0
        
        for doc_id, meta in zip(all_docs['ids'], all_docs['metadatas']):
            expires_at = datetime.fromisoformat(meta.get("expires_at", "2099-01-01"))
            
            if now > expires_at:
                # Check relevance antes de deletar
                relevance = meta.get("relevance_score", 0)
                access_count = meta.get("access_count", 0)
                
                # SRMU: documentos de alta relevância podem ser preservados
                if relevance > self.relevance_threshold and access_count > 5:
                    # Extend TTL para documentos valiosos
                    new_expiry = now + timedelta(days=self.default_ttl_days)
                    meta["expires_at"] = new_expiry.isoformat()
                    meta["ttl_extended"] = True
                    self.collection.update(ids=[doc_id], metadatas=[meta])
                    continue
                    
                expired_ids.append(doc_id)
                expired_count += 1
                
        if hard_delete and expired_ids:
            self.collection.delete(ids=expired_ids)
            
        return {
            "expired": expired_count,
            "preserved_by_relevance": len(expired_ids) - expired_count if expired_ids else 0,
            "hard_deleted": len(expired_ids) if hard_delete else 0
        }
        
    def _is_redundant(self, document: str) -> bool:
        """
        Verifica se documento similar já existe (relevance gating).
        """
        # Simple hash-based check
        doc_hash = hashlib.md5(document.encode()).hexdigest()[:16]
        
        # Check exact match
        existing = self.collection.get(
            where={"document_hash": doc_hash}
        )
        
        if existing['ids']:
            return True
            
        # Check semantic similarity
        similar = self.collection.query(
            query_texts=[document],
            n_results=1
        )
        
        if similar['distances'] and similar['distances'][0]:
            # Distance < 0.1 considerado similar (ajustar conforme embedding model)
            if similar['distances'][0][0] < 0.1:
                return True
                
        return False
        
    def _generate_id(self, document: str) -> str:
        """Gera ID único baseado em conteúdo + timestamp."""
        content_hash = hashlib.md5(document.encode()).hexdigest()[:12]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"eve_{timestamp}_{content_hash}"
        
    def get_stats(self) -> Dict:
        """Estatísticas da coleção."""
        all_docs = self.collection.get()
        now = datetime.utcnow()
        
        total = len(all_docs['ids'])
        expired = 0
        high_relevance = 0
        
        for meta in all_docs['metadatas']:
            expires_at = datetime.fromisoformat(meta.get("expires_at", "2099-01-01"))
            if now > expires_at:
                expired += 1
            if meta.get("relevance_score", 0) > self.relevance_threshold:
                high_relevance += 1
                
        return {
            "total_documents": total,
            "expired_documents": expired,
            "active_documents": total - expired,
            "high_relevance_documents": high_relevance,
            "collection_name": self.collection.name
        }


class RelevanceGatedMemory:
    """
    Interface high-level para memória com relevance gating.
    """
    
    def __init__(self, decay_manager: Optional[TemporalDecayManager] = None):
        self.decay = decay_manager or TemporalDecayManager()
        
    def remember(
        self,
        content: str,
        context: Optional[Dict] = None,
        ttl_days: int = 30,
        importance: float = 0.5
    ) -> str:
        """
        Armazena memória com relevance gating.
        
        Args:
            content: Conteúdo a armazenar
            context: Contexto adicional
            ttl_days: Tempo de vida
            importance: Importância (0-1), afeta TTL efetivo
        """
        # Higher importance = longer effective TTL
        effective_ttl = int(ttl_days * (1 + importance))
        
        metadata = {
            "importance": importance,
            "context": json.dumps(context) if context else "{}",
            "document_hash": hashlib.md5(content.encode()).hexdigest()[:16]
        }
        
        result = self.decay.add_with_decay(
            documents=[content],
            metadatas=[metadata],
            ttl_days=effective_ttl,
            relevance_check=True
        )
        
        return result.get("ids", [""])[0] if "ids" in result else ""
        
    def recall(
        self,
        query: str,
        n_results: int = 5,
        recency_weight: float = 0.3
    ) -> List[Dict]:
        """
        Recupera memórias com scoring combinado (relevance + recency).
        """
        results = self.decay.query_with_decay(
            query_text=query,
            n_results=n_results * 2,
            filter_expired=True
        )
        
        memories = []
        now = datetime.utcnow()
        
        for doc, meta, dist in zip(
            results.get("documents", []),
            results.get("metadatas", []),
            results.get("distances", [])
        ):
            # Calculate combined score
            relevance = meta.get("relevance_score", 0.5)
            created = datetime.fromisoformat(meta.get("created_at", now.isoformat()))
            age_days = (now - created).days
            
            # Recency score: newer = higher
            recency = max(0, 1 - (age_days / 30))
            
            # Combined score
            combined_score = (
                (1 - recency_weight) * relevance +
                recency_weight * recency -
                0.5 * dist  # Lower distance = better
            )
            
            memories.append({
                "content": doc,
                "metadata": meta,
                "relevance": relevance,
                "recency": recency,
                "distance": dist,
                "combined_score": combined_score
            })
            
        # Sort by combined score
        memories.sort(key=lambda x: x["combined_score"], reverse=True)
        
        return memories[:n_results]


if __name__ == "__main__":
    # Test
    print("=" * 60)
    print("Eve Temporal Decay Manager — Test")
    print("=" * 60)
    
    manager = TemporalDecayManager()
    
    # Test stats
    stats = manager.get_stats()
    print(f"\nCollection Stats: {stats}")
    
    # Test add
    result = manager.add_with_decay(
        documents=["Test memory for temporal decay"],
        metadatas=[{"test": True}],
        ttl_days=1  # 1 day for testing
    )
    print(f"\nAdd result: {result}")
    
    # Test query
    results = manager.query_with_decay("temporal decay memory")
    print(f"\nQuery results: {len(results.get('documents', []))} documents")
    
    # Test cleanup (soft)
    cleanup = manager.cleanup_expired(hard_delete=False)
    print(f"\nCleanup result: {cleanup}")
    
    print("\n" + "=" * 60)
    print("Test complete")
