#!/usr/bin/env python3
"""
Eve Model v1 - Model Merging Script

Usa mergekit para combinar:
1. Base model (Gemma 4 E2B)
2. LoRA SFT (Eve identity dataset)
3. LoRA ORPO (preference alignment)

Técnicas: TIES, DARE, ou Linear merge

Ciclo: #70
Data: 2026-04-14
"""

import os
import subprocess
import yaml
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

CONFIG = {
    # Modelos para merge
    "base_model": "unsloth/gemma-4-E2B-it",
    "sft_adapter": "/root/evolution/models/eve-v1-sft/lora_adapter",
    "orpo_adapter": "/root/evolution/models/eve-v1-orpo/lora_adapter",
    
    # Merge method
    "merge_method": "ties",  # ties | dare | linear | slerp
    "base_alpha": 0.3,  # Peso do modelo base (0-1)
    "sft_alpha": 0.4,   # Peso do SFT
    "orpo_alpha": 0.3,  # Peso do ORPO
    
    # DARE/TIES específicos
    "density": 0.6,  # Para DARE: fração de parâmetros mantidos
    "weight_mask": True,  # Para TIES: usar weight masking
    
    # Output
    "output_dir": "/root/evolution/models/eve-v1-merged",
    "output_name": "eve-v1-merged",
    
    # Quantização final (opcional)
    "quantize": True,
    "quantization": "q4_k_m",  # q4_k_m | q5_k_m | q8_0 | f16
}

def log_step(step: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{step}] {msg}")

def check_mergekit():
    """Verificar se mergekit está instalado"""
    try:
        result = subprocess.run(
            ["mergekit-yaml", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            log_step("CHECK", "✅ mergekit instalado")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    log_step("CHECK", "❌ mergekit não encontrado")
    log_step("CHECK", "Instale: git clone https://github.com/arcee-ai/mergekit.git")
    log_step("CHECK", "         cd mergekit && pip install -e .")
    return False

def create_merge_config(config: dict) -> str:
    """Criar arquivo de configuração YAML para mergekit"""
    
    output_path = f"/tmp/eve_merge_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    
    merge_config = {
        "models": [
            {
                "model": config["base_model"],
                "parameters": {
                    "weight": config["base_alpha"]
                }
            },
        ],
        "merge_method": config["merge_method"],
        "base_model": config["base_model"],
        "parameters": {
            "weight_mask": config.get("weight_mask", True),
        }
    }
    
    # Adicionar densidade se DARE
    if config["merge_method"] == "dare":
        merge_config["parameters"]["density"] = config["density"]
    
    # Adicionar adapters como models adicionais se existirem
    # Nota: mergekit trabalha com modelos completos, não adapters
    # Para adapters, precisamos merge primeiro os adapters com o base
    
    # Simplificação: mergekit mergeia modelos completos
    # Para LoRA adapters, precisamos aplicar ao base primeiro
    # ou usar mergekit-multi para workflow multi-estágio
    
    log_step("CONFIG", f"Criando config para método: {config['merge_method']}")
    
    with open(output_path, 'w') as f:
        yaml.dump(merge_config, f, default_flow_style=False)
    
    log_step("CONFIG", f"✅ Config salvo: {output_path}")
    return output_path

def create_lora_merge_script(config: dict) -> str:
    """
    Criar script Python para merge de LoRA adapters.
    
    Como mergekit trabalha com modelos completos, precisamos:
    1. Aplicar LoRA SFT ao base
    2. Aplicar LoRA ORPO ao resultado
    3. Merge com mergekit (se houver múltiplos modelos)
    """
    
    script_content = f'''#!/usr/bin/env python3
"""
Merge de LoRA adapters para Eve Model v1
"""

from peft import PeftModel, AutoPeftModelForCausalLM
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Config
base_model = "{config['base_model']}"
sft_adapter = "{config['sft_adapter']}"
orpo_adapter = "{config['orpo_adapter']}"
output_dir = "{config['output_dir']}"

print("Passo 1: Carregando modelo base...")
model = AutoModelForCausalLM.from_pretrained(
    base_model,
    torch_dtype=torch.float16,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained(base_model)

print("Passo 2: Aplicando LoRA SFT...")
model = PeftModel.from_pretrained(model, sft_adapter)
model = model.merge_and_unload()  # Merge LoRA ao base

print("Passo 3: Aplicando LoRA ORPO...")
# Recarregar como PEFT para aplicar segundo adapter
model = PeftModel.from_pretrained(model, orpo_adapter)
model = model.merge_and_unload()

print("Passo 4: Salvando modelo final...")
import os
os.makedirs(output_dir, exist_ok=True)
model.save_pretrained(f"{{output_dir}}/merged")
tokenizer.save_pretrained(f"{{output_dir}}/merged")

print(f"✅ Modelo salvo em: {{output_dir}}/merged")

# GGUF export opcional
try:
    from unsloth import FastLanguageModel
    print("Passo 5: Exportando para GGUF...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=f"{{output_dir}}/merged",
        max_seq_length=4096,
    )
    model.save_pretrained_gguf(
        f"{{output_dir}}/gguf",
        tokenizer,
        quantization_method="{config['quantization']}",
    )
    print(f"✅ GGUF exportado em: {{output_dir}}/gguf")
except Exception as e:
    print(f"⚠️ GGUF export falhou: {{e}}")
    print("Modelo disponível em formato safetensors")
'''
    
    script_path = "/tmp/eve_lora_merge.py"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    log_step("SCRIPT", f"✅ Script de merge criado: {script_path}")
    return script_path

def merge_with_mergekit(config: dict):
    """Executar merge com mergekit"""
    
    log_step("MERGE", "=" * 60)
    log_step("MERGE", f"Método: {config['merge_method']}")
    log_step("MERGE", "=" * 60)
    
    config_path = create_merge_config(config)
    
    # Criar diretório de saída
    os.makedirs(config["output_dir"], exist_ok=True)
    
    # Executar mergekit
    cmd = [
        "mergekit-yaml",
        config_path,
        config["output_dir"],
        "--cuda",  # Usar GPU se disponível
    ]
    
    log_step("MERGE", f"Executando: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )
    
    if result.returncode == 0:
        log_step("MERGE", "✅ Merge completo!")
        return True
    else:
        log_step("MERGE", f"❌ Erro no merge:")
        print(result.stderr)
        return False

def main():
    """Pipeline principal de merge"""
    
    print("=" * 70)
    print("  Eve Model v1 - Model Merging")
    print("=" * 70)
    print()
    
    config = CONFIG.copy()
    
    # Verificar mergekit (opcional, temos fallback)
    has_mergekit = check_mergekit()
    
    # Estratégia: LoRA merge primeiro (aplicar adapters ao base)
    # Depois mergekit se quisermos combinar com outros modelos
    
    log_step("MAIN", "Estratégia: LoRA adapters → Base model")
    log_step("MAIN", f"  Base: {config['base_model']}")
    log_step("MAIN", f"  SFT: {config['sft_adapter']}")
    log_step("MAIN", f"  ORPO: {config['orpo_adapter']}")
    
    # Verificar se adapters existem
    if not os.path.exists(config["sft_adapter"]):
        log_step("MAIN", f"❌ SFT adapter não encontrado: {config['sft_adapter']}")
        log_step("MAIN", "Execute eve_finetune_v1.py primeiro")
        return 1
    
    if not os.path.exists(config["orpo_adapter"]):
        log_step("MAIN", f"⚠️ ORPO adapter não encontrado: {config['orpo_adapter']}")
        log_step("MAIN", "Continuando apenas com SFT...")
        # Ajustar pesos
        config["sft_alpha"] = 0.7
    
    # Criar script de LoRA merge
    script_path = create_lora_merge_script(config)
    
    log_step("MAIN", f"\nPara executar o merge:")
    log_step("MAIN", f"  python {script_path}")
    
    print()
    print("=" * 70)
    print("  ⚠️  ATENÇÃO: Merge requer ~16GB VRAM livre")
    print("  Alternativa: Usar CPU (mais lento, mas funciona)")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    exit(main())
