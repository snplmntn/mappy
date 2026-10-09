"""Text embedders. E5Embedder runs multilingual-e5-small in-process on CPU."""

import hashlib
import re
from pathlib import Path
from typing import Literal, Protocol

import numpy as np

Kind = Literal["query", "passage"]


class Embedder(Protocol):
    model_id: str

    def embed(self, texts: list[str], kind: Kind) -> np.ndarray: ...


def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return (v / np.maximum(norms, 1e-9)).astype(np.float32)


class HashEmbedder:
    """Bag-of-words hashed into a fixed vector. Deterministic; used by tests and as an emergency fallback."""

    model_id = "hash-256"
    dim = 256

    def embed(self, texts: list[str], kind: Kind) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in re.findall(r"[\w&]+", text.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                out[i, h % self.dim] += 1.0
        return _normalize(out)


class E5Embedder:
    model_id = "multilingual-e5-small"

    def __init__(self, model_dir: Path, max_len: int = 128, threads: int = 2):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model = model_dir / "model_int8.onnx"
        if not model.exists():
            model = model_dir / "model.onnx"
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        self._session = ort.InferenceSession(str(model), opts, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tok.enable_truncation(max_len)
        self._tok.enable_padding()

    def embed(self, texts: list[str], kind: Kind) -> np.ndarray:
        enc = self._tok.encode_batch([f"{kind}: {t}" for t in texts])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feed)[0]
        summed = (hidden * mask[..., None]).sum(axis=1)
        return _normalize(summed / np.maximum(mask.sum(axis=1, keepdims=True), 1))
