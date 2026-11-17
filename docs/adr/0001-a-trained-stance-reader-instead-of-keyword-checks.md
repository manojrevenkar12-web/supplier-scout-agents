# 1. A trained stance reader decides, the model is asked only about sentences it is unsure of

## Context
The first agent asked the model about every candidate page and checked its claims with keyword lists (expired,
distributor, manufacturer). It met the 1% target only on the phrasing the lists were written for. Suppliers say "our
certificate lapsed", "we sold the die-casting line", "our sourcing team places orders with factories"; the lists do
not, and a model call per page made each search cost tens of cents.

## Decision
A small classifier, trained in PyTorch on labelled sentences, reads the stance of every sentence (makes or trades,
process on or off, certificate held, lapsed or someone else's). Names of processes, materials and certificates are
masked before it reads, so it learns how a sentence stands, and code decides which requirement a sentence is about
from the taxonomy. A rule in code turns stances into a verdict. A sentence that decides a requirement and that the
reader is not sure of goes to the model.

## Consequences
Qualification costs no model call for most pages, so retrieval can be exhaustive over facets. The reader needs
labelled data and a release process (ADRs 2 and 3). It can only be as good as its labels; agreed model answers are
not ground truth.
