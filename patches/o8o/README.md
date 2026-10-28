# Pending changes for Reach2trillion/o8o

Changes to the Sale Check module (`checkinme_sales_activity`, repository
`Reach2trillion/o8o`) made from this repository's session, which had no write
access to `o8o`. Apply them there so the repository matches the server:

```bash
cd o8o            # on the branch the server is deployed from (claude/checkinme-sales-activity-rf6wbe)
git am /path/to/0001-ABJ-directions-button.patch
```

| Patch | Base | Change |
|---|---|---|
| `0001-ABJ-directions-button.patch` | `542a751` | ABJ phone screen: round directions button (Google Maps route) on geolocated customers in the check-in customer list, Planned visits and Follow-ups today. Version 18.0.1.2.0. |
