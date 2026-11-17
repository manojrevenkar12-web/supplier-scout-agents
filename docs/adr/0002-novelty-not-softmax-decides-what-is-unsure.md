# 2. Novelty, not softmax confidence, says when the reader is out of its depth

## Context
Temperature scaling made the reader well calibrated on its validation split. During development, the reader without
a novelty guard read wording it had never seen with high confidence and was wrong: on the drifted world it asked the
model about ten sentences in 400 searches, and more than two in five searches failed.

## Decision
The model card stores which hashed features the reader saw in training. A sentence's novelty is the share of its
features never seen; above a threshold set at training (a quantile of validation novelty plus a margin, in config),
the reading counts as unsure whatever the softmax says. An unsure deciding sentence is read by the model twice with
different framings; a disagreement goes to a person. Agreed answers are cached across searches.

## Consequences
New wording costs model calls instead of wrong shortlists. Unfamiliar company names are novel too, so a few
percent of sentences are always asked about; the monitor's limit is set above the share the reader was released with.
One wrong cached answer would repeat on every page with that sentence, which is why it takes two agreeing readings.
