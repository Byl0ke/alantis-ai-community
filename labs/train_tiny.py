"""Train a SMALL char-level GRU from scratch, for educational purposes only.

This is a genuinely untrained neural language model at initialization,
but it cannot match large pre-trained models (and is not used by the chat UI).

Usage:
    pip install torch
    python labs/train_tiny.py labs/example_corpus.txt --steps 500
"""
import argparse
from pathlib import Path


def train(path: Path, steps: int, prompt: str):
    import torch
    from torch import nn

    text = path.read_text(encoding="utf-8")
    if len(text) < 128:
        raise SystemExit("Necesitas un corpus de al menos 128 caracteres.")
    torch.manual_seed(123)
    characters = sorted(set(text))
    to_index = {c: i for i, c in enumerate(characters)}
    sequence = torch.tensor([to_index[c] for c in text], dtype=torch.long)
    size = len(characters)

    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(size, 64)
            self.rnn = nn.GRU(64, 128, batch_first=True)
            self.output = nn.Linear(128, size)

        def forward(self, x, hidden=None):
            features = self.embedding(x)
            features, hidden = self.rnn(features, hidden)
            return self.output(features), hidden

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TinyModel().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
    batch_length = 64
    for step in range(1, steps + 1):
        indices = torch.randint(0, len(sequence) - batch_length - 1, (16,))
        x = torch.stack([sequence[i:i + batch_length] for i in indices]).to(device)
        y = torch.stack([sequence[i + 1:i + batch_length + 1] for i in indices]).to(device)
        prediction, _ = model(x)
        loss = nn.functional.cross_entropy(prediction.reshape(-1, size), y.reshape(-1))
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step % 100 == 0:
            print(f"Paso {step}/{steps} · pérdida {loss.item():.4f}")

    model.eval()
    output = prompt if prompt and all(c in to_index for c in prompt) else characters[0]
    hidden = None
    with torch.no_grad():
        for c in output[:-1]:
            _, hidden = model(torch.tensor([[to_index[c]]], device=device), hidden)
        next_char = output[-1]
        for _ in range(350):
            logits, hidden = model(torch.tensor([[to_index[next_char]]], device=device), hidden)
            probs = torch.softmax(logits[0, -1] / 0.8, dim=-1)
            next_char = characters[torch.multinomial(probs, 1).item()]
            output += next_char
    print("\n--- TEXTO GENERADO ---\n" + output)
    print("\nNota: demo educativa, no chatbot fiable.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--prompt", default="ALANTIS")
    args = parser.parse_args()
    train(args.corpus, args.steps, args.prompt)