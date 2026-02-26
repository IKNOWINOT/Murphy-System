import os
import json
from typing import Optional
from pathlib import Path

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    import torch
    _HAS_TRANSFORMERS = True
except ImportError:
    _HAS_TRANSFORMERS = False


class GPTOSSRunner:
    def __init__(self, model_path: str, max_tokens: int = 1024, device: Optional[str] = None):
        if not _HAS_TRANSFORMERS:
            raise ImportError("GPTOSSRunner requires 'transformers' and 'torch' packages")
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.pipe = None
        self._load_model()

    def _load_model(self):
        print(f"[GPT-OSS] Loading model from: {self.model_path} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_path, torch_dtype=torch.float16 if self.device == "cuda" else torch.float32)
        self.model.to(self.device)
        self.pipe = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer, device=0 if self.device == "cuda" else -1)

    def chat(self, prompt: str, temperature: float = 0.7, stop_token: Optional[str] = None) -> str:
        print(f"[GPT-OSS] Prompt sent to model:\n{prompt}\n")
        result = self.pipe(prompt, max_length=self.max_tokens, do_sample=True, temperature=temperature)
        output = result[0]['generated_text']
        if stop_token and stop_token in output:
            output = output.split(stop_token)[0]
        return output.strip()


# Simple callable version (what bots like TriageBot should use)
def call_gpt_oss_instance(bot_name: str, message: str, model_path: str = "./models/gpt-oss-20b") -> dict:
    """
    Given a bot name and message, returns the GPT response with structured subtask output.
    """
    prompt = f"""
You are {bot_name}. Your role is defined in the system configuration.
Respond ONLY if you can assist with the following task. Be concise.

Task: {message}

Format your response as:
{{
  "can_help": true/false,
  "confidence": float (0.0 - 1.0),
  "suggested_subtask": "..."
}}
"""
    runner = GPTOSSRunner(model_path=model_path)
    raw = runner.chat(prompt, stop_token="}")
    try:
        json_ready = raw + "}"
        response = json.loads(json_ready.replace("true", "true").replace("false", "false").replace("True", "true").replace("False", "false"))
        response = json.loads(json_ready.replace("\"", '"').replace("true", "true").replace("false", "false"))
        response["bot"] = bot_name
        return response
    except Exception as e:
        return {"bot": bot_name, "can_help": False, "confidence": 0.0, "error": str(e)}