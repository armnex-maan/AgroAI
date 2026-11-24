# Scientific & welfare guardrails

## Underground animal detection
There is no peer-reviewed per-species frequency signature for European moles.
The module extracts spectral/periodicity evidence and returns one of:
`repetitive_low_freq_pattern`, `noise`, `unknown` — with a confidence score,
signal-quality metric, and an evidence JSON. **It never returns a species ID.**

## Acoustic deterrents
Most birds hear roughly in the human audible range (~20 Hz – 12 kHz).
Ultrasonic emitters are not supported by evidence for bird deterrence.
Species-specific audio (distress calls, raptor calls) shows mixed efficacy
and habituation effects. In this platform:
- All deterrent devices are **simulated** by default.
- Physical emission is **disabled** until an authenticated user flips an
  explicit authorization flag per device, acknowledging welfare, protected
  species, and human-exposure constraints.
- No invented frequencies claimed to "repel animals" are generated.

## Crop vision
Leaf models trained on controlled datasets overfit to lab backgrounds.
All image analyses are presented as **visual assessments**, not confirmed
disease diagnoses. A verification workflow collects farmer feedback.

## BirdNET
CC BY-NC-SA 4.0 — non-commercial. Disabled by default. Enabling it
displays a licensing notice in the UI.
