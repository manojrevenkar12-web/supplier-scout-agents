# Held-out runs

## The first version (keyword checks)
Run once on 13 Nov 2026 at the commit in `config/archive/heldout-v1.lock`, on the world generator of that time, which
worded every fact in the phrasing the keyword checks were written for. Its numbers are in
`reports/archive/heldout-v1.json`. They are not comparable with today's worlds, where a third of the facts are worded
otherwise; the keyword design is measured on those in the README.

## The stance reader
See the README section "Held-out world (run once)" and below.
Run once at the commit in `config/heldout.lock`, with reader `v2`: 1,500 new companies, 400 RFQs, a quarter of the
facts in the drifted wording. Numbers in `reports/heldout.json` and the README table.

What it shows: the agent with the stance reader and its fallback met the 1% target, at the cost of the plan call
alone, while the keyword-checked agent failed about two searches in five on the same RFQs and paid for a model call
per page. What it does not show: that the reader generalises to wording outside the bank. The held-out wording comes
from the same templates as the traffic `v2` was harvested from, with new names, numbers and places; a perfect score
here says the design holds on fresh companies and RFQs in wording production had started to use, not on a real web.
The test for that is a sample of real supplier pages labelled by buyers, which this repository does not have.
