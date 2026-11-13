# ADR 0001 — Monolithe modulaire et architecture propre pragmatique

**Statut** : accepté. **Contexte** : équipe de hackathon, 48 h, évolution ensuite.
**Décision** : un frontend React et une API FastAPI dans un monorepo ; dans l'API, couches
`domain` (pur) → `application` (cas d'usage, ports `Protocol`) ← `infrastructure`, assemblées dans
`api/dependencies.py`. Un seul port réel (fournisseur climatique) ; pas d'abstraction sans besoin.
**Alternatives écartées** : microservices (coût opérationnel), logique dans les routes (non testable).
**Conséquences** : noyau testable sans réseau ; règle de dépendance vérifiée par un test.
