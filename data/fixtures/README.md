# Fictional brand presets

`brand_presets.json` contains three fictional testing brands:

- **Morrow Motion:** footwear and activewear; useful for product fidelity, event promotions, and everyday movement campaigns.
- **Juniper Cup:** coffee and home-brewing accessories; useful for warm brand voice and lifestyle campaigns.
- **Luma Grove:** cosmetic skincare; useful for restrained visual style and testing unsupported-claim limits.

Each record includes account profile fields, a structured catalog with sample prices, target markets/audience, past-post style examples, visual palette and art direction, commerce policies, approved/unsupported claims, and suggested test briefs. All facts and policies are fictional. `.example` domains are placeholders. No actual logos or product images are supplied; users can upload approved assets in settings/chat.

Sample campaign briefs are separate from the profile. Their example offers do not become active promotions simply by choosing a preset.

From the repository root, using the same Python environment as the backend:

```bash
conda run -n msml641 python src/backend/seed_brand_presets.py --dry-run
conda run -n msml641 python src/backend/seed_brand_presets.py
```

The importer reads `src/backend/.env` (`MONGODB_URI` and `MONGODB_DB_NAME`); existing environment variables take priority. An optional `--file path/to/brands.json` accepts another catalog with the same schema. All records are validated before MongoDB is opened. Imports upsert by `preset_id`, so rerunning updates presets instead of duplicating them. Records absent from the file are not deleted.

The importer writes only to `brand_presets`, never to `users` or `projects`. After restarting the backend once for the new API code, imported records appear in **Brand settings → Try a demo brand** on page refresh. Users preview the facts/test briefs, click **Fill brand details**, review/edit, and save. Only that save applies the chosen profile to their account; it clears the previous account logo from the form. Brand details, including visual guidance, are supplied to text/image generation.

Brand settings are currently account-wide. Use a fresh project to test another brand, because existing project logos and image references remain active. Updating a catalog preset later does not overwrite profiles already copied from it.
