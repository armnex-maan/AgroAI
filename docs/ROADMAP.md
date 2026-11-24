# Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo, Docker, migrations, provenance contract | ✅ |
| 1 | Core DB, telemetry ingest + simulator, Overview/Sensors/Simulation pages | ✅ |
| 2 | Acoustic Lab: upload, waveform, spectrogram, FFT/PSD, comparison, labelling, dataset export | ✅ |
| 2b | Animal identification: YAMNet (TFLite, 521 classes), optional BirdNET species, trainable farm model with cross-validation and manual activation, fusion with "unknown" verdict | ✅ |
| 2c | Species recognition with Google Perch 2.0 (ONNX, ~14.6k species incl. birds, insects, amphibians, mammals; Apache-2.0), iNaturalist local species list (250 km) + Italian names, YAMNet "is there an animal?" gate; farm model now trained on Perch embeddings. ESC-50 held-out check: right animal group 93% (83/89), false animals on machine/water/wind sounds 6% (7/116) | ✅ — still needs field recordings from the farm |
| 3d | Natural & biological remedies catalogue (36 entries: beneficial insects, microbials, organic-allowed products, practices, flagged folk remedies) linked to plant problems, with EPPO / EU sources | ✅ |
| 3a | Crop Advisor: Open-Meteo ERA5 climate + SoilGrids soil → 19-crop suitability, irrigation need, cost tips, rice integrated systems with EU legal checks | ✅ |
| 4a | ESP32: per-device HMAC secrets, provisioning + config.h, signed telemetry & audio upload, MQTT bridge, firmware sketch | ✅ software — **firmware not yet tested on hardware** |
| 3b | Weather forecast in predictions, alert rules from forecast | planned |
| 3c | Crop Vision: photo → colour measurement (chlorosis/necrosis %), Nemotron VL assessment restricted to an 18-cause KB, vetted fix/prevent/verify tips, sensor cross-check, farmer verification, trend | ✅ — needs real field photos to judge accuracy |
| 4b | Bench test firmware on real ESP32 + sensors; piezo/geophone ground-vibration node | next |
| 5 | Simulated deterrent devices + authorization gate + welfare/safety banners | planned |
| 6 | Field validation: collect labelled mole / non-mole recordings, publish model metrics | needs field data |
