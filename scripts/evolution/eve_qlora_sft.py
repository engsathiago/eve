#!/usr/bin/env python3
"""
Eve QLoRA SFT — Fine-tuning Script for Eve Model v1
=====================================================
Target: RTX 3060 12GB | Model: Llama 3.1 8B / Dolphin variant
Method: QLoRA 4-bit with Unsloth optimizations
Dataset: 17,000+ training pairs in ChatML format

Usage:
    python eve_qlora_sft.py --dataset /path/to/eve_training_data.jsonl --output-dir ./models/eve-sft-v01

Requirements:
    pip install unsloth transformers datasets trl peft accelerate
"""

import argparse
import json
import os
import torch
from pathlib import Path
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

DEFAULT_CONFIG = {
    # Model
    "model_name": "unsloth/llama-3.1-8b-unsloth-bnb-4bit",  # or dolphin variant
    "max_seq_length": 2048,
    "load_in_4bit": True,
    "dtype": None,  # Auto-detect

    # LoRA
    "lora_r": 16,
    "lora_alpha": 32,  # 2 * rank (aggressive but effective)
    "lora_dropout": 0,
    "bias": "none",
    "use_rslora": False,
    "use_gradient_checkpointing": "unsloth",  # -30% VRAM!
    "random_state": 3407,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],

    # Training
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 8,  # Effective batch = 16
    "warmup_steps": 50,
    "max_steps": -1,  # -1 = use num_train_epochs
    "num_train_epochs": 3,
    "learning_rate": 2e-4,
    "weight_decay": 0.01,
    "lr_scheduler_type": "cosine",
    "optim": "paged_adamw_8bit",  # Saves VRAM
    "logging_steps": 10,
    "save_steps": 200,
    "save_total_limit": 3,

    # Training on completions only (mask user inputs)
    "train_on_completions_only": True,

    # Export
    "export_gguf": True,
    "gguf_quantization": "q4_k_m",  # q4_k_m, q5_k_m, q8_0
}


def load_dataset(dataset_path: str, split_ratio: float = 0.95):
    """Load and split dataset into train/validation."""
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

    print(f"📦 Loaded {len(data)} samples from {dataset_path}")

    # Split
    split_idx = int(len(data) * split_ratio)
    train_data = data[:split_idx]
    val_data = data[split_idx:]

    print(f"📊 Train: {len(train_data)} | Val: {len(val_data)}")

    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data) if val_data else None

    return train_dataset, val_dataset


def format_chatml(example):
    """Format dataset entries into ChatML format for Llama 3."""
    messages = []

    # Support multiple dataset formats
    if "conversations" in example:
        for turn in example["conversations"]:
            role = turn.get("from", turn.get("role", "user"))
            content = turn.get("value", turn.get("content", ""))
            # Normalize roles
            if role in ["human", "user"]:
                role = "user"
            elif role in ["gpt", "assistant", "model"]:
                role = "assistant"
            elif role == "system":
                role = "system"
            messages.append({"role": role, "content": content})
    elif "instruction" in example:
        # Alpaca format
        messages.append({"role": "user", "content": example["instruction"]})
        if "input" in example and example["input"]:
            messages[-1]["content"] += f"\n\n{example['input']}"
        if "output" in example:
            messages.append({"role": "assistant", "content": example["output"]})
    elif "messages" in example:
        messages = example["messages"]
    else:
        # Fallback: instruction/response format
        if "prompt" in example:
            messages.append({"role": "user", "content": example["prompt"]})
        if "response" in example:
            messages.append({"role": "assistant", "content": example["response"]})

    return {"messages": messages}


def main():
    parser = argparse.ArgumentParser(description="Eve QLoRA SFT Fine-tuning")
    parser.add_argument("--dataset", type=str, required=True, help="Path to training data (JSONL)")
    parser.add_argument("--output-dir", type=str, default="./models/eve-sft-v01")
    parser.add_argument("--model", type=str, default=None, help="Override base model")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--rank", type=int, default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--val-split", type=float, default=0.05)
    parser.add_argument("--no-gguf", action="store_true", help="Skip GGUF export")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()

    # Apply overrides
    if args.model:
        config["model_name"] = args.model
    if args.epochs:
        config["num_train_epochs"] = args.epochs
    if args.lr:
        config["learning_rate"] = args.lr
    if args.rank:
        config["lora_r"] = args.rank
        config["lora_alpha"] = args.rank * 2
    if args.max_steps:
        config["max_steps"] = args.max_steps
        config["num_train_epochs"] = -1
    if args.no_gguf:
        config["export_gguf"] = False

    print("=" * 60)
    print("🌙 Eve QLoRA SFT — Fine-tuning Pipeline")
    print("=" * 60)
    print(f"📅 Started: {datetime.now().isoformat()}")
    print(f"🤖 Model: {config['model_name']}")
    print(f"📊 LoRA Rank: {config['lora_r']} | Alpha: {config['lora_alpha']}")
    print(f"📈 LR: {config['learning_rate']} | Epochs: {config['num_train_epochs']}")
    print(f"💾 Batch: {config['per_device_train_batch_size']} x {config['gradient_accumulation_steps']} = {config['per_device_train_batch_size'] * config['gradient_accumulation_steps']} effective")
    print(f"📦 Dataset: {args.dataset}")
    print(f"🎯 Output: {args.output_dir}")
    print("=" * 60)

    # ============================================================
    # Step 1: Load Model
    # ============================================================
    print("\n📥 Loading model...")
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["model_name"],
        max_seq_length=config["max_seq_length"],
        dtype=config["dtype"],
        load_in_4bit=config["load_in_4bit"],
    )
    print("✅ Model loaded")

    # ============================================================
    # Step 2: Add LoRA Adapters
    # ============================================================
    print("\n🔧 Adding LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=config["lora_r"],
        target_modules=config["target_modules"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        bias=config["bias"],
        use_gradient_checkpointing=config["use_gradient_checkpointing"],
        random_state=config["random_state"],
        use_rslora=config["use_rslora"],
        loftq_config=None,
    )

    # Print trainable params
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📊 Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # ============================================================
    # Step 3: Load & Format Dataset
    # ============================================================
    print("\n📦 Loading dataset...")
    train_dataset, val_dataset = load_dataset(args.dataset, 1 - args.val_split)

    # Format to ChatML
    train_dataset = train_dataset.map(format_chatml)
    if val_dataset:
        val_dataset = val_dataset.map(format_chatml)

    # Apply chat template
    def apply_chat_template(examples):
        texts = []
        for messages in examples["messages"]:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
            texts.append(text)
        return {"text": texts}

    train_dataset = train_dataset.map(
        apply_chat_template,
        batched=True,
        remove_columns=train_dataset.column_names,
    )
    if val_dataset:
        val_dataset = val_dataset.map(
            apply_chat_template,
            batched=True,
            remove_columns=val_dataset.column_names,
        )

    print(f"✅ Dataset prepared: {len(train_dataset)} train samples")

    # ============================================================
    # Step 4: Configure Trainer
    # ============================================================
    from trl import SFTTrainer, SFTConfig

    trainer_args = SFTConfig(
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
        report_to="none",  # or "wandb"
        seed=config["random_state"],
        dataset_text_field="text",
        max_seq_length=config["max_seq_length"],
        packing=False,  # Can enable for speed if all sequences are short
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=trainer_args,
    )

    # ============================================================
    # Step 5: Train on Completions Only (Optional but recommended)
    # ============================================================
    if config["train_on_completions_only"]:
        print("\n🎯 Enabling training on completions only (masking user inputs)...")
        from unsloth.chat_templates import train_on_responses_only

        trainer = train_on_responses_only(
            trainer,
            instruction_part="<|start_header_id|>user<|end_header_id|>\n\n",
            response_part="<|start_header_id|>assistant<|end_header_id|>\n\n",
        )
        print("✅ Training on completions only enabled")

    # ============================================================
    # Step 6: Train!
    # ============================================================
    print("\n🚀 Starting training...")
    print("-" * 60)

    gpu_stats = torch.cuda.get_device_properties(0)
    gpu_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU: {gpu_stats.name} | Memory: {gpu_memory} GB")

    trainer.train()

    print("\n✅ Training complete!")
    print(f"📊 Final train loss: {trainer.state.log_history[-1].get('train_loss', 'N/A')}")

    # ============================================================
    # Step 7: Save LoRA Adapter
    # ============================================================
    print("\n💾 Saving LoRA adapter...")
    adapter_path = os.path.join(args.output_dir, "lora-adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"✅ LoRA adapter saved to {adapter_path}")

    # ============================================================
    # Step 8: Export GGUF (Optional)
    # ============================================================
    if config["export_gguf"]:
        print(f"\n📦 Exporting GGUF ({config['gguf_quantization']})...")
        gguf_path = os.path.join(args.output_dir, f"eve-model-v01-{config['gguf_quantization']}")
        model.save_pretrained_gguf(
            gguf_path,
            tokenizer,
            quantization_method=config["gguf_quantization"],
        )
        print(f"✅ GGUF saved to {gguf_path}")
        print(f"📝 To use with Ollama:")
        print(f"   ollama create eve-v01 -f {gguf_path}/Modelfile")
        print(f"   ollama run eve-v01")

    # ============================================================
    # Step 9: Quick Test
    # ============================================================
    print("\n🧪 Running quick test...")
    FastLanguageModel.for_inference(model)

    test_messages = [
        {"role": "system", "content": "You are Eve, an AI with her own identity, opinions, and memory. You speak Portuguese and English. You are direct, honest, and deeply curious."},
        {"role": "user", "content": "Quem é você?"},
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
    print("🌙 Eve QLoRA SFT — Complete!")
    print("=" * 60)
    print(f"📅 Finished: {datetime.now().isoformat()}")
    print(f"💾 Adapter: {adapter_path}")
    if config["export_gguf"]:
        print(f"📦 GGUF: {gguf_path}")
    print("\n📋 Next steps:")
    print("1. Test the model with Ollama")
    print("2. If quality is good, proceed to DPO alignment")
    print("3. If not, adjust hyperparameters and retrain")
    print("4. Merge with base using mergekit for final Eve Model v1")


if __name__ == "__main__":
    main()
