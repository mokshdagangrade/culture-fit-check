---
team: Wavelength
session: 12
date: 2026-11-24
members:
- name: Stuti Patel
  github: stupatel
  hat: Product
- name: Riya Puri
  github: riyaapuri
  hat: Engineering
- name: Vyom Agarwal
  github: vyomya
  hat: "Data&Eval"
- name: Mokshda Gangrade
  github: mokshdagangrade
  hat: "Users&Research"


north_star:
  metric: precision@3 of selected signals against human judgement, reported with recall of usable signals
  value: not measured
  previous: not measured
  note: >
    Current work improves visual fidelity, date handling, preset-brand testing
    and visibility into regional grounding. Fresh raw signals are available,
    but cleaned candidates still need refreshing. No new human-reviewed
    retrieval or ranking quality measurement is claimed this session.
---


## Shipped this week


- **Improved campaign visuals:** Strengthened product-reference prompts to preserve geometry, orientation, colors and markings, and prevent branding from appearing on unrelated props. Added readable poster headlines, offers and dates extracted from the caption, with visual/poster downloads saved in History and project libraries.
- **Corrected date and freshness handling:** Added year-aware Black Friday date checks and distinguished missing fresh cleaned candidates from ranking failures. Traced weather-only output to current raw snapshots but stale ranked-candidate data; documented the full cleaning/loading workflow.
- **Added brand presets for testing:** Created three detailed fictional brands covering footwear, coffee and skincare, with catalogs, audiences, brand voices, visual guidelines, policies, claim limits and test briefs. Added a validated MongoDB importer, a preset picker in Brand settings, editable detailed facts, and setup instructions in README.
- **Fixed misleading regional-context displays:** Corrected the draft context panel to show signals actually selected for generation, with accurate counts, dates, geographic scope and relevance scores for evaluation and demonstrations.
- **Strengthened existing functionality:** Fixed missing-field handling and empty states, corrected a candidate-interleaving boundary, and removed a redundant image-history assignment while preserving behavior.
- **Investigated generation reliability:** Reviewed multi-state failure handling and requirements for preserving successful drafts, retrying failed states, and maintaining consistent history and follow-up context.
- **Validated integration stability:** Checked backend/image regressions and frontend rendering assertions for compatibility, missing data and context rendering.


## User evidence


- Review of a generated Black Friday campaign identified a distorted shoe, missing poster lettering and an incorrect November 29 date. Updated fidelity instructions, poster rendering and current-year date checks in response; exact product fidelity still needs visual review.
- The weather-only context display prompted a MongoDB freshness check: current raw data did not mean the cleaned candidate collection had also been refreshed.
- Detailed fictional brand presets were requested so testers can try different brands without repeatedly entering account details. Presets can be previewed and applied through Brand settings.
- The context-panel review improved visibility into selected evidence and exposed missing-data/empty-state issues. These checks support inspection, but do not establish improved ranking quality or independent user-study results.




## Metrics snapshot


### Validation


- Eight campaign-visual tests and five preset tests passed, along with 21 image, 16 generation and 22 backend regression tests. Python syntax, JavaScript syntax and whitespace checks passed.
- Verified calendar-date correction, caption-derived poster text, visual preservation in poster rendering, and persistence of both image and poster in project/History records using mocked integration checks.
- Validated all three fictional brand fixtures and repeat-import behavior. The importer passed dry-run validation; importing into the database is an optional step.
- Backend/image regression checks and frontend rendering assertions covered compatibility, missing data and selected-context rendering. No new aggregate test count was provided for this update.


### Retrieval and training


- MongoDB inspection found **50 raw state snapshots dated November 24, 2026**, while `signal_candidates` contained **1,295 rows dated October 20**. These candidates fall outside the generation freshness window, explaining the weather-only context.
- Fresh raw extraction is available; regenerating cleaned tables and loading fresh candidates are still required. No new precision@3, recall or visual-quality score is claimed.
- Work is underway to investigate ranking prompts, relevance thresholds and source balance, and to prepare a comparison of base and fine-tuned generation on unseen brands. Adapter-serving integration remains ongoing rather than completed.


## What did not work


- The generated shoe was distorted and the visual lacked readable promotional text. Stronger reference constraints and separately rendered poster lettering address these issues, but generative fidelity is not guaranteed.
- Generated copy used an incorrect Black Friday date. Added current-year calendar grounding and targeted correction while preserving explicitly supplied separate promotion dates.
- Loading raw signals alone did not refresh cleaned candidates used by the ranker. Documented the missing table conversion, cleaning and candidate-loading steps.
- The preset importer initially failed in the user's Conda environment because `email-validator` was missing; provided environment-specific dependency installation commands.
- Identified missing-field/empty-state inconsistencies and a candidate-interleaving boundary issue. Multi-state failure recovery and retrieval/filtering weaknesses remain under investigation.


## Challenges / blockers


- Uploaded product/logo references can still be altered by image editing; generated visuals require review against the originals.
- Fresh non-weather grounding requires the cleaned candidate collection to be refreshed, not just the raw daily collection. Stale-data handling and filtering errors can remove usable event references or admit sensitive political phrasing.
- Multi-state recovery must preserve successful drafts, retry only failed states, and keep history and follow-up context consistent. This capability is not yet shipped.
- Fine-tuned generation still needs a verified adapter-serving path and backend configuration. Final comparisons need unseen brands and measures of brand consistency, factual accuracy, regional relevance and finished-copy quality.
- Brand settings remain account-wide. When switching demo brands, testers should use a fresh project so existing project logos and visual references do not contaminate the test.


## Next week's goal


- Test product/logo fidelity and caption-derived poster layouts across the three demo brands, gather structured tester feedback, and validate the complete fresh-signal loading workflow.
- Improve ranking prompts, relevance thresholds and source balance to reduce forced campaign connections and prioritize useful regional hooks.
- Address stale-data and safety-filter weaknesses, including usable events being rejected and sensitive political phrasing passing through.
- Add targeted failure recovery that preserves successful state drafts and retries failed states without rerunning the campaign.
- Verify adapter-serving options and backend configuration, then refine base-versus-fine-tuned evaluation on unseen brands for brand consistency, factual accuracy, regional relevance and finished-copy quality.


## Individual contributions


- **Stuti Patel (Product):** Current-week contribution update pending.
- **Riya Puri (Engineering):** Fixed regional-context visibility and backend inconsistencies, validated compatibility, and investigated failure recovery across multi-state generation. Current work focuses on improving retrieval and ranking quality, integrating the fine-tuned generator, and adding recovery capabilities that make the application more reliable for the final deliverables.
- **Vyom Agarwal (Data&Eval):** Current-week contribution update pending.
- **Mokshda Gangrade (Users&Research):** Improved product-reference prompts and caption-derived poster text, added year-aware date checks, and diagnosed weather-only grounding through MongoDB freshness inspection. Created three detailed fictional brand presets, a validated catalog importer, and website controls to preview, apply and edit their facts. Added regression checks and documented preset setup and fresh-candidate loading.


## Lean canvas changes (if any)


- No formal canvas changes recorded. Work focused on trustworthy campaign visuals, inspectable regional grounding, repeatable brand testing and reliability for final evaluation.
- Product fidelity, useful fresh signals and consistent multi-state generation remain risks; current improvements do not establish higher retrieval or ranking accuracy.

