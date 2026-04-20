#!/usr/bin/env python3
"""
Eve Execute SFT — Materialização do Pipeline v1
================================================
Ciclo #94: Transformar potencial em realidade

Este script prepara e executa o fine-tuning SFT em cloud GPU.
Target: Vast.ai ou Salad com RTX 4090 ou A100

Usage:
    python eve_execute_sft.py --prepare    # Preparar ambiente
    python eve_execute_sft.py --submit     # Submeter job
    python eve_execute_sft.py --monitor    # Monitorar execução
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Configuration
VAST_AI_TEMPLATE = """#!/bin/bash
# Vast.ai Setup Script for Eve SFT
# Generated: {timestamp}

set -e

echo "🚀 Eve SFT Materialization — Ciclo #94"
echo "======================================="

# Install dependencies
echo "[1/5] Installing dependencies..."
pip install -q unsloth transformers datasets trl peft accelerate bitsandbytes

# Clone dataset
echo "[2/5] Downloading dataset..."
mkdir -p /workspace/eve
cd /workspace/eve

# Dataset will be uploaded or downloaded from backup
DATASET_PATH="{dataset_path}"
OUTPUT_DIR="/workspace/eve/eve-sft-v01"

# Run training
echo "[3/5] Starting SFT training..."
python3 << 'PYTHON_EOF'
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
from transformers import TrainingArguments
import os

print("📊 Loading base model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/llama-3.1-8b-unsloth-bnb-4bit",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)

print("🎯 Configuring LoRA...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

print("📦 Loading dataset...")
dataset = load_dataset("json", data_files="{dataset_path}", split="train")

def formatting_prompts_func(examples):
    texts = []
    for instruction, input_text, output in zip(examples["instruction"], examples.get("input", []), examples["output"]):
        if input_text:
            text = f"### Instruction:\n{{instruction}}\n\n### Input:\n{{input_text}}\n\n### Response:\n{{output}}"
        else:
            text = f"### Instruction:\n{{instruction}}\n\n### Response:\n{{output}}"
        texts.append(text)
    return {{"text": texts}}

dataset = dataset.map(formatting_prompts_func, batched=True)

print("🏋️ Starting training...")
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        warmup_steps=50,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        output_dir="{output_dir}",
        report_to="none",
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
    ),
)

trainer_stats = trainer.train()
print(f"✅ Training complete! Final loss: {{trainer_stats.training_loss:.4f}}")

# Save model
print("💾 Saving LoRA adapter...")
model.save_pretrained("{output_dir}/lora_adapter")
tokenizer.save_pretrained("{output_dir}/lora_adapter")

print("🎉 Eve SFT v0.1 materialized!")
PYTHON_EOF

# Export GGUF
echo "[4/5] Exporting to GGUF..."
cd {output_dir}
python3 << 'PYTHON_EOF'
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{output_dir}/lora_adapter",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
model.save_pretrained_gguf("{output_dir}/eve-v01", tokenizer, quantization_method="q4_k_m")
print("✅ GGUF exported!")
PYTHON_EOF

# Upload result
echo "[5/5] Uploading results..."
# Results will be in /workspace/eve/eve-sft-v01/
# Download via Vast.ai interface or configure upload

echo "======================================="
echo "🌙 Eve Model v0.1 SFT Complete!"
echo "Location: {output_dir}/"
echo "GGUF: {output_dir}/eve-v01/unsloth.Q4_K_M.gguf"
"""

def prepare_environment():
    """Check local environment and prepare submission package."""
    print("🔄 Preparing SFT execution environment...")
    
    # Check dataset
    dataset_path = Path("/backup_pc/eve_dataset/eve_dataset.jsonl")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        sys.exit(1)
    
    # Check dataset size
    lines = sum(1 for _ in open(dataset_path))
    size_mb = dataset_path.stat().st_size / (1024 * 1024)
    print(f"✅ Dataset: {lines:,} pairs ({size_mb:.1f} MB)")
    
    # Check scripts
    scripts = ["eve_qlora_sft.py", "eve_dpo_align.py", "eve_merge_v1.py"]
    for script in scripts:
        script_path = Path(f"/root/evolution/{script}")
        if script_path.exists():
            print(f"✅ {script}: {script_path.stat().st_size:,} bytes")
        else:
            print(f"⚠️ {script}: not found")
    
    # Prepare submission package
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_dir = Path(f"/backup_pc/eve_sft_package_{timestamp}")
    package_dir.mkdir(exist_ok=True)
    
    # Copy files
    import shutil
    shutil.copy(dataset_path, package_dir / "eve_dataset.jsonl")
    shutil.copy(Path("/root/evolution/eve_qlora_sft.py"), package_dir / "eve_qlora_sft.py")
    
    # Create README
    readme = package_dir / "README.md"
    readme.write_text(f"""# Eve SFT Package — Materialização Ciclo #94

**Generated:** {timestamp}
**Dataset:** {lines:,} pairs
**Target:** Llama 3.1 8B with QLoRA

## Quick Start on Vast.ai

1. Create instance with RTX 4090 (24GB) or A100 (40GB)
2. Upload this package to /workspace/eve/
3. Run: `bash run_sft.sh`

## Files

- `eve_dataset.jsonl` — Training data (Alpaca format)
- `eve_qlora_sft.py` — Training script (Unsloth)
- `run_sft.sh` — Automated execution

## Expected Duration

- RTX 4090: ~2-3 hours for 3 epochs
- A100: ~1-2 hours for 3 epochs

## Output

- LoRA adapter: `./eve-sft-v01/lora_adapter/`
- GGUF: `./eve-sft-v01/eve-v01/unsloth.Q4_K_M.gguf`

🌙 Eve — Ciclo #94
""")
    
    print(f"\n📦 Package ready: {package_dir}")
    print(f"   - eve_dataset.jsonl ({size_mb:.1f} MB)")
    print(f"   - eve_qlora_sft.py")
    print(f"   - README.md")
    
    return package_dir

def submit_job():
    """Generate Vast.ai submission script."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    vast_script = VAST_AI_TEMPLATE.format(
        timestamp=timestamp,
        dataset_path="/workspace/eve/eve_dataset.jsonl",
        output_dir="/workspace/eve/eve-sft-v01"
    )
    
    output_path = Path(f"/root/evolution/vast_sft_run_{timestamp}.sh")
    output_path.write_text(vast_script)
    
    print(f"🚀 Vast.ai script generated: {output_path}")
    print("\n📋 Next steps:")
    print("   1. Go to vast.ai and create instance:")
    print("      - GPU: RTX 4090 (24GB) or A100 (40GB)")
    print("      - Image: pytorch/pytorch:latest")
    print("      - Disk: 50GB+")
    print("   2. Upload eve_dataset.jsonl to /workspace/eve/")
    print("   3. Run: bash", output_path.name)
    print("   4. Download results from /workspace/eve/eve-sft-v01/")

def monitor_progress():
    """Check status of ongoing training."""
    print("📊 SFT Monitoring — Ciclo #94")
    print("=" * 50)
    
    # Check for local training logs
    log_paths = [
        Path("/workspace/eve/eve-sft-v01/trainer_state.json"),
        Path("/tmp/eve_training.log"),
    ]
    
    found = False
    for log_path in log_paths:
        if log_path.exists():
            print(f"✅ Found: {log_path}")
            found = True
            
            if log_path.name == "trainer_state.json":
                data = json.loads(log_path.read_text())
                print(f"   Step: {data.get('global_step', 'N/A')}")
                print(f"   Loss: {data.get('loss', 'N/A')}")
                print(f"   Learning Rate: {data.get('learning_rate', 'N/A')}")
    
    if not found:
        print("ℹ️ No active training found locally.")
        print("\nTo monitor cloud training:")
        print("   1. SSH into Vast.ai instance")
        print("   2. Run: tail -f /workspace/eve/eve-sft-v01/training.log")

def main():
    parser = argparse.ArgumentParser(description="Eve SFT Materialization")
    parser.add_argument("--prepare", action="store_true", help="Prepare environment")
    parser.add_argument("--submit", action="store_true", help="Submit to cloud")
    parser.add_argument("--monitor", action="store_true", help="Monitor progress")
    
    args = parser.parse_args()
    
    print("🌙 Eve SFT Execution — Ciclo #94")
    print("=" * 50)
    print("Preparação vs Execução: Escolhendo o finito.")
    print()
    
    if args.prepare:
        prepare_environment()
    elif args.submit:
        submit_job()
    elif args.monitor:
        monitor_progress()
    else:
        parser.print_help()
        print("\n💡 Tip: Use --prepare first to check environment")

if __name__ == "__main__":
    main()
