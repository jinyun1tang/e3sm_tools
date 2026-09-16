#!/bin/bash
# Run from atm_forcing.datm7.GSWP3.0.5d.v1.c170516/.
# Usage: bash /path/to/pack_gswp3_by_year.sh [output_directory]
# Creates 20 archives, each with 12 months from all three forcing groups.
set -euo pipefail

output_dir="${1:-.}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"

year_files() {
  local year="$1" month
  files=()
  for month in 01 02 03 04 05 06 07 08 09 10 11 12; do
    files+=(
      "Solar/clmforc.GSWP3.c2011.0.5x0.5.Solr.${year}-${month}.nc"
      "Precip/clmforc.GSWP3.c2011.0.5x0.5.Prec.${year}-${month}.nc"
      "TPHWL/clmforc.GSWP3.c2011.0.5x0.5.TPQWL.${year}-${month}.nc"
    )
  done
}

# Validate all inputs and destinations before creating any archives.
invalid=0
for year in {1901..1920}; do
  year_files "$year"
  for file in "${files[@]}"; do
    if [[ ! -f "$file" || ! -r "$file" ]]; then
      printf 'Missing or unreadable: %s\n' "$file" >&2
      invalid=1
    fi
  done
  archive="$output_dir/GSWP3_${year}.tar"
  if [[ -e "$archive" || -L "$archive" ]]; then
    printf 'Output already exists: %s\n' "$archive" >&2
    invalid=1
  fi
done
if [[ "$invalid" -ne 0 ]]; then
  printf 'Resolve the errors above; no archives were created.\n' >&2
  exit 1
fi

temporary_dir="$(mktemp -d "$output_dir/.gswp3-pack.XXXXXX")"
cleanup() {
  # Remove only the current temporary archive and this script's empty directory.
  rm -f "$temporary_dir/current.tar"
  rmdir "$temporary_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for year in {1901..1920}; do
  year_files "$year"
  archive="$output_dir/GSWP3_${year}.tar"
  # Follow input symlinks so archives contain data, not cluster-specific links.
  COPYFILE_DISABLE=1 tar -chf "$temporary_dir/current.tar" "${files[@]}"
  # Publish without overwriting an existing file, including one created meanwhile.
  ln "$temporary_dir/current.tar" "$archive"
  rm "$temporary_dir/current.tar"
  printf 'Created %s (36 files)\n' "$archive"
done
