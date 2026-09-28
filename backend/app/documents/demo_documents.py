"""Demo documents: 100% synthetic research-style content for the Try Demo flow.

These documents were written for MedRAG-X. They contain no real patient data
and make no real-world claims about actual products or trials — they exist so
the demo exercises the actual RAG pipeline (extraction -> cleaning ->
chunking -> embedding -> retrieval -> grounded generation) end to end.
"""

from __future__ import annotations

from app.documents.loader import extract_document

# --- Synthetic document 1: sleep & cognition (markdown, section-structured) ---
SLEEP_DOC = """# Sleep Quality and Cognitive Performance in Healthy Adults: A Synthetic Review

## Abstract
This synthetic review summarizes fictional findings from three simulated cohort studies examining the relationship between sleep duration, sleep regularity, and next-day cognitive task performance in healthy adults. All data described are artificial and were generated for software demonstration purposes.

## Introduction
Sleep is a recurring behavioral state that occupies roughly one third of human life. Population surveys suggest that many adults report sleeping less than seven hours per night. In this synthetic review we model how restricted or irregular sleep might relate to attention, working memory, and decision-making performance measured the following day.

## Methods
Three simulated cohorts were modeled. Cohort A included 1,200 simulated participants aged 18 to 35 who wore simulated wrist actigraphy devices for fourteen nights. Cohort B included 850 simulated participants aged 36 to 60 with seven nights of modeled sleep diary data. Cohort C included 400 simulated shift workers with irregular schedules. Cognitive outcomes were modeled as attention lapses on a sustained attention task, working memory span scores, and a decision-making task with ambiguous gambles.

## Results
Simulated participants whose average modeled sleep duration was below six hours showed a 24 percent higher rate of attention lapses compared with participants modeled at seven to eight hours. Working memory span scores were reduced by approximately 9 percent in the short sleep group. Irregular sleep timing, defined as more than 90 minutes of variation in sleep midpoint across nights, was associated with slower decision-making even when total sleep duration was adequate. Napping for 20 to 30 minutes partially improved attention scores in the shift worker cohort, but did not restore performance to the level of participants with regular nighttime sleep.

## Discussion
In these synthetic data, both duration and regularity of sleep mattered. The modeled association between irregular timing and impaired decision-making persisted after adjusting for total sleep time, caffeine intake, and age. This mirrors the broader research literature, in which circadian misalignment is proposed as a mechanism linking irregular schedules to cognitive performance. Because the data here are entirely fictional, no clinical or public health conclusions should be drawn from this document.

## Limitations
All results are simulated. Simulated effect sizes were chosen for illustration and do not estimate real-world effects. No real participants were involved. The modeled cohorts over-represent younger adults, limiting generality even within the simulation.

## Conclusion
Within this synthetic dataset, shorter sleep duration was associated with more attention lapses and lower working memory scores, while irregular sleep timing was associated with slower decision-making. The document exists to demonstrate retrieval-augmented question answering, not to provide medical guidance.
"""

# --- Synthetic document 2: wearable heart-rate accuracy (markdown) ---
WEARABLE_DOC = """# Accuracy of Wrist-Worn Heart Rate Monitors During Exercise: A Synthetic Evaluation

## Abstract
This fictional technical report describes a simulated bench-and-field evaluation of four consumer wrist-worn heart rate monitors against a modeled reference chest strap. All numbers are artificial and intended solely for demonstrating document question answering.

## Background
Wrist-worn devices estimate heart rate using photoplethysmography, in which an optical sensor measures blood volume changes under the skin. Motion artifacts, skin tone, tattoo ink, sensor-skin contact, and temperature are commonly discussed factors that can degrade optical signal quality.

## Methods
Four simulated devices, labeled Device A through Device D, were modeled across five activities: resting, walking, treadmill running at three speeds, cycling, and high-intensity interval training. Each simulated device produced modeled readings sampled once per second. Error was summarized as mean absolute percentage error against the modeled reference strap.

## Results
At rest, all four simulated devices showed a mean absolute percentage error below 2 percent. During treadmill running, error rose with speed: Device A showed 3.1 percent at moderate pace and 5.8 percent at fast pace. During high-intensity intervals, Device C showed the largest modeled error at 11.4 percent mean absolute percentage error, while Device B remained at 6.2 percent. On the cycling modality, all devices performed similarly with errors between 4 and 6 percent, likely because wrist flexion reduced optical contact in the modeled scenarios. Darker simulated skin tones increased modeled error by up to 3 percentage points across all devices during running tasks in the simulation.

## Discussion
The simulated pattern, in which accuracy degrades during rhythmic high-intensity movement, matches concerns frequently raised in published reviews of consumer wearables. Optical contact and motion artifact are the dominant modeled error sources. Because all figures are fictional, they must not be cited as evidence about any real device or brand.

## Limitations
The evaluation is entirely simulated. Real-world validation would require human participants, institutional review approval, and calibrated reference instruments. The simulated skin tone effect was modeled as a uniform offset and does not capture real physiological variation.

## Conclusion
Within this synthetic evaluation, wrist-worn heart rate estimates were most accurate at rest and least accurate during high-intensity interval exercise, with modeled error varying substantially across simulated devices and activities.
"""

# --- Synthetic document 3: evidence reporting (markdown) ---
EVIDENCE_DOC = """# A Primer on Reading Medical Research: Study Designs and Evidence Quality

## Abstract
This educational primer, written with fully illustrative content, introduces common clinical study designs and the vocabulary used to describe the strength of medical evidence. It is intended as demo material for an evidence-retrieval system.

## Study Designs
Randomized controlled trials assign participants to intervention or control arms by chance, which balances both measured and unmeasured confounding factors. Cohort studies follow exposed and unexposed groups forward in time and can estimate associations but are more vulnerable to confounding. Case-control studies start from an outcome and look backward at exposures, which is efficient for rare outcomes but prone to recall bias. Systematic reviews collect and appraise all studies answering a defined question, and meta-analyses pool their quantitative results statistically.

## Hierarchy of Evidence
In the commonly taught pyramid, systematic reviews and meta-analyses of randomized trials sit at the top, followed by individual randomized controlled trials, then cohort studies, then case-control studies, with expert opinion and mechanistic reasoning at the base. Position in the pyramid is a heuristic about susceptibility to bias, not a guarantee of truth; a large, well-designed cohort study can be more informative than a small, poorly conducted trial.

## Common Sources of Bias
Selection bias arises when the sampled population differs systematically from the target population. Measurement bias occurs when outcome ascertainment differs between groups. Attrition bias appears when participants drop out differentially. Publication bias means studies with positive results are more likely to be published, which can distort the apparent effect size in meta-analyses. Funnel plots are a common visual tool for detecting publication bias.

## Interpreting Effect Sizes
Relative risk compares the probability of an outcome between groups. Absolute risk reduction expresses the same contrast in percentage points and is often more intuitive for decision-making. The number needed to treat is the reciprocal of absolute risk reduction and estimates how many patients must receive an intervention to prevent one additional adverse outcome. Confidence intervals that cross the null value of 1.0 indicate results not conventionally statistically significant.

## Confounding and Causality
A confounder is a factor associated with both the exposure and the outcome that distorts the observed association. The Bradford Hill viewpoints, including strength, consistency, dose-response, and biological plausibility, are commonly used to judge whether an association is plausibly causal. No single criterion is decisive.

## Conclusion
Understanding study design, bias, and effect-size vocabulary helps readers evaluate whether a research claim is supported by the methods that produced it. This primer uses illustrative content only and contains no clinical recommendations.
"""

DEMO_DOCUMENTS: dict[str, str] = {
    "Sleep-Quality-and-Cognition.md": SLEEP_DOC,
    "Wearable-Heart-Rate-Accuracy.md": WEARABLE_DOC,
    "Reading-Medical-Research-Primer.md": EVIDENCE_DOC,
}

DEMO_DOCUMENT_META: dict[str, dict[str, str]] = {
    "Sleep-Quality-and-Cognition.md": {
        "title": "Sleep Quality and Cognitive Performance (Synthetic)",
        "description": "Simulated cohort review of sleep duration, regularity, attention, and decision-making.",
    },
    "Wearable-Heart-Rate-Accuracy.md": {
        "title": "Wearable Heart-Rate Accuracy (Synthetic)",
        "description": "Simulated evaluation of wrist-worn optical heart-rate monitors during exercise.",
    },
    "Reading-Medical-Research-Primer.md": {
        "title": "Reading Medical Research (Primer)",
        "description": "Educational primer on study designs, bias, and evidence vocabulary.",
    },
}


def load_demo_document(filename: str) -> tuple[str, str, list[int | None]]:
    """Return (clean_text, filetype, line_pages) for a built-in demo document."""
    if filename not in DEMO_DOCUMENTS:
        raise KeyError(f"Unknown demo document: {filename}")
    data = DEMO_DOCUMENTS[filename].encode("utf-8")
    return extract_document(filename, data)
