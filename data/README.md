# data/

Datasets and annotation guidelines for Wavelength.

## Planned structure

```
data/
├── us/           # US signals and examples (state-level, English)
├── india/        # India signals and examples (state/city-level, Hindi-English code-mixed)
├── annotations/  # Annotation guidelines and human ratings, kept separate per region
└── README.md
```

## Planned sources

| Region | Source | Purpose | License / access |
|---|---|---|---|
| US | Google Trends (state-level) | Regional trending topics | TBD |
| US | NWS / OpenWeather | State and city weather | TBD |
| US | Regional slang and dialect research | Register and slang variation | TBD |
| US | Sports signals (ESPN, team subreddits) | Local team and event context | TBD |
| US | Regional brand social copy | Real localized copy examples | TBD |
| India | Google Trends India (state-level) | Regional trending topics | TBD |
| India | L3Cube-HingCorpus and Hinglish datasets | Code-mixed language handling | TBD |
| India | State-specific festival calendar | Festival timing per state | TBD |
| India | IPL / cricket schedule | City team loyalty and event context | TBD |
| India | IMD / OpenWeather | City-level weather | TBD |
| India | Indian D2C brand social copy | Real localized copy examples | TBD |

## Notes

- Launch regions (3-4 US states, 3-4 Indian cities/states) are still to be decided.
- Do not commit raw datasets with unclear licenses. Record the source and license here first.
- Report inter-annotator agreement separately for US and India.