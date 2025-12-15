# _compose.sh
#!/usr/bin/env bash
# _compose.sh
# Concatenate relevant source files into _<folder>-composition.txt
# Separator protocol (Option A):
#   [FILE START] path=<qualified/path> lang=<language>
#   ``````                (long backtick fence, no language token)
#   ...file content...
#   ``````
#   [FILE END] path=<qualified/path>

set -euo pipefail

# --- Output target -----------------------------------------------------------
PROJECT_NAME=$(basename "$PWD")
OUTPUT_FILE="_${PROJECT_NAME}-composition.txt"

# --- Include rules -----------------------------------------------------------
# Extensions to include (without the dot)
EXTENSIONS=(
  py js ts mjs cjs jsx tsx
  json txt md sql
  html htm css scss less vue
  svelte mk sh
)

# Specific basenames to include (files without/with special names)
INCLUDE_NAMES=(
  Makefile
  makefile
  GNUmakefile
)

# --- Exclude rules -----------------------------------------------------------
EXCLUDES=(
  node_modules
  .git
  venv
  .venv
  dist
  build
  .svelte-kit
  coverage
  __pycache__
  .pytest_cache
  .DS_Store
  .idea
  .vscode
  kitagentsdk.egg-info
  .artifacts
  src/library/features
  martech/dukes-org.csv
  martech/brochu-org.csv
)

EXCLUDE_FILES=(
  package-lock.json
  yarn.lock
  pnpm-lock.yaml
  poetry.lock
  Pipfile.lock
  .env
  .env.local
  _compose.sh
)

# --- Helpers ----------------------------------------------------------------
# Map file path to a Markdown code-fence language
lang_for_file() {
  local path="$1"
  local base ext
  base="$(basename "$path")"
  ext="${path##*.}"

  # Named files first
  case "$base" in
    Makefile|makefile|GNUmakefile) echo "makefile"; return 0 ;;
  esac

  # By extension
  case "$ext" in
    py)   echo "python" ;;
    js|mjs|cjs) echo "javascript" ;;
    ts)   echo "typescript" ;;
    jsx)  echo "jsx" ;;
    tsx)  echo "tsx" ;;
    json) echo "json" ;;
    md)   echo "markdown" ;;
    sql)  echo "sql" ;;
    txt)  echo "text" ;;
    html|htm) echo "html" ;;
    css)  echo "css" ;;
    scss) echo "scss" ;;
    less) echo "less" ;;
    vue)  echo "vue" ;;
    svelte) echo "svelte" ;;
    sh)   echo "bash" ;;
    mk)   echo "makefile" ;;
    *)    echo "text" ;;
  esac
}

# Use a long backtick fence to minimize collisions with content that has ``` blocks
FENCE="``````"

# --- Build dynamic find expressions -----------------------------------------
FIND_EXPR=()

for ext in "${EXTENSIONS[@]}"; do
  FIND_EXPR+=( -name "*.${ext}" -o )
done

for nm in "${INCLUDE_NAMES[@]}"; do
  FIND_EXPR+=( -name "${nm}" -o )
done

# Trim trailing -o
unset 'FIND_EXPR[${#FIND_EXPR[@]}-1]'

EXCLUDE_EXPR=()
for excl in "${EXCLUDES[@]}"; do
  EXCLUDE_EXPR+=( ! -path "*/${excl}/*" )
done
for excl_file in "${EXCLUDE_FILES[@]}"; do
  EXCLUDE_EXPR+=( ! -name "${excl_file}" )
done
EXCLUDE_EXPR+=( ! -path "./$OUTPUT_FILE" )

# --- Create output -----------------------------------------------------------
: > "$OUTPUT_FILE"

# Collect, sort, and emit with sentinels
find . -type f \( "${FIND_EXPR[@]}" \) "${EXCLUDE_EXPR[@]}" \
| sort \
| while IFS= read -r file; do
    rel="${file#./}"
    lang="$(lang_for_file "$rel")"
    {
      echo "[FILE START] path=${rel} lang=${lang}"
      echo "${FENCE}"
      cat "$file"
      echo "${FENCE}"
      echo "[FILE END] path=${rel}"
      echo
    } >> "$OUTPUT_FILE"
  done

echo "Created $OUTPUT_FILE"