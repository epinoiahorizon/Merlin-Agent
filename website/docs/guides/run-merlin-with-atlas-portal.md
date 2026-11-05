---
title: Atlas Portal (not available in this distribution)
sidebar_label: Atlas Portal
---

<div className="alert alert--warning">

**The hosted Atlas Portal is not available in this distribution.** Its endpoints
(`portal.epinoiahorizon.com`, `inference-api.epinoiahorizon.com`) do not resolve, so
`merlin setup --portal`, `merlin portal`, and the `atlas` provider cannot log in here.

</div>

Merlin runs on any OpenAI-compatible provider instead. Pick one you already pay for:

- [`merlin model`](../user-guide/configuring-models.md) — set the provider and model
- [Providers](../integrations/providers.md) — what works out of the box (OpenRouter, OpenAI, local endpoints, …)
- [Keys](../user-guide/secrets.md) — where API keys live (`~/.merlin/.env`)

The `atlas` provider entry stays in the code so the fork can point at a hosted
gateway if one is ever provisioned; nothing else in Merlin depends on it.
