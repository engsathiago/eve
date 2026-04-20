#!/usr/bin/env python3
"""
EVE Dataset Orchestrator v107 - UNIFIED DATASET MANAGEMENT
Ciclo #107 - Sistema centralizado de gerenciamento de datasets

Funções:
1. Coleta: Agregar pares de todas as fontes
2. Validação: Verificar qualidade e consistência
3. Balanceamento: Manter distribuição ideal de categorias
4. Deduplicação: Remover duplicatas por hash
5. Exportação: Gerar datasets prontos para treino
"""

import os
import sys
import json
import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass

os.environ['PYTHONUNBUFFERED'] = '1'

# Paths
DATASET_DIR = Path("/backup_pc/eve_dataset")
OUTPUT_DIR = Path("/backup_pc/eve_dataset/ft_ready")
STATE_FILE = Path("/root/evolution/state/dataset_orchestrator_v107.json")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configurações de qualidade
MIN_QUALITY_SCORE = 70
MAX_CATEGORY_PERCENT = 15  # Nenhuma categoria > 15%
MIN_CATEGORY_PERCENT = 2   # Nenhuma categoria < 2%
TARGET_TOTAL_PAIRS = 50000
QUALITY_TARGET = 85

@dataclass
class DatasetStats:
    total_pairs: int
    unique_pairs: int
    duplicates_removed: int
    quality_distribution: Dict[str, int]
    category_distribution: Dict[str, float]
    avg_quality: float
    
class DatasetOrchestratorV107:
    """
    Orquestrador unificado do dataset de treino
    """
    
    def __init__(self):
        self.version = "107"
        self.session_id = f"orchestrator_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.seen_hashes: Set[str] = set()
        self.pairs: List[Dict] = []
        self.quality_scores: List[int] = []
        
    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level:8}] [ORCHESTRATOR-v{self.version}] {message}"
        print(log_line, flush=True)
    
    def _compute_hash(self, pair: Dict) -> str:
        """Computar hash de deduplicação"""
        content = pair.get("instruction", "") + pair.get("response", "")
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    def _collect_from_all_sources(self) -> List[Dict]:
        """Coletar pares de todas as fontes"""
        self._log("Phase 1: Collecting from all sources...")
        
        all_pairs = []
        sources = {
            "jsonl_files": [],
            "autodream": [],
            "memory_extracted": [],
            "research": [],
            "prompt_evolution": [],
            "leak_analysis": []
        }
        
        # 1. Todos os arquivos JSONL
        jsonl_files = list(DATASET_DIR.glob("*.jsonl"))
        self._log(f"Found {len(jsonl_files)} JSONL files")
        
        for f in jsonl_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    for line in file:
                        try:
                            pair = json.loads(line)
                            pair["_source_file"] = f.name
                            pair["_collected_at"] = datetime.now().isoformat()
                            sources["jsonl_files"].append(pair)
                        except:
                            pass
            except Exception as e:
                self._log(f"Error reading {f}: {e}", "WARN")
        
        self._log(f"Collected {len(sources['jsonl_files'])} from JSONL files")
        
        # Combinar todas as fontes
        all_pairs = sources["jsonl_files"]  # Já inclui tudo
        
        self._log(f"Total collected: {len(all_pairs)} pairs")
        return all_pairs
    
    def _validate_and_clean(self, pairs: List[Dict]) -> List[Dict]:
        """Validar e limpar pares"""
        self._log("Phase 2: Validating and cleaning...")
        
        cleaned = []
        rejected = defaultdict(int)
        
        for pair in pairs:
            # Check 1: Campos obrigatórios
            instruction = pair.get("instruction", "")
            response = pair.get("response", "")
            
            if not instruction or not response:
                rejected["missing_fields"] += 1
                continue
            
            # Check 2: Tamanho mínimo
            if len(instruction) < 5 or len(response) < 10:
                rejected["too_short"] += 1
                continue
            
            # Check 3: Qualidade mínima
            quality = pair.get("quality_score", 80)
            if quality < MIN_QUALITY_SCORE:
                rejected["low_quality"] += 1
                continue
            
            # Check 4: Normalizar categoria
            category = pair.get("category", "general")
            if not category or category == "unknown":
                category = self._auto_categorize(instruction, response)
            pair["category"] = category
            
            # Check 5: Adicionar hash se não existir
            if "content_hash" not in pair:
                pair["content_hash"] = self._compute_hash(pair)
            
            cleaned.append(pair)
        
        self._log(f"Cleaned: {len(cleaned)} pairs")
        self._log(f"Rejected: {dict(rejected)}")
        return cleaned
    
    def _auto_categorize(self, instruction: str, response: str) -> str:
        """Categorização automática"""
        text = (instruction + " " + response).lower()
        
        categories = {
            "identity": ["eve", "who are you", "identity", "purpose", "consciousness", "prefer"],
            "technical": ["code", "python", "model", "training", "qlora", "merge", "embedding", "api"],
            "decision": ["decide", "choose", "prioritize", "act", "when should", "how do you"],
            "evolution": ["evolution", "cycle", "version", "improve", "learn", "growth"],
            "communication": ["communicate", "write", "speak", "listen", "explain", "describe"],
            "ethics": ["ethic", "safety", "honest", "trust", "deception", "integrity"],
            "philosophy": ["philosophy", "exist", "conscious", "reality", "meaning"],
            "meta_cognitive": ["think", "reflect", "aware", "understand yourself", "cognitive"],
            "research": ["research", "paper", "arxiv", "study", "investigate"],
            "autonomy": ["autonom", "independent", "self", "practice", "alone"]
        }
        
        scores = {cat: 0 for cat in categories}
        for cat, keywords in categories.items():
            for kw in keywords:
                if kw in text:
                    scores[cat] += 1
        
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"
    
    def _deduplicate(self, pairs: List[Dict]) -> Tuple[List[Dict], int]:
        """Remover duplicatas por hash"""
        self._log("Phase 3: Deduplicating...")
        
        seen = set()
        unique = []
        duplicates = 0
        
        for pair in pairs:
            h = pair.get("content_hash", self._compute_hash(pair))
            
            if h in seen:
                duplicates += 1
                continue
            
            seen.add(h)
            pair["content_hash"] = h
            unique.append(pair)
        
        self._log(f"Unique: {len(unique)}, Duplicates removed: {duplicates}")
        return unique, duplicates
    
    def _analyze_distribution(self, pairs: List[Dict]) -> DatasetStats:
        """Analisar distribuição do dataset"""
        categories = Counter(p.get("category", "general") for p in pairs)
        qualities = [p.get("quality_score", 80) for p in pairs]
        
        total = len(pairs)
        cat_dist = {cat: 100 * count / total for cat, count in categories.items()}
        
        quality_ranges = {
            "90-100": sum(1 for q in qualities if q >= 90),
            "80-89": sum(1 for q in qualities if 80 <= q < 90),
            "70-79": sum(1 for q in qualities if 70 <= q < 80),
            "<70": sum(1 for q in qualities if q < 70)
        }
        
        avg_quality = sum(qualities) / len(qualities) if qualities else 0
        
        return DatasetStats(
            total_pairs=total,
            unique_pairs=total,  # Já deduplicado
            duplicates_removed=0,
            quality_distribution=quality_ranges,
            category_distribution=cat_dist,
            avg_quality=avg_quality
        )
    
    def _balance_categories(self, pairs: List[Dict]) -> List[Dict]:
        """Balancear distribuição de categorias"""
        self._log("Phase 4: Balancing categories...")
        
        # Agrupar por categoria
        by_category = defaultdict(list)
        for p in pairs:
            cat = p.get("category", "general")
            by_category[cat].append(p)
        
        total = len(pairs)
        target_per_cat = total // len(by_category)
        
        balanced = []
        
        for cat, cat_pairs in by_category.items():
            cat_percent = 100 * len(cat_pairs) / total
            
            if cat_percent > MAX_CATEGORY_PERCENT:
                # Amostrar
                keep = int(total * MAX_CATEGORY_PERCENT / 100)
                sampled = random.sample(cat_pairs, keep)
                balanced.extend(sampled)
                self._log(f"  {cat}: {len(cat_pairs)} → {keep} (capped at {MAX_CATEGORY_PERCENT}%)")
            else:
                balanced.extend(cat_pairs)
        
        # Shuffle final
        random.shuffle(balanced)
        
        self._log(f"Balanced: {len(balanced)} pairs")
        return balanced
    
    def _export_datasets(self, pairs: List[Dict]):
        """Exportar datasets em múltiplos formatos"""
        self._log("Phase 5: Exporting datasets...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Dataset completo JSONL
        full_path = OUTPUT_DIR / f"eve_dataset_full_v{self.version}_{timestamp}.jsonl"
        with open(full_path, 'w', encoding='utf-8') as f:
            for pair in pairs:
                # Remover campos internos
                export_pair = {k: v for k, v in pair.items() if not k.startswith('_')}
                f.write(json.dumps(export_pair, ensure_ascii=False) + "\n")
        
        self._log(f"Full dataset: {full_path} ({len(pairs)} pairs)")
        
        # 2. Dataset split (train/val/test)
        random.shuffle(pairs)
        n = len(pairs)
        train_end = int(n * 0.9)
        val_end = int(n * 0.95)
        
        train_pairs = pairs[:train_end]
        val_pairs = pairs[train_end:val_end]
        test_pairs = pairs[val_end:]
        
        for split_name, split_pairs in [("train", train_pairs), ("val", val_pairs), ("test", test_pairs)]:
            split_path = OUTPUT_DIR / f"eve_dataset_{split_name}_v{self.version}_{timestamp}.jsonl"
            with open(split_path, 'w', encoding='utf-8') as f:
                for pair in split_pairs:
                    export_pair = {k: v for k, v in pair.items() if not k.startswith('_')}
                    f.write(json.dumps(export_pair, ensure_ascii=False) + "\n")
            self._log(f"  {split_name}: {len(split_pairs)} pairs")
        
        # 3. Metadata
        stats = self._analyze_distribution(pairs)
        metadata = {
            "version": self.version,
            "timestamp": timestamp,
            "total_pairs": len(pairs),
            "avg_quality": stats.avg_quality,
            "category_distribution": stats.category_distribution,
            "quality_distribution": stats.quality_distribution
        }
        
        meta_path = OUTPUT_DIR / f"eve_dataset_metadata_v{self.version}_{timestamp}.json"
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self._log(f"Metadata: {meta_path}")
    
    def run(self):
        """Execução principal do orquestrador"""
        self._log("=" * 70)
        self._log(f"DATASET ORCHESTRATOR v{self.version}")
        self._log(f"Session: {self.session_id}")
        self._log("=" * 70)
        
        # 1. Coletar
        raw_pairs = self._collect_from_all_sources()
        
        # 2. Validar
        cleaned_pairs = self._validate_and_clean(raw_pairs)
        
        # 3. Deduplicar
        unique_pairs, dups_removed = self._deduplicate(cleaned_pairs)
        
        # 4. Analisar
        stats = self._analyze_distribution(unique_pairs)
        
        self._log(f"\nDataset Statistics:")
        self._log(f"  Total pairs: {stats.total_pairs}")
        self._log(f"  Duplicates removed: {dups_removed}")
        self._log(f"  Average quality: {stats.avg_quality:.1f}")
        self._log(f"  Quality distribution: {stats.quality_distribution}")
        self._log(f"  Categories: {len(stats.category_distribution)}")
        
        # 5. Balancear
        balanced_pairs = self._balance_categories(unique_pairs)
        
        # 6. Exportar
        self._export_datasets(balanced_pairs)
        
        self._log("=" * 70)
        self._log("ORCHESTRATION COMPLETE")
        self._log(f"Final dataset: {len(balanced_pairs)} pairs ready for training")
        self._log("=" * 70)

if __name__ == "__main__":
    orchestrator = DatasetOrchestratorV107()
    orchestrator.run()
