#!/usr/bin/env bash
set -Eeuo pipefail

# Output directory in this repo
OUTDIR="/Users/ruoyan/Desktop/WorkSpace/ETHPANDA_video/video"
mkdir -p "$OUTDIR"

# Prefer URL from environment if provided, otherwise use the embedded one
if [[ -n "${URL:-}" ]]; then
  URL_STR="${URL}"
else
  # Embedded direct googlevideo URL (may expire; script will still keep retrying)
  # Using a here-doc avoids quoting issues
  URL_STR="$(cat <<'EOF'
https://rr4---sn-oguesn6k.googlevideo.com/videoplayback?expire=1763387823&ei=T9UaaZykO8KCvcAPhIj7wAU&ip=160.16.200.209&id=o-AMJakGvfxO_xQKc3VJR5DDfZH3WlWM3-6j-Ckbh5NVVc&itag=18&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=268&met=1763366223%2C&mh=h8&mm=31%2C29&mn=sn-oguesn6k%2Csn-oguelnsz&ms=au%2Crdu&mv=m&mvi=4&pl=17&rms=au%2Cau&initcwndbps=2287500&bui=AdEuB5QBnLFEdo9K9D1e3OveDk6IbbKaqTzxAkSpr8s7cniD1hLYTFMI5Y1njwU55fNyldRIvLKOedXI&spc=6b0G_Exfkko0E2lwRzNC-UD5TdUQcP2F6dGrloZlg6jjNE1i0iHrnFDVlYIhtDhnM_QL820zUXvy4A&vprv=1&svpuc=1&mime=video%2Fmp4&ns=ucFT2SIZFNeBgZElx8c8w9IQ&rqh=1&gir=yes&clen=2285404&ratebypass=yes&dur=57.678&lmt=1762483175365462&mt=1763365792&fvip=1&fexp=51552689%2C51565116%2C51565681%2C51580968&c=WEB_EMBEDDED_PLAYER&sefc=1&txp=3300224&n=_uCd2gIVee1Kgg&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cratebypass%2Cdur%2Clmt&sig=AJfQdSswRAIgVgvgSVPLhGhqoV5NWZ2fBmoRTh5ustv2xC_WNI_CskUCICy76eXS-PiZBDlYXk7NtIc91C04z1NG-oR1S7_cf5NE&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRAIge7_OKuY05RWaSLpmuquYxSXQwAulcvSB0ruvmGNGpUUCIFnlwk4JTboj74Zy4nEkjvOqdgzOVmfiv2jAH7wSWGWd&pot=Mmi_P8eSKSEAvr8DeV8iiv0NjYJaXOkg165OjlzrR6fEq6R9OGPvwuetFAlMhTGR5DP-MubIyVcinSdRQ0xiWLahk8SiX5jNF7VGR-IvoKqnReJxloID0Vm6dcDTDsyr_LYzggsj52fPNQ%3D%3D&cver=1.20250219.01.00&title=%E7%89%B9%E6%9C%97%E6%99%AE%EF%BC%9A%E5%A5%BD%E7%BE%A1%E6%85%95%E4%B9%A0%E4%B8%BB%E5%B8%AD%EF%BC%8C%E4%B8%8B%E5%B1%9E%E6%AF%95%E6%81%AD%E6%AF%95%E6%95%AC
EOF
)"
fi
export URL_STR

# Minimal UA/headers to mimic browser
UA_STR="Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
HDR_REF="Referer: https://www.youtube.com/"
HDR_ORG="Origin: https://www.youtube.com"

# Build safe filename from URL title param
if command -v python3 >/dev/null 2>&1; then
  FILENAME="$(python3 - <<'PY'
import sys, urllib.parse, re, datetime, os
url = os.environ.get("URL_STR","")
qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
title = urllib.parse.unquote(qs.get('title', ['video'])[0])
safe = re.sub(r'[\\/:*?"<>|\\n\\r\\t]+', '_', title).strip('_ .')
date = datetime.datetime.now().strftime('%Y%m%d')
print(f"{date}_googlevideo_{safe or 'video'}.mp4")
PY
  )"
  EXP_SIZE="$(python3 - <<'PY'
import sys, urllib.parse, os
url = os.environ.get("URL_STR","")
qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
print(qs.get('clen', ['0'])[0])
PY
  )"
else
  FILENAME="$(date +%Y%m%d)_googlevideo_video.mp4"
  EXP_SIZE="0"
fi

OUTFILE="${OUTDIR}/${FILENAME}"
echo "目标文件: ${OUTFILE}"
echo "期望大小(clen): ${EXP_SIZE} bytes"

# Helper: get file size if exists
file_size() {
  if [[ -f "$1" ]]; then
    stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

attempt=0
while :; do
  attempt=$((attempt+1))
  echo "===== 下载尝试 #${attempt} ====="

  if command -v aria2c >/dev/null 2>&1; then
    echo "使用 aria2c 下载..."
    aria2c --disable-ipv6=true --continue=true --retry-wait=3 --max-tries=0 \
      --timeout=30 --connect-timeout=30 --file-allocation=none --split=5 --min-split-size=1M \
      --dir="${OUTDIR}" --out="${FILENAME}" \
      --header="${HDR_REF}" \
      --header="${HDR_ORG}" \
      --user-agent="${UA_STR}" \
      "${URL_STR}" || true
  else
    echo "aria2c 不存在，使用 curl 下载..."
    curl -L --fail -C - --http1.1 --tlsv1.2 --retry 5 --retry-delay 2 \
      -H "${HDR_REF}" \
      -H "${HDR_ORG}" \
      -A "${UA_STR}" \
      -o "${OUTFILE}.part" "${URL_STR}" && mv -f "${OUTFILE}.part" "${OUTFILE}" || true
  fi

  sz="$(file_size "${OUTFILE}")"
  echo "当前文件大小: ${sz} bytes"
  if [[ "${EXP_SIZE}" == "0" ]]; then
    if [[ "${sz}" -gt 0 ]]; then
      echo "下载完成（未知预期大小，但文件非空）。"
      open -R "${OUTFILE}" || true
      exit 0
    fi
  else
    # Some CDNs may deliver slightly larger than clen; consider success when >= EXP_SIZE
    if [[ "${sz}" -ge "${EXP_SIZE}" ]]; then
      echo "下载完成（达到或超过预期大小）。"
      open -R "${OUTFILE}" || true
      exit 0
    fi
  fi

  echo "未达到预期大小，3 秒后重试..."
  sleep 3
done


