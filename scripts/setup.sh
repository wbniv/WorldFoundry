#!/usr/bin/env bash
set -euo pipefail

# One-time credential setup for WorldFoundry (project slug: wf).
#
# Automates everything in docs/SETUP.md except the three things no
# credential can do for you: creating the AWS IAM user, minting the
# Codemagic API token, and creating the PagerDuty service + routing key.
# Every phase checks whether it is already done and skips itself, so this
# is safe to re-run after an interruption or a typo.
#
# This project has no Terraform and nothing to deploy — it is pure
# credential bootstrap for CI (the Codemagic Mac-minute budget monitor in
# .github/workflows/codemagic-budget.yml), so there is no --deploy flag.
#
# Usage:
#   ./scripts/setup.sh                 # interactive, prompts for anything missing
#   ./scripts/setup.sh --check         # report what is/isn't configured; never prompts,
#                                      #   never mutates anything (safe anywhere)
#   ./scripts/setup.sh --force         # re-check and re-offer every phase
#   ./scripts/setup.sh --yes           # auto-confirm every mutation (for a second,
#                                      #   already-reviewed run — still shows every plan)
#   ./scripts/setup.sh --import-creds=/path/to/bundle.tar
#                                      # restore the AWS profile + any live session-caches
#                                      #   from a scripts/creds-dump.sh bundle (another
#                                      #   machine) before running any phase. A .gpg path
#                                      #   (from scripts/creds-commit.sh) is decrypted
#                                      #   automatically — gpg prompts for the passphrase.
#
# Env var overrides (skip the matching prompt — useful for CI / re-runs):
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   for the wf-terraform profile
#   CODEMAGIC_API_TOKEN                         Codemagic API token (Phase B)
#   WF_CODEMAGIC_APP_ID                         hex app id from the codemagic.io/app/<id> URL
#   PAGERDUTY_ROUTING_KEY                       Events API v2 routing key (Phase C)
#   WF_AWS_REGION                               AWS region for the profile + SSM (default us-east-1)
#
# What ends up where:
#   AWS profile          wf-terraform                    ~/.aws/{credentials,config}
#   Codemagic token      /wf/codemagic-api-token         SSM SecureString (source of truth)
#                        secrets.CODEMAGIC_API_TOKEN     GitHub Actions secret
#                        ~/.config/codemagic/token       local, 0600, for the codemagic-build skill
#   Codemagic app id     vars.WF_CODEMAGIC_APP_ID        GitHub Actions variable (not a secret)
#                        ~/.config/codemagic/app-id      local, for the codemagic-build skill
#   PagerDuty key        /wf/pagerduty-routing-key       SSM SecureString (source of truth)
#                        secrets.PAGERDUTY_ROUTING_KEY   GitHub Actions secret
#
# See docs/SETUP.md for the narrative version of each step, including the
# exact dashboard click sequence for every manual part.

usage() {
  awk '
    /^[^#]/ && started { exit }
    /^#( |$)/ {
      started = 1
      sub(/^# ?/, "")
      print
    }
  ' "$0"
  exit 0
}

case "${1:-}" in
  -h|--help) usage ;;
esac

FORCE=0
AUTO_YES=0
CHECK_ONLY=0
IMPORT_CREDS=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --yes) AUTO_YES=1 ;;
    --check) CHECK_ONLY=1 ;;
    --import-creds=*) IMPORT_CREDS="${arg#*=}" ;;
    *) echo "ERROR: unknown argument '$arg' (try --help)" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Bundled locally (not sourced from ../python-tui-lib/scripts/) so this
# script works regardless of where the repo sits. Keep in sync with the
# canonical copy at ~/python-tui-lib/scripts/cleanup-stack.sh.
# shellcheck source=/dev/null
source "$SCRIPT_DIR/cleanup-stack.sh"

# Sourced (not bundled) — the credential-bundle export/import capability
# deliberately lives in one place for every project. Requires this repo to
# sit under ~/ alongside python-tui-lib.
CREDS_BUNDLE_LIB="$SCRIPT_DIR/../../python-tui-lib/scripts/creds-bundle.sh"
umask 077

# Capture a persistent log of every run — a failure reported second-hand
# is undiagnosable without one. Nothing sensitive lands here: every secret
# prompt uses `read -s` and every secret value is piped straight to a
# 0600 file, never echoed. Audit any new phase against that same rule.
LOG_DIR="$ROOT_DIR/.setup-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/setup-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1
ln -sf "$(basename "$LOG_FILE")" "$LOG_DIR/latest.log"
echo "Logging this run to $LOG_FILE"

# PROJECT and LOG_DIR look unused here but are required by creds-bundle.sh,
# which reads them from the caller's scope in the --import-creds path.
# shellcheck disable=SC2034
PROJECT="wf"
AWS_PROFILE_NAME="wf-terraform"
AWS_REGION="${WF_AWS_REGION:-us-east-1}"
GH_REPO="wbniv/WorldFoundry"

SSM_CODEMAGIC="/wf/codemagic-api-token"
SSM_PAGERDUTY="/wf/pagerduty-routing-key"
# These three names are consumed verbatim by
# .github/workflows/codemagic-budget.yml — do not rename one without the
# other.
GH_SECRET_CODEMAGIC="CODEMAGIC_API_TOKEN"
GH_SECRET_PAGERDUTY="PAGERDUTY_ROUTING_KEY"
GH_VAR_APP_ID="WF_CODEMAGIC_APP_ID"

# Local config the codemagic-build skill's driver reads directly, so
# neither the token nor the app id has to be exported every session.
CM_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/codemagic"
CM_TOKEN_FILE="$CM_CONFIG_DIR/token"
CM_APP_ID_FILE="$CM_CONFIG_DIR/app-id"

CODEMAGIC_CACHE="$LOG_DIR/.codemagic-session-cache"

log()  { printf '\033[1;36m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$1" >&2; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }
need aws
need curl
need gh
need jq
need python3
need tar

# Transient network/DNS flakiness is a real, observed failure mode — a call
# to an external host can fail once and succeed immediately on retry with
# nothing else changed. Don't let one blip fail the whole run.
retry() {
  local max_attempts="$1" delay="$2"
  shift 2
  local attempt=1
  while true; do
    if "$@"; then return 0; fi
    if [ "$attempt" -ge "$max_attempts" ]; then
      warn "FAILED after $max_attempts attempts: $*"
      return 1
    fi
    warn "  attempt $attempt/$max_attempts failed, retrying in ${delay}s: $*"
    sleep "$delay"
    attempt=$((attempt + 1))
  done
}

# Transparent retry wrapper — there is no single choke point to wrap by
# hand across every call site. `command aws` bypasses this function on the
# inner call, so it is not infinite recursion.
aws() { retry 10 8 command aws "$@"; }

# Existence checks are the one place the 10× retry above is wrong: a
# genuinely-absent profile or parameter is the expected answer, and
# retrying it for 80 s before prompting would be maddening. Two quick
# attempts still absorb a single network blip — quietly, since "missing" is
# a normal answer here and not something to warn about.
aws_check() {
  command aws "$@" >/dev/null 2>&1 && return 0
  sleep 3
  command aws "$@" >/dev/null 2>&1
}

# Every real mutation routes through here: show what is about to happen,
# then require an explicit yes. Nothing applies blindly. --check refuses
# outright so a report-only run can never mutate.
confirm() {
  local prompt="$1"
  if [[ "$CHECK_ONLY" == 1 ]]; then
    warn "--check: would ask '$prompt' — skipping (report-only run)."
    return 1
  fi
  if [[ "$AUTO_YES" == 1 ]]; then
    ok "auto-confirmed (--yes): $prompt"
    return 0
  fi
  local reply
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" == "y" || "$reply" == "Y" ]]
}

# In --check mode a phase reports and returns instead of prompting.
checking() { [[ "$CHECK_ONLY" == 1 ]]; }

aws_ssm_has() {
  # Existence only — deliberately no --with-decryption, so a cache check
  # never pulls a secret into this process (or this run's log).
  aws_check ssm get-parameter --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" \
    --name "$1" --no-cli-pager
}

aws_profile_works() {
  aws_check sts get-caller-identity --profile "$AWS_PROFILE_NAME"
}

aws_ssm_put_secret() {
  # Secrets never touch argv: the value goes through a 0600 temp file.
  local name="$1" value="$2" f
  f=$(mktemp -t wf-ssm.XXXXXX)
  push_cleanup "rm -f '$f'"
  printf '%s' "$value" > "$f"
  aws ssm put-parameter --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" \
    --name "$name" --type SecureString --value "file://$f" --overwrite \
    --no-cli-pager >/dev/null
  rm -f "$f"
}

gh_secret_exists() {
  gh secret list -R "$GH_REPO" --json name --jq '.[].name' 2>/dev/null \
    | grep -qx "$1"
}

gh_secret_put() {
  # `gh secret set` reads the value from stdin when --body is absent, so
  # the secret never appears in argv or shell history either.
  local name="$1" value="$2"
  printf '%s' "$value" | gh secret set "$name" -R "$GH_REPO"
}

gh_variable_exists() {
  gh variable list -R "$GH_REPO" --json name --jq '.[].name' 2>/dev/null \
    | grep -qx "$1"
}

# ── Phase A: AWS wf-terraform profile ────────────────────────────────────
# The minimal profile-exists-or-prompt half of the `iam-bootstrap` skill's
# Phase A. Its Phase B (Terraform state backend) and Phase C (self-narrowing
# IAM) are deliberately NOT run here: this repo has no infrastructure/
# Terraform at all, and the only AWS surface WorldFoundry uses is two SSM
# SecureStrings. If WF ever grows Terraform-managed infra, run the full
# iam-bootstrap flow then and narrow this user's AdministratorAccess as part
# of it — see docs/SETUP.md §A for the standing caveat.
phase_aws_profile() {
  log "Phase A: AWS '$AWS_PROFILE_NAME' profile (region $AWS_REGION)"
  if [[ "$FORCE" != 1 ]] && aws_profile_works; then
    ok "AWS profile '$AWS_PROFILE_NAME' already configured — skipping."
    return
  fi
  if checking; then
    warn "NOT CONFIGURED: AWS profile '$AWS_PROFILE_NAME' (run without --check to set it up)."
    return
  fi

  echo ""
  echo "  This is the only AWS step a credential cannot do for itself — there is"
  echo "  no existing WorldFoundry AWS access to create it with."
  echo ""
  echo "  1. Create the IAM user (one-time, ~3 min):"
  echo "     https://us-east-1.console.aws.amazon.com/iam/home#/users/create"
  echo "     Name: $AWS_PROFILE_NAME   |   do NOT tick 'console access'"
  echo "  2. 'Set permissions' → 'Attach policies directly':"
  echo "       Filter by Type: AWS managed - job function"
  echo "       search AdministratorAccess → tick it"
  echo "       search ReadOnlyAccess      → tick it   (same category, no filter switch)"
  echo "     Click the 'Policies selected' tab to confirm both, then Next → Create user."
  echo "  3. Open the new user → Security credentials → Create access key:"
  echo "       Use case: Command Line Interface (CLI) → acknowledge"
  echo "       Description tag: ${AWS_PROFILE_NAME}-$(hostname)"
  echo "     Copy both values now — the secret is shown exactly once."
  echo ""

  local key_id="${AWS_ACCESS_KEY_ID:-}"
  local key_secret="${AWS_SECRET_ACCESS_KEY:-}"
  if [[ -z "$key_id" ]]; then
    read -r -p "Paste Access Key ID: " key_id
  fi
  if [[ -z "$key_secret" ]]; then
    read -r -s -p "Paste Secret Access Key (hidden): " key_secret
    echo ""
  fi
  [[ -n "$key_id" && -n "$key_secret" ]] || die "access key required"

  if ! confirm "Write the [$AWS_PROFILE_NAME] profile to ~/.aws/credentials and ~/.aws/config?"; then
    die "Aborted — nothing written."
  fi

  # configparser rewrites an existing section rather than appending a
  # second one, so a re-run after a mistyped key repairs the entry instead
  # of leaving a broken duplicate (the lesson from the loom project).
  # The secret arrives on stdin, never in argv.
  local pyprog
  pyprog=$(mktemp -t wf-aws-creds.XXXXXX.py)
  push_cleanup "rm -f '$pyprog'"
  cat > "$pyprog" <<'PY'
import configparser, os, pathlib, sys
path, profile = sys.argv[1], sys.argv[2]
key_id = sys.stdin.readline().rstrip("\n")
secret = sys.stdin.readline().rstrip("\n")
p = pathlib.Path(path)
p.parent.mkdir(parents=True, exist_ok=True)
cp = configparser.ConfigParser()
cp.read(path)
if not cp.has_section(profile):
    cp.add_section(profile)
cp.set(profile, "aws_access_key_id", key_id)
cp.set(profile, "aws_secret_access_key", secret)
with open(path, "w") as fh:
    cp.write(fh)
os.chmod(path, 0o600)
PY
  printf '%s\n%s\n' "$key_id" "$key_secret" \
    | python3 "$pyprog" "$HOME/.aws/credentials" "$AWS_PROFILE_NAME"
  rm -f "$pyprog"

  mkdir -p "$HOME/.aws"
  grep -q "^\[profile $AWS_PROFILE_NAME\]" "$HOME/.aws/config" 2>/dev/null \
    || printf "\n[profile %s]\nregion = %s\noutput = json\n" \
         "$AWS_PROFILE_NAME" "$AWS_REGION" >> "$HOME/.aws/config"

  aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --no-cli-pager >/dev/null \
    || die "profile written but 'aws sts get-caller-identity' failed — check the pasted key"
  ok "AWS profile '$AWS_PROFILE_NAME' verified."
}

# ── Phase B: Codemagic API token + app id ────────────────────────────────
# Unblocks .github/workflows/codemagic-budget.yml, which is inert until the
# secret, the PagerDuty key (Phase C) and the app id variable all exist.
phase_codemagic() {
  log "Phase B: Codemagic API token + app id"

  # `cond && var=1` on its own line would abort under `set -e` when the
  # condition is false, which is the normal case here — hence the `|| true`.
  local have_ssm=0 have_secret=0 have_var=0
  aws_ssm_has "$SSM_CODEMAGIC" && have_ssm=1 || true
  gh_secret_exists "$GH_SECRET_CODEMAGIC" && have_secret=1 || true
  gh_variable_exists "$GH_VAR_APP_ID" && have_var=1 || true

  if [[ "$FORCE" != 1 && "$have_ssm" == 1 && "$have_secret" == 1 && "$have_var" == 1 ]]; then
    ok "$SSM_CODEMAGIC, secrets.$GH_SECRET_CODEMAGIC and vars.$GH_VAR_APP_ID all present — skipping."
    return
  fi

  if checking; then
    if [[ "$have_ssm" == 1 ]]; then ok "SSM $SSM_CODEMAGIC present."
    else warn "NOT CONFIGURED: SSM $SSM_CODEMAGIC"; fi
    if [[ "$have_secret" == 1 ]]; then ok "secrets.$GH_SECRET_CODEMAGIC present."
    else warn "NOT CONFIGURED: secrets.$GH_SECRET_CODEMAGIC on $GH_REPO"; fi
    if [[ "$have_var" == 1 ]]; then ok "vars.$GH_VAR_APP_ID present."
    else warn "NOT CONFIGURED: vars.$GH_VAR_APP_ID on $GH_REPO"; fi
    return
  fi

  if [[ "$have_ssm" != 1 || "$have_secret" != 1 || "$FORCE" == 1 ]]; then
    phase_codemagic_token
  else
    ok "Codemagic token already in SSM and GitHub Actions — only the app id is missing."
  fi
  phase_codemagic_app_id
}

# Prompt for, validate, and store the token. Session-cached so a failure in
# a later step (SSM, gh, the local config write) does not re-prompt for the
# same secret on the next run; the cache is deleted the moment the phase
# reaches its real end state.
phase_codemagic_token() {
  local token="${CODEMAGIC_API_TOKEN:-}"
  if [[ -z "$token" && -f "$CODEMAGIC_CACHE" ]]; then
    # shellcheck source=/dev/null
    source "$CODEMAGIC_CACHE"
    token="${CODEMAGIC_API_TOKEN:-}"
    [[ -n "$token" ]] && ok "Loaded the Codemagic token from this session's cache — not re-prompting."
  fi

  if [[ -z "$token" ]]; then
    echo ""
    echo "  Mint a Codemagic API token — this cannot be done via the API:"
    echo "    1. Open https://codemagic.io/settings"
    echo "    2. Top-left: pick your account/team (personal account for WorldFoundry)"
    echo "    3. Settings → Integrations"
    echo "    4. Row 'Codemagic API' → click 'Show' (or 'Connect' if not yet enabled)"
    echo "    5. Copy the token"
    echo ""
    read -r -s -p "Paste the Codemagic API token (hidden): " token
    echo ""
  fi
  [[ -n "$token" ]] || die "Codemagic API token required"
  printf 'CODEMAGIC_API_TOKEN=%q\n' "$token" > "$CODEMAGIC_CACHE"

  # Validate the same way the codemagic-build skill's driver does
  # (~/.claude/skills/codemagic-build/codemagic.py, cmd_bootstrap): a
  # GET /apps with an x-auth-token header, 200 = valid. Keeping the check
  # identical means both paths agree on what "valid" means.
  # The token goes in a 0600 curl config file, never in argv.
  log "Validating the token against GET https://api.codemagic.io/apps …"
  local curlcfg http
  curlcfg=$(mktemp -t wf-cm-curl.XXXXXX)
  push_cleanup "rm -f '$curlcfg'"
  {
    printf 'url = "https://api.codemagic.io/apps"\n'
    printf 'header = "x-auth-token: %s"\n' "$token"
  } > "$curlcfg"
  http=$(curl -sS --retry 5 --retry-delay 5 --retry-max-time 120 \
           -o /dev/null -w '%{http_code}' --config "$curlcfg" || echo "000")
  rm -f "$curlcfg"
  [[ "$http" == "200" ]] || die "token rejected by GET /apps (HTTP $http) — nothing stored"
  ok "Token validated (HTTP 200)."

  echo ""
  echo "  About to store the validated token in three places:"
  echo "    • AWS SSM SecureString  $SSM_CODEMAGIC  (profile $AWS_PROFILE_NAME, $AWS_REGION)"
  echo "    • GitHub Actions secret $GH_SECRET_CODEMAGIC on $GH_REPO"
  echo "    • local file            $CM_TOKEN_FILE (mode 0600, for the codemagic-build skill)"
  echo ""
  if confirm "Store the Codemagic token in those three places?"; then
    aws_ssm_put_secret "$SSM_CODEMAGIC" "$token"
    ok "SSM $SSM_CODEMAGIC written."
    gh_secret_put "$GH_SECRET_CODEMAGIC" "$token"
    ok "GitHub Actions secret $GH_SECRET_CODEMAGIC set on $GH_REPO."
    mkdir -p "$CM_CONFIG_DIR"
    printf '%s\n' "$token" > "$CM_TOKEN_FILE"
    chmod 600 "$CM_TOKEN_FILE"
    ok "Local token written to $CM_TOKEN_FILE (0600)."
    rm -f "$CODEMAGIC_CACHE"
  else
    warn "Skipped — the token stays in $CODEMAGIC_CACHE for this session; re-run to finish."
  fi
}

# The app id is not a secret and there is no API to look it up — it is the
# hex in the dashboard URL, so it has to be typed in.
phase_codemagic_app_id() {
  if [[ "$FORCE" != 1 ]] && gh_variable_exists "$GH_VAR_APP_ID" \
     && [[ -f "$CM_APP_ID_FILE" ]]; then
    ok "vars.$GH_VAR_APP_ID and $CM_APP_ID_FILE already set — skipping."
    return
  fi

  local app_id="${WF_CODEMAGIC_APP_ID:-}"
  if [[ -z "$app_id" && -f "$CM_APP_ID_FILE" ]]; then
    app_id="$(cat "$CM_APP_ID_FILE")"
    ok "Reusing the app id already in $CM_APP_ID_FILE."
  fi
  if [[ -z "$app_id" ]]; then
    echo ""
    echo "  Find the WorldFoundry Codemagic app id (not a secret, so it is echoed):"
    echo "    1. Open https://codemagic.io/apps"
    echo "    2. Click the WorldFoundry app"
    echo "    3. Copy the hex id out of the URL: codemagic.io/app/<APP_ID>/..."
    echo ""
    read -r -p "Paste the Codemagic app id: " app_id
  fi
  app_id="${app_id//[[:space:]]/}"
  [[ -n "$app_id" ]] || die "Codemagic app id required"
  [[ "$app_id" =~ ^[0-9a-fA-F]{24}$ ]] \
    || warn "'$app_id' does not look like a 24-char hex Codemagic app id — continuing anyway."

  echo ""
  echo "  About to store the app id in two places:"
  echo "    • GitHub Actions VARIABLE (not a secret) vars.$GH_VAR_APP_ID on $GH_REPO"
  echo "      — consumed by .github/workflows/codemagic-budget.yml as WF_APP_ID"
  echo "    • local file $CM_APP_ID_FILE, read by the codemagic-build skill's driver"
  echo "      so \$CODEMAGIC_APP_ID no longer has to be exported every session"
  echo ""
  if confirm "Store the app id '$app_id' in those two places?"; then
    gh variable set "$GH_VAR_APP_ID" -R "$GH_REPO" --body "$app_id"
    ok "GitHub Actions variable $GH_VAR_APP_ID set on $GH_REPO."
    mkdir -p "$CM_CONFIG_DIR"
    printf '%s\n' "$app_id" > "$CM_APP_ID_FILE"
    ok "Local app id written to $CM_APP_ID_FILE."
  else
    warn "Skipped the app id — the budget workflow fails loudly without it."
  fi
}

# ── Phase C: PagerDuty routing key ───────────────────────────────────────
# Structurally identical to Phase B's token half, minus the validation
# call: PagerDuty's Events API v2 has no read endpoint to probe with, and
# the only write endpoint creates a real incident, so the key is checked
# for shape rather than exercised.
phase_pagerduty() {
  log "Phase C: PagerDuty routing key"

  local have_ssm=0 have_secret=0
  aws_ssm_has "$SSM_PAGERDUTY" && have_ssm=1 || true
  gh_secret_exists "$GH_SECRET_PAGERDUTY" && have_secret=1 || true

  if [[ "$FORCE" != 1 && "$have_ssm" == 1 && "$have_secret" == 1 ]]; then
    ok "$SSM_PAGERDUTY and secrets.$GH_SECRET_PAGERDUTY both present — skipping."
    return
  fi

  if checking; then
    if [[ "$have_ssm" == 1 ]]; then ok "SSM $SSM_PAGERDUTY present."
    else warn "NOT CONFIGURED: SSM $SSM_PAGERDUTY"; fi
    if [[ "$have_secret" == 1 ]]; then ok "secrets.$GH_SECRET_PAGERDUTY present."
    else warn "NOT CONFIGURED: secrets.$GH_SECRET_PAGERDUTY on $GH_REPO"; fi
    return
  fi

  local key="${PAGERDUTY_ROUTING_KEY:-}"
  if [[ -z "$key" ]]; then
    echo ""
    echo "  Create the PagerDuty service and copy its Events API v2 routing key:"
    echo "    1. Open https://app.pagerduty.com/service-directory"
    echo "    2. '+ New Service'"
    echo "    3. Name: worldfoundry-codemagic-budget"
    echo "    4. Escalation policy: your default (Will Norris)"
    echo "    5. Integrations → select 'Events API V2' → Create Service"
    echo "    6. On the new service's Integrations tab, copy the 'Integration Key'"
    echo "       (this is the routing key)"
    echo ""
    read -r -s -p "Paste the PagerDuty routing key (hidden): " key
    echo ""
  fi
  [[ -n "$key" ]] || die "PagerDuty routing key required"
  key="${key//[[:space:]]/}"
  [[ "${#key}" -eq 32 ]] \
    || warn "routing key is ${#key} chars, not the usual 32 — continuing anyway."

  echo ""
  echo "  About to store the routing key in two places:"
  echo "    • AWS SSM SecureString  $SSM_PAGERDUTY  (profile $AWS_PROFILE_NAME, $AWS_REGION)"
  echo "    • GitHub Actions secret $GH_SECRET_PAGERDUTY on $GH_REPO"
  echo ""
  if confirm "Store the PagerDuty routing key in those two places?"; then
    aws_ssm_put_secret "$SSM_PAGERDUTY" "$key"
    ok "SSM $SSM_PAGERDUTY written."
    gh_secret_put "$GH_SECRET_PAGERDUTY" "$key"
    ok "GitHub Actions secret $GH_SECRET_PAGERDUTY set on $GH_REPO."
  else
    warn "Skipped — without this the budget monitor still reports usage, but only logs alerts."
  fi
}

# ── Summary ──────────────────────────────────────────────────────────────
summary() {
  echo ""
  log "Summary"
  if aws_profile_works; then
    ok "AWS profile $AWS_PROFILE_NAME"
  else
    warn "AWS profile $AWS_PROFILE_NAME — missing"
  fi
  local p
  for p in "$SSM_CODEMAGIC" "$SSM_PAGERDUTY"; do
    if aws_ssm_has "$p"; then ok "SSM $p"; else warn "SSM $p — missing"; fi
  done
  local s
  for s in "$GH_SECRET_CODEMAGIC" "$GH_SECRET_PAGERDUTY"; do
    if gh_secret_exists "$s"; then ok "secrets.$s on $GH_REPO"; else warn "secrets.$s on $GH_REPO — missing"; fi
  done
  if gh_variable_exists "$GH_VAR_APP_ID"; then
    ok "vars.$GH_VAR_APP_ID on $GH_REPO"
  else
    warn "vars.$GH_VAR_APP_ID on $GH_REPO — missing"
  fi
  echo ""
  echo "  Smoke-test the budget monitor once all of the above are green:"
  echo "    gh workflow run codemagic-budget.yml -R $GH_REPO -f dry_run=true"
  echo "    gh run list --workflow=codemagic-budget.yml -R $GH_REPO --limit 1"
}

main() {
  if [[ -n "$IMPORT_CREDS" ]]; then
    if [[ ! -f "$CREDS_BUNDLE_LIB" ]]; then
      echo "✗ Shared library not found: $CREDS_BUNDLE_LIB" >&2
      echo "  Clone python-tui-lib as a sibling of this repo first:" >&2
      echo "    cd \"$(dirname "$ROOT_DIR")\" && git clone git@github.com:wbniv/python-tui-lib.git" >&2
      exit 1
    fi
    # shellcheck source=../../python-tui-lib/scripts/creds-bundle.sh
    source "$CREDS_BUNDLE_LIB"
    creds_bundle_restore "$IMPORT_CREDS"
  fi

  phase_aws_profile
  phase_codemagic
  phase_pagerduty
  summary

  echo ""
  if [[ "$CHECK_ONLY" == 1 ]]; then
    ok "Report-only run complete — nothing was changed."
  else
    ok "Setup complete. See docs/SETUP.md for what each phase stored and where."
  fi
}

main
