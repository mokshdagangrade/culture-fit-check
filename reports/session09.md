---
team: Wavelength
session: 09
date: 2026-11-02
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
 metric: percentage of real localization edits independently flagged (recall vs. human expert adaptation)
 value: TBD
 previous: N/A
---

## Shipped this week

- Added hosted image/poster generation using Cloudflare FLUX, with generated images saved in project libraries and History.
- Connected visual prompts to the caption, original brief, brand details, and project references; removed product-specific prompt templates.
- Added product, style, setting, and logo uploads as actual inputs to reference-image generation, with project logos overriding brand settings.
- Improved upload validation, provider error messages, and chat composer alignment; documented the workflow in README.

## User evidence

- Feedback identified unrelated visual elements, an unintended third-party logo, and the need to integrate actual product photos into campaign images.
- Updated prompts and reference-image support in response; the user confirmed the corrected chat alignment worked.
- Feedback is qualitative; no new independent user study or measured localization improvement was recorded.

## Metrics snapshot

- 21 mocked image-generation tests pass; Python syntax and whitespace checks pass.
- Live Cloudflare generation succeeded with a synthetic reference and a saved project's references.
- Supports three image references plus one logo; PNG/JPEG/WebP uploads are limited to 1 MB and 16 megapixels each.

## What did not work

- Hugging Face billing requirements blocked hosted generation; added Cloudflare as an alternative.
- Early visuals included unrelated elements and invented branding; replaced generic scene assumptions and fixed overlays with campaign-specific planning and reference-image generation.
- One Cloudflare request returned HTTP 400/code 3030; a later retry succeeded, leaving the original cause unconfirmed. Added clearer diagnostics.

## Challenges / blockers

- Generated edits can alter product or logo details; exact fidelity requires review.
- Provider quotas, access restrictions, and content review can interrupt generation.
- Project-creation uploads are not automatically visual references; caption writing does not visually inspect images, and PDF/Office extraction remains unsupported.
- Poster layouts and broader browser/device testing need further work.

## Next week's goal

- Evaluate visual relevance and product/logo fidelity across multiple brands and campaigns.
- Improve reference selection, poster layouts, and recovery from provider failures.
- Run broader end-to-end/mobile checks and collect structured user feedback.

## Individual contributions

- Stuti Patel (Product): To be added.
- Riya Puri (Engineering): To be added.
- Vyom Agarwal (Data&Eval): To be added.
- Mokshda Gangrade (Users&Research): Implemented hosted image/poster generation, campaign-specific visual planning, reference/logo uploads, storage/downloads, diagnostics, and chat layout fixes. Added regression tests and checked live reference generation.

## Lean canvas changes (if any)

- No formal changes recorded. Added campaign visuals in response to the previously requested image/poster capability.
