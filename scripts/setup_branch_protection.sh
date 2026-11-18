#!/usr/bin/env bash
# Protege main e develop: merge só via PR revisado e com os jobs de CI verdes.
# Pré-requisito: gh auth login (com permissão de admin no repositório).
# Uso: scripts/setup_branch_protection.sh OWNER/REPO
set -euo pipefail

REPO="${1:?informe OWNER/REPO}"

for BRANCH in main develop; do
  gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" \
    -H "Accept: application/vnd.github+json" \
    --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint e análise estática",
      "Testes e coverage gate",
      "Teste de carga (50 usuários simultâneos)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
JSON
  echo "Proteção aplicada em ${BRANCH}"
done
