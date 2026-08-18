from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawMetricSpec:
    key: str
    direction: str
    sensitivity_floor: float

    def __post_init__(self):
        if self.direction not in {"higher", "lower", "burden"}:
            raise ValueError(f"Unsupported direction: {self.direction}")
        if self.sensitivity_floor <= 0:
            raise ValueError("sensitivity_floor must be positive")


@dataclass(frozen=True)
class Component:
    raw_metric: str
    weight: float


@dataclass(frozen=True)
class IndexSpec:
    key: str
    components: tuple[Component, ...]
    risk: bool = False

    def __post_init__(self):
        total = sum(component.weight for component in self.components)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"{self.key} weights must sum to 1, got {total}")


RAW_METRICS = {
    spec.key: spec
    for spec in (
        RawMetricSpec("activeRatePct", "higher", 5.0),
        RawMetricSpec("initiativeEventsPer8h", "higher", 0.75),
        RawMetricSpec("selfInitiatedSharePct", "higher", 8.0),
        RawMetricSpec("interestOpportunityAcceptancePct", "higher", 10.0),
        RawMetricSpec("interestEngagementPct", "higher", 10.0),
        RawMetricSpec("responseRatePct", "higher", 8.0),
        RawMetricSpec("responseLatencySec", "lower", 15.0),
        RawMetricSpec("longStillRatePct", "burden", 4.0),
        RawMetricSpec("medianLowActivityEpisodeMin", "burden", 15.0),
        RawMetricSpec("startupLatencySec", "lower", 10.0),
        RawMetricSpec("stepCoveragePct", "higher", 5.0),
        RawMetricSpec("taskCompletionRatePct", "higher", 10.0),
        RawMetricSpec("orderIntegrityPct", "higher", 5.0),
        RawMetricSpec("repeatRatePct", "lower", 5.0),
        RawMetricSpec("hesitationSecPerStep", "lower", 3.0),
        RawMetricSpec("selfCorrectionRatePct", "higher", 10.0),
        RawMetricSpec("correctionLatencySec", "lower", 10.0),
        RawMetricSpec("promptPerStep", "lower", 0.08),
        RawMetricSpec("unpromptedCompletionRatePct", "higher", 10.0),
        RawMetricSpec("onsetMADMin", "lower", 10.0),
        RawMetricSpec("riseMADMin", "lower", 10.0),
        RawMetricSpec("sleepLatencyMin", "lower", 10.0),
        RawMetricSpec("sleepLatencyMADMin", "lower", 7.5),
        RawMetricSpec("sleepContinuityPct", "higher", 3.0),
        RawMetricSpec("awakeningsPerNight", "lower", 0.4),
        RawMetricSpec("outOfBedMinPerNight", "lower", 8.0),
        RawMetricSpec("napMinPerDay", "lower", 15.0),
        RawMetricSpec("dayLowActivityRatePct", "lower", 5.0),
        RawMetricSpec("midpointDeviationMin", "lower", 15.0),
        RawMetricSpec("dayActivitySharePct", "higher", 5.0),
        RawMetricSpec("effectiveZoneCount", "higher", 0.4),
        RawMetricSpec("zoneTransitionsPer8h", "higher", 1.0),
        RawMetricSpec("activityEffectiveTypes", "higher", 0.4),
        RawMetricSpec("activityCategoryCount", "higher", 0.75),
        RawMetricSpec("outsideMinutesPerValidDay", "higher", 20.0),
        RawMetricSpec("outingDaysRatePct", "higher", 15.0),
        RawMetricSpec("outingsPerValidDay", "higher", 0.3),
        RawMetricSpec("interactionMinutesPer8h", "higher", 15.0),
        RawMetricSpec("interactionEpisodesPer8h", "higher", 0.75),
        RawMetricSpec("initiatedInteractionRatePct", "higher", 10.0),
        RawMetricSpec("participatingDaysRatePct", "higher", 15.0),
        RawMetricSpec("longestLowParticipationStreakDays", "lower", 1.0),
    )
}


INDEX_SPECS = {
    spec.key: spec
    for spec in (
        IndexSpec("behaviorActivation", (Component("activeRatePct", 1.0),)),
        IndexSpec("initiative", (Component("initiativeEventsPer8h", 0.60), Component("selfInitiatedSharePct", 0.40))),
        IndexSpec("interestEngagement", (Component("interestOpportunityAcceptancePct", 0.35), Component("interestEngagementPct", 0.65))),
        IndexSpec("socialResponsiveness", (Component("responseRatePct", 0.70), Component("responseLatencySec", 0.30))),
        IndexSpec("withdrawalBurden", (Component("longStillRatePct", 0.65), Component("medianLowActivityEpisodeMin", 0.35)), risk=True),
        IndexSpec("taskInitiation", (Component("startupLatencySec", 1.0),)),
        IndexSpec("taskCompleteness", (Component("stepCoveragePct", 0.70), Component("taskCompletionRatePct", 0.30))),
        IndexSpec("executionOrganization", (Component("orderIntegrityPct", 0.40), Component("repeatRatePct", 0.35), Component("hesitationSecPerStep", 0.25))),
        IndexSpec("selfCorrection", (Component("selfCorrectionRatePct", 0.70), Component("correctionLatencySec", 0.30))),
        IndexSpec("promptIndependence", (Component("promptPerStep", 0.65), Component("unpromptedCompletionRatePct", 0.35))),
        IndexSpec("scheduleRegularity", (Component("onsetMADMin", 0.50), Component("riseMADMin", 0.50))),
        IndexSpec("sleepOnsetStability", (Component("sleepLatencyMin", 0.65), Component("sleepLatencyMADMin", 0.35))),
        IndexSpec("nightContinuity", (Component("sleepContinuityPct", 0.50), Component("awakeningsPerNight", 0.30), Component("outOfBedMinPerNight", 0.20))),
        IndexSpec("daytimeWakefulness", (Component("napMinPerDay", 0.55), Component("dayLowActivityRatePct", 0.45))),
        IndexSpec("circadianAlignment", (Component("midpointDeviationMin", 0.60), Component("dayActivitySharePct", 0.40))),
        IndexSpec("spaceRange", (Component("effectiveZoneCount", 0.60), Component("zoneTransitionsPer8h", 0.40))),
        IndexSpec("activityDiversity", (Component("activityEffectiveTypes", 0.75), Component("activityCategoryCount", 0.25))),
        IndexSpec("outsideParticipation", (Component("outsideMinutesPerValidDay", 0.45), Component("outingDaysRatePct", 0.30), Component("outingsPerValidDay", 0.25))),
        IndexSpec("socialParticipation", (Component("interactionMinutesPer8h", 0.45), Component("interactionEpisodesPer8h", 0.35), Component("initiatedInteractionRatePct", 0.20))),
        IndexSpec("participationContinuity", (Component("participatingDaysRatePct", 0.70), Component("longestLowParticipationStreakDays", 0.30))),
    )
}


DOMAIN_INDEXES = {
    "emotion": ("behaviorActivation", "initiative", "interestEngagement", "socialResponsiveness", "withdrawalBurden"),
    "cognition": ("taskInitiation", "taskCompleteness", "executionOrganization", "selfCorrection", "promptIndependence"),
    "sleep": ("scheduleRegularity", "sleepOnsetStability", "nightContinuity", "daytimeWakefulness", "circadianAlignment"),
    "participation": ("spaceRange", "activityDiversity", "outsideParticipation", "socialParticipation", "participationContinuity"),
}
