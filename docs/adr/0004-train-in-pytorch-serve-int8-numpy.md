# 4. Train in PyTorch, serve an int8 NumPy runtime

## Context
The API and the workers scale with searches; a PyTorch install adds most of a gigabyte to the image and start-up
time, for a model that is an embedding lookup and two small layers.

## Decision
Training exports int8 embedding rows with a scale per row and the small float layers to `weights.npz`; the service
reads with NumPy. Every training run checks that the runtime gives the same label as PyTorch on the validation split
and records the largest probability gap; the gate requires both. A test fails if anything the service imports
imports torch, and CI checks the API image has no torch.

## Consequences
The image stays slim and the reader is about a quarter of its float size. Any change to the features must change both
paths together (they share `scout/nlp/features.py`).
