# -*- coding: utf-8 -*-
"""音频转换器端到端验证：真实生成多档位声源，逐样本校验无损/拒绝逻辑。"""
import os, sys, subprocess, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converters.audio_converter import AudioConverter
from core.plugin_base import ConvertError

tmp = tempfile.mkdtemp()
SR = 8000

def gen(bits):
    maxv = (1 << (bits-1)) - 1
    rng = np.random.default_rng(bits)
    t = np.linspace(0, 1, SR, endpoint=False)
    sig = np.clip(np.round(np.sin(2*np.pi*440*t)*0.6*maxv
                           + rng.normal(0, maxv*0.01, SR)),
                  -maxv-1, maxv).astype(np.int64)
    ff = {16:"s16le",24:"s24le",32:"s32le"}[bits]
    raw = sig.astype("<i4").tobytes() if bits==32 else (
        sig.astype("<i2").tobytes() if bits==16 else
        b"".join(int(x).to_bytes(3,"little",signed=True) for x in sig))
    p = os.path.join(tmp,f"src{bits}.wav")
    r=subprocess.run(["ffmpeg","-y","-f",ff,"-ar",str(SR),"-ac","1","-i","-",
                      "-c:a",f"pcm_{ff}",p],input=raw,capture_output=True)
    assert r.returncode==0
    return p, sig

def gen_float():
    rng=np.random.default_rng(99)
    t=np.linspace(0,1,SR,endpoint=False)
    sig=(np.sin(2*np.pi*440*t)*0.5+rng.normal(0,0.05,SR)).astype(np.float32)
    p=os.path.join(tmp,"srcf.wav")
    r=subprocess.run(["ffmpeg","-y","-f","f32le","-ar",str(SR),"-ac","1","-i","-",
                      "-c:a","pcm_f32le",p],input=sig.tobytes(),capture_output=True)
    assert r.returncode==0
    return p, sig

def decode(path, bits):
    ff={16:"s16le",24:"s24le",32:"s32le"}[bits]
    r=subprocess.run(["ffmpeg","-i",path,"-f",ff,"-ac","1","-ar",str(SR),"-"],
                     capture_output=True)
    b=r.stdout
    if bits==16: return np.frombuffer(b,"<i2").astype(np.int64)
    if bits==32: return np.frombuffer(b,"<i4").astype(np.int64)
    pad=len(b)%3
    if pad: b=b[:len(b)-pad]
    return np.array([int.from_bytes(b[i:i+3],"little",signed=True)
                     for i in range(0,len(b),3)],dtype=np.int64)

conv=AudioConverter()
results=[]

def case(bits, fmt, expect):
    src, ref = gen(bits)
    dst=os.path.join(tmp,f"a{bits}_{fmt.key}.{fmt.ext.lstrip('.')}")
    try:
        conv.convert(src,dst,fmt,lambda f:None,lambda:False)
        if expect=="reject":
            results.append((bits,fmt.key,"🔴","应拒绝却通过"));return
        if fmt.lossless:
            dec=decode(dst,bits)
            eq=len(dec)==len(ref) and np.array_equal(dec,ref)
            results.append((bits,fmt.key,"✅" if eq else "🔴",
                            "逐样本一致" if eq else f"无损但样本不一致"))
        else:
            results.append((bits,fmt.key,"✅",f"有损文件已生成 {os.path.getsize(dst)}B"))
    except ConvertError as e:
        results.append((bits,fmt.key,"✅" if expect=="reject" else "🔴",
                        ("正确拒绝: "+str(e)[:45]) if expect=="reject" else f"意外拒绝: {e}"))

fmts={f.key:f for f in conv.output_formats()}
for bits in (16,24,32):
    for k in ("flac","wav","alac","aiff"):
        case(bits,fmts[k],"reject" if (bits==32 and k in("flac","alac")) else "ok")
    for k in ("mp3","aac","ogg","opus"):
        case(bits,fmts[k],"ok")

# 浮点源
fsrc, fsig = gen_float()
for k, expect in [("wav","ok"),("flac","reject"),("alac","reject"),("aiff","reject"),("mp3","ok")]:
    dst=os.path.join(tmp,f"f_{k}.{fmts[k].ext.lstrip('.')}")
    try:
        conv.convert(fsrc,dst,fmts[k],lambda f:None,lambda:False)
        if expect=="reject":
            results.append(("flt",k,"🔴","应拒绝却通过"))
        elif k=="wav":
            r=subprocess.run(["ffmpeg","-i",dst,"-f","f32le","-ac","1","-ar",str(SR),"-"],
                             capture_output=True)
            dec=np.frombuffer(r.stdout,"<f4")
            results.append(("flt",k,"✅" if np.array_equal(dec,fsig) else "🔴",
                            "浮点逐样本一致" if np.array_equal(dec,fsig) else "浮点不一致"))
        else:
            results.append(("flt",k,"✅","有损文件已生成"))
    except ConvertError as e:
        results.append(("flt",k,"✅" if expect=="reject" else "🔴",
                        "正确拒绝: "+str(e)[:40] if expect=="reject" else f"意外拒绝: {e}"))

# 取消测试
src,_=gen(16)
dst=os.path.join(tmp,"cancel.mp3")
try:
    conv.convert(src,dst,fmts["mp3"],lambda f:None,lambda:True)
    results.append(("-","cancel","🔴","应取消却完成"))
except ConvertError:
    results.append(("-","cancel","✅","正确响应取消"))

print(f"{'位深':5s}{'目标':6s} 结果 说明")
print("-"*75)
fails=0
for bits,k,r,note in results:
    print(f"{str(bits):5s}{k:6s} {r} {note}")
    if r=="🔴": fails+=1
print("-"*75)
print(f"共 {len(results)} 项，{'全部通过 ✅' if fails==0 else str(fails)+' 项失败 🔴'}")
sys.exit(1 if fails else 0)
