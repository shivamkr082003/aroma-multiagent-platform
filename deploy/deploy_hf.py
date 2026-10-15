"""Deploy Aroma to a Hugging Face Space (Docker SDK) in one command.

    python deploy/deploy_hf.py --dry-run     # check settings and list the files, upload nothing
    python deploy/deploy_hf.py               # create/update the Space, set secrets, upload

Reads everything from .env (never committed):
    HF_TOKEN             Hugging Face access token with *write* permission
    HF_SPACE             optional, default "<your-username>/aroma-ai"
    GROQ_API_KEY, DEEPGRAM_API_KEY, TAVILY_API_KEY, DATABASE_URL
    QDRANT_CLOUD_URL, QDRANT_API_KEY       (Qdrant Cloud)
    UPSTASH_REDIS_URL                      (rediss://… from Upstash)

Production signing/encryption keys are generated on the first deploy and saved
back to .env as PROD_AUTH_SECRET_KEY / PROD_MCP_SECRET_KEY. Keep them: a new
MCP key makes saved MCP API keys unreadable, a new auth key signs everyone out.
"""

import argparse
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

# Space secret name -> .env key it comes from.
SECRETS = {
    "GROQ_API_KEY": "GROQ_API_KEY",
    "DEEPGRAM_API_KEY": "DEEPGRAM_API_KEY",
    "TAVILY_API_KEY": "TAVILY_API_KEY",
    "DATABASE_URL": "DATABASE_URL",
    "QDRANT_URL": "QDRANT_CLOUD_URL",
    "QDRANT_API_KEY": "QDRANT_API_KEY",
    "REDIS_URL": "UPSTASH_REDIS_URL",
    "AUTH_SECRET_KEY": "PROD_AUTH_SECRET_KEY",
    "MCP_SECRET_KEY": "PROD_MCP_SECRET_KEY",
}

# Non-secret settings, visible in the Space settings.
VARIABLES = {
    "AUTH_COOKIE_SECURE": "true",
    "MCP_ALLOW_STDIO": "false",
    "EMBEDDING_PROVIDER": "local",
    "RETRIEVAL_MODE": "hybrid_rerank",
}

SPACE_README = """---
title: Aroma AI
emoji: 🌿
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Multi-agent assistant for documents, voice, web and MCP
---

# Aroma AI

Chat with your documents, talk hands-free, search the web and plug in MCP tools.
Source code: https://github.com/shivamkr082003/aroma-multiagent-platform
"""


def ensure_prod_keys(env: dict) -> None:
    generated = {
        "PROD_AUTH_SECRET_KEY": lambda: secrets.token_urlsafe(48),
        "PROD_MCP_SECRET_KEY": lambda: Fernet.generate_key().decode(),
    }
    for key, make in generated.items():
        if not env.get(key):
            env[key] = make()
            set_key(str(ENV_FILE), key, env[key])
            print(f"  generated {key} and saved it to .env (keep it)")


def stage_files(target: Path) -> list[str]:
    """Copy what git would commit (tracked + new, .gitignore respected) into target."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    skip_prefixes = (".github/", "benchmark-results/", "docker/qdrant_storage/")
    files = [f for f in listed if not f.startswith(skip_prefixes) and (ROOT / f).is_file()]
    for f in files:
        (target / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, target / f)
    (target / "README.md").write_text(SPACE_README)  # Space config lives in the README front matter
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="validate and list files without uploading")
    args = parser.parse_args()

    env = {k: v for k, v in dotenv_values(ENV_FILE).items() if v}
    if not env.get("HF_TOKEN"):
        sys.exit("HF_TOKEN missing in .env (huggingface.co → Settings → Access Tokens → Write).")

    api = HfApi(token=env["HF_TOKEN"])
    username = api.whoami()["name"]
    repo_id = env.get("HF_SPACE") or f"{username}/aroma-ai"
    print(f"Space: {repo_id}")

    ensure_prod_keys(env)
    missing = [src for src in SECRETS.values() if not env.get(src)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as tmp:
        files = stage_files(Path(tmp))
        print(f"  {len(files)} files staged")
        if args.dry_run:
            print("Dry run: nothing uploaded. Secrets that would be set:", ", ".join(SECRETS))
            return

        api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
        for name, source in SECRETS.items():
            api.add_space_secret(repo_id, name, env[source])
        for name, value in VARIABLES.items():
            api.add_space_variable(repo_id, name, value)
        print(f"  {len(SECRETS)} secrets and {len(VARIABLES)} variables set")

        api.upload_folder(
            repo_id=repo_id, repo_type="space", folder_path=tmp,
            commit_message="Deploy Aroma AI",
            delete_patterns=["*", "**/*"],  # remove files deleted locally since the last deploy
        )

    owner, name = repo_id.split("/")
    print("\nUploaded. The Space now builds the image (about 10–15 minutes the first time).")
    print(f"  Build logs: https://huggingface.co/spaces/{repo_id}")
    print(f"  App:        https://{owner.lower()}-{name.lower().replace('_', '-').replace('.', '-')}.hf.space")


if __name__ == "__main__":
    main()
