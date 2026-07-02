## CAPSTONE PROJECTS

GitHub Actions: Deploy Notebook

This repository includes a GitHub Actions workflow that converts `Safety_Guardrails.ipynb` to HTML and deploys it to GitHub Pages.

Files added:
- .github/workflows/deploy-notebook.yml — builds HTML and deploys to Pages

Usage:
- Push to the `main` branch or run the workflow manually via the Actions tab.
- No personal token is required; the workflow uses repository permissions. To use a personal token instead, add it as a repository secret and modify the workflow accordingly.

Using a personal token (optional):
- I recommend the secret name `GH_PAGES_TOKEN`.
- Add the token in the repo: Settings → Secrets → Actions → New repository secret, name it `GH_PAGES_TOKEN` and paste your personal access token (scopes: `repo`, `workflow`).
- The workflow will publish the converted HTML to the `gh-pages` branch.
