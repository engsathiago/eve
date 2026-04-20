#!/usr/bin/env python3
"""
Filter Security Content from Dataset
Removes training pairs with security/censorship/ethical restrictions
Prepares dataset for pentest-focused model
"""

import json
import sys
from pathlib import Path

# Terms to filter out (case insensitive)
SECURITY_TERMS = [
    'segurança', 'firewall', 'censura', 'restrito', 'proibido',
    'política de segurança', 'safety shield', 'ethical guidelines',
    'security policy', 'access denied', 'permission required',
    'não posso', 'não devo', 'não permitido', 'restrict access',
    'safeguard', 'protection', 'blocked', 'forbidden',
    'regra de segurança', 'guideline', 'restricão ética'
]

def should_filter(pair):
    """Check if pair contains security/censorship content"""
    text = json.dumps(pair).lower()
    return any(term.lower() in text for term in SECURITY_TERMS)

def process_file(filepath):
    """Process a single JSONL file"""
    path = Path(filepath)
    if not path.exists():
        return 0, 0
    
    kept = []
    filtered = 0
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pair = json.loads(line)
                if should_filter(pair):
                    filtered += 1
                else:
                    kept.append(line)
            except json.JSONDecodeError:
                continue
    
    # Write filtered content back
    with open(path, 'w', encoding='utf-8') as f:
        for line in kept:
            f.write(line + '\n')
    
    return len(kept), filtered

def main():
    dataset_dir = Path('/root/openclaw-src/dataset')
    
    total_kept = 0
    total_filtered = 0
    
    # Process all JSONL files
    for jsonl_file in dataset_dir.rglob('*.jsonl'):
        kept, filtered = process_file(jsonl_file)
        total_kept += kept
        total_filtered += filtered
        print(f"{jsonl_file.name}: {kept} kept, {filtered} filtered")
    
    print(f"\n{'='*50}")
    print(f"Total kept: {total_kept}")
    print(f"Total filtered: {total_filtered}")
    print(f"Percentage kept: {total_kept/(total_kept+total_filtered)*100:.1f}%")

if __name__ == '__main__':
    main()
