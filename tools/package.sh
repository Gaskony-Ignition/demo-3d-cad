#!/usr/bin/env bash
# Package Machine_HMI_Demo as an importable Ignition 8.3 project zip.
#
#   tools/package.sh                     -> build/Machine_HMI_Demo-<version>-dev.zip
#   tools/package.sh --release           -> build/Machine_HMI_Demo-<version>.zip
#   tools/package.sh --edge              -> build/Machine_HMI_Demo_Edge-<version>-dev.zip
#   tools/package.sh --release --edge    -> build/Machine_HMI_Demo_Edge-<version>.zip
#
# The Edge build is the same project with the tag provider name substituted, and
# it exists because portability could not be bought at runtime. The views carry
# 395 literal [MachineDemo] tag paths, and a provider-less or [default] path does
# NOT resolve unless the project's global-props names a default provider -
# measured three ways in one view on 09/09/2026. global-props also carries the
# Perspective identity provider, so writing it at install time would reconfigure
# something that is not ours. A build-time substitution has none of that risk:
# it is deterministic, and nothing has to resolve a name at runtime.
#
# Edge permits exactly one realtime tag provider and it is called `edge` out of
# the box, so the Edge build ADOPTS that name rather than renaming the
# customer's provider. See docs/CONTRACT.md.
#
# Two things about Ignition project zips that are easy to get wrong and give no
# error when you do:
#
#   1. The zip is made from INSIDE the project directory. A zip whose entries
#      start with "Machine_HMI_Demo/" imports as an empty project.
#   2. Perspective global-props travels only as the workspace copy (md5 09d72c9d,
#      ../docs/lockdown-recipe.md): IdP `default`, no user source, no database,
#      autoIdpAuth on. A rig's own copy would carry its identity provider and
#      session settings to every gateway, so any other copy fails the build.
set -euo pipefail
# Repo gate (REPO-STANDARD.md). Blocking; bypass deliberately with --skip-readme-check.
if [[ " $* " != *" --skip-readme-check "* ]]; then
    _repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
    _gate=""; _d="$_repo"
    while [ "$_d" != / ]; do
        [ -x "$_d/modules/readme-gate.sh" ] && { _gate="$_d/modules/readme-gate.sh"; break; }
        _d=$(dirname "$_d")
    done
    if [ -n "$_gate" ]; then
        "$_gate" "$_repo" || { echo "repo gate failed: fix the README/tree or pass --skip-readme-check" >&2; exit 1; }
    else
        echo "readme-gate.sh not found above $_repo; gate skipped" >&2
    fi
fi
# Deploy the working tree to the test gateway once, for the gates that check
# what is deployed (a11y, scroll bars).
_deployed=0
_deploy() {
    [ "$_deployed" = 1 ] && return 0
    local _h; _h="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    (
        # shellcheck disable=SC1091
        source "$_h/env.local.sh"
        cd "$(git -C "$_h" rev-parse --show-toplevel)/project" && tar cf - . | docker exec -i "$GW_CONTAINER" tar xf - -C "$GW_PROJECTS/Machine_HMI_Demo"
        docker exec "$GW_CONTAINER" chown -R ignition:ignition "$GW_PROJECTS/Machine_HMI_Demo"
    )
    "$_h/scan.sh"
    _deployed=1
}
# a11y gate (WCAG 2.1 AA plan, Stage 5). Blocking; bypass deliberately with
# --skip-a11y-check. The gate checks what is DEPLOYED, so deploy the current
# project to module-testing (this repo's own tools/env.local.sh + scan.sh)
# before it runs.
if [[ " $* " != *" --skip-a11y-check "* ]]; then
    _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    _repo=$(git -C "$_here" rev-parse --show-toplevel)
    _gate=""; _d="$_repo"
    while [ "$_d" != / ]; do
        [ -x "$_d/modules/a11y-gate.sh" ] && { _gate="$_d/modules/a11y-gate.sh"; break; }
        _d=$(dirname "$_d")
    done
    if [ -z "$_gate" ]; then
        echo "a11y-gate.sh not found above $_repo; gate skipped" >&2
    elif [ ! -f "$_here/env.local.sh" ]; then
        echo "a11y gate skipped: no tools/env.local.sh - copy tools/env.example.sh and edit it to check against your own gateway" >&2
    else
        _deploy
        "$_gate" "$_repo" || { echo "a11y gate failed: fix the findings above, record a reasoned exception in a11y.json, or pass --skip-a11y-check" >&2; exit 1; }
    fi
fi
# Scroll-bar gate. Blocking; bypass deliberately with --skip-scrollbar-check.
# Only an intentional list, table or text pane may scroll: Perspective's
# default overflow:auto draws a bar on Windows over 1px of overflow, and
# headless Chromium hides bars, so nothing else catches it. Checks what is
# DEPLOYED, at 1366x640 up to 1920x1080, popups included.
if [[ " $* " != *" --skip-scrollbar-check "* ]]; then
    _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    _pw=""
    for _m in "${NODE_PATH:-/nonexistent}" "${IGNITION_TOOLKIT:-/nonexistent}/plugins/ignition/skills/verify-view/tool/node_modules"; do
        [ -d "$_m/playwright" ] && { _pw="$_m"; break; }
    done
    if [ ! -f "$_here/env.local.sh" ]; then
        echo "scroll-bar gate skipped: no tools/env.local.sh" >&2
    elif [ -z "$_pw" ]; then
        echo "scroll-bar gate skipped: playwright not found" >&2
    else
        _deploy
        # shellcheck disable=SC1091
        ( source "$_here/env.local.sh"; NODE_PATH="$_pw" node "$_here/verify/scrollbar_sweep.js" "$GW_URL" ) \
            || { echo "scroll-bar gate failed: fix the bars above, allowlist a genuine list in scrollbar_sweep.js with its reason, or pass --skip-scrollbar-check" >&2; exit 1; }
    fi
fi
# Lint gate (ign-lint + pylint over Jython 2.7). Blocking; bypass deliberately
# with --skip-lint-check.
if [[ " $* " != *" --skip-lint-check "* ]]; then
    _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    _repo=$(git -C "$_here" rev-parse --show-toplevel)
    _lint=""; _d="$_repo"
    while [ "$_d" != / ]; do
        [ -x "$_d/modules/lint-gate.sh" ] && { _lint="$_d/modules/lint-gate.sh"; break; }
        _d=$(dirname "$_d")
    done
    if [ -n "$_lint" ]; then
        "$_lint" "$_repo" || { echo "lint gate failed: fix the errors above or pass --skip-lint-check" >&2; exit 1; }
    else
        echo "lint-gate.sh not found above $_repo; gate skipped" >&2
    fi
fi
# Strip --skip-readme-check/--skip-a11y-check/--skip-lint-check/--skip-scrollbar-check (already
# consumed by the gates above) so this script's own argument parsing -- which
# rejects unrecognised args -- never sees them.
_pkgargs=(); for _a in "$@"; do
    [[ "$_a" == "--skip-readme-check" || "$_a" == "--skip-a11y-check" || "$_a" == "--skip-lint-check" || "$_a" == "--skip-scrollbar-check" ]] || _pkgargs+=("$_a")
done
set -- "${_pkgargs[@]}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$ROOT/project"
BUILD="$ROOT/build"
NAME="Machine_HMI_Demo"

RELEASE=0
EDGE=0
for arg in "$@"; do
  case "$arg" in
    --release) RELEASE=1 ;;
    --edge)    EDGE=1 ;;
    *) echo "package: unknown option '$arg'" >&2; exit 1 ;;
  esac
done

# The version lives in exactly one place: the script package. Everything else
# derives from it, so a release cannot ship a stale number in its filename.
VERSION="$(grep -oP 'VERSION\s*=\s*[\"'\'']\K[0-9]+\.[0-9]+\.[0-9]+' \
           "$PROJECT_DIR/ignition/script-python/MachineDemo/plant/code.py" | head -1)"
if [[ -z "$VERSION" ]]; then
  echo "package: cannot read VERSION from MachineDemo.plant" >&2
  exit 1
fi

EDITION=""
ARTEFACT="$NAME"
if [[ $EDGE -eq 1 ]]; then
  EDITION=" (Edge)"
  ARTEFACT="${NAME}_Edge"
fi

if [[ $RELEASE -eq 1 ]]; then
  TITLE="Machine HMI Demo${EDITION} $VERSION"
  SUFFIX="v$VERSION"
  ZIP="$BUILD/${ARTEFACT}-${VERSION}.zip"
else
  TITLE="Machine HMI Demo${EDITION} $VERSION (dev)"
  SUFFIX="dev"
  ZIP="$BUILD/${ARTEFACT}-${VERSION}-dev.zip"
fi

# What actually gets zipped. The standard build zips the repo directly and
# stamps the repo's project.json, because that version is meant to be committed.
# The Edge build must not touch the repo at all, so it stages a copy and
# rewrites that.
SRC="$PROJECT_DIR"
if [[ $EDGE -eq 1 ]]; then
  SRC="$(mktemp -d "${BUILD}/.edge-stage.XXXXXX")"
  trap 'rm -rf "$SRC"' EXIT
  cp -a "$PROJECT_DIR/." "$SRC/"
  # Compiled bytecode is not project content - the zip excludes it anyway - but
  # it carries the provider name INSIDE the .pyc, so leaving it here fails the
  # substitution gate below on files that were never going to ship.
  find "$SRC" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$SRC" -name '*.pyc' -delete 2>/dev/null || true

  # THREE functional forms carry the provider name, and 1.14.0 shipped with
  # only the first substituted - which left the Alarms journal table filtering
  # on prov:MachineDemo:/tag:* against a provider called `edge`, so it matched
  # nothing and the history read empty. The bracket form is the obvious one and
  # was never the whole story.
  #
  #   [MachineDemo]        a tag path                       (396 of them)
  #   prov:MachineDemo:    an alarm source filter           (2, both in Alarms)
  #   PROVIDER = "..."     the constant every script derives from
  #
  # Plus two cosmetic ones: the journal table's literal `name` default, and a
  # label that prints the provider to the operator. That label needs BOTH
  # middle-dot forms: json.dump writes the separator as the escape \u00b7, so
  # the raw-byte pattern alone matched nothing and the Edge build shipped an
  # Alarms header reading "This machine only . MachineDemo ." until 1.15.0.
  #
  # The bare word MachineDemo is ALSO the script package (MachineDemo.setup)
  # and the SQLite connection (MachineDemoDB), so a blanket substitution is
  # wrong - which is why each form is matched explicitly and anything left over
  # is reported below rather than assumed harmless.
  EDGE_PROVIDER="edge"
  find "$SRC" -type f \( -name '*.json' -o -name '*.py' \) -print0 \
    | xargs -0 sed -i \
        -e "s/\[MachineDemo\]/[${EDGE_PROVIDER}]/g" \
        -e "s/prov:MachineDemo:/prov:${EDGE_PROVIDER}:/g" \
        -e "s/\"name\": \"MachineDemo\"/\"name\": \"${EDGE_PROVIDER}\"/g" \
        -e "s/\xc2\xb7 MachineDemo \xc2\xb7/\xc2\xb7 ${EDGE_PROVIDER} \xc2\xb7/g" \
        -e "s/\\\\u00b7 MachineDemo \\\\u00b7/\\\\u00b7 ${EDGE_PROVIDER} \\\\u00b7/g"
  sed -i "s/^PROVIDER = \"MachineDemo\"/PROVIDER = \"${EDGE_PROVIDER}\"/" \
    "$SRC/ignition/script-python/MachineDemo/plant/code.py"

  # Prove the functional forms are gone. A silent no-op here ships a zip that
  # looks right and reads no tags - or worse, reads tags and shows no alarms.
  for form in '\[MachineDemo\]' 'prov:MachineDemo:'; do
    LEFT="$(grep -rl "$form" "$SRC" || true)"
    if [[ -n "$LEFT" ]]; then
      echo "package: these still carry $form after the Edge substitution:" >&2
      printf '%s\n' "$LEFT" | sed "s|$SRC|  project|" >&2
      exit 1
    fi
  done
  if ! grep -q "^PROVIDER = \"${EDGE_PROVIDER}\"" \
       "$SRC/ignition/script-python/MachineDemo/plant/code.py"; then
    echo "package: the Edge build did not rewrite PROVIDER" >&2
    exit 1
  fi
  if ! grep -rq 'MachineDemo\.setup' "$SRC"; then
    echo "package: the Edge substitution ate the MachineDemo script package" >&2
    exit 1
  fi

  # Everything else that still says MachineDemo. Expected: the script package
  # (MachineDemo.api and friends) and MachineDemoDB. Anything ELSE here is a
  # provider reference nobody has classified yet - report it, because that is
  # exactly the class of miss that shipped in 1.14.0.
  STRAY="$(grep -rho 'MachineDemo[A-Za-z]*' "$SRC" 2>/dev/null \
           | grep -v '^MachineDemoDB$' | grep -v '^MachineDemo$' | sort -u || true)"
  UNCLASSIFIED="$(grep -rn 'MachineDemo' "$SRC" --include='*.json' 2>/dev/null \
                  | grep -v 'MachineDemo\.' | grep -v 'MachineDemoDB' || true)"
  if [[ -n "$UNCLASSIFIED" ]]; then
    echo "package: WARNING - unclassified provider references left in the Edge build:" >&2
    printf '%s\n' "$UNCLASSIFIED" | sed "s|$SRC|project|" | head -20 >&2
  fi

  echo "         Edge build: tag provider -> [${EDGE_PROVIDER}]"
fi

# Stamp the version into the project Title AND the end of the Description, so a
# gateway shows which release it is running: the Config -> Projects grid shows
# only the Description, the Title shows in the Edit drawer and on Perspective
# launch surfaces. The project NAME is never touched - it breaks URLs.
python3 - "$SRC/project.json" "$TITLE" "$SUFFIX" <<'PY'
import json, re, sys
path, title, suffix = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as fh:
    p = json.load(fh)
p["title"] = title
desc = re.sub(r'\s*·\s*(v[0-9]+\.[0-9]+\.[0-9]+|dev)\s*$', '', p["description"]).rstrip()
p["description"] = desc + " · " + suffix
with open(path, "w") as fh:
    json.dump(p, fh, indent=2)
    fh.write("\n")
print("stamped:", title)
PY

mkdir -p "$BUILD"
rm -f "$ZIP"

# Build to a temporary name and only move it into place once every check below
# has passed. A half-written archive at the real path is indistinguishable from
# a finished one, and the one thing worse than a build that fails is a build
# that leaves a plausible-looking zip behind after failing.
# mktemp reserves the name collision-safely, but it also CREATES the file, and
# zip appends to an existing archive - a zero-byte one is "Zip file structure
# invalid". Take the name, drop the empty file, let zip create it properly.
TMPZIP="$(mktemp "${BUILD}/.package.XXXXXX.zip")"
rm -f "$TMPZIP"
trap 'rm -f "$TMPZIP"; [[ $EDGE -eq 1 ]] && rm -rf "$SRC"' EXIT

( cd "$SRC" && zip -q -r "$TMPZIP" . \
    -x '.gaskony/*' \
    -x '*.pyc' -x '*__pycache__*' -x '.DS_Store' )

# zip exits 0 on some partial writes; make it prove the archive reads back.
unzip -t "$TMPZIP" >/dev/null || { echo "package: archive failed its integrity test" >&2; exit 1; }

# Count what went in against what is on disk, so a silently short archive is
# caught by arithmetic rather than by spot-checking a few known files.
ON_DISK="$(cd "$SRC" && find . -type f \
             ! -path './.gaskony/*' \
             ! -name '*.pyc' ! -name '.DS_Store' | wc -l)"
IN_ZIP="$(unzip -Z1 "$TMPZIP" | grep -vc '/$' || true)"
if [[ "$ON_DISK" -ne "$IN_ZIP" ]]; then
  echo "package: archive has $IN_ZIP files but $ON_DISK are on disk" >&2
  exit 1
fi

# List the archive ONCE into a variable and check that.
#
# Do not pipe `unzip -Z1` into `grep -q` under `set -o pipefail`: grep -q exits
# the instant it matches, unzip is killed by SIGPIPE, and the PIPELINE reports
# non-zero even though the match succeeded. Wrapped in `if !`, that turns a
# PASSING check into a failure, intermittently, depending on whether unzip had
# finished writing. It cost a "the vendored 3D library is missing" failure on a
# file that was present in the tree, on the gateway and in git.
LISTING="$(unzip -Z1 "$TMPZIP")"

FIRST="$(printf '%s\n' "$LISTING" | head -1)"
if [[ "$FIRST" == "$NAME/"* ]]; then
  echo "package: zip is rooted at $NAME/ and would import empty" >&2
  exit 1
fi
GP_MD5="$( (unzip -p "$TMPZIP" ignition/global-props/data.bin 2>/dev/null || true) | md5sum | cut -d' ' -f1)"
if [[ "$GP_MD5" != 09d72c9db67fa5bcc763dab27816d0c8 ]]; then
  echo "package: ignition/global-props must be the workspace copy (md5 09d72c9d, docs/lockdown-recipe.md); it is $GP_MD5" >&2
  exit 1
fi
if ! printf '%s\n' "$LISTING" | grep -q 'webdev/resources/lib/three.min.js'; then
  echo "package: the vendored 3D library is missing - the 3D page would not render offline" >&2
  exit 1
fi

# Every resource directory must carry a resource.json whose files[] matches the
# directory exactly. A missing lastModification, or a file present on disk but
# absent from files[], makes the gateway's scan skip that resource for good --
# silently, with the import reporting success. Cheaper to fail here than to find
# out that one view is missing in front of a customer.
python3 - "$TMPZIP" <<'PY'
import zipfile, json, posixpath, sys
z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
bad = []
for r in [n for n in names if n.endswith("resource.json")]:
    d = posixpath.dirname(r)
    try:
        cfg = json.loads(z.read(r))
    except Exception as e:
        bad.append("%s: invalid JSON (%s)" % (r, e))
        continue
    if "lastModification" not in cfg.get("attributes", {}):
        bad.append("%s: no attributes.lastModification - the scan will skip it" % r)
    listed = cfg.get("files", [])
    for f in listed:
        if posixpath.join(d, f) not in names:
            bad.append("%s: lists '%s' which is not in the zip" % (r, f))
    for n in names:
        if posixpath.dirname(n) == d and not n.endswith("/"):
            f = posixpath.basename(n)
            if f != "resource.json" and f not in listed:
                bad.append("%s: '%s' is in the directory but not in files[]" % (r, f))
if bad:
    print("package: resource manifest problems:", file=sys.stderr)
    for b in bad:
        print("  - " + b, file=sys.stderr)
    sys.exit(1)
print("         %d resource manifests verified" % sum(1 for n in names if n.endswith("resource.json")))
PY

# Everything passed: publish the archive under its real name.
mv "$TMPZIP" "$ZIP"
trap '[[ $EDGE -eq 1 ]] && rm -rf "$SRC"' EXIT

echo "package: $ZIP"
echo "         $(unzip -Z1 "$ZIP" | wc -l) entries, $(du -h "$ZIP" | cut -f1)"
