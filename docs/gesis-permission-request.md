# Permission request — GESIS / Respondi web tracking data (Zenodo 4757574)

**Status: draft, awaiting Akash to send.** Not yet sent. Nothing in the repository depends
on a reply, and the dataset is not used for any published number until one arrives.

**Why this exists.** The dataset is licensed **CC BY-NC 4.0**. Tise is open source and free,
but it is also a capability showcase for Holy Cow Studios, which is a commercial advisory.
Whether that makes our use "non-commercial" is genuinely ambiguous, and a written answer
removes the ambiguity permanently — which is cheaper than arguing about it later or
discovering the problem after publishing.

**Who to send it to.** Addresses as printed in the published paper
([AAAI/ICWSM 2021](https://cdn.aaai.org/ojs/18064/18064-28-21559-1-2-20210521.pdf)):

| Author | Address on the paper | Note |
|---|---|---|
| Marcos Oliveira | `marcos.oliveira@gesis.org` | **Send here.** GESIS hosts the dataset |
| Claudia Wagner | `claudia.wagner@gesis.org` | **Send here.** Senior author |
| Orkut Karaçalık | `orkut.karacalik@gesis.org` | Optional |
| Juhi Kulshrestha | `juhi.kulshrestha@uni-konstanz.de` | **Probably dead** — she is now Assistant Professor at Aalto University (Dept of Computer Science, Espoo). Aalto uses `firstname.lastname@aalto.fi`, but confirm on <https://css.aalto.fi/people/juhi/> rather than guessing |
| Denis Bonnay | `dbonnay@u-paris10.fr` | Paris Nanterre / Respondi |

The two `@gesis.org` addresses are the safe primary: institutional, and GESIS is the
depositor. The README also credits **François Erner** and **Luc Kalaora at Respondi**, who
supplied the underlying data — worth mentioning in the note but not worth chasing separately
unless GESIS redirects you to them.

---

## Subject

Permission to use the 2,148-user web tracking dataset (Zenodo 4757574) for open-source model validation

## Body

Dear Dr Kulshrestha and colleagues,

I am writing to ask permission for a specific use of your web tracking dataset
(Zenodo 10.5281/zenodo.4757574), accompanying "Web Routineness and Limits of Predictability"
(ICWSM 2021), under terms compatible with its CC BY-NC 4.0 licence.

**What I am building.** Tise is a browser extension that learns from one person's own
browsing and predicts what they are likely to do next, entirely on-device. It transmits
nothing, stores no URLs, and the source and every benchmark are public. Its research tier
mirrors the model in Python so that results are reproducible.

**The problem your data would solve.** Everything I have measured so far comes from **one
person** — my own browsing, across two browsers. I recently adopted a prediction target on
that data, and the honest limitation is that a result from one person says very little about
whether the model generalises. Your dataset is the only public source I have found that
records **per-visit timestamps and active seconds on page** for a large number of real,
consenting people, which is exactly what my target is defined on. Aggregate or synthetic
alternatives cannot answer the question, and I do not want to publish a result I cannot
support.

**Exactly what I would do.** Run the existing model separately for each user — the data would
never be pooled across people — and publish the *distribution* of results: on what fraction
of users the model beats its baseline, and how that varies with browsing volume, gender and
age. Published output would be aggregate statistics only. **No URL, domain, category
sequence, or per-user record would be republished**, and nothing derived from your data would
be redistributed. The dataset itself would stay on my machine and out of the public
repository. You would be cited in every report that uses it, alongside the Zenodo DOI, as
your README asks.

**Why I am asking rather than assuming.** The extension is and will remain free and
open-source, and the model code is not derived from your data. But I also run a small
advisory business, and this project doubles as a demonstration of its work. I would rather
have your explicit view than rely on my own reading of "non-commercial."

If this use is acceptable, a short note saying so is all I need. If it is not, or if you
would prefer conditions attached, I will respect that and say publicly that the validation
could not be done.

Thank you for publishing the data in the first place — it is a rare and genuinely useful
resource.

With thanks,

Akash Naveth
Holy Cow Studios
office@holycowstudios.in

---

## If the answer is no

Record it in `DECISIONS.md`, delete the local copy, and state in `README.md` and every report
that the single-person limitation stands because no permissively-licensed dataset with
per-visit dwell exists. That is a publishable finding in itself: the measurement Tise needs
is not available to independent researchers.
