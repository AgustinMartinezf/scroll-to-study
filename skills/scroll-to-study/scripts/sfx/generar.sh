#!/usr/bin/env bash
# SFX de reemplazo sintetizados con ffmpeg (los originales venían de un skill del sandbox y no están).
# Uso: bash generar.sh   -> escribe los .mp3 y manifest.json en esta carpeta.
set -euo pipefail; cd "$(dirname "$0")"
f() { ffmpeg -loglevel error -y -f lavfi -i "$2" -ac 2 -ar 44100 -c:a libmp3lame -q:a 4 "$1"; }
f pop.mp3              "aevalsrc='sin(2*PI*(900-2500*t)*t)*exp(-30*t)':d=0.12"
f click.mp3            "aevalsrc='(random(0)*2-1)*exp(-250*t)+0.5*sin(2*PI*2200*t)*exp(-120*t)':d=0.06"
f click-soft.mp3       "aevalsrc='0.6*sin(2*PI*1400*t)*exp(-90*t)':d=0.08"
f impact-bass-1.mp3    "aevalsrc='sin(2*PI*(55+60*exp(-8*t))*t)*exp(-2.5*t)+0.3*(random(0)*2-1)*exp(-40*t)':d=1.6"
f impact-bass-2.mp3    "aevalsrc='sin(2*PI*(45+80*exp(-10*t))*t)*exp(-3*t)':d=1.2"
f riser.mp3            "aevalsrc='0.4*sin(2*PI*(200*t+300*t*t))*t/2+0.15*(random(0)*2-1)*t/2':d=2.0"
f glitch-3.mp3         "aevalsrc='0.5*(random(0)*2-1)*(lt(mod(t,0.07),0.035))*exp(-4*t)+0.3*sin(2*PI*180*t)*lt(mod(t,0.11),0.05)':d=0.4"
f typing.mp3           "aevalsrc='(random(0)*2-1)*exp(-300*mod(t,0.085))*0.5':d=0.9"
# whooshes: ruido filtrado con envolvente
w() { ffmpeg -loglevel error -y -f lavfi -i "anoisesrc=d=$2:c=pink:a=0.6" -af "highpass=f=300,lowpass=f=$3,afade=t=in:d=$4,afade=t=out:st=$4:d=$(awk "BEGIN{printf \"%.2f\", $2-$4}")" -ac 2 -ar 44100 -c:a libmp3lame -q:a 4 "$1"; }
w whoosh-short.mp3 0.30 4000 0.12
w whoosh.mp3       0.55 3000 0.25
w whoosh-cinematic.mp3 1.10 2000 0.55
python3 - <<'PY'
import json, subprocess, glob
m = {}
for p in sorted(glob.glob("*.mp3")):
    d = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
    m[p[:-4]] = {"file": p, "duration": round(d, 3)}
json.dump(m, open("manifest.json","w"), indent=1)
print(len(m), "sfx")
PY
