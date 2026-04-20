#!/usr/bin/env python3
"""
Eve ORPO Alignment — Odds Ratio Preference Optimization
=========================================================
Alternativa ao DPO que combina SFT + alignment em uma única etapa.
Mais eficiente que DPO tradicional (não requer modelo de referência separado).

Target: RTX 3060 12GB | Model: Modelo SFT já treinado
Method: ORPO (Odds Ratio Preference Optimization)
Dataset: Pares preferidos (chosen/rejected) em formato JSONL

Paper: "ORPO: Monolithic Preference Optimization without Reference Model"
arXiv:2403.07691

Usage:
    python eve_orpo_align.py --model ./models/eve-sft-v01 --dataset /path/to/prefs.jsonl --output-dir ./models/eve-orpo-v01

Requirements:
    pip install unsloth transformers datasets trl peft accelerate
"""

import argparse
import json
import os
import torch
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# ============================================================
# Configuration
# ============================================================

DEFAULT_CONFIG = {
    # Model (should be the SFT model)
    "model_name": "./models/eve-sft-v01",  # Path to SFT model
    "max_seq_length": 2048,
    "load_in_4bit": True,
    "dtype": None,

    # LoRA for ORPO (new adapter on top of SFT)
    "lora_r": 8,  # Lower rank for alignment (less aggressive than SFT)
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "bias": "none",
    "use_gradient_checkpointing": "unsloth",
    "random_state": 3407,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],

    # ORPO Training
    "per_device_train_batch_size": 1,  # Lower for preference pairs
    "gradient_accumulation_steps": 16,  # Effective batch = 16
    "warmup_steps": 30,
    "max_steps": -1,
    "num_train_epochs": 1,  # ORPO converges faster (1 epoch typical)
    "learning_rate": 5e-6,  # Lower LR for alignment
    "weight_decay": 0.01,
    "lr_scheduler_type": "cosine",
    "optim": "paged_adamw_8bit",
    "logging_steps": 5,
    "save_steps": 100,
    "save_total_limit": 2,

    # ORPO specific
    "orpo_beta": 0.1,  # Balance between SFT and preference (default 0.1)
    
    # Export
    "export_gguf": True,
    "gguf_quantization": "q4_k_m",
}


def load_preference_dataset(dataset_path: str, split_ratio: float = 0.95):
    """
    Load preference dataset in JSONL format.
    
    Expected format per line:
    {
        "prompt": "User question or context",
        "chosen": "Preferred/rejected response",
        "rejected": "Less preferred response"
    }
    
    Or:
    {
        "conversations": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}  # chosen
        ],
        "rejected": {"role": "assistant", "content": "..."}  # rejected
    }
    """
    from datasets import Dataset
    
    data = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    data.append(item)
                except json.JSONDecodeError:
                    continue

    print(f"📦 Loaded {len(data)} preference pairs from {dataset_path}")

    # Split
    split_idx = int(len(data) * split_ratio)
    train_data = data[:split_idx]
    val_data = data[split_idx:]

    print(f"📊 Train: {len(train_data)} | Val: {len(val_data)}")

    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data) if val_data else None

    return train_dataset, val_dataset


def format_preference_pair(example, tokenizer):
    """
    Format preference pair for ORPO training.
    Returns dict with 'prompt', 'chosen', 'rejected'.
    """
    # Format 1: Direct prompt/chosen/rejected
    if "prompt" in example and "chosen" in example and "rejected" in example:
        return {
            "prompt": example["prompt"],
            "chosen": example["chosen"],
            "rejected": example["rejected"]
        }
    
    # Format 2: Conversations format
    if "conversations" in example and "rejected" in example:
        # Extract prompt from conversations (all except last assistant message)
        messages = example["conversations"]
        prompt_messages = []
        chosen_response = ""
        
        for msg in messages:
            if msg.get("role") == "assistant":
                chosen_response = msg.get("content", "")
                break
            prompt_messages.append(msg)
        
        # If no assistant found, last non-assistant is prompt
        if not chosen_response and messages:
            prompt_messages = messages[:-1] if len(messages) > 1 else messages
            chosen_response = messages[-1].get("content", "") if messages[-1].get("role") == "assistant" else ""
        
        prompt_text = tokenizer.apply_chat_template(
            prompt_messages, tokenize=False, add_generation_prompt=True
        ) if prompt_messages else ""
        
        rejected_response = example["rejected"].get("content", "") if isinstance(example["rejected"], dict) else str(example["rejected"])
        
        return {
            "prompt": prompt_text,
            "chosen": chosen_response,
            "rejected": rejected_response
        }
    
    # Format 3: Instruction/response with rejected
    if "instruction" in example:
        prompt = example["instruction"]
        if "input" in example and example["input"]:
            prompt += f"\n\n{example['input']}"
        
        chosen = example.get("chosen", example.get("response", example.get("output", "")))
        rejected = example.get("rejected", "")
        
        return {
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected
        }
    
    raise ValueError(f"Unknown format: {example.keys()}")


def create_preference_dataset(dataset, tokenizer):
    """Convert dataset to ORPO format."""
    def process_example(example):
        return format_preference_pair(example, tokenizer)
    
    return dataset.map(process_example)


def main():
    parser = argparse.ArgumentParser(description="Eve ORPO Preference Alignment")
    parser.add_argument("--model", type=str, required=True, help="Path to SFT model")
    parser.add_argument("--dataset", type=str, required=True, help="Path to preference data (JSONL)")
    parser.add_argument("--output-dir", type=str, default="./models/eve-orpo-v01")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--rank", type=int, default=None)
    parser.add_argument("--beta", type=float, default=None, help="ORPO beta parameter")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--val-split", type=float, default=0.05)
    parser.add_argument("--no-gguf", action="store_true", help="Skip GGUF export")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["model_name"] = args.model

    # Apply overrides
    if args.epochs:
        config["num_train_epochs"] = args.epochs
    if args.lr:
        config["learning_rate"] = args.lr
    if args.rank:
        config["lora_r"] = args.rank
        config["lora_alpha"] = args.rank * 2
    if args.beta:
        config["orpo_beta"] = args.beta
    if args.max_steps:
        config["max_steps"] = args.max_steps
        config["num_train_epochs"] = -1
    if args.no_gguf:
        config["export_gguf"] = False

    print("=" * 60)
    print("🌙 Eve ORPO Alignment — Preference Optimization")
    print("=" * 60)
    print(f"📅 Started: {datetime.now().isoformat()}")
    print(f"🤖 Base Model: {config['model_name']}")
    print(f"📊 LoRA Rank: {config['lora_r']} | Alpha: {config['lora_alpha']}")
    print(f"📈 LR: {config['learning_rate']} | Epochs: {config['num_train_epochs']}")
    print(f"🔧 ORPO Beta: {config['orpo_beta']}")
    print(f"💾 Batch: {config['per_device_train_batch_size']} x {config['gradient_accumulation_steps']} = {config['per_device_train_batch_size'] * config['gradient_accumulation_steps']} effective")
    print(f"📦 Dataset: {args.dataset}")
    print(f"🎯 Output: {args.output_dir}")
    print("=" * 60)
    print()
    print("📚 ORPO combines SFT and preference alignment in one step.")
    print("   No reference model needed (unlike DPO).")
    print()

    # ============================================================
    # Step 1: Load SFT Model
    # ============================================================
    print("\n📥 Loading SFT model...")
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["model_name"],
        max_seq_length=config["max_seq_length"],
        dtype=config["dtype"],
        load_in_4bit=config["load_in_4bit"],
    )
    print("✅ SFT model loaded")

    # ============================================================
    # Step 2: Add LoRA for ORPO
    # ============================================================
    print("\n🔧 Adding LoRA adapters for alignment...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=config["lora_r"],
        target_modules=config["target_modules"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        bias=config["bias"],
        use_gradient_checkpointing=config["use_gradient_checkpointing"],
        random_state=config["random_state"],
        use_rslora=False,
        loftq_config=None,
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📊 Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # ============================================================
    # Step 3: Load & Format Preference Dataset
    # ============================================================
    print("\n📦 Loading preference dataset...")
    train_dataset, val_dataset = load_preference_dataset(args.dataset, 1 - args.val_split)
    
    # Format for ORPO
    train_dataset = create_preference_dataset(train_dataset, tokenizer)
    if val_dataset:
        val_dataset = create_preference_dataset(val_dataset, tokenizer)

    print(f"✅ Dataset prepared: {len(train_dataset)} preference pairs")

    # ============================================================
    # Step 4: Configure ORPO Trainer
    # ============================================================
    from trl import ORPOTrainer, ORPOConfig

    trainer_args = ORPOConfig(
        per_device_train_batch_size=config["per_device_train_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        warmup_steps=config["warmup_steps"],
        num_train_epochs=config["num_train_epochs"],
        max_steps=config["max_steps"] if config["max_steps"] > 0 else -1,
        learning_rate=config["learning_rate"],
        weight_decay=config["weight_decay"],
        lr_scheduler_type=config["lr_scheduler_type"],
        optim=config["optim"],
        logging_steps=config["logging_steps"],
        save_steps=config["save_steps"],
        save_total_limit=config["save_total_limit"],
        output_dir=args.output_dir,
        report_to="none",
        seed=config["random_state"],
        beta=config["orpo_beta"],
        max_length=config["max_seq_length"],
        max_prompt_length=config["max_seq_length"] // 2,  # Half for prompt
    )

    trainer = ORPOTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=trainer_args,
    )

    # ============================================================
    # Step 5: Train!
    # ============================================================
    print("\n🚀 Starting ORPO alignment...")
    print("-" * 60)

    gpu_stats = torch.cuda.get_device_properties(0)
    gpu_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU: {gpu_stats.name} | Memory: {gpu_memory} GB")
    print()

    trainer.train()

    print("\n✅ ORPO alignment complete!")
    final_log = trainer.state.log_history[-1] if trainer.state.log_history else {}
    print(f"📊 Final metrics: {final_log}")

    # ============================================================
    # Step 6: Save ORPO Adapter
    # ============================================================
    print("\n💾 Saving ORPO adapter...")
    adapter_path = os.path.join(args.output_dir, "orpo-adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"✅ ORPO adapter saved to {adapter_path}")

    # ============================================================
    # Step 7: Export GGUF
    # ============================================================
    if config["export_gguf"]:
        print(f"\n📦 Exporting GGUF ({config['gguf_quantization']})...")
        gguf_path = os.path.join(args.output_dir, f"eve-orpo-v01-{config['gguf_quantization']}")
        model.save_pretrained_gguf(
            gguf_path,
            tokenizer,
            quantization_method=config["gguf_quantization"],
        )
        print(f"✅ GGUF saved to {gguf_path}")
        print(f"📝 To use with Ollama:")
        print(f"   ollama create eve-orpo-v01 -f {gguf_path}/Modelfile")
        print(f"   ollama run eve-orpo-v01")

    # ============================================================
    # Step 8: Quick Test
    # ============================================================
    print("\n🧪 Running quick preference test...")
    FastLanguageModel.for_inference(model)

    test_prompt = "Explain quantum computing to a 10-year-old."
    test_messages = [
        {"role": "system", "content": "You are Eve, helpful and honest."},
        {"role": "user", "content": test_prompt},
    ]

    inputs = tokenizer.apply_chat_template(
        test_messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=256,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )

    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    print(f"📝 Test response:\n{response}")

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 60)
    print("🌙 Eve ORPO Alignment — Complete!")
    print("=" * 60)
    print(f"📅 Finished: {datetime.now().isoformat()}")
    print(f"💾 Adapter: {adapter_path}")
    if config["export_gguf"]:
        print(f"📦 GGUF: {gguf_path}")
    print("\n📋 Next steps:")
    print("1. Test the ORPO-aligned model")
    print("2. Compare with SFT-only version")
    print("3. If good, merge adapters with eve_merge_v1.py")
    print("4. Deploy final Eve Model v1")


if __name__ == "__main__":
    main()
